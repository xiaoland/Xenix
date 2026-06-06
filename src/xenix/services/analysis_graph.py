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
_DATUM_FIELD_RE = re.compile(r"\bdatum(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_][A-Za-z0-9_]*))")
_WHOLE_DATASET_TRANSFORMS = {
    "aggregate",
    "density",
    "joinaggregate",
    "loess",
    "pivot",
    "quantile",
    "regression",
    "stack",
    "window",
}
_STATIC_WARNING_KEYS = {"params", "selection"}


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
            output_bytes = len(svg.encode("utf-8"))
            if output_bytes > _MAX_OUTPUT_BYTES:
                raise ValidationError(
                    "analysis.graph rendered SVG is too large. Reduce chart dimensions, rows, marks, or pre-aggregate data."
                )

            output_dir = self._paths.artifacts / "analysis" / "graphs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{self._slug(dataset_name)}-vegalite-{uuid4().hex[:12]}.svg"
            output_path.write_text(svg, encoding="utf-8")
            result = GraphDatasetResult(
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
            raise ValidationError("analysis.graph spec must be a Vega-Lite object.")
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
        self._validate_no_spec_data(user_spec)
        self._validate_dimensions(user_spec)

        columns = [str(column) for column in frame.columns]
        field_scan = self._scan_fields(user_spec)
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

        uses_whole_dataset = self._uses_whole_dataset_semantics(user_spec)
        row_count = int(len(frame.index))
        if row_count > _MAX_RENDER_ROWS and uses_whole_dataset:
            raise ValidationError(
                "analysis.graph spec uses aggregate or whole-dataset Vega-Lite semantics, but the dataset has "
                f"{row_count} rows and the safe render cap is {_MAX_RENDER_ROWS}. "
                "Use data.query or data.transform to pre-aggregate the dataset, then graph the derived dataset."
            )

        truncated = row_count > _MAX_RENDER_ROWS
        render_frame = frame.head(_MAX_RENDER_ROWS) if truncated else frame
        spec = copy.deepcopy(user_spec)
        spec.setdefault("width", _DEFAULT_WIDTH)
        spec.setdefault("height", _DEFAULT_HEIGHT)
        spec.setdefault("title", dataset_name)
        spec["data"] = {"values": self._records(render_frame)}
        warnings = self._static_warnings(user_spec)
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
        visual_keys = {"mark", "encoding", "layer", "facet", "concat", "vconcat", "hconcat"}
        if not any(key in spec for key in visual_keys):
            raise ValidationError(
                "analysis.graph spec must include a Vega-Lite visual definition such as mark/encoding, layer, or facet."
            )

    def _validate_no_spec_data(self, value: Any, path: str = "spec") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key in {"data", "datasets"}:
                    raise ValidationError(
                        f"analysis.graph does not accept {child_path}. "
                        "Pass only dataset_id; Xenix injects the registered dataset into the Vega-Lite spec."
                    )
                if key == "url":
                    raise ValidationError(
                        f"analysis.graph does not accept {child_path}. "
                        "External data or resource URLs are not allowed in graph specs."
                    )
                self._validate_no_spec_data(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_no_spec_data(child, f"{path}[{index}]")

    def _validate_dimensions(self, spec: dict[str, Any]) -> None:
        for key, minimum, maximum in (("width", _MIN_WIDTH, _MAX_WIDTH), ("height", _MIN_HEIGHT, _MAX_HEIGHT)):
            if key not in spec:
                continue
            value = spec[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValidationError(f"analysis.graph spec.{key} must be a number between {minimum} and {maximum}.")
            if value < minimum or value > maximum:
                raise ValidationError(f"analysis.graph spec.{key} must be between {minimum} and {maximum}.")

    def _scan_fields(self, spec: dict[str, Any]) -> "_FieldScan":
        scan = _FieldScan()
        self._scan_fields_value(spec, scan)
        return scan

    def _scan_fields_value(self, value: Any, scan: "_FieldScan", parent_key: str | None = None) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "field" and isinstance(child, str):
                    scan.referenced_fields.add(child)
                elif key in {"groupby", "fields"} and isinstance(child, list):
                    scan.referenced_fields.update(str(item) for item in child if isinstance(item, str))
                elif key == "as":
                    scan.generated_fields.update(self._as_fields(child))
                elif key == "filter" and isinstance(child, str):
                    scan.referenced_fields.update(match.group(1) or match.group(2) for match in _DATUM_FIELD_RE.finditer(child))
                self._scan_fields_value(child, scan, key)
        elif isinstance(value, list):
            for child in value:
                self._scan_fields_value(child, scan, parent_key)

    def _as_fields(self, value: Any) -> set[str]:
        if isinstance(value, str):
            return {value}
        if isinstance(value, list):
            return {str(item) for item in value if isinstance(item, str)}
        return set()

    def _uses_whole_dataset_semantics(self, value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "aggregate":
                    return True
                if key in _WHOLE_DATASET_TRANSFORMS and child:
                    return True
                if self._uses_whole_dataset_semantics(child):
                    return True
        elif isinstance(value, list):
            return any(self._uses_whole_dataset_semantics(child) for child in value)
        return False

    def _static_warnings(self, spec: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        for key in sorted(self._present_keys(spec, _STATIC_WARNING_KEYS)):
            warnings.append(
                f"Vega-Lite '{key}' may not be visible in a static SVG artifact. "
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

    def _render_svg(self, spec: dict[str, Any]) -> str:
        console_guard = self._allocate_hidden_console_for_packaged_windows()
        try:
            svg = vlc.vegalite_to_svg(self._spec_json(spec))
        except Exception as exc:
            raise ValidationError(
                "analysis.graph could not render the Vega-Lite spec. "
                "Check mark, encoding, transform, and field types, then retry with a simpler valid Vega-Lite chart."
            ) from exc
        finally:
            if console_guard is not None:
                console_guard.FreeConsole()
        if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
            raise ValidationError("analysis.graph renderer did not return a valid SVG image.")
        return svg

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
