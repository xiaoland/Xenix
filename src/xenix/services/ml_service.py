from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError, report_exception
from .audit_contracts import ExecutionOrigin
from .dataset_service import DatasetService
from .ml.contracts import (
    ApplyTaskRequest,
    CandidateMetrics,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    HyperparameterTuningTaskRequest,
    TaskLogEntry,
)
from .ml.registry import get_model_catalog_entry, list_model_catalog
from .ml.trained_model_metadata import parse_trained_model_metadata, with_evaluation, with_evaluation_task
from .ml_apply_inputs import (
    ApplyInputPreparation,
    ApplySourceInput as ApplySourceInput,
    ApplyWithFilesInput as ApplyWithFilesInput,
    InlineApplyRowsInput as InlineApplyRowsInput,
)
from .ml_column_bindings import ColumnBindingService, CreateColumnBindingInput as CreateColumnBindingInput
from .ml_task_service import CancelMLTaskInput, CreateMLTaskInput, MLTaskService
from .ml_training_inputs import (
    FitWithEvaluateInput as FitWithEvaluateInput,
    TrainingInputPreparation,
    TuneWithEvaluateInput as TuneWithEvaluateInput,
)
from .storage.identity import reserve_ids
from .storage.models import (
    DatasetColumnBindingRow,
    JobDomain,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from .storage.repositories import TrainedModelRepository

if TYPE_CHECKING:
    from .job_scheduler import JobScheduler


class BulkTuningSelection(SQLModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuneWithEvaluateInput(SQLModel):
    binding_id: int
    run_name: str | None = None
    selections: list[BulkTuningSelection] = Field(default_factory=list)


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
        self._session_factory = session_factory
        self._ml_task_service = ml_task_service
        self._scheduler = scheduler or self._build_default_scheduler()
        self._trained_models = TrainedModelRepository()
        self._column_bindings = ColumnBindingService(session_factory, dataset_service)
        self._apply_inputs = ApplyInputPreparation(paths, session_factory, dataset_service, self._trained_models)
        self._training_inputs = TrainingInputPreparation(session_factory, dataset_service, self._column_bindings)
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
        return self._column_bindings.create(input_data)

    def get_column_binding(self, binding_id: int) -> DatasetColumnBindingRow:
        return self._column_bindings.get(binding_id)

    def fit_with_evaluate(self, input_data: FitWithEvaluateInput) -> MLTaskRow:
        request = self._training_inputs.build_fit_request(input_data)
        return self._create_task_from_request(MLTaskType.FIT, request, auto_submit=True, origin=input_data.origin)

    def tune_with_evaluate(self, input_data: TuneWithEvaluateInput) -> MLTaskRow:
        request = self._training_inputs.build_tuning_request(input_data)
        return self._create_task_from_request(
            MLTaskType.HYPERPARAMETER_TUNING,
            request,
            auto_submit=True,
            origin=input_data.origin,
        )

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
                    pass
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
        request = self._apply_inputs.build_request(input_data)
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
        origin = (ExecutionOrigin(thread_id=task.origin_thread_id,
            tool_call_message_id=task.origin_tool_call_message_id,
            explanation=task.agent_explanation, submitted_parameters=task.submitted_parameters or {})
            if task.origin_thread_id and task.agent_explanation else None)
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


def _now() -> Any:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
