from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
    is_string_dtype,
)
from pydantic import BaseModel, Field

from ..exceptions import ValidationError
from .storage.models import DatasetSourceFormat


class DatasetColumnKind(StrEnum):
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    TEXT = "text"
    UNKNOWN = "unknown"


class InspectDatasetInput(BaseModel):
    source_path: str


class DatasetColumnMetadata(BaseModel):
    name: str
    kind: DatasetColumnKind
    nullable: bool


class DatasetInspection(BaseModel):
    source_path: str
    source_format: DatasetSourceFormat
    file_name: str
    row_count: int
    column_count: int
    columns: list[DatasetColumnMetadata]
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)


def detect_source_format(path: Path) -> DatasetSourceFormat:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return DatasetSourceFormat.CSV
    if suffix == ".xlsx":
        return DatasetSourceFormat.XLSX
    if suffix == ".xls":
        return DatasetSourceFormat.XLS
    return DatasetSourceFormat.UNKNOWN


def load_dataframe(path: Path, source_format: DatasetSourceFormat) -> pd.DataFrame:
    if source_format is DatasetSourceFormat.CSV:
        return pd.read_csv(path)
    if source_format in {DatasetSourceFormat.XLSX, DatasetSourceFormat.XLS}:
        return pd.read_excel(path)
    raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")


def infer_column_kind(series: pd.Series) -> DatasetColumnKind:
    if is_bool_dtype(series):
        return DatasetColumnKind.BOOLEAN
    if is_numeric_dtype(series):
        return DatasetColumnKind.NUMERIC
    if is_datetime64_any_dtype(series):
        return DatasetColumnKind.DATETIME
    if is_string_dtype(series):
        unique_values = {value for value in series.dropna().unique()}
        if unique_values and len(unique_values) <= 16:
            return DatasetColumnKind.CATEGORICAL
        return DatasetColumnKind.TEXT
    if is_object_dtype(series):
        unique_values = {value for value in series.dropna().unique()}
        if unique_values and len(unique_values) <= 16:
            return DatasetColumnKind.CATEGORICAL
        return DatasetColumnKind.TEXT
    return DatasetColumnKind.UNKNOWN


def inspect_dataset_file(source_path: Path) -> DatasetInspection:
    source_format = detect_source_format(source_path)
    if source_format is DatasetSourceFormat.UNKNOWN:
        raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")

    dataframe = load_dataframe(source_path, source_format)
    if len(dataframe.columns) == 0:
        raise ValidationError("Dataset file must contain at least one column.")
    if len(dataframe.index) == 0:
        raise ValidationError("Dataset file must contain at least one data row.")

    columns = [
        DatasetColumnMetadata(
            name=str(column_name),
            kind=infer_column_kind(dataframe[column_name]),
            nullable=bool(dataframe[column_name].isna().any()),
        )
        for column_name in dataframe.columns
    ]
    preview_columns = [str(column_name) for column_name in dataframe.columns]
    preview_rows = [
        [_format_preview_value(value) for value in row]
        for row in dataframe.head(5).itertuples(index=False, name=None)
    ]
    return DatasetInspection(
        source_path=str(source_path),
        source_format=source_format,
        file_name=source_path.name,
        row_count=int(len(dataframe.index)),
        column_count=int(len(dataframe.columns)),
        columns=columns,
        preview_columns=preview_columns,
        preview_rows=preview_rows,
    )


def _format_preview_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)
