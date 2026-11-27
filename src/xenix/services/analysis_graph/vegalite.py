from __future__ import annotations

import copy
import json
import re
from typing import Any

import pandas as pd
import vl_convert as vlc

from ...config import AppPaths
from ...exceptions import ValidationError
from .contracts import (
    MAX_COLUMNS_IN_ERROR,
    MAX_HEIGHT,
    MAX_OUTPUT_BYTES,
    MAX_SPEC_BYTES,
    MAX_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    GraphDatasetResult,
    _FieldScan,
    _PreparedSpec,
    spec_json,
)
from .svg import (
    allocate_hidden_console_for_packaged_windows,
    normalize_svg_for_qt,
    write_svg_output,
)

_DEFAULT_WIDTH = 960
_DEFAULT_HEIGHT = 540
_MAX_RENDER_ROWS = 10_000
_DATUM_FIELD_RE = re.compile(r"\bdatum(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_][A-Za-z0-9_]*))")
_STATIC_WARNING_KEYS = {"params"}


def validate_spec_object(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("analysis.graph spec must be a Vega-Lite object.")
    if not value:
        raise ValidationError("analysis.graph spec cannot be empty.")
    return value


def graph_vegalite_dataset(
    paths: AppPaths,
    *,
    user_spec: dict[str, Any],
    frame: pd.DataFrame,
    dataset_name: str,
) -> GraphDatasetResult:
    serialized = spec_json(user_spec, field_name="spec")
    if len(serialized.encode("utf-8")) > MAX_SPEC_BYTES:
        raise ValidationError(f"analysis.graph spec cannot exceed {MAX_SPEC_BYTES} bytes.")

    prepared = _prepare_spec(user_spec, frame, dataset_name)
    svg = _render_vegalite_svg(prepared.spec)
    output_bytes = len(svg.encode("utf-8"))
    if output_bytes > MAX_OUTPUT_BYTES:
        raise ValidationError(
            "analysis.graph rendered SVG is too large. Reduce chart dimensions, rows, marks, or pre-aggregate data."
        )

    output_path = write_svg_output(paths, svg=svg, dataset_name=dataset_name, suffix="vegalite")
    return GraphDatasetResult(
        effective_parameters={key: value for key, value in prepared.spec.items() if key != "datasets"},
        output_path=str(output_path.resolve()),
        graph_metadata={
            "renderer": "vl-convert-python",
            "renderer_version": getattr(vlc, "__version__", None),
            "spec_format": "vega-lite",
            "schema": prepared.schema_url,
            "dataset_name": dataset_name,
            "title": prepared.title,
            "row_count": int(len(frame.index)),
            "rendered_row_count": prepared.rendered_row_count,
            "truncated": prepared.truncated,
            "referenced_fields": prepared.referenced_fields,
            "generated_fields": prepared.generated_fields,
            "warnings": prepared.warnings,
            "output_bytes": output_bytes,
        },
    )


def _prepare_spec(user_spec: dict[str, Any], frame: pd.DataFrame, dataset_name: str) -> _PreparedSpec:
    _validate_visual_shape(user_spec)
    _validate_no_wordcloud_transform(user_spec)
    spec = copy.deepcopy(user_spec)
    _validate_dataset_sources(spec)
    _validate_no_external_urls(spec)
    _validate_dimensions(spec)
    spec.setdefault("width", _DEFAULT_WIDTH)
    spec.setdefault("height", _DEFAULT_HEIGHT)

    columns = [str(column) for column in frame.columns]
    field_scan = _scan_fields(spec)
    unknown_fields = sorted(field_scan.referenced_fields - set(columns) - field_scan.generated_fields)
    if unknown_fields:
        available = ", ".join(columns[:MAX_COLUMNS_IN_ERROR])
        if len(columns) > MAX_COLUMNS_IN_ERROR:
            available += ", ..."
        raise ValidationError(
            "analysis.graph spec references unknown field(s): "
            + ", ".join(unknown_fields)
            + f". Use exact dataset columns. Available columns: {available}."
        )

    row_count = int(len(frame.index))
    truncated = row_count > _MAX_RENDER_ROWS
    render_frame = frame.head(_MAX_RENDER_ROWS) if truncated else frame
    spec.setdefault("$schema", "https://vega.github.io/schema/vega-lite/v5.json")
    spec.setdefault("title", dataset_name)
    spec["datasets"] = {"data": _records(render_frame)}
    spec.setdefault("data", {"name": "data"})
    warnings = _static_warnings(spec)
    if truncated:
        warnings.append(
            f"Rendered the first {_MAX_RENDER_ROWS} rows from {row_count} rows. "
            "Use data.query or data.transform before graphing if row order, grouping, or sampling affects the conclusion."
        )
    return _PreparedSpec(
        spec=spec,
        title=_title(spec, dataset_name),
        schema_url=str(user_spec.get("$schema") or ""),
        rendered_row_count=int(len(render_frame.index)),
        truncated=truncated,
        referenced_fields=sorted(field_scan.referenced_fields),
        generated_fields=sorted(field_scan.generated_fields),
        warnings=warnings,
    )


def _validate_visual_shape(spec: dict[str, Any]) -> None:
    if "mark" in spec:
        return
    for key in ("layer", "hconcat", "vconcat", "concat"):
        value = spec.get(key)
        if isinstance(value, list) and value:
            return
    for key in ("facet", "repeat"):
        if key in spec and isinstance(spec.get("spec"), dict):
            return
    raise ValidationError("analysis.graph spec must include a Vega-Lite mark, layer, concat, facet, or repeat view.")


def _validate_no_wordcloud_transform(spec: dict[str, Any]) -> None:
    _validate_no_wordcloud_transform_value(spec)


def _validate_no_wordcloud_transform_value(value: Any) -> None:
    if isinstance(value, dict):
        transforms = value.get("transform")
        if isinstance(transforms, list):
            for transform in transforms:
                if isinstance(transform, dict) and transform.get("type") == "wordcloud":
                    raise ValidationError(
                        "analysis.graph Vega-Lite specs do not support wordcloud transforms. "
                        "Use wordcloud_spec instead, and prepare the frequency table with data.query or data.transform first."
                    )
        for child in value.values():
            _validate_no_wordcloud_transform_value(child)
    elif isinstance(value, list):
        for child in value:
            _validate_no_wordcloud_transform_value(child)


def _validate_dataset_sources(spec: dict[str, Any], path: str = "spec") -> None:
    # Visit source-bearing Vega-Lite nodes, not arbitrary objects: a datum,
    # parameter or user metadata may legitimately contain a key named data.
    if "data" in spec and spec["data"] != {"name": "data"}:
        raise ValidationError(
            f"analysis.graph {path}.data conflicts with the selected Dataset. "
            'Omit data or use {"name":"data"} to reference that Dataset. '
            "Inline values and other sources are not substituted for it."
        )
    if spec.get("datasets"):
        raise ValidationError(
            f"analysis.graph {path}.datasets conflicts with the selected Dataset. "
            'Xenix binds that Dataset as "data"; omit datasets.'
        )
    for key in ("layer", "hconcat", "vconcat", "concat"):
        children = spec.get(key)
        if isinstance(children, list):
            for index, child in enumerate(children):
                if isinstance(child, dict):
                    _validate_dataset_sources(child, f"{path}.{key}[{index}]")
    child_spec = spec.get("spec")
    if isinstance(child_spec, dict):
        _validate_dataset_sources(child_spec, f"{path}.spec")
    transforms = spec.get("transform")
    if isinstance(transforms, list):
        for index, transform in enumerate(transforms):
            if isinstance(transform, dict) and "lookup" in transform:
                source = transform.get("from")
                if isinstance(source, dict):
                    _validate_dataset_sources(source, f"{path}.transform[{index}].from")


# LLM-authored specs must stay local-only: reject every "url" key so rendering
# cannot fetch remote data (SSRF / exfiltration via Vega-Lite url loading).
def _validate_no_external_urls(value: Any, path: str = "spec") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "url":
                raise ValidationError(
                    f"analysis.graph does not accept {child_path}. "
                    "External data or resource URLs are not allowed in graph specs."
                )
            _validate_no_external_urls(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_no_external_urls(child, f"{path}[{index}]")


def _validate_dimensions(spec: dict[str, Any]) -> None:
    for key, minimum, maximum in (("width", MIN_WIDTH, MAX_WIDTH), ("height", MIN_HEIGHT, MAX_HEIGHT)):
        if key not in spec:
            continue
        value = spec[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValidationError(f"analysis.graph spec.{key} must be a number between {minimum} and {maximum}.")
        if value < minimum or value > maximum:
            raise ValidationError(f"analysis.graph spec.{key} must be between {minimum} and {maximum}.")


def _scan_fields(spec: dict[str, Any]) -> _FieldScan:
    scan = _FieldScan()
    _scan_fields_value(spec, scan)
    return scan


def _scan_fields_value(value: Any, scan: _FieldScan, parent_key: str | None = None) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "field" and isinstance(child, str):
                normalized = _normalize_field_reference(child)
                if normalized is not None:
                    scan.referenced_fields.add(normalized)
            elif key in {"groupby", "fields"} and isinstance(child, list):
                scan.referenced_fields.update(
                    normalized
                    for item in child
                    if isinstance(item, str)
                    for normalized in [_normalize_field_reference(item)]
                    if normalized is not None
                )
            elif key == "as":
                scan.generated_fields.update(_as_fields(child))
            elif key in {"filter", "calculate"} and isinstance(child, str):
                scan.referenced_fields.update(match.group(1) or match.group(2) for match in _DATUM_FIELD_RE.finditer(child))
            _scan_fields_value(child, scan, key)
    elif isinstance(value, list):
        for child in value:
            _scan_fields_value(child, scan, parent_key)


def _normalize_field_reference(value: str) -> str | None:
    if value.startswith("datum."):
        return value.removeprefix("datum.")
    if value.startswith("datum["):
        match = _DATUM_FIELD_RE.search(value)
        if match is not None:
            return match.group(1) or match.group(2)
        return None
    return value


def _as_fields(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value if isinstance(item, str)}
    return set()


def _static_warnings(spec: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in sorted(_present_keys(spec, _STATIC_WARNING_KEYS)):
        warnings.append(
            f"Vega-Lite '{key}' may not be visible in a static SVG artifact. "
            "The chart was rendered as a static image."
        )
    return warnings


def _present_keys(value: Any, keys: set[str]) -> set[str]:
    present: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys:
                present.add(key)
            present.update(_present_keys(child, keys))
    elif isinstance(value, list):
        for child in value:
            present.update(_present_keys(child, keys))
    return present


def _render_vegalite_svg(spec: dict[str, Any]) -> str:
    console_guard = allocate_hidden_console_for_packaged_windows()
    try:
        svg = vlc.vegalite_to_svg(spec_json(spec, field_name="spec"))
    except Exception as exc:
        raise ValidationError(
            "analysis.graph could not render the Vega-Lite spec. "
            "Check marks, encodings, transforms, and field types, then retry with a simpler valid Vega-Lite chart."
        ) from exc
    finally:
        if console_guard is not None:
            console_guard.FreeConsole()
    if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
        raise ValidationError("analysis.graph renderer did not return a valid SVG image.")
    if "ERROR" in svg:
        raise ValidationError("analysis.graph renderer returned a Vega-Lite error SVG. Simplify the spec and retry.")
    return normalize_svg_for_qt(svg)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    cleaned = frame.astype(object).where(pd.notna(frame), None)
    return json.loads(cleaned.to_json(orient="records", date_format="iso"))


def _title(spec: dict[str, Any], dataset_name: str) -> str:
    title = spec.get("title")
    if isinstance(title, str):
        return title.strip() or dataset_name
    if isinstance(title, dict):
        text = title.get("text")
        if isinstance(text, str):
            return text.strip() or dataset_name
    return dataset_name
