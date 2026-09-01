from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any
import unicodedata

from pydantic import Field, model_validator
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import DatasetSourceMissingError, ValidationError
from .dataset_inspection import InspectDatasetInput
from .dataset_service import DatasetService, MaterializeManualApplyCsvInput
from .data_tokenization_contracts import StagedTextResourceInput, TextPreparationInput
from .ml.contracts import (
    ApplyInputFile,
    ApplyModelPayload,
    ApplyTaskRequest,
    CandidateMetrics,
    ColumnSelection,
    DatasetSnapshotFact,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    ForecastOptions,
    HyperparameterTuningPayload,
    HyperparameterTuningTaskRequest,
    ManualTrainingPayload,
    TaskContinuationPlan,
    TaskLogEntry,
    TrainedModelContextPayload,
)
from .ml.evaluation import get_default_policy
from .ml.registry import get_model_catalog_entry, get_model_service, list_model_catalog
from .ml.types import ApplyMode, ColumnRoleBinding, ColumnRoleKind, ModelFamily, ModelRoleSchema
from .ml_task_service import CancelMLTaskInput, CreateMLTaskInput, MLTaskService
from .storage.models import (
    DatasetColumnBindingRow,
    DatasetRow,
    JobDomain,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from .storage.repositories import DatasetColumnBindingRepository, MLTaskRepository, TrainedModelRepository
from .trained_model_metadata import parse_trained_model_metadata, with_evaluation, with_evaluation_task
from .tabular import resolve_tabular_column_index, resolve_tabular_schema

if TYPE_CHECKING:
    from .job_scheduler import JobScheduler

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
_MULTILINGUAL_TEXT_MODEL_KEYS = frozenset(
    {
        "text.classification.multilingual_logistic_regression_tfidf",
        "text.clustering.multilingual_kmeans_tfidf",
        "text.topic_modeling.multilingual_lda",
        "text.similarity.multilingual_tfidf_cosine",
    }
)
_MAX_TEXT_RESOURCE_ROWS = 20_000
_MULTILINGUAL_TEXT_RETRIEVAL_KEY = "text.similarity.multilingual_tfidf_cosine"
_MAX_EXACT_TEXT_RETRIEVAL_ROWS = 2_000


class CreateColumnBindingInput(SQLModel):
    dataset_id: str
    role_bindings: list[dict[str, Any]] = Field(default_factory=list)
    model_key: str | None = None


class FitWithEvaluateInput(SQLModel):
    binding_id: str
    run_name: str | None = None
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class TuneWithEvaluateInput(SQLModel):
    binding_id: str
    run_name: str | None = None
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuningSelection(SQLModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuneWithEvaluateInput(SQLModel):
    binding_id: str
    run_name: str | None = None
    selections: list[BulkTuningSelection] = Field(default_factory=list)


class InlineApplyRowsInput(SQLModel):
    header_index_map: dict[str, int] = Field(default_factory=dict)
    data: list[list[Any]] = Field(default_factory=list)


class ApplySourceInput(SQLModel):
    source_path: str
    dataset_id: str | None = None
    artifact_id: str | None = None


class ApplyWithFilesInput(SQLModel):
    trained_model_id: str
    input_files: list[str] = Field(default_factory=list)
    input_sources: list[ApplySourceInput] = Field(default_factory=list)
    input_rows: InlineApplyRowsInput | None = None
    horizon: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _has_one_apply_mode(self) -> "ApplyWithFilesInput":
        has_rows = bool(self.input_files or self.input_sources) or self.input_rows is not None
        has_horizon = self.horizon is not None
        if has_rows == has_horizon:
            raise ValueError(
                "Apply requires exactly one input mode: rows/files or a forecast horizon."
            )
        return self


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
        scheduler: "JobScheduler | None" = None,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._ml_task_service = ml_task_service
        self._scheduler = scheduler or self._build_default_scheduler()
        self._trained_models = TrainedModelRepository()
        self._ml_tasks = MLTaskRepository()
        self._column_bindings = DatasetColumnBindingRepository()
        self._ml_task_service.register_completion_listener(self._handle_task_completion)

    def _build_default_scheduler(self) -> "JobScheduler":
        from .job_scheduler import JobScheduler
        from .ml_job_handler import MLJobHandler

        scheduler = JobScheduler(
            self._session_factory,
            [MLJobHandler(self._ml_task_service)],
        )
        scheduler.start()
        return scheduler

    def _submit_ml_task(self, task: MLTaskRow) -> None:
        self._ml_task_service.prepare_ml_task(task.id)
        self._scheduler.enqueue(JobDomain.ML, task.task_type.value, task.id)

    def list_models(self) -> list[Any]:
        return list_model_catalog()

    def get_model(self, model_key: str) -> Any:
        return get_model_catalog_entry(model_key)

    def create_column_binding(self, input_data: CreateColumnBindingInput) -> DatasetColumnBindingRow:
        dataset_id = input_data.dataset_id.strip()
        if not dataset_id:
            raise ValidationError("Column binding requires a dataset.")

        dataset = self._dataset_service.get_dataset(dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        dataset_snapshot = self._build_dataset_snapshot(dataset, inspection)
        available_columns = {column.name for column in inspection.columns}
        catalog = get_model_catalog_entry(input_data.model_key) if input_data.model_key else None
        role_bindings = self._normalize_role_bindings(
            input_data.role_bindings,
            train_role_schema=catalog.train_role_schema if catalog is not None else None,
            inspection_column_names=[column.name for column in inspection.columns],
        )
        missing_by_role = {
            binding.role: [column for column in binding.columns if column not in available_columns]
            for binding in role_bindings
        }
        missing_by_role = {role: columns for role, columns in missing_by_role.items() if columns}
        if missing_by_role:
            raise ValidationError(
                self._column_binding_error_message(
                    missing_by_role=missing_by_role,
                    available_columns=[column.name for column in inspection.columns],
                )
            )
        self._validate_feature_target_projection(role_bindings)

        with self._session_factory() as session:
            row = self._column_bindings.create(
                session,
                DatasetColumnBindingRow(
                    dataset_id=dataset.id,
                    role_bindings=[binding.model_dump(mode="json") for binding in role_bindings],
                    dataset_snapshot_payload=dataset_snapshot.model_dump(mode="json"),
                    model_key=catalog.model_key if catalog is not None else None,
                    model_family=catalog.model_family.value if catalog is not None else None,
                    model_task_kind=catalog.model_task_kind.value if catalog is not None else None,
                    schema_version=2,
                ),
            )
            session.commit()
            session.refresh(row)
            return row

    def get_column_binding(self, binding_id: str) -> DatasetColumnBindingRow:
        with self._session_factory() as session:
            row = self._column_bindings.get(session, binding_id.strip())
            if row is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(row)
            return row

    def fit_with_evaluate(self, input_data: FitWithEvaluateInput) -> MLTaskRow:
        context = self._build_training_context(input_data, input_data.model_key)
        self._validate_model_runtime_admission(context)
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
            evaluation_kind=context.catalog.evaluation_kind,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            evaluation_policy=context.evaluation_policy,
            dataset_snapshot=context.dataset_snapshot,
            forecast_options=(
                ForecastOptions.model_validate(params_model.model_dump(mode="python"))
                if context.catalog.model_family is ModelFamily.FORECASTING
                else None
            ),
            text_preparation=self._build_text_preparation_input(
                context,
                params_model,
            ),
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.supports_evaluation
                else None
            ),
            manual_training=ManualTrainingPayload(
                model_key=input_data.model_key,
                params=params_model.model_dump(mode="json", by_alias=True),
            ),
            trained_model_context=self._build_trained_model_context(context),
        )
        return self._create_and_submit_task(context, MLTaskType.FIT, request)

    @staticmethod
    def _validate_model_runtime_admission(context: "_TrainingContext") -> None:
        if (
            context.catalog.model_key == _MULTILINGUAL_TEXT_RETRIEVAL_KEY
            and context.inspection.row_count > _MAX_EXACT_TEXT_RETRIEVAL_ROWS
        ):
            raise ValidationError(
                "Exact multilingual text retrieval supports at most "
                f"{_MAX_EXACT_TEXT_RETRIEVAL_ROWS:,} source rows in v1."
            )

    def tune_with_evaluate(self, input_data: TuneWithEvaluateInput) -> MLTaskRow:
        context = self._build_training_context(input_data, input_data.model_key)
        if not context.catalog.supports_hyperparameter_tuning:
            raise ValidationError(
                f"Model '{input_data.model_key}' does not support hyperparameter tuning."
            )
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
            evaluation_kind=context.catalog.evaluation_kind,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            evaluation_policy=context.evaluation_policy,
            dataset_snapshot=context.dataset_snapshot,
            forecast_options=(
                ForecastOptions.model_validate(param_grid_model.model_dump(mode="python"))
                if context.catalog.model_family is ModelFamily.FORECASTING
                else None
            ),
            continuation_plan=(
                TaskContinuationPlan(next_operation=MLTaskType.EVALUATE.value)
                if context.catalog.supports_evaluation
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
                        binding_id=input_data.binding_id,
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

    def get_trained_model(self, trained_model_id: str) -> TrainedModelRow | None:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is not None:
                session.expunge(trained_model)
            return trained_model

    def get_trained_model_by_ml_task(self, ml_task_id: str) -> TrainedModelRow | None:
        with self._session_factory() as session:
            trained_model = self._trained_models.get_by_ml_task(session, ml_task_id)
            if trained_model is not None:
                session.expunge(trained_model)
            return trained_model

    def wait_for_task(
        self,
        task_id: str,
        *,
        cancel_requested: Callable[[], bool],
        timeout_seconds: float,
    ) -> MLTaskRow | None:
        """Poll one ML task until it settles or the timeout elapses.

        A non-successful terminal status raises; a timeout returns None so the
        caller can choose an async receipt instead of blocking the turn.
        """
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if cancel_requested():
                try:
                    self.cancel_task(task_id)
                except Exception:
                    pass
                raise ValidationError("Agent run was cancelled.")
            task = self.get_task_details(task_id).task
            if task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
                if task.status is not MLTaskStatus.SUCCEEDED:
                    raise ValidationError(f"ML task '{task.id}' finished with status '{task.status.value}'.")
                return task
            time.sleep(0.1)
        return None

    def wait_for_training_models(
        self,
        root_task_ids: list[str],
        *,
        cancel_requested: Callable[[], bool],
        timeout_seconds: float,
    ) -> tuple[list[MLTaskRow], list[TrainedModelRow]] | None:
        """Poll a training run and its required follow-up evaluation to completion."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            root_tasks = [self.get_task_details(task_id).task for task_id in root_task_ids]
            trained_models = self.trained_models_for_root_tasks(root_task_ids)
            related_tasks = self.related_training_tasks(root_tasks, trained_models)
            if cancel_requested():
                for task_id in ([task.id for task in related_tasks] or root_task_ids):
                    try:
                        self.cancel_task(task_id)
                    except Exception:
                        continue
                raise ValidationError("Agent run was cancelled.")

            failed = [
                task
                for task in related_tasks
                if task.status in {MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            ]
            if failed:
                raise ValidationError(f"ML task '{failed[0].id}' finished with status '{failed[0].status.value}'.")

            root_tasks_succeeded = all(task.status is MLTaskStatus.SUCCEEDED for task in root_tasks)
            if root_tasks_succeeded and len(trained_models) == len(root_task_ids):
                if not self._training_follow_up_pending(root_tasks, trained_models):
                    return related_tasks, trained_models

            time.sleep(0.1)
        return None

    def _training_follow_up_pending(
        self,
        root_tasks: list[MLTaskRow],
        trained_models: list[TrainedModelRow],
    ) -> bool:
        models_by_root_task = {model.ml_task_id: model for model in trained_models}
        for root_task in root_tasks:
            model = models_by_root_task.get(root_task.id)
            if model is None:
                return True
            if self.training_task_requires_follow_up_evaluation(root_task):
                evaluation_task_id = self.evaluation_task_id_for_model(model)
                if not evaluation_task_id:
                    return True
                evaluation_task = self.get_task_details(evaluation_task_id).task
                if evaluation_task.status is not MLTaskStatus.SUCCEEDED:
                    return True
        return False

    def trained_models_for_root_tasks(self, root_task_ids: list[str]) -> list[TrainedModelRow]:
        models_by_task_id: dict[str, TrainedModelRow] = {}
        for task_id in root_task_ids:
            model = self.get_trained_model_by_ml_task(task_id)
            if model is not None:
                models_by_task_id[task_id] = model
        return [models_by_task_id[task_id] for task_id in root_task_ids if task_id in models_by_task_id]

    def related_training_tasks(
        self,
        root_tasks: list[MLTaskRow],
        trained_models: list[TrainedModelRow],
    ) -> list[MLTaskRow]:
        tasks: list[MLTaskRow] = []
        seen_task_ids: set[str] = set()
        for task in root_tasks:
            tasks.append(task)
            seen_task_ids.add(task.id)
        for model in trained_models:
            evaluation_task_id = self.evaluation_task_id_for_model(model)
            if not evaluation_task_id or evaluation_task_id in seen_task_ids:
                continue
            task = self.get_task_details(evaluation_task_id).task
            tasks.append(task)
            seen_task_ids.add(task.id)
        return tasks

    @staticmethod
    def evaluation_task_id_for_model(model: TrainedModelRow) -> str | None:
        task_id = model.metadata_payload.get("evaluation_ml_task_id")
        if isinstance(task_id, str) and task_id.strip():
            return task_id
        return None

    @staticmethod
    def training_task_requires_follow_up_evaluation(task: MLTaskRow) -> bool:
        continuation = task.request_payload.get("continuation_plan")
        return isinstance(continuation, dict) and continuation.get("next_operation") == "evaluate"

    def apply(self, input_data: ApplyWithFilesInput) -> MLTaskRow:
        apply_context = self._build_apply_context(input_data)
        input_sources = list(input_data.input_sources)
        input_sources.extend(
            ApplySourceInput(source_path=path)
            for path in input_data.input_files
        )
        inline_path = (
            self._materialize_inline_apply_rows(
                apply_context.feature_columns,
                input_data.input_rows,
            )
            if apply_context.apply_mode is ApplyMode.ROWS
            else None
        )
        if inline_path is not None:
            input_sources.append(ApplySourceInput(source_path=str(inline_path)))
        input_files = (
            self._build_apply_input_files(apply_context.feature_columns, input_sources)
            if apply_context.apply_mode is ApplyMode.ROWS
            else []
        )
        request = ApplyTaskRequest(
            task_id="",
            project_id=apply_context.project_id,
            dataset_id=apply_context.dataset.id,
            dataset_source_path=apply_context.dataset.source_path,
            feature_columns=apply_context.feature_columns,
            apply_model=ApplyModelPayload(
                trained_model_id=apply_context.trained_model.id,
                model_key=apply_context.trained_model.model_key,
                trained_model_artifact_path=apply_context.trained_model.artifact_path,
            ),
            input_files=input_files,
            forecast_horizon=input_data.horizon,
        )
        return self._create_task_from_request(MLTaskType.APPLY, request, auto_submit=True)

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
        evaluation_model_path = result_payload.get("evaluation_model_artifact_path") or canonical_model_path
        holdout_artifact_path = result_payload.get("holdout_artifact_path")
        model_key = result_payload.get("model_key")
        if not all(
            isinstance(value, str) and value
            for value in (trained_model_id, evaluation_model_path, holdout_artifact_path, model_key)
        ):
            return

        evaluate_request = EvaluateTaskRequest(
            task_id="",
            project_id=request_payload["project_id"],
            dataset_id=request_payload["dataset_id"],
            dataset_source_path=request_payload["dataset_source_path"],
            evaluation_kind=request_payload["evaluation_kind"],
            train_role_bindings=request_payload["train_role_bindings"],
            evaluation_policy=request_payload["evaluation_policy"],
            dataset_snapshot=request_payload["dataset_snapshot"],
            forecast_options=request_payload.get("forecast_options"),
            evaluate_model=EvaluateModelPayload(
                trained_model_id=trained_model_id,
                model_key=model_key,
                trained_model_artifact_path=evaluation_model_path,
                holdout_artifact_path=holdout_artifact_path,
            ),
        )
        created = self._create_task_from_request(MLTaskType.EVALUATE, evaluate_request)
        self._attach_evaluation_task_to_trained_model(trained_model_id, created.id)
        self._submit_ml_task(created)

    def _update_evaluated_trained_model(self, task: MLTaskRow) -> None:
        result_payload = task.result_payload or {}
        request_payload = task.request_payload
        with self._session_factory() as session:
            evaluated_model_id = request_payload.get("evaluate_model", {}).get("trained_model_id")
            if not isinstance(evaluated_model_id, str):
                return
            new_metrics = EvaluateTaskResult.model_validate(result_payload).evaluation
            if new_metrics is not None:
                self._update_trained_model_metadata_with_evaluation(
                    session,
                    evaluated_model_id,
                    new_metrics,
                    evaluation_ml_task_id=task.id,
                )
            session.commit()

    def _build_training_context(
        self,
        input_data: FitWithEvaluateInput | TuneWithEvaluateInput,
        model_key: str,
    ) -> "_TrainingContext":
        binding = self._resolve_column_binding(input_data.binding_id, model_key=model_key)
        feature_columns = binding.feature_columns
        target_columns = binding.target_columns
        run_name = (input_data.run_name or "").strip()

        catalog = get_model_catalog_entry(model_key)
        requires_complete_target = any(role.name == "target" and role.required for role in catalog.train_role_schema.roles)
        if requires_complete_target and len(target_columns) != 1:
            raise ValidationError("The selected model requires exactly one target column.")

        return _TrainingContext(
            project_id=binding.dataset.project_id,
            dataset=binding.dataset,
            run_name=run_name or binding.dataset.name,
            catalog=catalog,
            train_role_bindings=list(binding.role_bindings),
            column_selection=ColumnSelection(
                feature_columns=feature_columns,
                target_columns=target_columns,
            ),
            evaluation_policy=get_default_policy(
                catalog.evaluation_kind,
                summary_metric_name=catalog.summary_metric_name,
                group_aware=any(
                    role_binding.role == "group" and role_binding.columns
                    for role_binding in binding.role_bindings
                ),
            ),
            inspection=binding.inspection,
            dataset_snapshot=binding.dataset_snapshot,
        )

    def _build_trained_model_context(self, context: "_TrainingContext") -> TrainedModelContextPayload:
        return TrainedModelContextPayload(
            run_name=context.run_name,
            dataset_name=context.dataset.name,
            dataset_file_name=context.inspection.file_name,
            evaluation_kind=context.catalog.evaluation_kind.value,
            model_family=context.catalog.model_family.value,
            model_task_kind=context.catalog.model_task_kind.value,
            train_role_bindings=[binding.model_dump(mode="json") for binding in context.train_role_bindings],
            apply_role_schema=context.catalog.apply_role_schema.model_dump(mode="json"),
            result_contract=context.catalog.result_contract.model_dump(mode="json"),
            dataset_row_count=context.inspection.row_count,
            dataset_column_count=context.inspection.column_count,
            preview_columns=list(context.inspection.preview_columns),
            preview_rows=[list(row) for row in context.inspection.preview_rows],
        )

    def _build_text_preparation_input(
        self,
        context: "_TrainingContext",
        params_model: Any,
    ) -> TextPreparationInput | None:
        if context.catalog.model_key not in _MULTILINGUAL_TEXT_MODEL_KEYS:
            return None
        params = params_model.model_dump(mode="python")
        custom_ids = self._text_resource_dataset_ids(
            params.get("custom_dictionary_dataset_ids"),
            field_name="custom_dictionary_dataset_ids",
        )
        stopword_ids = self._text_resource_dataset_ids(
            params.get("stopword_dataset_ids"),
            field_name="stopword_dataset_ids",
        )
        if set(custom_ids) & set(stopword_ids):
            raise ValidationError(
                "A text resource Dataset cannot be both a custom dictionary and a stopword list."
            )
        return TextPreparationInput.model_validate(
            {
                "tokenizer_profile": params.get("preparation_profile"),
                "phrase_mode": params.get("phrase_mode"),
                "custom_dictionary_resources": [
                    self._stage_text_resource(context, dataset_id)
                    for dataset_id in custom_ids
                ],
                "stopword_resources": [
                    self._stage_text_resource(context, dataset_id)
                    for dataset_id in stopword_ids
                ],
            }
        )

    @staticmethod
    def _text_resource_dataset_ids(value: Any, *, field_name: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValidationError(f"{field_name} must contain registered Dataset ids.")
        normalized = [item.strip() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValidationError(f"{field_name} cannot contain duplicate Dataset ids.")
        return normalized

    def _stage_text_resource(
        self,
        context: "_TrainingContext",
        dataset_id: str,
    ) -> StagedTextResourceInput:
        dataset = self._dataset_service.get_dataset(dataset_id)
        if dataset.project_id != context.project_id:
            raise ValidationError(
                "Text preparation resources must belong to the training project."
            )
        source_path = Path(dataset.source_path)
        if not source_path.is_file():
            raise DatasetSourceMissingError("Text preparation resource source file is missing.")
        inspection = self._dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=str(source_path.resolve()))
        )
        if inspection.column_count != 1 or not 1 <= inspection.row_count <= _MAX_TEXT_RESOURCE_ROWS:
            raise ValidationError(
                "Each text preparation resource must contain one term column and 1-20,000 rows."
            )
        digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return StagedTextResourceInput(
            dataset_id=dataset.id,
            absolute_path=str(source_path.resolve()),
            source_sha256=digest.hexdigest(),
        )

    def _create_and_submit_task(
        self,
        context: "_TrainingContext",
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
    ) -> MLTaskRow:
        created = self._create_task_from_request(task_type, request)
        self._submit_ml_task(created)
        return created

    def _create_task_from_request(
        self,
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest | EvaluateTaskRequest | ApplyTaskRequest,
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
                self._submit_ml_task(created)
            return row

    def _build_apply_context(self, input_data: ApplyWithFilesInput) -> "_ApplyContext":
        trained_model_id = input_data.trained_model_id.strip()
        if not trained_model_id:
            raise ValidationError("Apply requires a trained model.")

        trained_model = self._resolve_apply_model(trained_model_id)
        catalog = get_model_catalog_entry(trained_model.model_key)
        if not catalog.supports_apply:
            raise ValidationError(
                f"Model '{trained_model.model_key}' does not support apply."
            )
        requested_mode = (
            ApplyMode.FUTURE_HORIZON
            if input_data.horizon is not None
            else ApplyMode.ROWS
        )
        if catalog.apply_mode is not requested_mode:
            raise ValidationError(
                f"Model '{trained_model.model_key}' requires {catalog.apply_mode.value} apply input."
            )
        if not trained_model.dataset_id:
            raise ValidationError("The selected trained model is not tied to a dataset.")
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        if metadata is None or not metadata.train_role_bindings:
            raise ValidationError("The selected trained model does not contain a train role-binding contract.")

        dataset = self._dataset_service.get_dataset(trained_model.dataset_id)
        apply_columns = (
            self._normalize_columns(
                self._apply_columns_from_metadata(metadata),
                "apply",
            )
            if requested_mode is ApplyMode.ROWS
            else []
        )
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        return _ApplyContext(
            project_id=dataset.project_id,
            dataset=dataset,
            feature_columns=apply_columns,
            trained_model=trained_model,
            apply_mode=requested_mode,
        )

    def _resolve_apply_model(
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

    def _resolve_column_binding(self, binding_id: str, *, model_key: str) -> "_ResolvedColumnBinding":
        normalized_binding_id = binding_id.strip()
        if not normalized_binding_id:
            raise ValidationError("Training requires a column binding.")
        with self._session_factory() as session:
            binding = self._column_bindings.get(session, normalized_binding_id)
            if binding is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(binding)

        catalog = get_model_catalog_entry(model_key)
        role_bindings = self._normalize_role_bindings(
            binding.role_bindings,
            train_role_schema=catalog.train_role_schema,
        )
        self._validate_feature_target_projection(role_bindings)
        feature_columns, target_columns = self._feature_target_columns(role_bindings)

        dataset = self._dataset_service.get_dataset(binding.dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        if binding.schema_version < 2 or not binding.dataset_snapshot_payload:
            raise ValidationError(
                "This column binding predates immutable Dataset identity. Re-create the column binding before training."
            )
        try:
            stored_snapshot = DatasetSnapshotFact.model_validate(binding.dataset_snapshot_payload)
        except Exception as exc:
            raise ValidationError(
                "The stored Dataset identity is invalid. Re-create the column binding before training."
            ) from exc
        current_snapshot = self._build_dataset_snapshot(dataset, inspection)
        if stored_snapshot != current_snapshot:
            raise ValidationError(
                "The Dataset contents changed after its column roles were bound. Re-create the column binding "
                "to review roles against the current data."
            )
        available_columns = {column.name for column in inspection.columns}
        missing_by_role = {
            role_binding.role: [column for column in role_binding.columns if column not in available_columns]
            for role_binding in role_bindings
        }
        missing_by_role = {role: columns for role, columns in missing_by_role.items() if columns}
        if missing_by_role:
            raise ValidationError("The stored column binding is invalid for the current dataset file.")
        return _ResolvedColumnBinding(
            dataset=dataset,
            role_bindings=role_bindings,
            feature_columns=feature_columns,
            target_columns=target_columns,
            inspection=inspection,
            dataset_snapshot=stored_snapshot,
        )

    def _build_apply_input_files(
        self,
        feature_columns: list[str],
        input_sources: list[ApplySourceInput],
    ) -> list[ApplyInputFile]:
        if not input_sources:
            raise ValidationError("Select at least one apply input file or provide inline apply rows.")
        manual_root = (self._paths.temp / "manual-apply").resolve()
        files: list[ApplyInputFile] = []
        for input_source in input_sources:
            raw_path = input_source.source_path
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(Path(raw_path).resolve()))
            )
            available = {column.name for column in inspection.columns}
            if not set(feature_columns).issubset(available):
                raise ValidationError("Apply input file does not contain the required apply columns.")
            absolute_path = Path(inspection.source_path).resolve()
            source_kind = "manual_csv" if manual_root in absolute_path.parents else "user_file"
            files.append(
                ApplyInputFile(
                    absolute_path=str(absolute_path),
                    file_name=absolute_path.name,
                    source_kind=source_kind,
                    dataset_id=input_source.dataset_id,
                    artifact_id=input_source.artifact_id,
                )
            )
        return files

    def _build_dataset_snapshot(
        self,
        dataset: DatasetRow,
        inspection: Any,
    ) -> DatasetSnapshotFact:
        source_path = Path(dataset.source_path)
        source_digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                source_digest.update(chunk)
        schema_payload = {
            "source_format": inspection.source_format.value,
            "columns": [
                {
                    "name": column.name,
                    "kind": column.kind.value,
                    "nullable": column.nullable,
                }
                for column in inspection.columns
            ],
        }
        schema_bytes = json.dumps(
            schema_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return DatasetSnapshotFact(
            dataset_id=dataset.id,
            source_sha256=source_digest.hexdigest(),
            source_byte_size=source_path.stat().st_size,
            schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
        )

    def _materialize_inline_apply_rows(
        self,
        feature_columns: list[str],
        input_rows: InlineApplyRowsInput | None,
    ) -> Path | None:
        if input_rows is None:
            return None

        header_index_map = self._normalize_inline_header_index_map(input_rows.header_index_map)
        if set(header_index_map) != set(feature_columns):
            raise ValidationError("Inline apply columns must match the trained model apply columns exactly.")
        if not input_rows.data:
            raise ValidationError("Inline apply rows require at least one data row.")

        row_width = len(header_index_map)
        rows: list[dict[str, str | None]] = []
        for row in input_rows.data:
            if len(row) != row_width:
                raise ValidationError("Inline apply data rows must match the header index map width.")
            rows.append(
                {
                    column: self._normalize_inline_cell(row[header_index_map[column]])
                    for column in feature_columns
                }
            )

        return self._dataset_service.materialize_manual_apply_csv(
            MaterializeManualApplyCsvInput(
                feature_columns=feature_columns,
                rows=rows,
            )
        )

    def _normalize_inline_header_index_map(self, header_index_map: dict[str, int]) -> dict[str, int]:
        if not header_index_map:
            raise ValidationError("Inline apply rows require a header_index_map.")

        normalized: dict[str, int] = {}
        for raw_column, raw_index in header_index_map.items():
            column = str(raw_column).strip()
            if not column:
                raise ValidationError("Inline apply column names cannot be empty.")
            if column in normalized:
                raise ValidationError("Inline apply column names cannot be duplicated.")
            if not isinstance(raw_index, int) or isinstance(raw_index, bool) or raw_index < 0:
                raise ValidationError("Inline apply header indexes must be non-negative integers.")
            normalized[column] = raw_index

        indexes = list(normalized.values())
        if len(set(indexes)) != len(indexes):
            raise ValidationError("Inline apply header indexes cannot be duplicated.")
        if sorted(indexes) != list(range(len(indexes))):
            raise ValidationError("Inline apply header indexes must be contiguous and start at 0.")
        return normalized

    def _normalize_inline_cell(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        raise ValidationError("Inline apply row values must be scalar JSON values.")

    def _normalize_role_bindings(
        self,
        raw_bindings: list[dict[str, Any]],
        *,
        train_role_schema: ModelRoleSchema | None,
        inspection_column_names: list[str] | None = None,
    ) -> list[ColumnRoleBinding]:
        if not raw_bindings:
            raise ValidationError("At least one column role binding is required.")
        schema_by_role = {
            role.name: role
            for role in train_role_schema.roles
        } if train_role_schema is not None else {}
        normalized: list[ColumnRoleBinding] = []
        seen_roles: set[str] = set()
        for raw_binding in raw_bindings:
            binding_payload = self._canonicalize_role_binding_columns(
                raw_binding,
                inspection_column_names=inspection_column_names,
            )
            try:
                binding = ColumnRoleBinding.model_validate(binding_payload)
            except Exception as exc:
                raise ValidationError("Column role bindings must be valid role binding objects.") from exc
            role = binding.role.strip()
            if not role:
                raise ValidationError("Column role binding names cannot be empty.")
            if role in seen_roles:
                raise ValidationError(f"Duplicate column role binding '{role}' is not allowed.")
            seen_roles.add(role)
            role_definition = schema_by_role.get(role)
            if train_role_schema is not None and role_definition is None and not train_role_schema.additional_roles:
                raise ValidationError(f"Column role '{role}' is not accepted by the selected model.")
            columns = self._normalize_role_columns(binding.columns, role)
            role_kind = binding.role_kind or (
                role_definition.kind if role_definition is not None else self._infer_role_kind(columns)
            )
            if role_definition is not None and role_kind != role_definition.kind:
                raise ValidationError(f"Column role '{role}' must use role kind '{role_definition.kind.value}'.")
            if role_kind is ColumnRoleKind.SINGLE_COLUMN and len(columns) != 1:
                raise ValidationError(f"Column role '{role}' must bind exactly one column.")
            if role_kind is ColumnRoleKind.MANY_COLUMNS and not columns:
                raise ValidationError(f"Column role '{role}' must bind at least one column.")
            normalized.append(
                ColumnRoleBinding(
                    role=role,
                    columns=columns,
                    role_kind=role_kind,
                    required=role_definition.required if role_definition is not None else binding.required,
                    metadata=dict(binding.metadata),
                )
            )

        if train_role_schema is not None:
            missing_roles = [
                role.name
                for role in train_role_schema.roles
                if role.required and role.name not in seen_roles
            ]
            if missing_roles:
                raise ValidationError(f"Missing required column roles: {', '.join(missing_roles)}.")
        return normalized

    def _canonicalize_role_binding_columns(
        self,
        raw_binding: dict[str, Any],
        *,
        inspection_column_names: list[str] | None,
    ) -> dict[str, Any]:
        if not isinstance(raw_binding, dict):
            raise ValidationError("Column role bindings must be valid role binding objects.")

        reference_keys = [
            key
            for key in ("columns", "column_indexes")
            if key in raw_binding and raw_binding[key] is not None
        ]
        if len(reference_keys) > 1:
            raise ValidationError("Column role bindings must use either columns or column_indexes, not both.")
        if not reference_keys:
            raise ValidationError("Column role bindings require columns or column_indexes.")

        payload = dict(raw_binding)
        if reference_keys[0] == "column_indexes":
            payload["columns"] = self._resolve_role_column_indexes(
                raw_binding["column_indexes"],
                role=str(raw_binding.get("role") or ""),
                inspection_column_names=inspection_column_names,
            )
        payload.pop("column_indexes", None)
        return payload

    def _resolve_role_column_indexes(
        self,
        raw_indexes: Any,
        *,
        role: str,
        inspection_column_names: list[str] | None,
    ) -> list[str]:
        role_label = role.strip() or "<unnamed>"
        if inspection_column_names is None:
            raise ValidationError("Column indexes can only be resolved while creating a column binding.")
        if not isinstance(raw_indexes, list):
            raise ValidationError(f"Column role '{role_label}' column_indexes must be a list.")
        if not raw_indexes:
            raise ValidationError(f"Column role '{role_label}' column_indexes cannot be empty.")

        schema = resolve_tabular_schema(inspection_column_names)
        columns: list[str] = []
        for index in raw_indexes:
            field_name = f"Column role '{role_label}' column_indexes"
            try:
                columns.append(resolve_tabular_column_index(schema, index, field_name=field_name))
            except ValidationError as exc:
                # Keep the role-binding contract's actionable wording while
                # delegating strict type/range semantics to the shared helper.
                if isinstance(index, bool) or not isinstance(index, int):
                    raise ValidationError(
                        f"Column role '{role_label}' column_indexes must contain zero-based integer indexes."
                    ) from exc
                raise ValidationError(
                    f"Column role '{role_label}' column_indexes index {index} is outside the available "
                    "zero-based column range."
                ) from exc
        return columns

    def _normalize_role_columns(self, columns: list[str], role: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized:
            raise ValidationError(f"Column role '{role}' must bind at least one column.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate columns are not allowed for role '{role}'.")
        return normalized

    def _infer_role_kind(self, columns: list[str]) -> ColumnRoleKind:
        return ColumnRoleKind.SINGLE_COLUMN if len(columns) == 1 else ColumnRoleKind.MANY_COLUMNS

    def _feature_target_columns(self, role_bindings: list[ColumnRoleBinding]) -> tuple[list[str], list[str]]:
        feature_columns: list[str] = []
        target_columns: list[str] = []
        for binding in role_bindings:
            if binding.role == "feature":
                feature_columns = list(binding.columns)
            elif binding.role == "target":
                target_columns = list(binding.columns)
        return feature_columns, target_columns

    def _validate_feature_target_projection(self, role_bindings: list[ColumnRoleBinding]) -> None:
        role_by_column: dict[str, str] = {}
        for binding in role_bindings:
            for column in binding.columns:
                previous = role_by_column.get(column)
                if previous is not None and previous != binding.role:
                    raise ValidationError(
                        f"Column '{column}' cannot be bound to multiple roles: '{previous}' and '{binding.role}'."
                    )
                role_by_column[column] = binding.role

    def _apply_columns_from_metadata(self, metadata: Any) -> list[str]:
        schema_roles = metadata.apply_role_schema.get("roles") if isinstance(metadata.apply_role_schema, dict) else None
        role_names = [
            str(role.get("name"))
            for role in schema_roles or []
            if isinstance(role, dict) and role.get("required", True)
        ]
        if not role_names:
            role_names = ["feature"]
        columns: list[str] = []
        for role_name in role_names:
            columns.extend(_role_columns(metadata.train_role_bindings, role_name))
        return columns

    def _normalize_columns(self, columns: list[str], label: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized:
            raise ValidationError(f"At least one {label} column must be selected.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate {label} columns are not allowed.")
        return normalized

    def _column_binding_error_message(
        self,
        *,
        missing_by_role: dict[str, list[str]],
        available_columns: list[str],
    ) -> str:
        lines = ["Bound columns must exist in the dataset."]
        missing_columns: list[str] = []
        for role, columns in missing_by_role.items():
            missing_columns.extend(columns)
            lines.append(f"Missing columns for role '{role}': {_format_column_names(columns)}.")
        suggestions = _column_name_suggestions(
            missing_columns,
            available_columns,
        )
        if suggestions:
            lines.append("Closest available column suggestions:")
            for missing, matches in suggestions.items():
                lines.append(f"- `{missing}` -> {_format_column_names(matches)}")
        lines.append(f"Available columns: {_format_column_names(available_columns)}.")
        lines.append("Use the exact column names returned by data.query or dataset inspection.")
        return "\n".join(lines)

    def _update_trained_model_metadata_with_evaluation(
        self,
        session: Any,
        trained_model_id: str,
        evaluation: CandidateMetrics,
        *,
        evaluation_ml_task_id: str | None = None,
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
            with_evaluation(
                metadata,
                evaluation,
                evaluation_ml_task_id=evaluation_ml_task_id,
            ).model_dump(mode="json"),
            _now(),
        )

    def _attach_evaluation_task_to_trained_model(
        self,
        trained_model_id: str,
        evaluation_ml_task_id: str,
    ) -> None:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is None:
                return
            metadata = parse_trained_model_metadata(trained_model.metadata_payload)
            if metadata is None:
                return
            self._trained_models.update_metadata(
                session,
                trained_model.id,
                with_evaluation_task(metadata, evaluation_ml_task_id).model_dump(mode="json"),
                _now(),
            )
            session.commit()


@dataclass(frozen=True)
class _TrainingContext:
    project_id: str
    dataset: Any
    run_name: str
    catalog: Any
    train_role_bindings: list[ColumnRoleBinding]
    column_selection: ColumnSelection
    evaluation_policy: Any
    inspection: Any
    dataset_snapshot: DatasetSnapshotFact


@dataclass(frozen=True)
class _ResolvedColumnBinding:
    dataset: DatasetRow
    role_bindings: list[ColumnRoleBinding]
    feature_columns: list[str]
    target_columns: list[str]
    inspection: Any
    dataset_snapshot: DatasetSnapshotFact


@dataclass(frozen=True)
class _ApplyContext:
    project_id: str
    dataset: Any
    feature_columns: list[str]
    trained_model: TrainedModelRow
    apply_mode: ApplyMode


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


def _role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            columns = binding.get("columns")
            if isinstance(columns, list):
                return [str(column) for column in columns]
    return []


def _normalize_column_name_for_match(value: str) -> str:
    return (
        unicodedata.normalize("NFKC", value)
        .translate(_COLUMN_NAME_NORMALIZATION_TRANSLATION)
        .casefold()
        .strip()
    )
