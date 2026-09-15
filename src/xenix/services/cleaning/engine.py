"""Worker entry: read once, apply in order, publish a separate Parquet result."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import pandas as pd

from ...config import AppPaths
from ...exceptions import ValidationError
from ...observability import record_counter, record_histogram, start_span
from ..dataset_inspection import detect_source_format
from ..storage.models import DatasetSourceFormat
from ..tabular import load_pandas_frame_with_schema
from .contracts import CleanDatasetInput, CleanDatasetResult
from .operations import apply_operation


_COLUMN_INDEX_INVALIDATING_OPERATIONS = frozenset({"missing.drop_high_missing_columns", "encoding.one_hot"})


def clean_dataset(input_data: CleanDatasetInput, paths: AppPaths) -> CleanDatasetResult:
    started_at = perf_counter()
    with start_span("data.clean"):
        source_path = Path(input_data.source_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source path must point to an existing file.")

        source_format = detect_source_format(source_path)
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Only .csv, .parquet, .xlsx, and .xls dataset files are supported.")

        loaded = load_pandas_frame_with_schema(source_path, source_format, preserve_types=True)
        frame = loaded.frame
        if len(frame.columns) == 0:
            raise ValidationError("Dataset file must contain at least one column.")

        report: dict[str, Any] = {
            "row_count_before": int(len(frame.index)),
            "row_count_after": int(len(frame.index)),
            "operations": [],
            "validation_rules": [],
            "warnings": [],
        }

        if not input_data.operations:
            report["rows_removed"] = 0
            report["no_op"] = True
            _record_operation(started_at)
            return CleanDatasetResult(output_path=str(source_path.resolve()), report=report)

        index_reference_invalidated_by: str | None = None
        for operation in input_data.operations:
            operation_name = str(operation.operation or "").strip()
            if index_reference_invalidated_by and _uses_index_reference(operation.params):
                raise ValidationError(
                    f"{operation_name or 'cleaning operation'}.params cannot use column_index(es) "
                    f"after '{index_reference_invalidated_by}' may add or remove columns in the same "
                    "data.clean call; use column_name(s), or start a new data.query/data.clean call."
                )
            frame = apply_operation(frame, operation, report)
            if operation_name in _COLUMN_INDEX_INVALIDATING_OPERATIONS:
                # Be conservative even when the operation happens to be a
                # no-op (for example, one-hot skips a high-cardinality
                # column): the caller cannot safely know the post-op index
                # mapping while planning one atomic call.
                index_reference_invalidated_by = operation_name

        output_dir = paths.artifacts / "datasets" / "cleaned"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{_slug(input_data.name)}-{uuid4().hex[:12]}.parquet"
        _write_parquet(frame, output_path)

        report["row_count_after"] = int(len(frame.index))
        report["rows_removed"] = int(report["row_count_before"] - report["row_count_after"])
        report["no_op"] = False
        _record_operation(started_at)
        return CleanDatasetResult(output_path=str(output_path.resolve()), report=report)


def _write_parquet(frame: pd.DataFrame, output_path: Path) -> None:
    import duckdb

    with duckdb.connect(database=":memory:") as connection:
        connection.register("cleaned_frame", frame)
        connection.execute(
            "COPY cleaned_frame TO ? (FORMAT PARQUET)",
            [str(output_path)],
        )


def _record_operation(started_at: float) -> None:
    attributes = {"data.operation": "data.clean", "status": "succeeded"}
    record_counter("xenix.data.operation.count", attributes=attributes)
    record_histogram(
        "xenix.data.operation.duration",
        (perf_counter() - started_at) * 1000,
        attributes=attributes,
        unit="ms",
    )


def _uses_index_reference(params: dict[str, Any]) -> bool:
    return any(key in params and params.get(key) is not None for key in ("column_index", "column_indexes"))


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return normalized or "dataset"
