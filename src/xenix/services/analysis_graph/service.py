from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Literal

import pandas as pd

from ...config import AppPaths
from ...exceptions import ValidationError
from ...observability import record_counter, record_histogram, start_span
from ..dataset_inspection import detect_source_format, load_dataframe
from ..storage.models import DatasetSourceFormat
from .contracts import GraphDatasetInput, GraphDatasetResult
from .vegalite import graph_vegalite_dataset, validate_spec_object
from .wordcloud import graph_wordcloud_dataset, validate_wordcloud_spec_object


class AnalysisGraphService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def graph_dataset(self, input_data: GraphDatasetInput) -> GraphDatasetResult:
        started_at = perf_counter()
        with start_span("analysis.graph"):
            source_path = self._resolve_source_path(input_data.source_path)
            frame = self._load_frame(source_path)
            dataset_name = input_data.dataset_name.strip() or source_path.stem
            mode = self._select_graph_mode(input_data)
            if mode == "vegalite":
                result = graph_vegalite_dataset(
                    self._paths,
                    user_spec=validate_spec_object(input_data.spec),
                    frame=frame,
                    dataset_name=dataset_name,
                )
            else:
                result = graph_wordcloud_dataset(
                    self._paths,
                    user_spec=validate_wordcloud_spec_object(input_data.wordcloud_spec),
                    frame=frame,
                    dataset_name=dataset_name,
                )
            self._record_operation("analysis.graph", started_at)
            return result

    def _select_graph_mode(self, input_data: GraphDatasetInput) -> Literal["vegalite", "wordcloud"]:
        has_spec = input_data.spec is not None
        has_wordcloud_spec = input_data.wordcloud_spec is not None
        if has_spec == has_wordcloud_spec:
            raise ValidationError("analysis.graph requires exactly one of spec or wordcloud_spec.")
        return "vegalite" if has_spec else "wordcloud"

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
            raise ValidationError("Only .csv, .parquet, .xlsx, and .xls dataset files are supported.")
        frame = load_dataframe(source_path, source_format).rename(columns=str)
        if len(frame.columns) == 0:
            raise ValidationError("Dataset file must contain at least one column.")
        if len(frame.index) == 0:
            raise ValidationError("Dataset file must contain at least one data row.")
        return frame
