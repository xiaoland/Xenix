from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError
from .dataset_inspection import detect_source_format, load_dataframe
from .storage.models import DatasetSourceFormat


_WIDTH = 960
_HEIGHT = 540
_MARGIN_LEFT = 82
_MARGIN_RIGHT = 42
_MARGIN_TOP = 64
_MARGIN_BOTTOM = 96
_PLOT_WIDTH = _WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT
_PLOT_HEIGHT = _HEIGHT - _MARGIN_TOP - _MARGIN_BOTTOM
_MAX_TOP_N = 20
_MAX_BINS = 50
_MAX_POINTS = 500
_MAX_HEATMAP_COLUMNS = 12
_PALETTE = ["#2563eb", "#0f766e", "#c2410c", "#7c3aed", "#be123c", "#4b5563"]


class GraphDatasetInput(SQLModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    dataset_name: str
    operation: str
    params: dict[str, Any] = Field(default_factory=dict)


class GraphDatasetResult(SQLModel):
    output_path: str
    graph_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisGraphService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def graph_dataset(self, input_data: GraphDatasetInput) -> GraphDatasetResult:
        source_path = self._resolve_source_path(input_data.source_path)
        frame = self._load_frame(source_path)
        operation = input_data.operation.strip()
        if not operation:
            raise ValidationError("analysis.graph operation cannot be empty.")
        dataset_name = input_data.dataset_name.strip() or source_path.stem
        params = dict(input_data.params or {})

        if operation == "bar_count":
            svg, metadata = self._bar_count(frame, dataset_name, params)
        elif operation == "histogram":
            svg, metadata = self._histogram(frame, dataset_name, params)
        elif operation == "scatter":
            svg, metadata = self._scatter(frame, dataset_name, params)
        elif operation == "line":
            svg, metadata = self._line(frame, dataset_name, params)
        elif operation == "correlation_heatmap":
            svg, metadata = self._correlation_heatmap(frame, dataset_name, params)
        else:
            raise ValidationError(
                "Unknown analysis.graph operation "
                f"'{operation}'. Available operations: bar_count, histogram, scatter, line, correlation_heatmap."
            )

        output_dir = self._paths.artifacts / "analysis" / "graphs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self._slug(dataset_name)}-{operation}-{uuid4().hex[:12]}.svg"
        output_path.write_text(svg, encoding="utf-8")
        return GraphDatasetResult(
            output_path=str(output_path.resolve()),
            graph_metadata={
                "operation": operation,
                "dataset_name": dataset_name,
                **metadata,
            },
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

    def _bar_count(self, frame: pd.DataFrame, dataset_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        column = self._column_param(frame, params, "column")
        top_n = self._int_param(params, "top_n", default=10, minimum=1, maximum=_MAX_TOP_N)
        counts = frame[column].value_counts(dropna=False).head(top_n)
        labels = [self._display_value(value) for value in counts.index]
        values = [int(value) for value in counts.values]
        title = str(params.get("title") or f"{dataset_name}: {column} counts")
        return self._bar_svg(title, labels, values, y_label="Count"), {
            "columns": [column],
            "row_count": int(len(frame.index)),
            "top_n": top_n,
            "points": [{"label": label, "count": count} for label, count in zip(labels, values, strict=False)],
        }

    def _histogram(self, frame: pd.DataFrame, dataset_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        column = self._numeric_column_param(frame, params, "column")
        bins = self._int_param(params, "bins", default=10, minimum=1, maximum=_MAX_BINS)
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            raise ValidationError(f"Column '{column}' has no numeric values to plot.")
        min_value = float(series.min())
        max_value = float(series.max())
        if math.isclose(min_value, max_value):
            labels = [self._format_number(min_value)]
            values = [int(series.count())]
        else:
            bucketed = pd.cut(series, bins=bins, include_lowest=True)
            counts = bucketed.value_counts(sort=False)
            labels = [
                f"{self._format_number(interval.left)} to {self._format_number(interval.right)}"
                for interval in counts.index
            ]
            values = [int(value) for value in counts.values]
        title = str(params.get("title") or f"{dataset_name}: {column} histogram")
        return self._bar_svg(title, labels, values, y_label="Count"), {
            "columns": [column],
            "row_count": int(len(series.index)),
            "bins": bins,
            "min": self._number(min_value),
            "max": self._number(max_value),
        }

    def _scatter(self, frame: pd.DataFrame, dataset_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        x_column = self._numeric_column_param(frame, params, "x")
        y_column = self._numeric_column_param(frame, params, "y")
        max_points = self._int_param(params, "max_points", default=200, minimum=1, maximum=_MAX_POINTS)
        plot_frame = frame[[x_column, y_column]].dropna().head(max_points)
        if plot_frame.empty:
            raise ValidationError("Selected columns have no paired values to plot.")
        points = [
            (float(row[x_column]), float(row[y_column]))
            for row in plot_frame.to_dict(orient="records")
        ]
        title = str(params.get("title") or f"{dataset_name}: {x_column} vs {y_column}")
        return self._scatter_svg(title, points, x_column, y_column), {
            "columns": [x_column, y_column],
            "point_count": len(points),
            "truncated": len(frame[[x_column, y_column]].dropna().index) > len(points),
        }

    def _line(self, frame: pd.DataFrame, dataset_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        x_column = self._column_param(frame, params, "x")
        y_column = self._numeric_column_param(frame, params, "y")
        max_points = self._int_param(params, "max_points", default=200, minimum=2, maximum=_MAX_POINTS)
        plot_frame = frame[[x_column, y_column]].dropna().copy()
        if plot_frame.empty:
            raise ValidationError("Selected columns have no paired values to plot.")
        x_values = self._line_x_values(plot_frame[x_column], x_column)
        plot_frame["_xenix_graph_x"] = x_values
        plot_frame = plot_frame.dropna(subset=["_xenix_graph_x"]).sort_values("_xenix_graph_x").head(max_points)
        points = [
            (float(row["_xenix_graph_x"]), float(row[y_column]))
            for row in plot_frame.to_dict(orient="records")
        ]
        if len(points) < 2:
            raise ValidationError("Line charts require at least two valid points.")
        title = str(params.get("title") or f"{dataset_name}: {y_column} by {x_column}")
        return self._line_svg(title, points, x_column, y_column), {
            "columns": [x_column, y_column],
            "point_count": len(points),
            "truncated": len(frame[[x_column, y_column]].dropna().index) > len(points),
        }

    def _correlation_heatmap(
        self,
        frame: pd.DataFrame,
        dataset_name: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        requested_columns = self._optional_columns_param(frame, params, "columns")
        numeric_columns = [
            column
            for column in (requested_columns or list(frame.columns))
            if is_numeric_dtype(frame[column])
        ]
        if len(numeric_columns) < 2:
            raise ValidationError("Correlation heatmap requires at least two numeric columns.")
        selected_columns = numeric_columns[:_MAX_HEATMAP_COLUMNS]
        matrix = frame[selected_columns].corr()
        title = str(params.get("title") or f"{dataset_name}: correlation heatmap")
        return self._heatmap_svg(title, selected_columns, matrix), {
            "columns": selected_columns,
            "truncated": len(numeric_columns) > len(selected_columns),
            "correlations": [
                {
                    "column": row_column,
                    "values": {
                        column: self._number(matrix.loc[row_column, column])
                        for column in selected_columns
                    },
                }
                for row_column in selected_columns
            ],
        }

    def _line_x_values(self, series: pd.Series, column: str) -> pd.Series:
        if is_numeric_dtype(series):
            return pd.to_numeric(series, errors="coerce")
        if is_datetime64_any_dtype(series):
            return self._datetime_seconds(series)
        converted = self._datetime_seconds(series)
        if converted.notna().any():
            return converted
        raise ValidationError(f"Line chart x column '{column}' must be numeric or datetime-like.")

    def _datetime_seconds(self, series: pd.Series) -> pd.Series:
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        seconds = pd.Series(float("nan"), index=series.index, dtype="float64")
        valid = converted.notna()
        if valid.any():
            seconds.loc[valid] = converted.loc[valid].astype("int64") / 1_000_000_000
        return seconds

    def _column_param(self, frame: pd.DataFrame, params: dict[str, Any], key: str) -> str:
        value = str(params.get(key) or "").strip()
        if not value:
            raise ValidationError(f"analysis.graph params requires '{key}'.")
        if value not in frame.columns:
            raise ValidationError(f"Unknown column '{value}'.")
        return value

    def _numeric_column_param(self, frame: pd.DataFrame, params: dict[str, Any], key: str) -> str:
        column = self._column_param(frame, params, key)
        if not is_numeric_dtype(frame[column]):
            raise ValidationError(f"Column '{column}' must be numeric.")
        return column

    def _optional_columns_param(self, frame: pd.DataFrame, params: dict[str, Any], key: str) -> list[str]:
        values = params.get(key)
        if values is None:
            return []
        if not isinstance(values, list):
            raise ValidationError(f"analysis.graph params '{key}' must be a list.")
        columns: list[str] = []
        for raw_value in values:
            column = str(raw_value or "").strip()
            if not column or column in columns:
                continue
            if column not in frame.columns:
                raise ValidationError(f"Unknown column '{column}'.")
            columns.append(column)
        return columns

    def _int_param(
        self,
        params: dict[str, Any],
        key: str,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        value = params.get(key, default)
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"analysis.graph params '{key}' must be an integer.") from exc
        if normalized < minimum or normalized > maximum:
            raise ValidationError(f"analysis.graph params '{key}' must be between {minimum} and {maximum}.")
        return normalized

    def _bar_svg(self, title: str, labels: list[str], values: list[int], *, y_label: str) -> str:
        max_value = max(values) if values else 1
        bar_gap = 10
        bar_width = max(10, (_PLOT_WIDTH - bar_gap * max(0, len(values) - 1)) / max(len(values), 1))
        elements = self._svg_base(title)
        elements.append(self._axes(y_label=y_label))
        for index, (label, value) in enumerate(zip(labels, values, strict=False)):
            height = 0 if max_value == 0 else (value / max_value) * _PLOT_HEIGHT
            x = _MARGIN_LEFT + index * (bar_width + bar_gap)
            y = _MARGIN_TOP + _PLOT_HEIGHT - height
            elements.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{height:.2f}" '
                f'rx="3" fill="{_PALETTE[index % len(_PALETTE)]}" />'
            )
            elements.append(
                f'<text x="{x + bar_width / 2:.2f}" y="{_MARGIN_TOP + _PLOT_HEIGHT + 22}" '
                f'text-anchor="end" transform="rotate(-35 {x + bar_width / 2:.2f} {_MARGIN_TOP + _PLOT_HEIGHT + 22})" '
                f'class="tick">{self._escape(self._truncate(label, 22))}</text>'
            )
            elements.append(
                f'<text x="{x + bar_width / 2:.2f}" y="{max(y - 8, _MARGIN_TOP + 12):.2f}" '
                f'text-anchor="middle" class="value">{value}</text>'
            )
        return self._svg_document(elements)

    def _scatter_svg(self, title: str, points: list[tuple[float, float]], x_label: str, y_label: str) -> str:
        x_scale = self._scale([point[0] for point in points], _MARGIN_LEFT, _MARGIN_LEFT + _PLOT_WIDTH)
        y_scale = self._scale([point[1] for point in points], _MARGIN_TOP + _PLOT_HEIGHT, _MARGIN_TOP)
        elements = self._svg_base(title)
        elements.append(self._axes(x_label=x_label, y_label=y_label))
        for x_value, y_value in points:
            elements.append(
                f'<circle cx="{x_scale(x_value):.2f}" cy="{y_scale(y_value):.2f}" r="4" fill="#2563eb" opacity="0.72" />'
            )
        return self._svg_document(elements)

    def _line_svg(self, title: str, points: list[tuple[float, float]], x_label: str, y_label: str) -> str:
        x_scale = self._scale([point[0] for point in points], _MARGIN_LEFT, _MARGIN_LEFT + _PLOT_WIDTH)
        y_scale = self._scale([point[1] for point in points], _MARGIN_TOP + _PLOT_HEIGHT, _MARGIN_TOP)
        path = " ".join(f"{x_scale(x):.2f},{y_scale(y):.2f}" for x, y in points)
        elements = self._svg_base(title)
        elements.append(self._axes(x_label=x_label, y_label=y_label))
        elements.append(f'<polyline points="{path}" fill="none" stroke="#2563eb" stroke-width="3" />')
        for x_value, y_value in points:
            elements.append(
                f'<circle cx="{x_scale(x_value):.2f}" cy="{y_scale(y_value):.2f}" r="3" fill="#0f766e" />'
            )
        return self._svg_document(elements)

    def _heatmap_svg(self, title: str, columns: list[str], matrix: pd.DataFrame) -> str:
        cell_size = min(52, max(28, int((_PLOT_HEIGHT - 20) / len(columns))))
        start_x = _MARGIN_LEFT + 140
        start_y = _MARGIN_TOP + 36
        elements = self._svg_base(title)
        for index, column in enumerate(columns):
            x = start_x + index * cell_size + cell_size / 2
            elements.append(
                f'<text x="{x:.2f}" y="{start_y - 12}" text-anchor="end" '
                f'transform="rotate(-35 {x:.2f} {start_y - 12})" class="tick">{self._escape(self._truncate(column, 18))}</text>'
            )
            y = start_y + index * cell_size + cell_size / 2
            elements.append(
                f'<text x="{start_x - 12}" y="{y + 4:.2f}" text-anchor="end" class="tick">'
                f"{self._escape(self._truncate(column, 22))}</text>"
            )
        for row_index, row_column in enumerate(columns):
            for column_index, column in enumerate(columns):
                value = self._number(matrix.loc[row_column, column]) or 0
                color = self._correlation_color(float(value))
                x = start_x + column_index * cell_size
                y = start_y + row_index * cell_size
                elements.append(
                    f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}" stroke="#ffffff" />'
                )
                elements.append(
                    f'<text x="{x + cell_size / 2:.2f}" y="{y + cell_size / 2 + 4:.2f}" '
                    f'text-anchor="middle" class="heat">{self._format_number(value)}</text>'
                )
        return self._svg_document(elements)

    def _svg_base(self, title: str) -> list[str]:
        return [
            "<style>"
            "text{font-family:Segoe UI,Arial,sans-serif;fill:#111827}"
            ".title{font-size:22px;font-weight:700}"
            ".axis{stroke:#374151;stroke-width:1.5}"
            ".tick{font-size:11px;fill:#4b5563}"
            ".label{font-size:13px;font-weight:600;fill:#374151}"
            ".value{font-size:11px;fill:#374151}"
            ".heat{font-size:10px;fill:#111827}"
            "</style>",
            f'<rect x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}" fill="#ffffff" />',
            f'<text x="{_MARGIN_LEFT}" y="36" class="title">{self._escape(title)}</text>',
        ]

    def _axes(self, *, x_label: str | None = None, y_label: str | None = None) -> str:
        elements = [
            f'<line x1="{_MARGIN_LEFT}" y1="{_MARGIN_TOP + _PLOT_HEIGHT}" '
            f'x2="{_MARGIN_LEFT + _PLOT_WIDTH}" y2="{_MARGIN_TOP + _PLOT_HEIGHT}" class="axis" />',
            f'<line x1="{_MARGIN_LEFT}" y1="{_MARGIN_TOP}" x2="{_MARGIN_LEFT}" '
            f'y2="{_MARGIN_TOP + _PLOT_HEIGHT}" class="axis" />',
        ]
        if x_label:
            elements.append(
                f'<text x="{_MARGIN_LEFT + _PLOT_WIDTH / 2}" y="{_HEIGHT - 18}" text-anchor="middle" '
                f'class="label">{self._escape(x_label)}</text>'
            )
        if y_label:
            elements.append(
                f'<text x="24" y="{_MARGIN_TOP + _PLOT_HEIGHT / 2}" text-anchor="middle" '
                f'transform="rotate(-90 24 {_MARGIN_TOP + _PLOT_HEIGHT / 2})" class="label">{self._escape(y_label)}</text>'
            )
        return "\n".join(elements)

    def _svg_document(self, elements: list[str]) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" '
            f'viewBox="0 0 {_WIDTH} {_HEIGHT}">\n'
            + "\n".join(elements)
            + "\n</svg>\n"
        )

    def _scale(self, values: list[float], output_min: float, output_max: float):
        minimum = min(values)
        maximum = max(values)
        if math.isclose(minimum, maximum):
            midpoint = (output_min + output_max) / 2
            return lambda _value: midpoint
        return lambda value: output_min + ((value - minimum) / (maximum - minimum)) * (output_max - output_min)

    def _correlation_color(self, value: float) -> str:
        clamped = max(-1.0, min(1.0, value))
        if clamped >= 0:
            intensity = int(255 - clamped * 120)
            return f"rgb({intensity},{intensity},255)"
        intensity = int(255 + clamped * 120)
        return f"rgb(255,{intensity},{intensity})"

    def _number(self, value: Any, *, digits: int = 4) -> float | None:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    def _format_number(self, value: Any) -> str:
        number = self._number(value)
        if number is None:
            return ""
        return f"{number:g}"

    def _display_value(self, value: Any) -> str:
        try:
            if pd.isna(value):
                return "<missing>"
        except (TypeError, ValueError):
            pass
        return str(value)

    def _escape(self, value: Any) -> str:
        return html.escape(str(value), quote=True)

    def _truncate(self, value: str, limit: int) -> str:
        return value if len(value) <= limit else value[: max(0, limit - 1)] + "..."

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "graph"
