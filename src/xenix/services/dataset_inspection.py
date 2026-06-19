from __future__ import annotations

import csv
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


class DatasetAttachmentMetadata(BaseModel):
    source_path: str
    source_format: DatasetSourceFormat
    file_name: str
    row_count: int
    column_count: int
    preview_columns: list[str] = Field(default_factory=list)


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


def inspect_attachment_metadata_file(source_path: Path) -> DatasetAttachmentMetadata:
    source_format = detect_source_format(source_path)
    if source_format is DatasetSourceFormat.UNKNOWN:
        raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")
    if source_format is DatasetSourceFormat.CSV:
        return _inspect_csv_attachment_metadata(source_path, source_format)
    if source_format is DatasetSourceFormat.XLSX:
        return _inspect_xlsx_attachment_metadata(source_path, source_format)

    inspection = inspect_dataset_file(source_path)
    return DatasetAttachmentMetadata(
        source_path=inspection.source_path,
        source_format=inspection.source_format,
        file_name=inspection.file_name,
        row_count=inspection.row_count,
        column_count=inspection.column_count,
        preview_columns=inspection.preview_columns,
    )


def _inspect_csv_attachment_metadata(
    source_path: Path,
    source_format: DatasetSourceFormat,
) -> DatasetAttachmentMetadata:
    try:
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValidationError("Dataset file must contain at least one column.") from exc

            preview_columns = [
                _format_preview_column(column_name, index)
                for index, column_name in enumerate(header)
            ]
            if not preview_columns:
                raise ValidationError("Dataset file must contain at least one column.")

            row_count = 0
            for row in reader:
                if row and any(str(value).strip() for value in row):
                    row_count += 1
    except UnicodeDecodeError as exc:
        raise ValidationError("Unable to read dataset file.") from exc

    if row_count == 0:
        raise ValidationError("Dataset file must contain at least one data row.")
    return DatasetAttachmentMetadata(
        source_path=str(source_path),
        source_format=source_format,
        file_name=source_path.name,
        row_count=row_count,
        column_count=len(preview_columns),
        preview_columns=preview_columns,
    )


def _inspect_xlsx_attachment_metadata(
    source_path: Path,
    source_format: DatasetSourceFormat,
) -> DatasetAttachmentMetadata:
    import openpyxl

    workbook = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        row_count_with_header = int(worksheet.max_row or 0)
        column_count = int(worksheet.max_column or 0)
        if row_count_with_header == 0 or column_count == 0:
            raise ValidationError("Dataset file must contain at least one column.")

        header_row = next(
            worksheet.iter_rows(min_row=1, max_row=1, max_col=column_count, values_only=True),
            (),
        )
        preview_columns = [
            _format_preview_column(value, index)
            for index, value in enumerate(header_row)
        ]
        if len(preview_columns) < column_count:
            preview_columns.extend([""] * (column_count - len(preview_columns)))
        if not preview_columns:
            raise ValidationError("Dataset file must contain at least one column.")

        row_count = row_count_with_header - 1
        if row_count <= 0:
            raise ValidationError("Dataset file must contain at least one data row.")
    finally:
        workbook.close()

    return DatasetAttachmentMetadata(
        source_path=str(source_path),
        source_format=source_format,
        file_name=source_path.name,
        row_count=row_count,
        column_count=column_count,
        preview_columns=preview_columns,
    )


def _format_preview_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _format_preview_column(value: object, index: int) -> str:
    text = _format_preview_value(value)
    if text:
        return text
    return f"Unnamed: {index}"
