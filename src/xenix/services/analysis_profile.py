from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype
from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ..exceptions import ValidationError
from .dataset_inspection import detect_source_format, load_dataframe
from .storage.models import DatasetSourceFormat


_DEFAULT_TOP_N = 10
_MAX_TOP_N = 20
_DEFAULT_CORRELATION_COLUMN_LIMIT = 8
_MAX_CORRELATION_COLUMN_LIMIT = 12
_MAX_FIELD_ROWS_IN_MARKDOWN = 20
_MAX_FREQUENCY_COLUMNS = 8
_MAX_TARGET_GROUP_ROWS = 30


class ProfileDatasetInput(SQLModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    dataset_name: str
    target_columns: list[str] = Field(default_factory=list)
    top_n: int = _DEFAULT_TOP_N
    correlation_column_limit: int = _DEFAULT_CORRELATION_COLUMN_LIMIT


class ProfileDatasetResult(SQLModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    markdown: str


class AnalysisProfileService:
    def profile_dataset(self, input_data: ProfileDatasetInput) -> ProfileDatasetResult:
        source_path = self._resolve_source_path(input_data.source_path)
        top_n = self._normalize_int(
            input_data.top_n,
            field_name="top_n",
            minimum=1,
            maximum=_MAX_TOP_N,
        )
        correlation_column_limit = self._normalize_int(
            input_data.correlation_column_limit,
            field_name="correlation_column_limit",
            minimum=2,
            maximum=_MAX_CORRELATION_COLUMN_LIMIT,
        )
        frame = self._load_frame(source_path)
        dataset_name = input_data.dataset_name.strip() or source_path.stem

        column_groups = self._column_groups(frame)
        target_columns = self._normalize_target_columns(
            frame,
            input_data.target_columns,
            column_groups["continuous_numeric"],
        )
        profile = {
            "dataset": {
                "name": dataset_name,
                "file_name": source_path.name,
            },
            "limits": {
                "top_n": top_n,
                "correlation_column_limit": correlation_column_limit,
            },
            "basic_info": self._basic_info(frame),
            "field_info": self._field_info(frame),
            "field_type_summary": self._field_type_summary(column_groups),
            "numeric_statistics": self._numeric_statistics(frame, column_groups["continuous_numeric"]),
            "binary_frequencies": self._frequencies(frame, column_groups["binary"], top_n),
            "category_frequencies": self._frequencies(frame, column_groups["non_numeric"], top_n),
            "datetime_statistics": self._datetime_statistics(frame, column_groups["datetime"]),
            "correlation_matrix": self._correlation_matrix(
                frame,
                column_groups["continuous_numeric"],
                correlation_column_limit,
            ),
            "target_group_statistics": self._target_group_statistics(
                frame,
                target_columns,
                [*column_groups["binary"], *column_groups["non_numeric"]],
                top_n,
            ),
        }
        return ProfileDatasetResult(
            profile=profile,
            markdown=self._profile_markdown(profile),
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
        frame = load_dataframe(source_path, source_format)
        frame = frame.rename(columns=str)
        if len(frame.columns) == 0:
            raise ValidationError("Dataset file must contain at least one column.")
        if len(frame.index) == 0:
            raise ValidationError("Dataset file must contain at least one data row.")
        return frame

    def _normalize_int(self, value: Any, *, field_name: str, minimum: int, maximum: int) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field_name} must be an integer.") from exc
        if normalized < minimum or normalized > maximum:
            raise ValidationError(f"{field_name} must be between {minimum} and {maximum}.")
        return normalized

    def _column_groups(self, frame: pd.DataFrame) -> dict[str, list[str]]:
        binary_columns = [column for column in frame.columns if self._is_binary_column(frame[column])]
        datetime_columns = [
            column
            for column in frame.columns
            if column not in binary_columns and self._is_datetime_column(frame[column])
        ]
        numeric_columns = [
            column
            for column in frame.columns
            if column not in binary_columns
            and column not in datetime_columns
            and is_numeric_dtype(frame[column])
        ]
        non_numeric_columns = [
            column
            for column in frame.columns
            if column not in binary_columns
            and column not in datetime_columns
            and column not in numeric_columns
        ]
        return {
            "continuous_numeric": [str(column) for column in numeric_columns],
            "binary": [str(column) for column in binary_columns],
            "non_numeric": [str(column) for column in non_numeric_columns],
            "datetime": [str(column) for column in datetime_columns],
        }

    def _is_binary_column(self, series: pd.Series) -> bool:
        if is_bool_dtype(series):
            return True
        values = series.dropna().unique()
        if len(values) == 0 or len(values) > 2:
            return False
        normalized_values = {self._binary_value(value) for value in values}
        return None not in normalized_values and normalized_values.issubset({0, 1})

    def _binary_value(self, value: Any) -> int | None:
        try:
            if value == 0:
                return 0
            if value == 1:
                return 1
        except ValueError:
            return None
        return None

    def _is_datetime_column(self, series: pd.Series) -> bool:
        if is_datetime64_any_dtype(series):
            return True
        if is_numeric_dtype(series):
            return False
        values = series.dropna()
        if values.empty:
            return False
        parsed = pd.to_datetime(values, errors="coerce", format="mixed")
        return bool(parsed.notna().mean() >= 0.8)

    def _normalize_target_columns(
        self,
        frame: pd.DataFrame,
        raw_columns: list[str],
        numeric_columns: list[str],
    ) -> list[str]:
        normalized: list[str] = []
        numeric_set = set(numeric_columns)
        for raw_column in raw_columns:
            column = str(raw_column or "").strip()
            if not column or column in normalized:
                continue
            if column not in frame.columns:
                raise ValidationError(f"target_columns contains unknown column '{column}'.")
            if column not in numeric_set:
                raise ValidationError(f"target column '{column}' must be a continuous numeric column.")
            normalized.append(column)
        return normalized

    def _basic_info(self, frame: pd.DataFrame) -> dict[str, int]:
        return {
            "row_count": int(len(frame.index)),
            "column_count": int(len(frame.columns)),
            "duplicate_row_count": int(frame.duplicated().sum()),
        }

    def _field_info(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        row_count = max(int(len(frame.index)), 1)
        fields: list[dict[str, Any]] = []
        for column in frame.columns:
            series = frame[column]
            missing_count = int(series.isna().sum())
            fields.append(
                {
                    "column": str(column),
                    "dtype": str(series.dtype),
                    "non_null_count": int(series.notna().sum()),
                    "missing_count": missing_count,
                    "missing_ratio": self._number(missing_count / row_count),
                    "unique_count": int(series.nunique(dropna=True)),
                }
            )
        return fields

    def _field_type_summary(self, column_groups: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        return {
            "continuous_numeric": self._field_type_entry(column_groups["continuous_numeric"]),
            "binary": self._field_type_entry(column_groups["binary"]),
            "non_numeric": self._field_type_entry(column_groups["non_numeric"]),
            "datetime": self._field_type_entry(column_groups["datetime"]),
        }

    def _field_type_entry(self, columns: list[str]) -> dict[str, Any]:
        return {"count": len(columns), "columns": columns}

    def _numeric_statistics(self, frame: pd.DataFrame, numeric_columns: list[str]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for column in numeric_columns:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            mode = series.mode()
            mean = series.mean() if not series.empty else None
            std = series.std() if not series.empty else None
            summaries.append(
                {
                    "column": column,
                    "count": int(series.count()),
                    "mean": self._number(mean),
                    "std": self._number(std),
                    "min": self._number(series.min() if not series.empty else None),
                    "q1": self._number(series.quantile(0.25) if not series.empty else None),
                    "median": self._number(series.median() if not series.empty else None),
                    "q3": self._number(series.quantile(0.75) if not series.empty else None),
                    "max": self._number(series.max() if not series.empty else None),
                    "mode": self._number(mode.iloc[0] if not mode.empty else None),
                    "skew": self._number(series.skew() if len(series.index) >= 3 else None),
                    "kurtosis": self._number(series.kurtosis() if len(series.index) >= 4 else None),
                    "coefficient_of_variation": self._coefficient_of_variation(mean, std),
                }
            )
        return summaries

    def _coefficient_of_variation(self, mean: Any, std: Any) -> float | None:
        mean_value = self._number(mean)
        std_value = self._number(std)
        if mean_value in {None, 0} or std_value is None:
            return None
        return self._number(std_value / mean_value)

    def _frequencies(self, frame: pd.DataFrame, columns: list[str], top_n: int) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        row_count = max(int(len(frame.index)), 1)
        for column in columns[:_MAX_FREQUENCY_COLUMNS]:
            counts = frame[column].value_counts(dropna=False).head(top_n)
            values = [
                {
                    "value": self._display_value(value),
                    "count": int(count),
                    "ratio": self._number(int(count) / row_count),
                }
                for value, count in counts.items()
            ]
            summaries.append({"column": column, "values": values})
        return summaries

    def _datetime_statistics(self, frame: pd.DataFrame, datetime_columns: list[str]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for column in datetime_columns:
            series = pd.to_datetime(frame[column], errors="coerce", format="mixed").dropna()
            min_value = series.min() if not series.empty else None
            max_value = series.max() if not series.empty else None
            span_days = None
            if min_value is not None and max_value is not None:
                span = max_value - min_value
                span_days = getattr(span, "days", None)
            summaries.append(
                {
                    "column": column,
                    "min": self._display_value(min_value),
                    "max": self._display_value(max_value),
                    "span_days": span_days,
                }
            )
        return summaries

    def _correlation_matrix(
        self,
        frame: pd.DataFrame,
        numeric_columns: list[str],
        column_limit: int,
    ) -> dict[str, Any]:
        selected_columns = numeric_columns[:column_limit]
        if len(selected_columns) < 2:
            return {"columns": selected_columns, "rows": [], "truncated": False}
        matrix = frame[selected_columns].corr()
        rows = [
            {
                "column": row_column,
                "values": {
                    column: self._number(matrix.loc[row_column, column])
                    for column in selected_columns
                },
            }
            for row_column in selected_columns
        ]
        return {
            "columns": selected_columns,
            "rows": rows,
            "truncated": len(numeric_columns) > len(selected_columns),
        }

    def _target_group_statistics(
        self,
        frame: pd.DataFrame,
        target_columns: list[str],
        group_columns: list[str],
        top_n: int,
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for target_column in target_columns:
            for group_column in group_columns[:_MAX_FREQUENCY_COLUMNS]:
                if frame[group_column].nunique(dropna=True) > top_n:
                    continue
                grouped = (
                    frame.groupby(group_column, dropna=False)[target_column]
                    .agg(["count", "mean", "median", "std", "min", "max"])
                    .reset_index()
                    .sort_values("count", ascending=False)
                    .head(top_n)
                )
                for row in grouped.to_dict(orient="records"):
                    summaries.append(
                        {
                            "target_column": target_column,
                            "group_column": group_column,
                            "group_value": self._display_value(row.get(group_column)),
                            "count": int(row.get("count") or 0),
                            "mean": self._number(row.get("mean")),
                            "median": self._number(row.get("median")),
                            "std": self._number(row.get("std")),
                            "min": self._number(row.get("min")),
                            "max": self._number(row.get("max")),
                        }
                    )
                    if len(summaries) >= _MAX_TARGET_GROUP_ROWS:
                        return summaries
        return summaries

    def _profile_markdown(self, profile: dict[str, Any]) -> str:
        dataset = profile["dataset"]
        basic = profile["basic_info"]
        lines = [
            f"# Dataset profile: {dataset['name']}",
            "",
            "## Basic information",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Rows | {basic['row_count']} |",
            f"| Columns | {basic['column_count']} |",
            f"| Duplicate rows | {basic['duplicate_row_count']} |",
            "",
            "## Field types",
            "",
            "| Type | Count | Columns |",
            "| --- | ---: | --- |",
        ]
        type_labels = {
            "continuous_numeric": "Continuous numeric",
            "binary": "Binary",
            "non_numeric": "Categorical/text",
            "datetime": "Datetime",
        }
        for key, label in type_labels.items():
            entry = profile["field_type_summary"][key]
            columns = ", ".join(entry["columns"]) if entry["columns"] else "-"
            lines.append(f"| {label} | {entry['count']} | {self._markdown_cell(columns)} |")

        self._append_field_info(lines, profile["field_info"])
        self._append_numeric_statistics(lines, profile["numeric_statistics"])
        self._append_frequency_section(lines, "Binary frequencies", profile["binary_frequencies"])
        self._append_frequency_section(lines, "Categorical/text top values", profile["category_frequencies"])
        self._append_datetime_statistics(lines, profile["datetime_statistics"])
        self._append_correlation_matrix(lines, profile["correlation_matrix"])
        self._append_target_group_statistics(lines, profile["target_group_statistics"])
        return "\n".join(lines)

    def _append_field_info(self, lines: list[str], field_info: list[dict[str, Any]]) -> None:
        lines.extend(
            [
                "",
                "## Missing values and cardinality",
                "",
                "| Column | Type | Missing | Missing ratio | Unique values |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        sorted_fields = sorted(field_info, key=lambda item: item["missing_count"], reverse=True)
        for field in sorted_fields[:_MAX_FIELD_ROWS_IN_MARKDOWN]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._markdown_cell(field["column"]),
                        self._markdown_cell(field["dtype"]),
                        str(field["missing_count"]),
                        self._percent(field["missing_ratio"]),
                        str(field["unique_count"]),
                    ]
                )
                + " |"
            )
        if len(sorted_fields) > _MAX_FIELD_ROWS_IN_MARKDOWN:
            lines.append(f"\nOnly the first {_MAX_FIELD_ROWS_IN_MARKDOWN} fields are shown.")

    def _append_numeric_statistics(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.extend(["", "## Numeric statistics", ""])
        if not rows:
            lines.append("No continuous numeric columns were detected.")
            return
        lines.extend(
            [
                "| Column | Count | Mean | Std | Min | Q1 | Median | Q3 | Max | Skew |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in rows[:_MAX_FIELD_ROWS_IN_MARKDOWN]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._markdown_cell(row["column"]),
                        str(row["count"]),
                        self._markdown_cell(row["mean"]),
                        self._markdown_cell(row["std"]),
                        self._markdown_cell(row["min"]),
                        self._markdown_cell(row["q1"]),
                        self._markdown_cell(row["median"]),
                        self._markdown_cell(row["q3"]),
                        self._markdown_cell(row["max"]),
                        self._markdown_cell(row["skew"]),
                    ]
                )
                + " |"
            )

    def _append_frequency_section(self, lines: list[str], title: str, summaries: list[dict[str, Any]]) -> None:
        lines.extend(["", f"## {title}", ""])
        if not summaries:
            lines.append("No matching columns were detected.")
            return
        for summary in summaries:
            lines.append(f"### {summary['column']}")
            lines.extend(["", "| Value | Count | Ratio |", "| --- | ---: | ---: |"])
            for value in summary["values"]:
                lines.append(
                    f"| {self._markdown_cell(value['value'])} | {value['count']} | {self._percent(value['ratio'])} |"
                )
            lines.append("")

    def _append_datetime_statistics(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.extend(["", "## Datetime statistics", ""])
        if not rows:
            lines.append("No datetime columns were detected.")
            return
        lines.extend(["| Column | Earliest | Latest | Span days |", "| --- | --- | --- | ---: |"])
        for row in rows:
            lines.append(
                f"| {self._markdown_cell(row['column'])} | {self._markdown_cell(row['min'])} | "
                f"{self._markdown_cell(row['max'])} | {self._markdown_cell(row['span_days'])} |"
            )

    def _append_correlation_matrix(self, lines: list[str], matrix: dict[str, Any]) -> None:
        lines.extend(["", "## Correlation matrix", ""])
        columns = matrix.get("columns") or []
        rows = matrix.get("rows") or []
        if len(columns) < 2 or not rows:
            lines.append("At least two continuous numeric columns are required.")
            return
        header = "| Column | " + " | ".join(self._markdown_cell(column) for column in columns) + " |"
        separator = "| --- | " + " | ".join("---:" for _column in columns) + " |"
        lines.extend([header, separator])
        for row in rows:
            values = row.get("values") or {}
            lines.append(
                "| "
                + self._markdown_cell(row["column"])
                + " | "
                + " | ".join(self._markdown_cell(values.get(column)) for column in columns)
                + " |"
            )
        if matrix.get("truncated"):
            lines.append("\nThe matrix was truncated to the configured column limit.")

    def _append_target_group_statistics(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.extend(["", "## Target group statistics", ""])
        if not rows:
            lines.append("No target columns were requested.")
            return
        lines.extend(
            [
                "| Target | Group column | Group value | Count | Mean | Median | Std | Min | Max |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._markdown_cell(row["target_column"]),
                        self._markdown_cell(row["group_column"]),
                        self._markdown_cell(row["group_value"]),
                        str(row["count"]),
                        self._markdown_cell(row["mean"]),
                        self._markdown_cell(row["median"]),
                        self._markdown_cell(row["std"]),
                        self._markdown_cell(row["min"]),
                        self._markdown_cell(row["max"]),
                    ]
                )
                + " |"
            )

    def _number(self, value: Any, *, digits: int = 4) -> float | int | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            return None
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    def _display_value(self, value: Any) -> str:
        try:
            if pd.isna(value):
                return "<missing>"
        except (TypeError, ValueError):
            pass
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        return str(value)

    def _percent(self, ratio: Any) -> str:
        value = self._number(ratio)
        if value is None:
            return ""
        return f"{round(float(value) * 100, 2)}%"

    def _markdown_cell(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\n", " ").replace("|", "\\|")
