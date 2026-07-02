from __future__ import annotations

import importlib.metadata
import math
from pathlib import Path
from typing import Any

from ..exceptions import ValidationError
from .storage.models import DatasetSourceFormat


class TabularRuntimeError(RuntimeError):
    def __init__(self, message: str, *, error_details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_details = dict(error_details or {})


def tabular_runtime_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package_name in ("polars", "polars-runtime-32", "polars-runtime-64", "fastexcel"):
        try:
            versions[package_name] = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def load_tabular_frame(path: Path, source_format: DatasetSourceFormat):
    try:
        import polars as pl
    except Exception as exc:  # pragma: no cover - depends on local runtime state
        raise TabularRuntimeError(
            "Polars import failed.",
            error_details=_tabular_runtime_error_details(
                path=path,
                source_format=source_format,
                exc=exc,
                phase="import",
            ),
        ) from exc

    try:
        if source_format is DatasetSourceFormat.CSV:
            return pl.read_csv(path, try_parse_dates=False)
        if source_format in {DatasetSourceFormat.XLSX, DatasetSourceFormat.XLS}:
            return pl.read_excel(path, engine="calamine")
    except Exception as exc:  # pragma: no cover - depends on local runtime state
        raise TabularRuntimeError(
            "Polars failed to read the dataset file.",
            error_details=_tabular_runtime_error_details(
                path=path,
                source_format=source_format,
                exc=exc,
                phase="read",
            ),
        ) from exc

    raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")


def preview_rows(frame: Any, *, limit: int) -> list[list[str]]:
    return [
        [format_value(value) for value in row]
        for row in frame.head(limit).iter_rows()
    ]


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def format_column(value: Any, index: int) -> str:
    text = format_value(value)
    if text:
        return text
    return f"Unnamed: {index}"


def _tabular_runtime_error_details(
    *,
    path: Path,
    source_format: DatasetSourceFormat,
    exc: Exception,
    phase: str,
) -> dict[str, Any]:
    return {
        "engine": "polars",
        "phase": phase,
        "source_path": str(path),
        "source_format": source_format.value,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "package_versions": tabular_runtime_versions(),
    }
