from __future__ import annotations

import copy
import json
import math
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
_WORDCLOUD_TOP_N = 80
_WORDCLOUD_MIN_RECOMMENDED_TERMS = 20
_WORDCLOUD_DENSE_TERM_THRESHOLD = 60
_WORDCLOUD_DEFAULT_FONT_SIZE_RANGE = [12, 56]
_WORDCLOUD_DENSE_FONT_SIZE_RANGE = [10, 42]
_WORDCLOUD_ALLOWED_ROTATIONS = (-30, 0, 30)
_WORDCLOUD_DEFAULT_COLORS = ["#1f4e79", "#4f7cac", "#b8c5d6"]
_WORDCLOUD_COLOR_SCALE_NAME = "__xenix_wordcloud_color"
_WORDCLOUD_COLOR_TIER_FIELD = "__xenix_wordcloud_color_tier"
_WORDCLOUD_ROTATE_FIELD = "__xenix_wordcloud_rotate"
_WORDCLOUD_INTERNAL_FIELDS = {_WORDCLOUD_COLOR_TIER_FIELD, _WORDCLOUD_ROTATE_FIELD}
_WORDCLOUD_SUPPORTED_WORD_FIELDS = ("word", "term")
_WORDCLOUD_SUPPORTED_COUNT_FIELDS = ("count", "frequency")
_WORDCLOUD_FONT_FAMILY = "Microsoft YaHei, Noto Sans SC, Arial Unicode MS, sans-serif"
_WORDCLOUD_REPAIR_HINT = (
    "Use a text mark with grouped Vega encoding and tooltip, prepare an upstream Top 20-80 "
    "word table with `word` and `count`, keep most terms horizontal with only small -30/30 "
    "rotation, and use `fontSizeRange` [12, 56] or [10, 42] for dense clouds. For Chinese raw "
    "text, do not use countpattern as the tokenizer."
)


class AnalysisGraphValidationError(ValidationError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        error_details: dict[str, Any] | None = None,
        repair_hints: list[str] | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_details = error_details or {}
        self.repair_hints = repair_hints or []
        self.retryable = retryable


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
        spec.setdefault("width", _DEFAULT_WIDTH)
        spec.setdefault("height", _DEFAULT_HEIGHT)
        wordcloud_warnings: list[str] = []
        prepared_frame = frame
        if self._has_wordcloud_transform(spec):
            prepared_frame, wordcloud_warnings = self._normalize_wordcloud_spec(spec, frame)
        self._validate_wordcloud_spec_shape(spec)

        columns = [str(column) for column in prepared_frame.columns]
        field_scan = self._scan_fields(spec)
        referenced_wordcloud_internal_fields = field_scan.referenced_fields & _WORDCLOUD_INTERNAL_FIELDS
        unknown_fields = sorted(
            field_scan.referenced_fields - set(columns) - field_scan.generated_fields - referenced_wordcloud_internal_fields
        )
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
        truncated = int(len(prepared_frame.index)) > _MAX_RENDER_ROWS
        render_frame = prepared_frame.head(_MAX_RENDER_ROWS) if truncated else prepared_frame
        spec.setdefault("$schema", "https://vega.github.io/schema/vega/v6.json")
        spec.setdefault("title", dataset_name)
        self._patch_vega_references(spec)
        spec["data"] = [{"name": _INJECTED_DATA_NAME, "values": self._records(render_frame)}]
        warnings = wordcloud_warnings + self._static_warnings(spec)
        if truncated:
            warnings.append(
                f"Rendered the first {_MAX_RENDER_ROWS} rows from {int(len(prepared_frame.index))} prepared rows. "
                "Use data.query or data.transform before graphing if row order or sampling affects the conclusion."
            )
        return _PreparedSpec(
            spec=spec,
            title=self._title(spec, dataset_name),
            schema_url=str(user_spec.get("$schema") or ""),
            rendered_row_count=int(len(render_frame.index)),
            truncated=truncated,
            referenced_fields=sorted(field_scan.referenced_fields - referenced_wordcloud_internal_fields),
            generated_fields=sorted(field_scan.generated_fields | referenced_wordcloud_internal_fields),
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

    def _normalize_wordcloud_spec(
        self,
        spec: dict[str, Any],
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, list[str]]:
        normalized_frame = frame.copy()
        warnings: list[str] = []
        for mark in self._iter_marks(spec.get("marks", [])):
            transforms = mark.get("transform")
            if not isinstance(transforms, list):
                continue
            for transform in transforms:
                if isinstance(transform, dict) and transform.get("type") == "wordcloud":
                    normalized_frame, mark_warnings = self._normalize_wordcloud_mark(
                        spec,
                        mark,
                        transform,
                        normalized_frame,
                    )
                    warnings.extend(mark_warnings)
        return normalized_frame, warnings

    def _normalize_wordcloud_mark(
        self,
        spec: dict[str, Any],
        mark: dict[str, Any],
        transform: dict[str, Any],
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, list[str]]:
        if mark.get("type") != "text":
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform must be used on a text mark.",
                error_code="wordcloud_mark_type_invalid",
                error_details={"mark_type": mark.get("type")},
            )

        warnings: list[str] = []
        encode, enter, _update = self._normalize_wordcloud_encode(mark)
        columns = [str(column) for column in frame.columns]
        word_field = self._resolve_wordcloud_dataset_field(
            explicit_field=self._extract_wordcloud_text_field(mark, transform),
            available_columns=columns,
            supported_fields=_WORDCLOUD_SUPPORTED_WORD_FIELDS,
            role="word",
        )
        count_field = self._resolve_wordcloud_dataset_field(
            explicit_field=self._extract_wordcloud_count_field(transform),
            available_columns=columns,
            supported_fields=_WORDCLOUD_SUPPORTED_COUNT_FIELDS,
            role="count",
        )
        normalized_frame, frame_warnings = self._prepare_wordcloud_frame(
            frame,
            word_field=word_field,
            count_field=count_field,
        )
        warnings.extend(frame_warnings)
        if word_field != "word":
            warnings.append(
                f"Wordcloud used non-canonical word field '{word_field}'. Prefer upstream column name `word`."
            )
        if count_field != "count":
            warnings.append(
                f"Wordcloud used non-canonical count field '{count_field}'. Prefer upstream column name `count`."
            )

        enter["text"] = {"field": word_field}
        transform["text"] = {"field": word_field}
        transform["fontSize"] = {"field": f"datum.{count_field}"}

        default_font_size_range = self._default_wordcloud_font_size_range(normalized_frame[word_field].tolist())
        if not self._is_font_size_range(transform.get("fontSizeRange")):
            transform["fontSizeRange"] = list(default_font_size_range)
            warnings.append(
                f"Wordcloud defaulted fontSizeRange to [{default_font_size_range[0]}, {default_font_size_range[1]}]."
            )

        font = transform.get("font")
        if not isinstance(font, str) or not font.strip():
            transform["font"] = _WORDCLOUD_FONT_FAMILY
        transform.setdefault("padding", 2)
        transform.setdefault("fontWeight", {"value": 600})

        width, height = self._effective_dimensions(spec)
        size = transform.get("size")
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in size)
        ):
            transform["size"] = [width, height]

        rotation_series, rotation_warnings = self._wordcloud_rotation_series(normalized_frame, transform.get("rotate"))
        normalized_frame[_WORDCLOUD_ROTATE_FIELD] = rotation_series
        transform["rotate"] = {"field": f"datum.{_WORDCLOUD_ROTATE_FIELD}"}
        warnings.extend(rotation_warnings)

        normalized_frame[_WORDCLOUD_COLOR_TIER_FIELD] = self._wordcloud_color_tiers(int(len(normalized_frame.index)))
        if self._should_use_default_wordcloud_fill(encode, word_field):
            enter["fill"] = {"scale": _WORDCLOUD_COLOR_SCALE_NAME, "field": _WORDCLOUD_COLOR_TIER_FIELD}
            self._ensure_wordcloud_color_scale(spec)
            warnings.append(
                "Wordcloud color encoding was normalized to restrained rank tiers; avoid coloring every word randomly."
            )

        if not self._has_wordcloud_tooltip(encode):
            enter["tooltip"] = {"signal": self._wordcloud_tooltip_signal(word_field, count_field)}
            warnings.append("Wordcloud defaulted tooltip to `word: count`.")
        return normalized_frame, warnings

    def _normalize_wordcloud_encode(
        self,
        mark: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        encode = mark.get("encode")
        if not isinstance(encode, dict):
            encode = {}
            mark["encode"] = encode
        enter = encode.get("enter")
        if not isinstance(enter, dict):
            enter = {}
            encode["enter"] = enter
        update = encode.get("update")
        if not isinstance(update, dict):
            update = {}
            encode["update"] = update

        grouped_keys = {"enter", "update", "hover", "exit"}
        direct_keys = [key for key, value in encode.items() if key not in grouped_keys and isinstance(value, dict)]
        for key in direct_keys:
            enter.setdefault(key, encode[key])
            del encode[key]
        return encode, enter, update

    def _extract_wordcloud_text_field(self, mark: dict[str, Any], transform: dict[str, Any]) -> str | None:
        text = transform.get("text")
        if isinstance(text, dict) and isinstance(text.get("field"), str):
            return self._normalize_field_reference(text["field"])

        encode = mark.get("encode")
        if not isinstance(encode, dict):
            return None
        for phase in ("enter", "update"):
            phase_encode = encode.get(phase)
            if isinstance(phase_encode, dict):
                phase_text = phase_encode.get("text")
                if isinstance(phase_text, dict) and isinstance(phase_text.get("field"), str):
                    return self._normalize_field_reference(phase_text["field"])
        return None

    def _extract_wordcloud_count_field(self, transform: dict[str, Any]) -> str | None:
        font_size = transform.get("fontSize")
        if isinstance(font_size, dict) and isinstance(font_size.get("field"), str):
            return self._normalize_field_reference(font_size["field"])
        return None

    def _resolve_wordcloud_dataset_field(
        self,
        *,
        explicit_field: str | None,
        available_columns: list[str],
        supported_fields: tuple[str, ...],
        role: str,
    ) -> str:
        if explicit_field:
            if explicit_field in available_columns:
                return explicit_field
            self._raise_wordcloud_error(
                f"analysis.graph wordcloud {role} field '{explicit_field}' was not found in the dataset.",
                error_code=f"wordcloud_{role}_field_missing",
                error_details={
                    "requested_field": explicit_field,
                    "available_columns": available_columns[:_MAX_COLUMNS_IN_ERROR],
                    "expected_columns": list(supported_fields),
                },
            )

        for candidate in supported_fields:
            if candidate in available_columns:
                return candidate

        self._raise_wordcloud_error(
            f"analysis.graph wordcloud requires a dataset column for {role}.",
            error_code=f"wordcloud_{role}_field_missing",
            error_details={
                "available_columns": available_columns[:_MAX_COLUMNS_IN_ERROR],
                "expected_columns": list(supported_fields),
            },
        )

    def _prepare_wordcloud_frame(
        self,
        frame: pd.DataFrame,
        *,
        word_field: str,
        count_field: str,
    ) -> tuple[pd.DataFrame, list[str]]:
        warnings: list[str] = []
        normalized_frame = frame.copy()
        normalized_words = normalized_frame[word_field].where(pd.notna(normalized_frame[word_field]), "").astype(str).str.strip()
        normalized_counts = pd.to_numeric(normalized_frame[count_field], errors="coerce")
        valid_mask = normalized_words.ne("") & normalized_counts.notna() & normalized_counts.gt(0)
        removed_rows = int((~valid_mask).sum())
        if removed_rows:
            warnings.append(f"Wordcloud ignored {removed_rows} rows with blank words or non-positive counts.")

        normalized_frame = normalized_frame.loc[valid_mask].copy()
        if normalized_frame.empty:
            self._raise_wordcloud_error(
                "analysis.graph wordcloud requires at least one non-empty word with a positive count.",
                error_code="wordcloud_no_valid_terms",
                error_details={"word_field": word_field, "count_field": count_field},
            )
        normalized_frame[word_field] = normalized_words.loc[valid_mask]
        normalized_frame[count_field] = normalized_counts.loc[valid_mask]
        normalized_frame.sort_values(
            by=[count_field, word_field],
            ascending=[False, True],
            kind="mergesort",
            inplace=True,
        )

        if len(normalized_frame.index) > _WORDCLOUD_TOP_N:
            warnings.append(
                f"Wordcloud rendered the top {_WORDCLOUD_TOP_N} terms by `{count_field}` for readability."
            )
            normalized_frame = normalized_frame.head(_WORDCLOUD_TOP_N).copy()
        elif len(normalized_frame.index) < _WORDCLOUD_MIN_RECOMMENDED_TERMS:
            warnings.append(
                f"Wordcloud dataset contains only {int(len(normalized_frame.index))} terms. "
                f"Top {_WORDCLOUD_MIN_RECOMMENDED_TERMS}+ usually reads better when the source supports it."
            )
        return normalized_frame, warnings

    def _default_wordcloud_font_size_range(self, words: list[str]) -> list[int]:
        longest_word = max((len(word) for word in words), default=0)
        if len(words) >= _WORDCLOUD_DENSE_TERM_THRESHOLD or longest_word >= 8:
            return list(_WORDCLOUD_DENSE_FONT_SIZE_RANGE)
        return list(_WORDCLOUD_DEFAULT_FONT_SIZE_RANGE)

    def _effective_dimensions(self, spec: dict[str, Any]) -> tuple[int, int]:
        width = spec.get("width", _DEFAULT_WIDTH)
        height = spec.get("height", _DEFAULT_HEIGHT)
        resolved_width = int(width) if isinstance(width, (int, float)) and not isinstance(width, bool) else _DEFAULT_WIDTH
        resolved_height = (
            int(height) if isinstance(height, (int, float)) and not isinstance(height, bool) else _DEFAULT_HEIGHT
        )
        return resolved_width, resolved_height

    def _wordcloud_rotation_series(
        self,
        frame: pd.DataFrame,
        rotate: Any,
    ) -> tuple[pd.Series, list[str]]:
        warnings: list[str] = []
        term_count = int(len(frame.index))
        target_tilt_count = 0 if term_count < 10 else max(1, math.floor(term_count * 0.2))
        default_angles = self._default_wordcloud_rotations(term_count, target_tilt_count)

        if isinstance(rotate, dict) and isinstance(rotate.get("field"), str):
            rotation_field = self._normalize_field_reference(rotate["field"])
            if rotation_field is not None and rotation_field in frame.columns:
                raw_series = pd.to_numeric(frame[rotation_field], errors="coerce").fillna(0)
                normalized = raw_series.apply(self._normalize_rotation_value)
                if normalized.tolist() != [int(value) for value in raw_series.tolist()]:
                    warnings.append("Wordcloud rotation angles were normalized to -30, 0, or 30 degrees.")
                non_zero_indices = [index for index, value in enumerate(normalized.tolist()) if value != 0]
                if len(non_zero_indices) > target_tilt_count:
                    trimmed = normalized.tolist()
                    for index in non_zero_indices[target_tilt_count:]:
                        trimmed[index] = 0
                    normalized = pd.Series(trimmed, index=frame.index)
                    warnings.append("Wordcloud rotation was capped so that at least 80% of terms stay horizontal.")
                return normalized.astype("int64"), warnings
            warnings.append("Wordcloud rotation field was missing; defaulted to mostly horizontal placement.")
            return pd.Series(default_angles, index=frame.index, dtype="int64"), warnings

        if isinstance(rotate, dict) and "value" in rotate:
            explicit_value = self._normalize_rotation_value(rotate.get("value"))
            if explicit_value == 0:
                return pd.Series([0] * term_count, index=frame.index, dtype="int64"), warnings
            warnings.append("Wordcloud constant rotation was normalized to mostly horizontal placement.")
            return pd.Series(default_angles, index=frame.index, dtype="int64"), warnings

        warnings.append("Wordcloud defaulted rotation to mostly horizontal placement.")
        return pd.Series(default_angles, index=frame.index, dtype="int64"), warnings

    def _default_wordcloud_rotations(self, term_count: int, target_tilt_count: int) -> list[int]:
        angles = [0] * term_count
        if target_tilt_count <= 0:
            return angles
        positions = []
        for index in range(target_tilt_count):
            position = round(((index + 1) * (term_count + 1)) / (target_tilt_count + 1)) - 1
            positions.append(max(0, min(term_count - 1, position)))
        for index, position in enumerate(sorted(set(positions))):
            angles[position] = -30 if index % 2 == 0 else 30
        return angles

    def _normalize_rotation_value(self, value: Any) -> int:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return 0
        numeric = float(value)
        return int(min(_WORDCLOUD_ALLOWED_ROTATIONS, key=lambda candidate: abs(candidate - numeric)))

    def _wordcloud_color_tiers(self, term_count: int) -> list[str]:
        if term_count <= 0:
            return []
        top_cut = max(1, math.ceil(term_count * 0.2))
        mid_cut = max(top_cut, math.ceil(term_count * 0.5))
        tiers: list[str] = []
        for index in range(term_count):
            if index < top_cut:
                tiers.append("top")
            elif index < mid_cut:
                tiers.append("mid")
            else:
                tiers.append("tail")
        return tiers

    def _should_use_default_wordcloud_fill(self, encode: dict[str, Any], word_field: str) -> bool:
        fill_encodings: list[dict[str, Any]] = []
        for phase in ("enter", "update"):
            phase_encode = encode.get(phase)
            if isinstance(phase_encode, dict) and isinstance(phase_encode.get("fill"), dict):
                fill_encodings.append(phase_encode["fill"])
        if not fill_encodings:
            return True
        for fill in fill_encodings:
            field = fill.get("field")
            if isinstance(field, str):
                normalized = self._normalize_field_reference(field)
                if normalized in {word_field, "rank_tier", "color_tier", _WORDCLOUD_COLOR_TIER_FIELD}:
                    return True
            if fill.get("scale") == _WORDCLOUD_COLOR_SCALE_NAME:
                return False
        return False

    def _ensure_wordcloud_color_scale(self, spec: dict[str, Any]) -> None:
        scales = spec.get("scales")
        if not isinstance(scales, list):
            scales = []
            spec["scales"] = scales
        for scale in scales:
            if isinstance(scale, dict) and scale.get("name") == _WORDCLOUD_COLOR_SCALE_NAME:
                scale["type"] = "ordinal"
                scale["domain"] = ["top", "mid", "tail"]
                scale["range"] = list(_WORDCLOUD_DEFAULT_COLORS)
                return
        scales.append(
            {
                "name": _WORDCLOUD_COLOR_SCALE_NAME,
                "type": "ordinal",
                "domain": ["top", "mid", "tail"],
                "range": list(_WORDCLOUD_DEFAULT_COLORS),
            }
        )

    def _has_wordcloud_tooltip(self, encode: dict[str, Any]) -> bool:
        for phase in ("enter", "update"):
            phase_encode = encode.get(phase)
            if isinstance(phase_encode, dict) and isinstance(phase_encode.get("tooltip"), dict):
                return True
        return False

    def _wordcloud_tooltip_signal(self, word_field: str, count_field: str) -> str:
        return f"datum.{word_field} + ': ' + datum.{count_field}"

    def _raise_wordcloud_error(
        self,
        message: str,
        *,
        error_code: str,
        error_details: dict[str, Any] | None = None,
        repair_hints: list[str] | None = None,
        retryable: bool = True,
    ) -> None:
        hints = [
            "Prepare a chart-ready dataset with exact columns `word` and `count` whenever possible.",
            "Use data.query or data.transform to pre-aggregate and keep roughly the Top 20-80 terms.",
            "For Chinese raw text, segment upstream first; do not use countpattern as the tokenizer.",
        ]
        if repair_hints:
            hints.extend(repair_hints)
        raise AnalysisGraphValidationError(
            f"{message} {_WORDCLOUD_REPAIR_HINT}",
            error_code=error_code,
            error_details=error_details,
            repair_hints=hints,
            retryable=retryable,
        )

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
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform must be used on a text mark.",
                error_code="wordcloud_mark_type_invalid",
                error_details={"mark_type": mark.get("type")},
            )

        encode = mark.get("encode")
        if not isinstance(encode, dict):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud text mark must define encode.enter or encode.update.",
                error_code="wordcloud_encode_missing",
            )
        grouped_text = False
        for phase in ("enter", "update"):
            phase_encode = encode.get(phase)
            if isinstance(phase_encode, dict) and isinstance(phase_encode.get("text"), dict):
                grouped_text = True
                break
        if not grouped_text:
            self._raise_wordcloud_error(
                "analysis.graph wordcloud text mark must encode text under encode.enter or encode.update.",
                error_code="wordcloud_text_encoding_missing",
            )

        text = transform.get("text")
        if not isinstance(text, dict) or not isinstance(text.get("field"), str):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform.text must be {'field': '<word>'}.",
                error_code="wordcloud_text_field_invalid",
            )

        font_size = transform.get("fontSize")
        if not isinstance(font_size, dict) or not isinstance(font_size.get("field"), str):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform.fontSize must be {'field': 'datum.<count>'}.",
                error_code="wordcloud_font_size_invalid",
            )
        if not font_size["field"].startswith("datum."):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform.fontSize field must use datum.<count>.",
                error_code="wordcloud_font_size_field_invalid",
            )

        font_size_range = transform.get("fontSizeRange")
        if not self._is_font_size_range(font_size_range):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud transform must include a bounded fontSizeRange.",
                error_code="wordcloud_font_size_range_invalid",
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
                self._raise_wordcloud_error(
                    "analysis.graph could not render the Vega wordcloud spec.",
                    error_code="wordcloud_render_failed",
                    error_details={
                        "width": spec.get("width"),
                        "height": spec.get("height"),
                    },
                    repair_hints=[
                        "Reduce the number of terms or long labels before graphing.",
                        "Increase width or height when labels are long.",
                    ],
                )
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
                self._raise_wordcloud_error(
                    "analysis.graph renderer returned a Vega wordcloud error SVG.",
                    error_code="wordcloud_render_error_svg",
                )
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
            self._raise_wordcloud_error(
                self._wordcloud_render_failure_message(),
                error_code="wordcloud_rendered_no_terms",
                error_details={"visible_terms": 0, "failed_terms": 0},
            )

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
            self._raise_wordcloud_error(
                self._wordcloud_render_failure_message(),
                error_code="wordcloud_rendered_no_terms",
                error_details={"visible_terms": 0, "failed_terms": failed_terms},
            )

        total_terms = visible_terms + failed_terms
        if total_terms and (
            failed_terms > _MAX_WORDCLOUD_FAILED_TERM_COUNT
            and failed_terms / total_terms > _MAX_WORDCLOUD_FAILED_TERM_RATIO
        ):
            self._raise_wordcloud_error(
                "analysis.graph wordcloud could not place enough terms.",
                error_code="wordcloud_term_placement_failed",
                error_details={
                    "visible_terms": visible_terms,
                    "failed_terms": failed_terms,
                    "total_terms": total_terms,
                },
                repair_hints=[
                    "Reduce the cloud to fewer top terms before graphing.",
                    "Use the denser fontSizeRange [10, 42] when terms are many or labels are long.",
                ],
            )

    def _wordcloud_render_failure_message(self) -> str:
        return "analysis.graph wordcloud rendered no visible terms."

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
