from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import sessionmaker

from ...config import AppPaths
from ...exceptions import DatasetSourceMissingError, ValidationError, report_exception
from ..audit_contracts import ExecutionOrigin
from ..dataset_inspection import InspectDatasetInput
from ..dataset_service import DatasetService
from ..ml.contracts import (
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
)
from ..ml.evaluation import get_default_policy
from ..ml.registry import get_model_catalog_entry, get_model_service, list_model_catalog
from ..ml.trained_model_metadata import (
    parse_trained_model_metadata,
    with_evaluation,
    with_evaluation_task,
)
from ..ml.types import ApplyMode, ModelFamily
from ..ml_task_service import CancelMLTaskInput, CreateMLTaskInput, MLTaskService
from ..storage.identity import reserve_ids
from ..storage.models import (
    DatasetColumnBindingRow,
    JobDomain,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from ..storage.repositories import DatasetColumnBindingRepository, TrainedModelRepository
from .column_binding import (
    apply_columns_from_metadata,
    column_binding_error_message,
    feature_target_columns,
    normalize_columns,
    normalize_role_bindings,
    validate_feature_target_projection,
)
from .contracts import (
    ApplySourceInput,
    ApplyWithFilesInput,
    BulkTuneWithEvaluateInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLTaskDetails,
    TuneWithEvaluateInput,
    _ApplyContext,
    _ResolvedColumnBinding,
    _TrainingContext,
)
from .preparation import (
    build_apply_input_files,
    build_dataset_snapshot,
    build_text_preparation_input,
    build_trained_model_context,
    materialize_inline_apply_rows,
    validate_model_runtime_admission,
)

if TYPE_CHECKING:
    from ..job_scheduler import JobScheduler


class MLService:
    def __init__(
        self,
        paths: AppPaths,
        session_factory: sessionmaker,
        dataset_service: DatasetService,
        ml_task_service: MLTaskService,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._ml_task_service = ml_task_service
        self._scheduler = scheduler or self._build_default_scheduler()
        self._trained_models = TrainedModelRepository()
        self._column_bindings = DatasetColumnBindingRepository()
        self._ml_task_service.register_completion_listener(self._handle_task_completion)

    def _build_default_scheduler(self) -> JobScheduler:
        from ..job_scheduler import JobScheduler
        from ..ml_job_handler import MLJobHandler

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
        dataset_id = input_data.dataset_id
        if not dataset_id:
            raise ValidationError("Column binding requires a dataset.")

        dataset = self._dataset_service.get_dataset(dataset_id)
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        dataset_snapshot = build_dataset_snapshot(dataset, inspection)
        available_columns = {column.name for column in inspection.columns}
        catalog = get_model_catalog_entry(input_data.model_key) if input_data.model_key else None
        role_bindings = normalize_role_bindings(
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
                column_binding_error_message(
                    missing_by_role=missing_by_role,
                    available_columns=[column.name for column in inspection.columns],
                )
            )
        validate_feature_target_projection(role_bindings)

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

    def get_column_binding(self, binding_id: int) -> DatasetColumnBindingRow:
        with self._session_factory() as session:
            row = self._column_bindings.get(session, binding_id)
            if row is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(row)
            return row

    def fit_with_evaluate(self, input_data: FitWithEvaluateInput) -> MLTaskRow:
        context = self._build_training_context(input_data, input_data.model_key)
        validate_model_runtime_admission(context)
        model_service = get_model_service(input_data.model_key)
        try:
            params_model = model_service.validate_params(input_data.params)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        request = FitTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
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
            text_preparation=build_text_preparation_input(
                self._dataset_service,
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
            trained_model_context=build_trained_model_context(context),
        )
        return self._create_and_submit_task(context, MLTaskType.FIT, request, origin=input_data.origin)

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
            task_id=reserve_ids(self._session_factory)[0],
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
            trained_model_context=build_trained_model_context(context),
        )
        return self._create_and_submit_task(context, MLTaskType.HYPERPARAMETER_TUNING, request, origin=input_data.origin)

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

    def get_task_details(self, ml_task_id: int) -> MLTaskDetails:
        task = self._ml_task_service.get_ml_task(ml_task_id)
        artifacts = self._ml_task_service.list_ml_task_artifacts(ml_task_id)
        logs = self._ml_task_service.read_task_logs(ml_task_id)
        return MLTaskDetails(task=task, artifacts=artifacts, logs=logs)

    def cancel_task(self, ml_task_id: int) -> MLTaskRow:
        return self._ml_task_service.cancel_ml_task(CancelMLTaskInput(ml_task_id=ml_task_id))

    def list_dataset_tasks(self, dataset_id: int) -> list[MLTaskRow]:
        return self._ml_task_service.list_dataset_ml_tasks(dataset_id)

    def list_dataset_trained_models(self, dataset_id: int) -> list[TrainedModelRow]:
        with self._session_factory() as session:
            return self._trained_models.list_by_dataset(session, dataset_id)

    def get_trained_model(self, trained_model_id: int) -> TrainedModelRow | None:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is not None:
                session.expunge(trained_model)
            return trained_model

    def get_trained_model_by_ml_task(self, ml_task_id: int) -> TrainedModelRow | None:
        with self._session_factory() as session:
            trained_model = self._trained_models.get_by_ml_task(session, ml_task_id)
            if trained_model is not None:
                session.expunge(trained_model)
            return trained_model

    def wait_for_task(
        self,
        task_id: int,
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
                except Exception as exc:
                    report_exception(exc)
                raise ValidationError("Agent run was cancelled.")
            task = self.get_task_details(task_id).task
            if task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
                if task.status is not MLTaskStatus.SUCCEEDED:
                    raise _unsuccessful_task_error(task)
                return task
            time.sleep(0.1)
        return None

    def wait_for_training_models(
        self,
        root_task_ids: list[int],
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
                    except Exception as exc:
                        report_exception(exc)
                        continue
                raise ValidationError("Agent run was cancelled.")

            failed = [
                task
                for task in related_tasks
                if task.status in {MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            ]
            if failed:
                raise _unsuccessful_task_error(failed[0])

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

    def trained_models_for_root_tasks(self, root_task_ids: list[int]) -> list[TrainedModelRow]:
        models_by_task_id: dict[int, TrainedModelRow] = {}
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
        seen_task_ids: set[int] = set()
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
    def evaluation_task_id_for_model(model: TrainedModelRow) -> int | None:
        task_id = model.metadata_payload.get("evaluation_ml_task_id")
        if isinstance(task_id, int):
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
            materialize_inline_apply_rows(
                self._dataset_service,
                apply_context.feature_columns,
                input_data.input_rows,
            )
            if apply_context.apply_mode is ApplyMode.ROWS
            else None
        )
        if inline_path is not None:
            input_sources.append(ApplySourceInput(source_path=str(inline_path)))
        input_files = (
            build_apply_input_files(
                self._paths,
                self._dataset_service,
                apply_context.feature_columns,
                input_sources,
            )
            if apply_context.apply_mode is ApplyMode.ROWS
            else []
        )
        request = ApplyTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
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
        return self._create_task_from_request(MLTaskType.APPLY, request, auto_submit=True, origin=input_data.origin)

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
        if not isinstance(trained_model_id, int) or not all(
            isinstance(value, str) and value
            for value in (evaluation_model_path, holdout_artifact_path, model_key)
        ):
            raise ValidationError("Training result is missing the references required for evaluation.")

        evaluate_request = EvaluateTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
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
        origin = (
            ExecutionOrigin(
                thread_id=task.origin_thread_id,
                tool_call_message_id=task.origin_tool_call_message_id,
                explanation=task.agent_explanation,
                submitted_parameters=task.submitted_parameters or {},
            )
            if task.origin_thread_id and task.agent_explanation
            else None
        )
        created = self._create_task_from_request(MLTaskType.EVALUATE, evaluate_request, origin=origin)
        self._attach_evaluation_task_to_trained_model(trained_model_id, created.id)
        self._submit_ml_task(created)

    def _update_evaluated_trained_model(self, task: MLTaskRow) -> None:
        result_payload = task.result_payload or {}
        request_payload = task.request_payload
        with self._session_factory() as session:
            evaluated_model_id = request_payload.get("evaluate_model", {}).get("trained_model_id")
            if not isinstance(evaluated_model_id, int):
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
    ) -> _TrainingContext:
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
                model_key=model_key,
                summary_metric_name=catalog.summary_metric_name,
                group_aware=get_model_service(model_key).uses_automatic_groups
                or any(
                    role_binding.role == "group" and role_binding.columns
                    for role_binding in binding.role_bindings
                ),
            ),
            inspection=binding.inspection,
            dataset_snapshot=binding.dataset_snapshot,
        )

    def _create_and_submit_task(
        self,
        context: _TrainingContext,
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
        *,
        origin: ExecutionOrigin | None = None,
    ) -> MLTaskRow:
        created = self._create_task_from_request(task_type, request, origin=origin)
        self._submit_ml_task(created)
        return created

    def _create_task_from_request(
        self,
        task_type: MLTaskType,
        request: FitTaskRequest | HyperparameterTuningTaskRequest | EvaluateTaskRequest | ApplyTaskRequest,
        *,
        auto_submit: bool = False,
        origin: ExecutionOrigin | None = None,
    ) -> MLTaskRow:
        created = self._ml_task_service.create_ml_task(
            CreateMLTaskInput(
                id=request.task_id,
                origin=origin,
                project_id=request.project_id,
                dataset_id=request.dataset_id,
                task_type=task_type,
                request_payload=request.model_dump(mode="json"),
            )
        )
        if auto_submit:
            self._submit_ml_task(created)
        return created

    def _build_apply_context(self, input_data: ApplyWithFilesInput) -> _ApplyContext:
        trained_model_id = input_data.trained_model_id
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
            normalize_columns(
                apply_columns_from_metadata(metadata),
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
        trained_model_id: int,
    ) -> TrainedModelRow:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is None:
                raise ValidationError("The selected trained model is invalid for the current dataset.")
            if not Path(trained_model.artifact_path).exists():
                raise ValidationError("The selected trained model artifact is missing.")
            session.expunge(trained_model)
            return trained_model

    def _resolve_column_binding(self, binding_id: int, *, model_key: str) -> _ResolvedColumnBinding:
        normalized_binding_id = binding_id
        if not normalized_binding_id:
            raise ValidationError("Training requires a column binding.")
        with self._session_factory() as session:
            binding = self._column_bindings.get(session, normalized_binding_id)
            if binding is None:
                raise ValidationError("The selected column binding is invalid.")
            session.expunge(binding)

        catalog = get_model_catalog_entry(model_key)
        role_bindings = normalize_role_bindings(
            binding.role_bindings,
            train_role_schema=catalog.train_role_schema,
        )
        validate_feature_target_projection(role_bindings)
        feature_columns, target_columns = feature_target_columns(role_bindings)

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
        current_snapshot = build_dataset_snapshot(dataset, inspection)
        if stored_snapshot.model_dump(exclude={"sampling_fingerprint"}) != current_snapshot.model_dump(exclude={"sampling_fingerprint"}):
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

    def _update_trained_model_metadata_with_evaluation(
        self,
        session: Any,
        trained_model_id: int,
        evaluation: CandidateMetrics,
        *,
        evaluation_ml_task_id: int | None = None,
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
        trained_model_id: int,
        evaluation_ml_task_id: int,
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


def _unsuccessful_task_error(task: MLTaskRow) -> ValidationError:
    message = f"ML task '{task.id}' finished with status '{task.status.value}'."
    if task.error_summary:
        message = f"{message} {task.error_summary}"
    return ValidationError(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)
