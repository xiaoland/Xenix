from __future__ import annotations

from dataclasses import dataclass
import difflib
from pathlib import Path
from typing import Any
import unicodedata

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import DatasetSourceMissingError, ValidationError
from .dataset_inspection import InspectDatasetInput
from .dataset_service import DatasetService, MaterializeManualInferenceCsvInput
from .ml.contracts import (
    CandidateMetrics,
    ColumnSelection,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    HyperparameterTuningPayload,
    HyperparameterTuningTaskRequest,
    InferenceInputFile,
    InferenceModelPayload,
    InferenceTaskRequest,
    ManualTrainingPayload,
    TaskContinuationPlan,
    TaskLogEntry,
    TrainedModelContextPayload,
)
from .ml.evaluation import get_default_policy
from .ml.registry import get_model_catalog_entry, get_model_service, list_model_catalog
from .ml_task_service import CancelMLTaskInput, CreateMLTaskInput, MLTaskService
from .storage.models import (
    DatasetColumnSelectionRow,
    DatasetRow,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from .storage.repositories import DatasetColumnSelectionRepository, MLTaskRepository, TrainedModelRepository
from .trained_model_metadata import parse_trained_model_metadata, with_evaluation

_COLUMN_NAME_NORMALIZATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


class CreateColumnSelectionInput(SQLModel):
    dataset_id: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)


class FitWithEvaluateInput(SQLModel):
    selection_id: str
    run_name: str | None = None
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class TuneWithEvaluateInput(SQLModel):
    selection_id: str
    run_name: str | None = None
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuningSelection(SQLModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuneWithEvaluateInput(SQLModel):
    selection_id: str
    run_name: str | None = None
    selections: list[BulkTuningSelection] = Field(default_factory=list)


class InlineInferenceRowsInput(SQLModel):
    header_index_map: dict[str, int] = Field(default_factory=dict)
    data: list[list[Any]] = Field(default_factory=list)


class InferWithFilesInput(SQLModel):
    trained_model_id: str
    input_files: list[str] = Field(default_factory=list)
    input_rows: InlineInferenceRowsInput | None = None


@dataclass(frozen=True)
class MLTaskDetails:
    task: MLTaskRow
    artifacts: list[MLTaskArtifactRow]
    logs: list[TaskLogEntry]


class MLService:
    def __init__(
        self,
        paths: AppPaths,
        session_factory: sessionmaker,
        dataset_service: DatasetService,
        ml_task_service: MLTaskService,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._ml_task_service = ml_task_service
        self._trained_models = TrainedModelRepository()
        self._ml_tasks = MLTaskRepository()
        self._column_selections = DatasetColumnSelectionRepository()
        self._ml_task_service.register_completion_listener(self._handle_task_completion)

    def list_models(self) -> list[Any]:
        return list_model_catalog()

    def get_model(self, model_key: str) -> Any:
        return get_model_catalog_entry(model_key)

    def create_column_selection(self, input_data: CreateColumnSelectionInput) -> DatasetColumnSelectionRow:
        dataset_id = input_data.dataset_id.strip()
        if not dataset_id:
            raise ValidationError("Column selection requires a dataset.")
        feature_columns = self._normalize_columns(input_data.feature_columns, "feature")
        target_columns = self._normalize_columns(input_data.target_columns, "target")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")

        dataset = self._dataset_service.get_dataset(dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        available_columns = {column.name for column in inspection.columns}
        missing_feature_columns = [column for column in feature_columns if column not in available_columns]
        missing_target_columns = [column for column in target_columns if column not in available_columns]
        if missing_feature_columns or missing_target_columns:
            raise ValidationError(
                self._column_selection_error_message(
                    missing_feature_columns=missing_feature_columns,
                    missing_target_columns=missing_target_columns,
                    available_columns=[column.name for column in inspection.columns],
                )
            )

        with self._session_factory() as session:
            row = self._column_selections.create(
                session,
                DatasetColumnSelectionRow(
                    dataset_id=dataset.id,
                    feature_columns=feature_columns,
                    target_columns=target_columns,
                ),
            )
            session.commit()
            session.refresh(row)
            return row

    def get_column_selection(self, selection_id: str) -> DatasetColumnSelectionRow:
        with self._session_factory() as session:
            row = self._column_selections.get(session, selection_id.strip())
            if row is None:
                raise ValidationError("The selected column selection is invalid.")
            session.expunge(row)
            return row

    def fit_with_evaluate(self, input_data: FitWithEvaluateInput) -> MLTaskRow:
        context = self._build_training_context(input_data, input_data.model_key)
        model_service = get_model_service(input_data.model_key)
        try:
            params_model = model_service.validate_params(input_data.params)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        request = FitTaskRequest(
            task_id="",
            project_id=context.project_id,
            dataset_id=context.dataset.id,
            dataset_source_path=context.dataset.source_path,
            problem_kind=context.catalog.problem_kind,
            column_selection=context.column_selection,
            evaluation_policy=context.evaluation_policy,
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.requires_target
                else None
            ),
            manual_training=ManualTrainingPayload(
                model_key=input_data.model_key,
                params=params_model.model_dump(mode="json", by_alias=True),
            ),
            trained_model_context=self._build_trained_model_context(context),
        )
        return self._create_and_submit_task(context, MLTaskType.FIT, request)

    def tune_with_evaluate(self, input_data: TuneWithEvaluateInput) -> MLTaskRow:
        context = self._build_training_context(input_data, input_data.model_key)
        model_service = get_model_service(input_data.model_key)
        try:
            param_grid_model = model_service.validate_param_grid(input_data.param_grid)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        request = HyperparameterTuningTaskRequest(
            task_id="",
            project_id=context.project_id,
            dataset_id=context.dataset.id,
            dataset_source_path=context.dataset.source_path,
            problem_kind=context.catalog.problem_kind,
            column_selection=context.column_selection,
            evaluation_policy=context.evaluation_policy,
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.requires_target
                else None
            ),
            hyperparameter_tuning=HyperparameterTuningPayload(
                model_key=input_data.model_key,
                param_grid=param_grid_model.model_dump(mode="json", by_alias=True),
            ),
            trained_model_context=self._build_trained_model_context(context),
        )
        return self._create_and_submit_task(context, MLTaskType.HYPERPARAMETER_TUNING, request)

    def bulk_tune_with_evaluate(self, input_data: BulkTuneWithEvaluateInput) -> list[MLTaskRow]:
        tasks: list[MLTaskRow] = []
        for selection in input_data.selections:
            tasks.append(
                self.tune_with_evaluate(
                    TuneWithEvaluateInput(
                        selection_id=input_data.selection_id,
                        run_name=input_data.run_name,
                        model_key=selection.model_key,
                        param_grid=selection.param_grid,
                    )
                )
            )
        return tasks

    def get_task_details(self, ml_task_id: str) -> MLTaskDetails:
        task = self._ml_task_service.get_ml_task(ml_task_id)
        artifacts = self._ml_task_service.list_ml_task_artifacts(ml_task_id)
        logs = self._ml_task_service.read_task_logs(ml_task_id)
        return MLTaskDetails(task=task, artifacts=artifacts, logs=logs)

    def cancel_task(self, ml_task_id: str) -> MLTaskRow:
        return self._ml_task_service.cancel_ml_task(CancelMLTaskInput(ml_task_id=ml_task_id))

    def list_dataset_tasks(self, dataset_id: str) -> list[MLTaskRow]:
        return self._ml_task_service.list_dataset_ml_tasks(dataset_id)

    def list_dataset_trained_models(self, dataset_id: str) -> list[TrainedModelRow]:
        with self._session_factory() as session:
            return self._trained_models.list_by_dataset(session, dataset_id)

    def infer(self, input_data: InferWithFilesInput) -> MLTaskRow:
        inference_context = self._build_inference_context(input_data)
        input_paths = list(input_data.input_files)
        inline_path = self._materialize_inline_inference_rows(
            inference_context.feature_columns,
            input_data.input_rows,
        )
        if inline_path is not None:
            input_paths.append(str(inline_path))
        input_files = self._build_inference_input_files(inference_context.feature_columns, input_paths)
        request = InferenceTaskRequest(
            task_id="",
            project_id=inference_context.project_id,
            dataset_id=inference_context.dataset.id,
            dataset_source_path=inference_context.dataset.source_path,
            feature_columns=inference_context.feature_columns,
            inference_model=InferenceModelPayload(
                trained_model_id=inference_context.trained_model.id,
                model_key=inference_context.trained_model.model_key,
                trained_model_artifact_path=inference_context.trained_model.artifact_path,
            ),
            input_files=input_files,
        )
        return self._create_task_from_request(MLTaskType.INFERENCE, request, auto_submit=True)

    def _handle_task_completion(self, task: MLTaskRow) -> None:
        if task.status is not MLTaskStatus.SUCCEEDED:
            return
        if task.task_type in {MLTaskType.FIT, MLTaskType.HYPERPARAMETER_TUNING}:
            self._submit_follow_up_evaluation(task)
        elif task.task_type is MLTaskType.EVALUATE:
            self._update_evaluated_trained_model(task)

    def _submit_follow_up_evaluation(self, task: MLTaskRow) -> None:
        request_payload = task.request_payload
        continuation = request_payload.get("continuation_plan")
        if not isinstance(continuation, dict) or continuation.get("next_operation") != MLTaskType.EVALUATE.value:
            return
        result_payload = task.result_payload or {}
        trained_model_id = result_payload.get("trained_model_id")
        canonical_model_path = result_payload.get("canonical_model_artifact_path")
        holdout_artifact_path = result_payload.get("holdout_artifact_path")
        model_key = result_payload.get("model_key")
        if not all(
            isinstance(value, str) and value
            for value in (trained_model_id, canonical_model_path, holdout_artifact_path, model_key)
        ):
            return

        evaluate_request = EvaluateTaskRequest(
            task_id="",
            project_id=request_payload["project_id"],
            dataset_id=request_payload["dataset_id"],
            dataset_source_path=request_payload["dataset_source_path"],
            problem_kind=request_payload["problem_kind"],
            column_selection=request_payload["column_selection"],
            evaluation_policy=request_payload["evaluation_policy"],
            evaluate_model=EvaluateModelPayload(
                trained_model_id=trained_model_id,
                model_key=model_key,
                source_ml_task_id=task.id,
                trained_model_artifact_path=canonical_model_path,
                holdout_artifact_path=holdout_artifact_path,
            ),
        )
        created = self._create_task_from_request(MLTaskType.EVALUATE, evaluate_request)
        self._ml_task_service.submit_ml_task(created.id)

    def _update_evaluated_trained_model(self, task: MLTaskRow) -> None:
        result_payload = task.result_payload or {}
        request_payload = task.request_payload
        with self._session_factory() as session:
            evaluated_model_id = request_payload.get("evaluate_model", {}).get("trained_model_id")
            if not isinstance(evaluated_model_id, str):
                return
            new_metrics = EvaluateTaskResult.model_validate(result_payload).evaluation
            self._update_trained_model_metadata_with_evaluation(session, evaluated_model_id, new_metrics)
            session.commit()

    def _build_training_context(
        self,
        input_data: FitWithEvaluateInput | TuneWithEvaluateInput,
        model_key: str,
    ) -> "_TrainingContext":
        selection = self._resolve_column_selection(input_data.selection_id)
        feature_columns = selection.feature_columns
        target_columns = selection.target_columns
        run_name = (input_data.run_name or "").strip()

        catalog = get_model_catalog_entry(model_key)
        if catalog.requires_target and len(target_columns) != 1:
            raise ValidationError("The selected model requires exactly one target column.")

        return _TrainingContext(
            project_id=selection.dataset.project_id,
            dataset=selection.dataset,
            run_name=run_name or selection.dataset.name,
            catalog=catalog,
            column_selection=ColumnSelection(
                feature_columns=feature_columns,
                target_columns=target_columns,
            ),
            evaluation_policy=get_default_policy(catalog.problem_kind),
            inspection=selection.inspection,
        )

    def _build_trained_model_context(self, context: "_TrainingContext") -> TrainedModelContextPayload:
        return TrainedModelContextPayload(
            run_name=context.run_name,
            dataset_name=context.dataset.name,
            dataset_file_name=context.inspection.file_name,
            feature_columns=list(context.column_selection.feature_columns),
            target_columns=list(context.column_selection.target_columns),
            dataset_row_count=context.inspection.row_count,
            dataset_column_count=context.inspection.column_count,
            preview_columns=list(context.inspection.preview_columns),
            preview_rows=[list(row) for row in context.inspection.preview_rows],
        )

    def _create_and_submit_task(
        self,
        context: "_TrainingContext",
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
    ) -> MLTaskRow:
        created = self._create_task_from_request(task_type, request)
        self._ml_task_service.submit_ml_task(created.id)
        return created

    def _create_task_from_request(
        self,
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest | EvaluateTaskRequest | InferenceTaskRequest,
        *,
        auto_submit: bool = False,
    ) -> MLTaskRow:
        created = self._ml_task_service.create_ml_task(
            CreateMLTaskInput(
                project_id=request.project_id,
                dataset_id=request.dataset_id,
                task_type=task_type,
                request_payload={},
            )
        )
        request.task_id = created.id
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, created.id)
            if row is None:
                raise ValidationError("Unable to persist the ML task request.")
            row.request_payload = request.model_dump(mode="json")
            session.add(row)
            session.commit()
            session.refresh(row)
            if auto_submit:
                self._ml_task_service.submit_ml_task(created.id)
            return row

    def _build_inference_context(self, input_data: InferWithFilesInput) -> "_InferenceContext":
        trained_model_id = input_data.trained_model_id.strip()
        if not trained_model_id:
            raise ValidationError("Inference requires a trained model.")

        trained_model = self._resolve_inference_model(trained_model_id)
        if not trained_model.dataset_id:
            raise ValidationError("The selected trained model is not tied to a dataset.")
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        if metadata is None or not metadata.feature_columns:
            raise ValidationError("The selected trained model does not contain a feature-column contract.")

        dataset = self._dataset_service.get_dataset(trained_model.dataset_id)
        feature_columns = self._normalize_columns(metadata.feature_columns, "feature")
        if list(metadata.feature_columns) != feature_columns:
            raise ValidationError("The selected trained model contains an invalid feature-column contract.")
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        return _InferenceContext(
            project_id=dataset.project_id,
            dataset=dataset,
            feature_columns=feature_columns,
            trained_model=trained_model,
        )

    def _resolve_inference_model(
        self,
        trained_model_id: str,
    ) -> TrainedModelRow:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is None:
                raise ValidationError("The selected trained model is invalid for the current dataset.")
            if not Path(trained_model.artifact_path).exists():
                raise ValidationError("The selected trained model artifact is missing.")
            session.expunge(trained_model)
            return trained_model

    def _resolve_column_selection(self, selection_id: str) -> "_ResolvedColumnSelection":
        normalized_selection_id = selection_id.strip()
        if not normalized_selection_id:
            raise ValidationError("Training requires a column selection.")
        with self._session_factory() as session:
            selection = self._column_selections.get(session, normalized_selection_id)
            if selection is None:
                raise ValidationError("The selected column selection is invalid.")
            session.expunge(selection)

        feature_columns = self._normalize_columns(selection.feature_columns, "feature")
        target_columns = self._normalize_columns(selection.target_columns, "target")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")

        dataset = self._dataset_service.get_dataset(selection.dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        available_columns = {column.name for column in inspection.columns}
        if not set(feature_columns).issubset(available_columns):
            raise ValidationError("The stored feature-column selection is invalid for the current dataset file.")
        if not set(target_columns).issubset(available_columns):
            raise ValidationError("The stored target-column selection is invalid for the current dataset file.")
        return _ResolvedColumnSelection(
            dataset=dataset,
            feature_columns=feature_columns,
            target_columns=target_columns,
            inspection=inspection,
        )

    def _build_inference_input_files(
        self,
        feature_columns: list[str],
        input_paths: list[str],
    ) -> list[InferenceInputFile]:
        if not input_paths:
            raise ValidationError("Select at least one inference input file or provide inline inference rows.")
        manual_root = (self._paths.temp / "manual-inference").resolve()
        files: list[InferenceInputFile] = []
        for raw_path in input_paths:
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(Path(raw_path).resolve()))
            )
            available = {column.name for column in inspection.columns}
            if not set(feature_columns).issubset(available):
                raise ValidationError("Inference input file does not contain the required feature columns.")
            absolute_path = Path(inspection.source_path).resolve()
            source_kind = "manual_csv" if manual_root in absolute_path.parents else "user_file"
            files.append(
                InferenceInputFile(
                    absolute_path=str(absolute_path),
                    file_name=absolute_path.name,
                    source_kind=source_kind,
                )
            )
        return files

    def _materialize_inline_inference_rows(
        self,
        feature_columns: list[str],
        input_rows: InlineInferenceRowsInput | None,
    ) -> Path | None:
        if input_rows is None:
            return None

        header_index_map = self._normalize_inline_header_index_map(input_rows.header_index_map)
        if set(header_index_map) != set(feature_columns):
            raise ValidationError("Inline inference columns must match the trained model feature columns exactly.")
        if not input_rows.data:
            raise ValidationError("Inline inference rows require at least one data row.")

        row_width = len(header_index_map)
        rows: list[dict[str, str | None]] = []
        for row in input_rows.data:
            if len(row) != row_width:
                raise ValidationError("Inline inference data rows must match the header index map width.")
            rows.append(
                {
                    column: self._normalize_inline_cell(row[header_index_map[column]])
                    for column in feature_columns
                }
            )

        return self._dataset_service.materialize_manual_inference_csv(
            MaterializeManualInferenceCsvInput(
                feature_columns=feature_columns,
                rows=rows,
            )
        )

    def _normalize_inline_header_index_map(self, header_index_map: dict[str, int]) -> dict[str, int]:
        if not header_index_map:
            raise ValidationError("Inline inference rows require a header_index_map.")

        normalized: dict[str, int] = {}
        for raw_column, raw_index in header_index_map.items():
            column = str(raw_column).strip()
            if not column:
                raise ValidationError("Inline inference column names cannot be empty.")
            if column in normalized:
                raise ValidationError("Inline inference column names cannot be duplicated.")
            if not isinstance(raw_index, int) or isinstance(raw_index, bool) or raw_index < 0:
                raise ValidationError("Inline inference header indexes must be non-negative integers.")
            normalized[column] = raw_index

        indexes = list(normalized.values())
        if len(set(indexes)) != len(indexes):
            raise ValidationError("Inline inference header indexes cannot be duplicated.")
        if sorted(indexes) != list(range(len(indexes))):
            raise ValidationError("Inline inference header indexes must be contiguous and start at 0.")
        return normalized

    def _normalize_inline_cell(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        raise ValidationError("Inline inference row values must be scalar JSON values.")

    def _normalize_columns(self, columns: list[str], label: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized and label == "feature":
            raise ValidationError("At least one feature column must be selected.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate {label} columns are not allowed.")
        return normalized

    def _column_selection_error_message(
        self,
        *,
        missing_feature_columns: list[str],
        missing_target_columns: list[str],
        available_columns: list[str],
    ) -> str:
        lines = ["Selected columns must exist in the dataset."]
        if missing_feature_columns:
            lines.append(f"Missing feature columns: {_format_column_names(missing_feature_columns)}.")
        if missing_target_columns:
            lines.append(f"Missing target columns: {_format_column_names(missing_target_columns)}.")
        suggestions = _column_name_suggestions(
            [*missing_feature_columns, *missing_target_columns],
            available_columns,
        )
        if suggestions:
            lines.append("Closest available column suggestions:")
            for missing, matches in suggestions.items():
                lines.append(f"- `{missing}` -> {_format_column_names(matches)}")
        lines.append(f"Available columns: {_format_column_names(available_columns)}.")
        lines.append("Use the exact column names returned by data.peek, data.query, or dataset inspection.")
        return "\n".join(lines)

    def _update_trained_model_metadata_with_evaluation(
        self,
        session: Any,
        trained_model_id: str,
        evaluation: CandidateMetrics,
    ) -> None:
        trained_model = self._trained_models.get(session, trained_model_id)
        if trained_model is None:
            return
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        if metadata is None:
            return
        self._trained_models.update_metadata(
            session,
            trained_model.id,
            with_evaluation(metadata, evaluation).model_dump(mode="json"),
            _now(),
        )


@dataclass(frozen=True)
class _TrainingContext:
    project_id: str
    dataset: Any
    run_name: str
    catalog: Any
    column_selection: ColumnSelection
    evaluation_policy: Any
    inspection: Any


@dataclass(frozen=True)
class _ResolvedColumnSelection:
    dataset: DatasetRow
    feature_columns: list[str]
    target_columns: list[str]
    inspection: Any


@dataclass(frozen=True)
class _InferenceContext:
    project_id: str
    dataset: Any
    feature_columns: list[str]
    trained_model: TrainedModelRow


def _now() -> Any:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _format_column_names(columns: list[str]) -> str:
    return ", ".join(f"`{column}`" for column in columns) if columns else "none"


def _column_name_suggestions(missing_columns: list[str], available_columns: list[str]) -> dict[str, list[str]]:
    available_by_normalized: dict[str, list[str]] = {}
    for column in available_columns:
        available_by_normalized.setdefault(_normalize_column_name_for_match(column), []).append(column)

    suggestions: dict[str, list[str]] = {}
    normalized_available = list(available_by_normalized)
    for missing in missing_columns:
        normalized_missing = _normalize_column_name_for_match(missing)
        matches = list(available_by_normalized.get(normalized_missing) or [])
        if not matches:
            close_keys = difflib.get_close_matches(normalized_missing, normalized_available, n=3, cutoff=0.84)
            for key in close_keys:
                matches.extend(available_by_normalized[key])
        if matches:
            suggestions[missing] = matches[:3]
    return suggestions


def _normalize_column_name_for_match(value: str) -> str:
    return (
        unicodedata.normalize("NFKC", value)
        .translate(_COLUMN_NAME_NORMALIZATION_TRANSLATION)
        .casefold()
        .strip()
    )
