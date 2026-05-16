from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import DatasetSourceMissingError, ValidationError
from .dataset_inspection import InspectDatasetInput
from .dataset_service import DatasetService
from .ml.contracts import (
    CandidateMetrics,
    ColumnSelection,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningPayload,
    InferenceInputFile,
    InferenceModelPayload,
    InferenceTaskRequest,
    ManualTrainingPayload,
    TaskContinuationPlan,
    TaskLogEntry,
    TrainedModelContextPayload,
)
from .ml.evaluation import compare_metric_snapshots, get_default_policy
from .ml.registry import get_model_catalog_entry, get_model_service, list_model_catalog
from .ml_task_service import CancelMLTaskInput, CreateMLTaskInput, MLTaskService
from .trained_model_metadata import parse_trained_model_metadata, with_evaluation
from .storage.models import MLTaskArtifactRow, MLTaskRow, MLTaskStatus, MLTaskType, TrainedModelRow
from .storage.repositories import MLTaskRepository, TrainedModelRepository, WorkItemRepository
from .work_item_service import WorkItemService


class FitWithEvaluateInput(SQLModel):
    work_item_id: str | None = None
    dataset_id: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    run_name: str | None = None
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class TuneWithEvaluateInput(SQLModel):
    work_item_id: str | None = None
    dataset_id: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    run_name: str | None = None
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuningSelection(SQLModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuneWithEvaluateInput(SQLModel):
    work_item_id: str | None = None
    dataset_id: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    run_name: str | None = None
    selections: list[BulkTuningSelection] = Field(default_factory=list)


class InferWithFilesInput(SQLModel):
    work_item_id: str | None = None
    dataset_id: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    trained_model_id: str | None = None
    input_files: list[str] = Field(default_factory=list)


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
        work_item_service: WorkItemService,
        ml_task_service: MLTaskService,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._work_item_service = work_item_service
        self._ml_task_service = ml_task_service
        self._work_items = WorkItemRepository()
        self._trained_models = TrainedModelRepository()
        self._ml_tasks = MLTaskRepository()
        self._ml_task_service.register_completion_listener(self._handle_task_completion)

    def list_models(self) -> list[Any]:
        return list_model_catalog()

    def get_model(self, model_key: str) -> Any:
        return get_model_catalog_entry(model_key)

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
            work_item_id=context.work_item.id if context.work_item is not None else None,
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
            work_item_id=context.work_item.id if context.work_item is not None else None,
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
                        work_item_id=input_data.work_item_id,
                        dataset_id=input_data.dataset_id,
                        feature_columns=list(input_data.feature_columns),
                        target_columns=list(input_data.target_columns),
                        run_name=input_data.run_name,
                        model_key=selection.model_key,
                        param_grid=selection.param_grid,
                    )
                )
            )
        return tasks

    def list_work_item_tasks(self, work_item_id: str) -> list[MLTaskRow]:
        return self._ml_task_service.list_ml_tasks(work_item_id)

    def get_task_details(self, ml_task_id: str) -> MLTaskDetails:
        task = self._ml_task_service.get_ml_task(ml_task_id)
        artifacts = self._ml_task_service.list_ml_task_artifacts(ml_task_id)
        logs = self._ml_task_service.read_task_logs(ml_task_id)
        return MLTaskDetails(task=task, artifacts=artifacts, logs=logs)

    def cancel_task(self, ml_task_id: str) -> MLTaskRow:
        return self._ml_task_service.cancel_ml_task(CancelMLTaskInput(ml_task_id=ml_task_id))

    def list_trained_models(self, work_item_id: str) -> list[TrainedModelRow]:
        with self._session_factory() as session:
            return self._trained_models.list_by_work_item(session, work_item_id)

    def list_dataset_tasks(self, dataset_id: str) -> list[MLTaskRow]:
        return self._ml_task_service.list_dataset_ml_tasks(dataset_id)

    def list_dataset_trained_models(self, dataset_id: str) -> list[TrainedModelRow]:
        with self._session_factory() as session:
            return self._trained_models.list_by_dataset(session, dataset_id)

    def infer(self, input_data: InferWithFilesInput) -> MLTaskRow:
        inference_context = self._build_inference_context(input_data)
        input_files = self._build_inference_input_files(inference_context.feature_columns, input_data.input_files)
        request = InferenceTaskRequest(
            task_id="",
            project_id=inference_context.project_id,
            work_item_id=inference_context.work_item.id if inference_context.work_item is not None else None,
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
            self._update_best_trained_model(task)

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
        if not all(isinstance(value, str) and value for value in (trained_model_id, canonical_model_path, holdout_artifact_path, model_key)):
            return

        evaluate_request = EvaluateTaskRequest(
            task_id="",
            project_id=request_payload["project_id"],
            work_item_id=request_payload["work_item_id"],
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

    def _update_best_trained_model(self, task: MLTaskRow) -> None:
        result_payload = task.result_payload or {}
        request_payload = task.request_payload
        with self._session_factory() as session:
            evaluated_model_id = request_payload.get("evaluate_model", {}).get("trained_model_id")
            if not isinstance(evaluated_model_id, str):
                return
            new_metrics = EvaluateTaskResult.model_validate(result_payload).evaluation
            self._update_trained_model_metadata_with_evaluation(session, evaluated_model_id, new_metrics)
            if task.work_item_id is None:
                session.commit()
                return

            work_item = self._work_items.get(session, task.work_item_id)
            if work_item is None:
                session.commit()
                return
            if work_item.best_trained_model_id is None:
                self._work_items.set_best_trained_model(session, work_item.id, evaluated_model_id, _now())
                session.commit()
                return

            current_metrics = self._find_trained_model_evaluation(session, work_item.id, work_item.best_trained_model_id)
            if current_metrics is None:
                self._work_items.set_best_trained_model(session, work_item.id, evaluated_model_id, _now())
                session.commit()
                return
            if compare_metric_snapshots(
                EvaluateTaskResult.model_validate(result_payload).evaluation_policy,
                new_metrics,
                current_metrics,
            ) > 0:
                self._work_items.set_best_trained_model(session, work_item.id, evaluated_model_id, _now())
                session.commit()

    def _find_trained_model_evaluation(
        self,
        session: Any,
        work_item_id: str,
        trained_model_id: str,
    ) -> CandidateMetrics | None:
        for task in self._ml_tasks.list_by_work_item(session, work_item_id):
            if task.task_type is not MLTaskType.EVALUATE or task.status is not MLTaskStatus.SUCCEEDED:
                continue
            evaluate_model = (task.request_payload or {}).get("evaluate_model", {})
            if evaluate_model.get("trained_model_id") != trained_model_id:
                continue
            return EvaluateTaskResult.model_validate(task.result_payload).evaluation
        return None

    def _build_training_context(
        self,
        input_data: FitWithEvaluateInput | TuneWithEvaluateInput,
        model_key: str,
    ) -> "_TrainingContext":
        work_item = None
        if input_data.work_item_id is not None:
            work_item = self._work_item_service.get_work_item(input_data.work_item_id)
            if work_item.dataset_id is None:
                raise ValidationError("The selected work item does not have a linked dataset.")
            if not work_item.feature_columns:
                raise ValidationError("The selected work item does not have feature columns.")
            dataset_id = work_item.dataset_id
            feature_columns = list(work_item.feature_columns)
            target_columns = list(work_item.target_columns)
            run_name = work_item.name
        else:
            if input_data.dataset_id is None:
                raise ValidationError("Training requires either a work item or a dataset.")
            dataset_id = input_data.dataset_id
            feature_columns = self._normalize_columns(input_data.feature_columns, "feature")
            target_columns = self._normalize_columns(input_data.target_columns, "target")
            run_name = (input_data.run_name or "").strip()

        dataset = self._dataset_service.get_dataset(dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")

        catalog = get_model_catalog_entry(model_key)
        if catalog.requires_target and len(target_columns) != 1:
            raise ValidationError("The selected model requires exactly one target column.")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")

        inspection = self._dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=dataset.source_path)
        )
        available_columns = {column.name for column in inspection.columns}
        if not set(feature_columns).issubset(available_columns):
            raise ValidationError("The stored feature-column selection is invalid for the current dataset file.")
        if not set(target_columns).issubset(available_columns):
            raise ValidationError("The stored target-column selection is invalid for the current dataset file.")

        return _TrainingContext(
            project_id=dataset.project_id,
            work_item=work_item,
            dataset=dataset,
            run_name=run_name or dataset.name,
            catalog=catalog,
            column_selection=ColumnSelection(
                feature_columns=feature_columns,
                target_columns=target_columns,
            ),
            evaluation_policy=get_default_policy(catalog.problem_kind),
            inspection=inspection,
        )

    def _build_trained_model_context(self, context: "_TrainingContext") -> TrainedModelContextPayload:
        return TrainedModelContextPayload(
            work_item_name=context.run_name,
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
                work_item_id=request.work_item_id,
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

    def _resolve_inference_model(self, work_item: Any, trained_model_id: str | None) -> TrainedModelRow:
        with self._session_factory() as session:
            model_id = trained_model_id or work_item.best_trained_model_id
            if model_id is None:
                raise ValidationError("The selected work item does not have a best model yet. Select a trained model first.")
            trained_model = self._trained_models.get(session, model_id)
            if trained_model is None:
                raise ValidationError("The selected trained model is invalid for the current work item.")
            if trained_model.work_item_id is None:
                raise ValidationError("The selected trained model is not tied to this work item.")
            source_work_item = self._work_items.get(session, trained_model.work_item_id)
            if source_work_item is None:
                raise ValidationError("The selected trained model is invalid for the current work item.")
            if (
                list(source_work_item.feature_columns) != list(work_item.feature_columns)
                or list(source_work_item.target_columns) != list(work_item.target_columns)
            ):
                raise ValidationError(
                    "The selected trained model is incompatible with the current feature and target selection."
                )
            if not Path(trained_model.artifact_path).exists():
                raise ValidationError("The selected trained model artifact is missing.")
            return trained_model

    def _build_inference_context(self, input_data: InferWithFilesInput) -> "_InferenceContext":
        work_item = None
        if input_data.work_item_id is not None:
            work_item = self._work_item_service.get_work_item(input_data.work_item_id)
            if not work_item.feature_columns:
                raise ValidationError("The selected work item does not have feature columns.")
            dataset = self._dataset_service.get_dataset(work_item.dataset_id)
            if not Path(dataset.source_path).exists():
                raise DatasetSourceMissingError("Dataset source file is missing.")
            trained_model = self._resolve_inference_model(work_item, input_data.trained_model_id)
            feature_columns = list(work_item.feature_columns)
            return _InferenceContext(
                project_id=work_item.project_id,
                work_item=work_item,
                dataset=dataset,
                feature_columns=feature_columns,
                trained_model=trained_model,
            )

        if input_data.dataset_id is None:
            raise ValidationError("Inference requires either a work item or a dataset.")
        if input_data.trained_model_id is None:
            raise ValidationError("Dataset-scoped inference requires a trained model.")

        dataset = self._dataset_service.get_dataset(input_data.dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        feature_columns = self._normalize_columns(input_data.feature_columns, "feature")
        trained_model = self._resolve_dataset_inference_model(dataset.id, feature_columns, input_data.trained_model_id)
        return _InferenceContext(
            project_id=dataset.project_id,
            work_item=None,
            dataset=dataset,
            feature_columns=feature_columns,
            trained_model=trained_model,
        )

    def _resolve_dataset_inference_model(
        self,
        dataset_id: str,
        feature_columns: list[str],
        trained_model_id: str,
    ) -> TrainedModelRow:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is None:
                raise ValidationError("The selected trained model is invalid for the current dataset.")
            if trained_model.dataset_id != dataset_id:
                raise ValidationError("The selected trained model is not tied to this dataset.")
            metadata = parse_trained_model_metadata(trained_model.metadata_payload)
            if metadata is not None and list(metadata.feature_columns) != list(feature_columns):
                raise ValidationError("The selected trained model is incompatible with the current feature selection.")
            if not Path(trained_model.artifact_path).exists():
                raise ValidationError("The selected trained model artifact is missing.")
            return trained_model

    def _build_inference_input_files(
        self,
        feature_columns: list[str],
        input_paths: list[str],
    ) -> list[InferenceInputFile]:
        if not input_paths:
            raise ValidationError("Select at least one inference input file.")
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

    def _normalize_columns(self, columns: list[str], label: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized and label == "feature":
            raise ValidationError("At least one feature column must be selected.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate {label} columns are not allowed.")
        return normalized

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
    work_item: Any | None
    dataset: Any
    run_name: str
    catalog: Any
    column_selection: ColumnSelection
    evaluation_policy: Any
    inspection: Any


@dataclass(frozen=True)
class _InferenceContext:
    project_id: str
    work_item: Any | None
    dataset: Any
    feature_columns: list[str]
    trained_model: TrainedModelRow


def _now() -> Any:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
