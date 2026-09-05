"""Public cleaning boundary: metadata and requests do not import the execution engine."""

from __future__ import annotations

from ..config import AppPaths
from .cleaning.catalog import cleaning_operation_group_names, cleaning_operation_metadata
from .cleaning.contracts import CleanDatasetInput, CleanDatasetResult, CleanOperation
from .preprocessing_worker import LocalPreprocessingWorkerRunner, PreprocessingWorkerRunner


class DataCleaningService:
    def __init__(
        self,
        paths: AppPaths,
        *,
        worker_runner: PreprocessingWorkerRunner | None = None,
    ) -> None:
        self._paths = paths
        self._worker_runner = worker_runner or LocalPreprocessingWorkerRunner()

    def clean_dataset(self, input_data: CleanDatasetInput) -> CleanDatasetResult:
        payload = self._worker_runner.run(
            "data.clean",
            {"input": input_data.model_dump(mode="json")},
            paths=self._paths,
        )
        return CleanDatasetResult.model_validate(payload)


__all__ = [
    "CleanDatasetInput",
    "CleanDatasetResult",
    "CleanOperation",
    "DataCleaningService",
    "cleaning_operation_group_names",
    "cleaning_operation_metadata",
]
