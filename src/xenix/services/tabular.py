from __future__ import annotations

import importlib.metadata
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import duckdb

from ..exceptions import ValidationError
from .storage.models import DatasetSourceFormat


class TabularRuntimeError(RuntimeError):
    def __init__(self, message: str, *, error_details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_details = dict(error_details or {})


@dataclass(frozen=True)
class TabularColumnSchema:
    index: int
    tool_name: str
    source_name: str | None
    loader_name: str | None
    name_source: str


@dataclass(frozen=True)
class TabularSchema:
    columns: list[TabularColumnSchema]
    resolver_version: int = 1


@dataclass(frozen=True)
class LoadedPandasFrame:
    frame: pd.DataFrame
    schema: TabularSchema


_PANDAS_UNNAMED_PATTERN = re.compile(r"^Unnamed:\s*\d+(?:_level_\d+)?$")
_POLARS_UNNAMED_PATTERN = re.compile(r"^__UNNAMED__\d+$")
_PANDAS_DUPLICATE_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)\.(?P<suffix>[1-9]\d*)$")
_MAX_STABLE_COLUMN_NAME_LENGTH = 120


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
            return pl.read_csv(path, try_parse_dates=False, infer_schema_length=None)
        if source_format is DatasetSourceFormat.PARQUET:
            return pl.read_parquet(path)
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

    raise ValidationError("Only .csv, .parquet, .xlsx, and .xls dataset files are supported.")


def load_pandas_frame_with_schema(path: Path, source_format: DatasetSourceFormat) -> LoadedPandasFrame:
    frame = _load_pandas_frame_for_tools(path, source_format)
    schema = resolve_tabular_schema(frame.columns)
    rename_map = {
        original_name: column.tool_name
        for original_name, column in zip(frame.columns, schema.columns, strict=True)
    }
    return LoadedPandasFrame(frame=frame.rename(columns=rename_map), schema=schema)


def resolve_tabular_schema(column_names: Any) -> TabularSchema:
    raw_columns = list(column_names)
    inspected = [_inspect_column_name(value, index) for index, value in enumerate(raw_columns)]
    duplicate_names = _duplicate_normalized_names(inspected)
    pandas_duplicate_indexes = _pandas_duplicate_suffix_indexes(inspected)
    proposed: list[dict[str, Any]] = []
    for item in inspected:
        generated_reason = _generated_name_reason(item, duplicate_names, pandas_duplicate_indexes)
        if generated_reason:
            tool_name = _generated_column_name(item["index"])
            name_source = generated_reason
            source_name = None if item["is_loader_placeholder"] or item["is_empty"] else item["text"]
        else:
            tool_name = item["text"]
            name_source = "preserved_source_name"
            source_name = item["text"]
        proposed.append(
            {
                **item,
                "tool_name": tool_name,
                "source_name": source_name,
                "name_source": name_source,
            }
        )

    conflicted = _duplicate_tool_names(proposed)
    if conflicted:
        proposed = [
            {
                **item,
                "tool_name": _generated_column_name(item["index"]),
                "name_source": "generated_tool_name_conflict",
            }
            if _normalize_column_name(item["tool_name"]) in conflicted
            else item
            for item in proposed
        ]

    return TabularSchema(
        columns=[
            TabularColumnSchema(
                index=item["index"],
                tool_name=item["tool_name"],
                source_name=item["source_name"],
                loader_name=item["loader_name"],
                name_source=item["name_source"],
            )
            for item in proposed
        ]
    )


def tabular_schema_payload(schema: TabularSchema) -> dict[str, Any]:
    return {
        "resolver_version": schema.resolver_version,
        "columns": [
            {
                "index": column.index,
                "tool_name": column.tool_name,
                "source_name": column.source_name,
                "loader_name": column.loader_name,
                "name_source": column.name_source,
            }
            for column in schema.columns
        ],
    }


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


def _load_pandas_frame_for_tools(path: Path, source_format: DatasetSourceFormat) -> pd.DataFrame:
    if source_format is DatasetSourceFormat.CSV:
        return pd.read_csv(path)
    if source_format is DatasetSourceFormat.PARQUET:
        return duckdb.connect(database=":memory:").execute(
            "SELECT * FROM read_parquet(?)",
            [str(path)],
        ).fetchdf()
    if source_format in {DatasetSourceFormat.XLSX, DatasetSourceFormat.XLS}:
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise ValidationError("Only .csv, .parquet, .xlsx, and .xls dataset files are supported.")


def _inspect_column_name(value: Any, index: int) -> dict[str, Any]:
    is_empty = value is None or (isinstance(value, str) and not value.strip())
    text = "" if value is None else str(value).strip()
    is_loader_placeholder = _is_known_loader_placeholder(text)
    return {
        "index": index,
        "raw": value,
        "text": text,
        "loader_name": None if is_empty else str(value),
        "is_empty": is_empty,
        "is_loader_placeholder": is_loader_placeholder,
        "is_unstable": _is_unstable_column_name(value, text),
    }


def _generated_name_reason(
    item: dict[str, Any],
    duplicate_names: set[str],
    pandas_duplicate_indexes: set[int],
) -> str | None:
    normalized = _normalize_column_name(item["text"])
    if item["is_empty"]:
        return "generated_empty_name"
    if item["is_loader_placeholder"]:
        return "generated_loader_placeholder"
    if item["index"] in pandas_duplicate_indexes:
        return "generated_loader_duplicate"
    if normalized in duplicate_names:
        return "generated_duplicate_name"
    if item["is_unstable"]:
        return "generated_unstable_name"
    return None


def _is_known_loader_placeholder(value: str) -> bool:
    return bool(_PANDAS_UNNAMED_PATTERN.match(value) or _POLARS_UNNAMED_PATTERN.match(value))


def _is_unstable_column_name(raw_value: Any, text: str) -> bool:
    if not isinstance(raw_value, str):
        return True
    if len(text) > _MAX_STABLE_COLUMN_NAME_LENGTH:
        return True
    if "\n" in text or "\r" in text:
        return True
    return any(ord(char) < 32 for char in text)


def _duplicate_normalized_names(items: list[dict[str, Any]]) -> set[str]:
    counts: dict[str, int] = {}
    for item in items:
        normalized = _normalize_column_name(item["text"])
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1
    return {name for name, count in counts.items() if count > 1}


def _pandas_duplicate_suffix_indexes(items: list[dict[str, Any]]) -> set[int]:
    normalized_names = {_normalize_column_name(item["text"]) for item in items}
    duplicate_indexes: set[int] = set()
    for item in items:
        match = _PANDAS_DUPLICATE_SUFFIX_PATTERN.match(item["text"])
        if match and _normalize_column_name(match.group("base")) in normalized_names:
            duplicate_indexes.add(item["index"])
    return duplicate_indexes


def _duplicate_tool_names(items: list[dict[str, Any]]) -> set[str]:
    counts: dict[str, int] = {}
    for item in items:
        normalized = _normalize_column_name(item["tool_name"])
        counts[normalized] = counts.get(normalized, 0) + 1
    return {name for name, count in counts.items() if count > 1}


def _normalize_column_name(value: str) -> str:
    return value.strip().casefold()


def _generated_column_name(index: int) -> str:
    return f"column_{index + 1}"


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
