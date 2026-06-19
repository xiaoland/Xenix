from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import pandas as pd
import vl_convert as vlc
from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError
from ..observability import record_counter, record_histogram, start_span
from .dataset_inspection import detect_source_format, load_dataframe
from .storage.models import DatasetSourceFormat


_DEFAULT_WIDTH = 960
_DEFAULT_HEIGHT = 540
_MIN_WIDTH = 200
_MAX_WIDTH = 1600
_MIN_HEIGHT = 160
_MAX_HEIGHT = 1200
_MAX_SPEC_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 2 * 1024 * 1024
_MAX_RENDER_ROWS = 10_000
_MAX_COLUMNS_IN_ERROR = 30
_INJECTED_DATA_NAME = "__xenix_dataset"
_DATUM_FIELD_RE = re.compile(r"\bdatum(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_][A-Za-z0-9_]*))")
_STATIC_WARNING_KEYS = {"signals"}
_TEXT_NODE_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<text>.*?)</text>|<text\b(?P<self_attrs>[^>]*)/>", re.DOTALL)
_MAX_WORDCLOUD_FAILED_TERM_RATIO = 0.2
_MAX_WORDCLOUD_FAILED_TERM_COUNT = 8
_WORDCLOUD_REPAIR_HINT = (
    "For wordcloud charts, use a text mark with grouped Vega encoding such as "
    "encode.enter.text {'field': '<word>'}; use a mark-level wordcloud transform with "
    "text {'field': '<word>'}, fontSize {'field': 'datum.<count>'}, and a bounded "
    "fontSizeRange such as [10, 48]; pre-filter to fewer top terms or increase width/height "
    "when labels are many or long."
)


class GraphDatasetInput(SQLModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    dataset_name: str
    spec: dict[str, Any] = Field(default_factory=dict)


class GraphDatasetResult(SQLModel):
    output_path: str
    graph_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisGraphService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def graph_dataset(self, input_data: GraphDatasetInput) -> GraphDatasetResult:
        started_at = perf_counter()
        with start_span("analysis.graph"):
            source_path = self._resolve_source_path(input_data.source_path)
            frame = self._load_frame(source_path)
            dataset_name = input_data.dataset_name.strip() or source_path.stem
            user_spec = self._validate_spec_object(input_data.spec)
            spec_json = self._spec_json(user_spec)
            if len(spec_json.encode("utf-8")) > _MAX_SPEC_BYTES:
                raise ValidationError(f"analysis.graph spec cannot exceed {_MAX_SPEC_BYTES} bytes.")

            prepared = self._prepare_spec(user_spec, frame, dataset_name)
            svg = self._render_svg(prepared.spec)
            self._validate_rendered_svg(prepared.spec, svg, prepared.title)
            output_bytes = len(svg.encode("utf-8"))
            if output_bytes > _MAX_OUTPUT_BYTES:
                raise ValidationError(
                    "analysis.graph rendered SVG is too large. Reduce chart dimensions, rows, marks, or pre-aggregate data."
                )

            output_dir = self._paths.artifacts / "analysis" / "graphs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{self._slug(dataset_name)}-vega-{uuid4().hex[:12]}.svg"
            output_path.write_text(svg, encoding="utf-8")
            result = GraphDatasetResult(
                output_path=str(output_path.resolve()),
                graph_metadata={
                    "renderer": "vl-convert-python",
                    "renderer_version": getattr(vlc, "__version__", None),
                    "spec_format": "vega",
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
            self._record_operation("analysis.graph", started_at)
            return result

    def _record_operation(self, operation: str, started_at: float) -> None:
        attributes = {"analysis.operation": operation, "status": "succeeded"}
        record_counter("xenix.analysis.operation.count", attributes=attributes)
        record_histogram(
            "xenix.analysis.operation.duration",
            (perf_counter() - started_at) * 1000,
            attributes=attributes,
            unit="ms",
        )

    def _resolve_source_path(self, raw_path: str) -> Path:
        source_path = Path(raw_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source path must point to an existing file.")
        return source_path.resolve()

    def _load_frame(self, source_path: Path) -> pd.DataFrame:
        source_format = detect_source_format(source_path)
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")
        frame = load_dataframe(source_path, source_format).rename(columns=str)
        if len(frame.columns) == 0:
            raise ValidationError("Dataset file must contain at least one column.")
        if len(frame.index) == 0:
            raise ValidationError("Dataset file must contain at least one data row.")
        return frame

    def _validate_spec_object(self, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError("analysis.graph spec must be a Vega object.")
        if not value:
            raise ValidationError("analysis.graph spec cannot be empty.")
        return value

    def _spec_json(self, spec: dict[str, Any]) -> str:
        try:
            return json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("analysis.graph spec must be JSON-serializable.") from exc

    def _prepare_spec(self, user_spec: dict[str, Any], frame: pd.DataFrame, dataset_name: str) -> "_PreparedSpec":
        self._validate_visual_shape(user_spec)
        spec = copy.deepcopy(user_spec)
        self._drop_user_data_declarations(spec)
        self._validate_no_external_urls(spec)
        self._validate_transform_scope(spec)
        self._validate_dimensions(spec)
        self._validate_wordcloud_spec_shape(spec)

        columns = [str(column) for column in frame.columns]
        field_scan = self._scan_fields(spec)
        unknown_fields = sorted(field_scan.referenced_fields - set(columns) - field_scan.generated_fields)
        if unknown_fields:
            available = ", ".join(columns[:_MAX_COLUMNS_IN_ERROR])
            if len(columns) > _MAX_COLUMNS_IN_ERROR:
                available += ", ..."
            raise ValidationError(
                "analysis.graph spec references unknown field(s): "
                + ", ".join(unknown_fields)
                + f". Use exact dataset columns. Available columns: {available}."
            )

        row_count = int(len(frame.index))
        truncated = row_count > _MAX_RENDER_ROWS
        render_frame = frame.head(_MAX_RENDER_ROWS) if truncated else frame
        spec.setdefault("$schema", "https://vega.github.io/schema/vega/v6.json")
        spec.setdefault("width", _DEFAULT_WIDTH)
        spec.setdefault("height", _DEFAULT_HEIGHT)
        spec.setdefault("title", dataset_name)
        self._patch_vega_references(spec)
        spec["data"] = [{"name": _INJECTED_DATA_NAME, "values": self._records(render_frame)}]
        warnings = self._static_warnings(spec)
        if truncated:
            warnings.append(
                f"Rendered the first {_MAX_RENDER_ROWS} rows from {row_count} total rows. "
                "Use data.query or data.transform before graphing if row order or sampling affects the conclusion."
            )
        return _PreparedSpec(
            spec=spec,
            title=self._title(spec, dataset_name),
            schema_url=str(user_spec.get("$schema") or ""),
            rendered_row_count=int(len(render_frame.index)),
            truncated=truncated,
            referenced_fields=sorted(field_scan.referenced_fields),
            generated_fields=sorted(field_scan.generated_fields),
            warnings=warnings,
        )

    def _validate_visual_shape(self, spec: dict[str, Any]) -> None:
        marks = spec.get("marks")
        if not isinstance(marks, list) or not marks:
            raise ValidationError("analysis.graph spec must include a non-empty Vega marks array.")
        if not all(isinstance(mark, dict) for mark in marks):
            raise ValidationError("analysis.graph spec.marks entries must be Vega mark objects.")

    def _drop_user_data_declarations(self, value: Any, path: str = "spec") -> None:
        if isinstance(value, dict):
            for key in list(value):
                child = value[key]
                child_path = f"{path}.{key}"
                if key == "data" and not self._is_patchable_data_reference(path):
                    del value[key]
                    continue
                if key == "datasets":
                    del value[key]
                    continue
                self._drop_user_data_declarations(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._drop_user_data_declarations(child, f"{path}[{index}]")

    def _is_patchable_data_reference(self, parent_path: str) -> bool:
        return parent_path.endswith(".from") or parent_path.endswith(".domain")

    def _validate_no_external_urls(self, value: Any, path: str = "spec") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == "url":
                    raise ValidationError(
                        f"analysis.graph does not accept {child_path}. "
                        "External data or resource URLs are not allowed in graph specs."
                    )
                self._validate_no_external_urls(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_no_external_urls(child, f"{path}[{index}]")

    def _validate_dimensions(self, spec: dict[str, Any]) -> None:
        for key, minimum, maximum in (("width", _MIN_WIDTH, _MAX_WIDTH), ("height", _MIN_HEIGHT, _MAX_HEIGHT)):
            if key not in spec:
                continue
            value = spec[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValidationError(f"analysis.graph spec.{key} must be a number between {minimum} and {maximum}.")
            if value < minimum or value > maximum:
                raise ValidationError(f"analysis.graph spec.{key} must be between {minimum} and {maximum}.")

    def _validate_transform_scope(self, spec: dict[str, Any]) -> None:
        mark_ids = {id(mark) for mark in self._iter_marks(spec.get("marks", []))}
        self._validate_transform_scope_value(spec, mark_ids)

    def _validate_transform_scope_value(self, value: Any, mark_ids: set[int], path: str = "spec") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == "transform" and id(value) not in mark_ids:
                    raise ValidationError(
                        f"analysis.graph only supports Vega mark-level transform at {child_path}. "
                        "Use data.transform before graphing for data preparation."
                    )
                self._validate_transform_scope_value(child, mark_ids, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_transform_scope_value(child, mark_ids, f"{path}[{index}]")

    def _scan_fields(self, spec: dict[str, Any]) -> "_FieldScan":
        scan = _FieldScan()
        self._scan_fields_value(spec, scan)
        return scan

    def _scan_fields_value(self, value: Any, scan: "_FieldScan", parent_key: str | None = None) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "field" and isinstance(child, str):
                    normalized = self._normalize_field_reference(child)
                    if normalized is not None:
                        scan.referenced_fields.add(normalized)
                elif key in {"groupby", "fields"} and isinstance(child, list):
                    scan.referenced_fields.update(
                        normalized
                        for item in child
                        if isinstance(item, str)
                        for normalized in [self._normalize_field_reference(item)]
                        if normalized is not None
                    )
                elif key == "as":
                    scan.generated_fields.update(self._as_fields(child))
                elif key == "filter" and isinstance(child, str):
                    scan.referenced_fields.update(match.group(1) or match.group(2) for match in _DATUM_FIELD_RE.finditer(child))
                self._scan_fields_value(child, scan, key)
        elif isinstance(value, list):
            for child in value:
                self._scan_fields_value(child, scan, parent_key)

    def _normalize_field_reference(self, value: str) -> str | None:
        if value.startswith("datum."):
            return value.removeprefix("datum.")
        if value.startswith("datum["):
            match = _DATUM_FIELD_RE.search(value)
            if match is not None:
                return match.group(1) or match.group(2)
            return None
        return value

    def _as_fields(self, value: Any) -> set[str]:
        if isinstance(value, str):
            return {value}
        if isinstance(value, list):
            return {str(item) for item in value if isinstance(item, str)}
        return set()

    def _static_warnings(self, spec: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        for key in sorted(self._present_keys(spec, _STATIC_WARNING_KEYS)):
            warnings.append(
                f"Vega '{key}' may not be visible in a static SVG artifact. "
                "The chart was rendered as a static image."
            )
        return warnings

    def _present_keys(self, value: Any, keys: set[str]) -> set[str]:
        present: set[str] = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys:
                    present.add(key)
                present.update(self._present_keys(child, keys))
        elif isinstance(value, list):
            for child in value:
                present.update(self._present_keys(child, keys))
        return present

    def _patch_vega_references(self, spec: dict[str, Any]) -> None:
        for mark in self._iter_marks(spec.get("marks", [])):
            self._patch_mark_source(mark)
        self._patch_scale_domains(spec.get("scales", []))

    def _iter_marks(self, marks: Any):
        if not isinstance(marks, list):
            return
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            yield mark
            yield from self._iter_marks(mark.get("marks", []))

    def _patch_mark_source(self, mark: dict[str, Any]) -> None:
        source = mark.get("from")
        if source is None:
            mark["from"] = {"data": _INJECTED_DATA_NAME}
            return
        if not isinstance(source, dict):
            raise ValidationError("analysis.graph spec marks must use object-shaped Vega from definitions.")
        if "facet" in source:
            raise ValidationError(
                "analysis.graph does not support Vega facet dataflow inside marks. "
                "Use data.transform to prepare a drawable dataset first."
            )
        unsupported_keys = sorted(set(source) - {"data"})
        if unsupported_keys:
            raise ValidationError(
                "analysis.graph does not support complex Vega mark dataflow keys: " + ", ".join(unsupported_keys)
            )
        source["data"] = _INJECTED_DATA_NAME

    def _patch_scale_domains(self, scales: Any) -> None:
        if not isinstance(scales, list):
            return
        for scale in scales:
            if not isinstance(scale, dict):
                continue
            domain = scale.get("domain")
            if isinstance(domain, dict):
                self._patch_scale_domain(domain)

    def _patch_scale_domain(self, domain: dict[str, Any]) -> None:
        if "fields" in domain:
            raise ValidationError(
                "analysis.graph does not support complex Vega scale domains. "
                "Use data.transform to prepare one drawable field first."
            )
        unsupported_keys = sorted(set(domain) - {"data", "field", "sort"})
        if unsupported_keys:
            raise ValidationError(
                "analysis.graph does not support complex Vega scale domain keys: " + ", ".join(unsupported_keys)
            )
        if "field" in domain:
            domain["data"] = _INJECTED_DATA_NAME

    def _validate_wordcloud_spec_shape(self, spec: dict[str, Any]) -> None:
        for mark in self._iter_marks(spec.get("marks", [])):
            transforms = mark.get("transform")
            if not isinstance(transforms, list):
                continue
            for transform in transforms:
                if isinstance(transform, dict) and transform.get("type") == "wordcloud":
                    self._validate_wordcloud_mark_shape(mark, transform)

    def _validate_wordcloud_mark_shape(self, mark: dict[str, Any], transform: dict[str, Any]) -> None:
        if mark.get("type") != "text":
            raise ValidationError("analysis.graph wordcloud transform must be used on a text mark. " + _WORDCLOUD_REPAIR_HINT)

        encode = mark.get("encode")
        if not isinstance(encode, dict):
            raise ValidationError(
                "analysis.graph wordcloud text mark must define encode.enter or encode.update. "
                + _WORDCLOUD_REPAIR_HINT
            )
        grouped_text = False
        for phase in ("enter", "update"):
            phase_encode = encode.get(phase)
            if isinstance(phase_encode, dict) and isinstance(phase_encode.get("text"), dict):
                grouped_text = True
                break
        if not grouped_text:
            raise ValidationError(
                "analysis.graph wordcloud text mark must encode text under encode.enter or encode.update. "
                + _WORDCLOUD_REPAIR_HINT
            )

        text = transform.get("text")
        if not isinstance(text, dict) or not isinstance(text.get("field"), str):
            raise ValidationError("analysis.graph wordcloud transform.text must be {'field': '<word>'}. " + _WORDCLOUD_REPAIR_HINT)

        font_size = transform.get("fontSize")
        if not isinstance(font_size, dict) or not isinstance(font_size.get("field"), str):
            raise ValidationError(
                "analysis.graph wordcloud transform.fontSize must be {'field': 'datum.<count>'}. "
                + _WORDCLOUD_REPAIR_HINT
            )
        if not font_size["field"].startswith("datum."):
            raise ValidationError(
                "analysis.graph wordcloud transform.fontSize field must use datum.<count>. " + _WORDCLOUD_REPAIR_HINT
            )

        font_size_range = transform.get("fontSizeRange")
        if not self._is_font_size_range(font_size_range):
            raise ValidationError(
                "analysis.graph wordcloud transform must include a bounded fontSizeRange. " + _WORDCLOUD_REPAIR_HINT
            )

    def _is_font_size_range(self, value: Any) -> bool:
        if not isinstance(value, list) or len(value) != 2:
            return False
        low, high = value
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            return False
        if isinstance(low, bool) or isinstance(high, bool):
            return False
        return 1 <= low < high <= 200

    def _render_svg(self, spec: dict[str, Any]) -> str:
        console_guard = self._allocate_hidden_console_for_packaged_windows()
        try:
            svg = vlc.vega_to_svg(self._spec_json(spec))
        except Exception as exc:
            if self._has_wordcloud_transform(spec):
                raise ValidationError(
                    "analysis.graph could not render the Vega wordcloud spec. " + _WORDCLOUD_REPAIR_HINT
                ) from exc
            raise ValidationError(
                "analysis.graph could not render the Vega spec. "
                "Check marks, scales, encodings, transforms, and field types, then retry with a simpler valid Vega chart."
            ) from exc
        finally:
            if console_guard is not None:
                console_guard.FreeConsole()
        if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
            raise ValidationError("analysis.graph renderer did not return a valid SVG image.")
        if "ERROR" in svg:
            if self._has_wordcloud_transform(spec):
                raise ValidationError("analysis.graph renderer returned a Vega wordcloud error SVG. " + _WORDCLOUD_REPAIR_HINT)
            raise ValidationError("analysis.graph renderer returned a Vega error SVG. Simplify the spec and retry.")
        return svg

    def _validate_rendered_svg(self, spec: dict[str, Any], svg: str, title: str) -> None:
        if self._has_wordcloud_transform(spec):
            self._validate_wordcloud_svg(svg, title)

    def _has_wordcloud_transform(self, spec: dict[str, Any]) -> bool:
        for mark in self._iter_marks(spec.get("marks", [])):
            transforms = mark.get("transform")
            if not isinstance(transforms, list):
                continue
            for transform in transforms:
                if isinstance(transform, dict) and transform.get("type") == "wordcloud":
                    return True
        return False

    def _validate_wordcloud_svg(self, svg: str, title: str) -> None:
        text_nodes = list(_TEXT_NODE_RE.finditer(svg))
        if not text_nodes:
            raise ValidationError(self._wordcloud_render_failure_message())

        visible_terms = 0
        failed_terms = 0
        for node in text_nodes:
            attrs = node.group("attrs") or node.group("self_attrs") or ""
            text = re.sub(r"<[^>]+>", "", node.group("text") or "").strip()
            if text == title:
                continue
            failed = 'font-size="0px"' in attrs or "translate(0,0)" in attrs or not text
            if failed:
                failed_terms += 1
            else:
                visible_terms += 1

        if visible_terms == 0:
            raise ValidationError(self._wordcloud_render_failure_message())

        total_terms = visible_terms + failed_terms
        if total_terms and (
            failed_terms > _MAX_WORDCLOUD_FAILED_TERM_COUNT
            and failed_terms / total_terms > _MAX_WORDCLOUD_FAILED_TERM_RATIO
        ):
            raise ValidationError(
                "analysis.graph wordcloud could not place enough terms. " + _WORDCLOUD_REPAIR_HINT
            )

    def _wordcloud_render_failure_message(self) -> str:
        return "analysis.graph wordcloud rendered no visible terms. " + _WORDCLOUD_REPAIR_HINT

    def _allocate_hidden_console_for_packaged_windows(self):
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return None
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            if kernel32.GetConsoleWindow():
                return None
            if not kernel32.AllocConsole():
                return None
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
            return kernel32
        except Exception:
            return None

    def _records(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        cleaned = frame.astype(object).where(pd.notna(frame), None)
        return json.loads(cleaned.to_json(orient="records", date_format="iso"))

    def _title(self, spec: dict[str, Any], dataset_name: str) -> str:
        title = spec.get("title")
        if isinstance(title, str):
            return title.strip() or dataset_name
        if isinstance(title, dict):
            text = title.get("text")
            if isinstance(text, str):
                return text.strip() or dataset_name
        return dataset_name

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "graph"


class _FieldScan(SQLModel):
    referenced_fields: set[str] = Field(default_factory=set)
    generated_fields: set[str] = Field(default_factory=set)


class _PreparedSpec(SQLModel):
    spec: dict[str, Any]
    title: str
    schema_url: str
    rendered_row_count: int
    truncated: bool
    referenced_fields: list[str]
    generated_fields: list[str]
    warnings: list[str]
