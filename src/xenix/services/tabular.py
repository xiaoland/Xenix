from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import polars as pl

from ..exceptions import ValidationError
from .storage.models import DatasetSourceFormat


def load_tabular_frame(path: Path, source_format: DatasetSourceFormat) -> pl.DataFrame:
    if source_format is DatasetSourceFormat.CSV:
        return pl.read_csv(path, try_parse_dates=False)
    if source_format in {DatasetSourceFormat.XLSX, DatasetSourceFormat.XLS}:
        return pl.read_excel(path, engine="calamine")
    raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")


def preview_rows(frame: pl.DataFrame, *, limit: int) -> list[list[str]]:
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
