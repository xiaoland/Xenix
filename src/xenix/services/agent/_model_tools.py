"""Model tool handlers, ML task waiting, and summary projection."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError as PydanticValidationError

from ...exceptions import NotFoundError, ValidationError
from ..ml.registry import get_model_catalog_entry, list_model_catalog
from ..ml.contracts import (
    ApplyTaskResult,
    CandidateMetrics,
    EvaluateTaskResult,
    FitTaskResult,
    HyperparameterTuningTaskResult,
)
from ..ml.types import ModelFamily
from ..ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    FitWithEvaluateInput,
    InlineApplyRowsInput as ServiceInlineApplyRowsInput,
    TuneWithEvaluateInput,
)
from ..storage.models import (
    MLTaskArtifactKind,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from ..trained_model_metadata import parse_trained_model_metadata
from ..llm.tooling import (
    ToolExecutionContext,
    ToolSuccess,
)
from .tool_inputs import (
    ModelApplyInput,
    ModelHyperTrainInput,
    ModelMetadataInput,
    ModelTaskQueryInput,
    ModelTrainInput,
)
from ._model_keys import (
    model_catalog_payload,
    normalize_model_keys,
    normalize_model_mapping,
)
from ._tool_common import _raise_if_cancelled


# Synchronous wait window before a model tool returns a running_background
# receipt. ML fit/tune/apply can outlive one conversation turn: wait up to this
# window so fast tasks return results inline, otherwise hand back a receipt with
# async_state="running_background" and let the Agent poll model.task.query
# instead of blocking the turn for the task's full duration.
MODEL_APPLY_GRACE_SECONDS = 30.0
MODEL_TRAIN_GRACE_SECONDS = 60.0
MAX_CLEANING_REPORT_OPERATION_ENTRIES = 12
MAX_CLEANING_REPORT_VALIDATION_ENTRIES = 12
MAX_CLEANING_REPORT_WARNING_ENTRIES = 5
MAX_CLEANING_REPORT_COLUMN_NAMES = 6
MAX_CLEANING_REPORT_WARNING_CHARS = 240
MAX_CLEANING_REPORT_COLUMN_NAME_CHARS = 96
MAX_CLEANING_REPORT_FILL_VALUE_CHARS = 96
MODEL_HYPER_TRAIN_GRACE_SECONDS = 60.0
MAX_MODEL_TASK_LOG_CHARS = 500
MAX_MODEL_METRICS = 24
MAX_MODEL_ROLE_BINDINGS = 16
MAX_MODEL_ROLE_COLUMNS = 20
MAX_MODEL_COLUMN_NAME_CHARS = 96
_LOCAL_PATH_PATTERN = re.compile(r"(?:(?:[A-Za-z]:[\\/]|\\\\|/)[^\s'\"<>]*)")


class ModelTools:
    def __init__(
        self,
        *,
        paths,
        dataset_service,
        artifact_service,
        ml_service,
        model_key_aliases,
    ) -> None:
        self._paths = paths
        self._dataset_service = dataset_service
        self._artifact_service = artifact_service
        self._ml_service = ml_service
        self._model_key_aliases = model_key_aliases


    def _model_metadata(
        self,
        input_data: ModelMetadataInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        detail_model_key: str | None = None
        if input_data.model_key is not None:
            detail_model_key = normalize_model_keys(
                [input_data.model_key],
                self._model_key_aliases,
                field_name="model_key",
            )[0]

        detail_query = detail_model_key is not None

        if detail_query:
            assert detail_model_key is not None
            catalog_entries = [get_model_catalog_entry(detail_model_key)]
        else:
            catalog_entries = list_model_catalog()

        selected_model_family = (
            ModelFamily(input_data.model_family)
            if input_data.model_family is not None
            else None
        )
        if selected_model_family is not None:
            catalog_entries = [
                entry for entry in catalog_entries if entry.model_family == selected_model_family
            ]

        catalog_entries = sorted(
            catalog_entries,
            key=lambda entry: (
                entry.model_family.value,
                entry.model_task_kind.value,
                entry.evaluation_kind.value,
                entry.problem_kind.value if entry.problem_kind is not None else "",
                entry.recommendation_tier,
                entry.model_key,
            ),
        )
        include_param_grid_schema = input_data.include_param_grid_schema
        include_param_schema = detail_query or include_param_grid_schema
        if not detail_query:
            include_param_schema = False
            include_param_grid_schema = False
        models = [
            model_catalog_payload(
                entry,
                detail_query=detail_query,
                include_param_schema=include_param_schema,
                include_param_grid_schema=include_param_grid_schema,
            )
            for entry in catalog_entries
        ]
        payload = {
            "model_keys": [model["model_key"] for model in models],
            "models": models,
        }
        return ToolSuccess(value=payload)

    def _model_train(
        self,
        input_data: ModelTrainInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        binding_id = input_data.binding_id
        models = normalize_model_keys(
            input_data.models,
            self._model_key_aliases,
            field_name="models",
        )
        params_by_model = normalize_model_mapping(
            input_data.params_by_model,
            self._model_key_aliases,
            field_name="params_by_model",
        )
        binding = self._ml_service.get_column_binding(binding_id)
        dataset_id = binding.dataset_id
        created_task_ids: list[str] = []
        for model_key in models:
            _raise_if_cancelled(self._ml_service, context)
            created = self._ml_service.fit_with_evaluate(
                FitWithEvaluateInput(
                    binding_id=binding_id,
                    run_name=input_data.run_name,
                    model_key=model_key,
                    params=dict(params_by_model.get(model_key) or {}),
                )
            )
            created_task_ids.append(created.id)
        training_result = self._wait_for_training_models_or_none(
            created_task_ids,
            context=context,
            timeout_seconds=MODEL_TRAIN_GRACE_SECONDS,
        )
        if training_result is None:
            return self._training_task_receipt(
                dataset_id=dataset_id,
                root_task_ids=created_task_ids,
                operation="fit",
            )
        tasks, trained_models = training_result
        payload = {
            "async_state": "completed",
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "ml_tasks": [self._ml_task_payload(task) for task in tasks],
            "trained_models": [self._trained_model_payload(model) for model in trained_models],
        }
        return ToolSuccess(value=payload)

    def _model_hyper_train(
        self,
        input_data: ModelHyperTrainInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        binding_id = input_data.binding_id
        normalized_grids = normalize_model_mapping(
            input_data.param_grids_by_model,
            self._model_key_aliases,
            field_name="param_grids_by_model",
            require_hyperparameter_tuning=True,
        )
        binding = self._ml_service.get_column_binding(binding_id)
        dataset_id = binding.dataset_id
        created_task_ids: list[str] = []
        for model_key, grid in normalized_grids.items():
            _raise_if_cancelled(self._ml_service, context)
            created = self._ml_service.tune_with_evaluate(
                TuneWithEvaluateInput(
                    binding_id=binding_id,
                    run_name=input_data.run_name,
                    model_key=model_key,
                    param_grid=dict(grid),
                )
            )
            created_task_ids.append(created.id)
        training_result = self._wait_for_training_models_or_none(
            created_task_ids,
            context=context,
            timeout_seconds=MODEL_HYPER_TRAIN_GRACE_SECONDS,
        )
        if training_result is None:
            return self._training_task_receipt(
                dataset_id=dataset_id,
                root_task_ids=created_task_ids,
                operation="hyperparameter_tuning",
            )
        tasks, trained_models = training_result
        payload = {
            "async_state": "completed",
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "ml_tasks": [self._ml_task_payload(task) for task in tasks],
            "trained_models": [self._trained_model_payload(model) for model in trained_models],
        }
        return ToolSuccess(value=payload)

    def _model_apply(
        self,
        input_data: ModelApplyInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        resolved_input_sources = self._resolve_apply_input_sources(input_data.input_sources)
        apply_input = ApplyWithFilesInput(
            trained_model_id=input_data.trained_model_id,
            input_sources=resolved_input_sources,
            input_rows=(
                ServiceInlineApplyRowsInput(
                    **input_data.input_rows.model_dump(mode="python")
                )
                if input_data.input_rows is not None
                else None
            ),
            horizon=input_data.horizon,
        )
        task = self._ml_service.apply(apply_input)
        completed_task = self._wait_for_task_or_none(
            task.id,
            context=context,
            timeout_seconds=MODEL_APPLY_GRACE_SECONDS,
        )
        if completed_task is None:
            return self._single_task_receipt(
                task_id=task.id,
                operation="apply",
            )
        task = completed_task
        details = self._ml_service.get_task_details(task.id)
        output_artifact = next(
            artifact
            for artifact in details.artifacts
            if artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT
        )
        if not output_artifact.artifact_id:
            raise ValidationError(
                "The completed apply task has no public Artifact reference. Re-run apply."
            )
        result_payload = details.task.result_payload or {}
        typed_result = ApplyTaskResult.model_validate(result_payload)
        text_apply_facts = typed_result.text_classification_apply_facts
        raw_text_apply = any(
            facts is not None
            for facts in (
                text_apply_facts,
                typed_result.text_clustering_apply_facts,
                typed_result.text_topic_apply_facts,
                typed_result.text_retrieval_apply_facts,
            )
        )
        return ToolSuccess(
            value={
                "async_state": "completed",
                "ml_task_id": task.id,
                "task_ids": [task.id],
                "ml_tasks": [self._ml_task_payload(task)],
                "model_key": typed_result.model_key,
                "training_dataset_id": task.dataset_id,
                "source_dataset_ids": list(result_payload.get("source_dataset_ids", [])),
                "source_artifact_ids": list(result_payload.get("source_artifact_ids", [])),
                "result_dataset_id": result_payload.get("result_dataset_id"),
                "artifact_id": output_artifact.artifact_id,
                "row_count": result_payload.get("row_count"),
                "apply_input_contract": "raw_text" if raw_text_apply else None,
                "text_classification_apply_facts": (
                    text_apply_facts.model_dump(mode="json") if text_apply_facts else None
                ),
                "text_clustering_apply_facts": (
                    self._text_discovery_payload(typed_result.text_clustering_apply_facts)
                    if typed_result.text_clustering_apply_facts
                    else None
                ),
                "text_topic_apply_facts": (
                    self._text_discovery_payload(typed_result.text_topic_apply_facts)
                    if typed_result.text_topic_apply_facts
                    else None
                ),
                "text_retrieval_apply_facts": (
                    self._text_discovery_payload(typed_result.text_retrieval_apply_facts)
                    if typed_result.text_retrieval_apply_facts
                    else None
                ),
            },
        )

    def _model_task_query(
        self,
        input_data: ModelTaskQueryInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        tasks = [
            self._ml_task_details_payload(
                task_id,
                include_logs=input_data.include_logs,
                max_log_entries=input_data.max_log_entries,
            )
            for task_id in input_data.task_ids
        ]
        payload = {
            "task_ids": input_data.task_ids,
            "tasks": tasks,
        }
        return ToolSuccess(value=payload)

    def _resolve_apply_input_sources(self, input_sources: list[str]) -> list[ApplySourceInput]:
        return [self._resolve_apply_input_source(input_source) for input_source in input_sources]

    def _resolve_apply_input_source(self, input_source: str) -> ApplySourceInput:
        source = input_source.strip()
        if source.startswith("artifact://"):
            artifact = self._artifact_service.resolve_uri(source)
            if not artifact.exists:
                raise ValidationError("Apply input artifact file is missing.")
            return ApplySourceInput(
                source_path=artifact.absolute_path,
                artifact_id=artifact.artifact_id,
            )

        try:
            dataset = self._dataset_service.get_dataset(source)
        except NotFoundError:
            raise ValidationError("model.apply input_sources must be registered dataset ids or artifact:// URIs.") from None
        if not Path(dataset.source_path).exists():
            raise ValidationError("Apply input dataset source file is missing.")
        return ApplySourceInput(
            source_path=dataset.source_path,
            dataset_id=dataset.id,
        )

    def _wait_for_training_models_or_none(
        self,
        root_task_ids: list[str],
        *,
        context: ToolExecutionContext,
        timeout_seconds: float,
    ) -> tuple[list[MLTaskRow], list[TrainedModelRow]] | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            root_tasks = [self._ml_service.get_task_details(task_id).task for task_id in root_task_ids]
            trained_models = self._trained_models_for_root_tasks(root_task_ids)
            related_tasks = self._related_training_tasks(root_tasks, trained_models)
            _raise_if_cancelled(self._ml_service, 
                context,
                ml_task_ids=[task.id for task in related_tasks] or root_task_ids,
            )

            failed = [
                task
                for task in related_tasks
                if task.status in {MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            ]
            if failed:
                raise ValidationError(f"ML task '{failed[0].id}' finished with status '{failed[0].status.value}'.")

            root_tasks_succeeded = all(task.status is MLTaskStatus.SUCCEEDED for task in root_tasks)
            if root_tasks_succeeded and len(trained_models) == len(root_task_ids):
                pending_evaluation = False
                models_by_root_task = {model.ml_task_id: model for model in trained_models}
                for root_task in root_tasks:
                    model = models_by_root_task.get(root_task.id)
                    if model is None:
                        pending_evaluation = True
                        break
                    if self._training_task_requires_follow_up_evaluation(root_task):
                        evaluation_task_id = self._evaluation_task_id_for_model(model)
                        if not evaluation_task_id:
                            pending_evaluation = True
                            break
                        evaluation_task = self._ml_service.get_task_details(evaluation_task_id).task
                        if evaluation_task.status is not MLTaskStatus.SUCCEEDED:
                            pending_evaluation = True
                            break
                if not pending_evaluation:
                    return self._related_training_tasks(root_tasks, trained_models), trained_models

            time.sleep(0.1)
        return None

    def _wait_for_task(
        self,
        task_id: str,
        *,
        context: ToolExecutionContext,
        timeout_seconds: float = 120.0,
    ) -> MLTaskRow:
        task = self._wait_for_task_or_none(task_id, context=context, timeout_seconds=timeout_seconds)
        if task is None:
            raise ValidationError(f"Timed out waiting for ML task '{task_id}'.")
        return task

    def _wait_for_task_or_none(
        self,
        task_id: str,
        *,
        context: ToolExecutionContext,
        timeout_seconds: float,
    ) -> MLTaskRow | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            _raise_if_cancelled(self._ml_service, context, ml_task_ids=[task_id])
            task = self._ml_service.get_task_details(task_id).task
            if task.status in self._terminal_statuses():
                if task.status is not MLTaskStatus.SUCCEEDED:
                    raise ValidationError(f"ML task '{task.id}' finished with status '{task.status.value}'.")
                return task
            time.sleep(0.1)
        return None

    def _terminal_statuses(self) -> set[MLTaskStatus]:
        return {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}

    def _trained_models_for_root_tasks(self, root_task_ids: list[str]) -> list[TrainedModelRow]:
        models_by_task_id: dict[str, TrainedModelRow] = {}
        for task_id in root_task_ids:
            model = self._ml_service.get_trained_model_by_ml_task(task_id)
            if model is not None:
                models_by_task_id[task_id] = model
        return [models_by_task_id[task_id] for task_id in root_task_ids if task_id in models_by_task_id]

    def _related_training_tasks(
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
            evaluation_task_id = self._evaluation_task_id_for_model(model)
            if not evaluation_task_id or evaluation_task_id in seen_task_ids:
                continue
            task = self._ml_service.get_task_details(evaluation_task_id).task
            tasks.append(task)
            seen_task_ids.add(task.id)
        return tasks

    def _evaluation_task_id_for_model(self, model: TrainedModelRow) -> str | None:
        task_id = model.metadata_payload.get("evaluation_ml_task_id")
        if isinstance(task_id, str) and task_id.strip():
            return task_id
        return None

    def _training_task_requires_follow_up_evaluation(self, task: MLTaskRow) -> bool:
        continuation = task.request_payload.get("continuation_plan")
        return isinstance(continuation, dict) and continuation.get("next_operation") == "evaluate"

    def _training_task_receipt(
        self,
        *,
        dataset_id: str,
        root_task_ids: list[str],
        operation: str,
    ) -> ToolSuccess:
        root_tasks = [self._ml_service.get_task_details(task_id).task for task_id in root_task_ids]
        trained_models = self._trained_models_for_root_tasks(root_task_ids)
        tasks = self._related_training_tasks(root_tasks, trained_models)
        task_ids = [task.id for task in tasks] or list(root_task_ids)
        payload = {
            "async_state": "running_background",
            "dataset_id": dataset_id,
            "operation": operation,
            "task_ids": task_ids,
            "root_task_ids": list(root_task_ids),
            "ml_tasks": [self._ml_task_payload(task) for task in tasks],
            "trained_models": [self._trained_model_payload(model) for model in trained_models],
        }
        return ToolSuccess(value=payload)

    def _single_task_receipt(
        self,
        *,
        task_id: str,
        operation: str,
    ) -> ToolSuccess:
        task = self._ml_service.get_task_details(task_id).task
        payload = {
            "async_state": "running_background",
            "operation": operation,
            "ml_task_id": task.id,
            "task_ids": [task.id],
            "root_task_ids": [task.id],
            "dataset_id": task.dataset_id,
            "ml_tasks": [self._ml_task_payload(task)],
        }
        return ToolSuccess(value=payload)

    def _ml_task_payload(self, task: MLTaskRow) -> dict[str, Any]:
        return {
            "task_id": task.id,
            "dataset_id": task.dataset_id,
            "task_type": task.task_type.value,
            "status": task.status.value,
            "model_key": self._model_key_from_task_payload(task.request_payload),
            "error_summary": self._bounded_status_message(task.error_summary),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "follow_up_task_ids": self._follow_up_task_ids(task),
        }

    def _ml_task_details_payload(
        self,
        task_id: str,
        *,
        include_logs: bool,
        max_log_entries: int,
    ) -> dict[str, Any]:
        details = self._ml_service.get_task_details(task_id)
        task_payload = self._ml_task_payload(details.task)
        logs = (
            [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": self._bounded_status_message(log.message),
                }
                for log in details.logs[-max_log_entries:]
            ]
            if include_logs and max_log_entries
            else []
        )
        task_payload.update(
            {
                "request": self._task_request_summary(
                    details.task.request_payload,
                    task_type=details.task.task_type,
                ),
                "result": self._task_result_summary(details.task),
                "artifacts": [
                    {
                        "ml_task_artifact_id": artifact.id,
                        "artifact_id": artifact.artifact_id,
                        "artifact_kind": artifact.artifact_kind.value,
                        "ready_to_open": artifact.ready_to_open,
                        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                    }
                    for artifact in details.artifacts
                ],
                "logs": logs,
            }
        )
        return task_payload

    def _task_request_summary(
        self,
        request_payload: dict[str, Any],
        *,
        task_type: MLTaskType,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            key: request_payload[key]
            for key in ("project_id", "dataset_id", "evaluation_kind")
            if isinstance(request_payload.get(key), str)
        }
        roles = request_payload.get("train_role_bindings")
        if isinstance(roles, list):
            summary["train_role_bindings"] = self._bounded_role_bindings(roles)
        snapshot = request_payload.get("dataset_snapshot")
        if isinstance(snapshot, dict):
            summary["dataset_snapshot"] = {
                key: snapshot[key]
                for key in (
                    "schema_version",
                    "dataset_id",
                    "source_sha256",
                    "source_byte_size",
                    "schema_digest",
                )
                if key in snapshot
            }
        policy = request_payload.get("evaluation_policy")
        if isinstance(policy, dict):
            summary["evaluation_policy"] = {
                key: policy[key]
                for key in (
                    "policy_key",
                    "evaluation_kind",
                    "primary_metric_name",
                    "primary_metric_direction",
                    "split_strategy",
                    "test_size",
                    "cv_folds",
                    "random_state",
                )
                if key in policy
            }
        if task_type is MLTaskType.FIT:
            summary["manual_training"] = self._model_command_summary(
                request_payload.get("manual_training"),
                parameter_field="params",
            )
        elif task_type is MLTaskType.HYPERPARAMETER_TUNING:
            summary["hyperparameter_tuning"] = self._model_command_summary(
                request_payload.get("hyperparameter_tuning"),
                parameter_field="param_grid",
            )
        elif task_type is MLTaskType.EVALUATE:
            summary["evaluate_model"] = self._model_reference_summary(
                request_payload.get("evaluate_model")
            )
        elif task_type is MLTaskType.APPLY:
            summary["apply_model"] = self._model_reference_summary(
                request_payload.get("apply_model")
            )
            inputs = request_payload.get("input_files")
            if isinstance(inputs, list):
                summary["input_sources"] = [
                    {
                        key: value[key]
                        for key in ("source_kind", "dataset_id", "artifact_id")
                        if isinstance(value, dict) and value.get(key) is not None
                    }
                    for value in inputs[:20]
                    if isinstance(value, dict)
                ]
                summary["input_source_count"] = len(inputs)
                summary["input_sources_truncated"] = len(inputs) > 20
            if isinstance(request_payload.get("forecast_horizon"), int):
                summary["forecast_horizon"] = request_payload["forecast_horizon"]
        return summary

    def _task_result_summary(self, task: MLTaskRow) -> dict[str, Any] | None:
        payload = task.result_payload
        if not isinstance(payload, dict):
            return None
        try:
            if task.task_type is MLTaskType.FIT:
                result = FitTaskResult.model_validate(payload)
                return self._training_result_summary(result, payload)
            if task.task_type is MLTaskType.HYPERPARAMETER_TUNING:
                result = HyperparameterTuningTaskResult.model_validate(payload)
                summary = self._training_result_summary(result, payload)
                summary["best_params"] = self._bounded_parameter_mapping(result.best_params)
                return summary
            if task.task_type is MLTaskType.EVALUATE:
                result = EvaluateTaskResult.model_validate(payload)
                return {
                    "trained_model_id": result.trained_model_id,
                    "model_key": result.model_key,
                    "evaluation_kind": result.evaluation_kind.value,
                    "evaluation": (
                        self._candidate_metrics_payload(result.evaluation)
                        if result.evaluation
                        else None
                    ),
                    "baseline_evaluation": (
                        self._candidate_metrics_payload(result.baseline_evaluation)
                        if result.baseline_evaluation
                        else None
                    ),
                    "comparison": (
                        result.comparison.model_dump(mode="json")
                        if result.comparison
                        else None
                    ),
                    "split_facts": (
                        result.split_facts.model_dump(mode="json")
                        if result.split_facts
                        else None
                    ),
                    "preparation_facts": (
                        result.preparation_facts.model_dump(mode="json")
                        if result.preparation_facts
                        else None
                    ),
                    "forecast_evaluation": (
                        self._forecast_evaluation_payload(result.forecast_evaluation)
                        if result.forecast_evaluation
                        else None
                    ),
                    "clustering_evaluation": (
                        self._clustering_evaluation_payload(
                            result.clustering_evaluation
                        )
                        if result.clustering_evaluation
                        else None
                    ),
                    "recommendation_evaluation": (
                        self._recommendation_evaluation_payload(
                            result.recommendation_evaluation
                        )
                        if result.recommendation_evaluation
                        else None
                    ),
                    "text_classification_evaluation": (
                        result.text_classification_evaluation.model_dump(mode="json")
                        if result.text_classification_evaluation
                        else None
                    ),
                    "text_clustering_evaluation": (
                        self._text_discovery_payload(result.text_clustering_evaluation)
                        if result.text_clustering_evaluation
                        else None
                    ),
                    "text_topic_evaluation": (
                        self._text_discovery_payload(result.text_topic_evaluation)
                        if result.text_topic_evaluation
                        else None
                    ),
                    "text_retrieval_evaluation": (
                        self._text_discovery_payload(result.text_retrieval_evaluation)
                        if result.text_retrieval_evaluation
                        else None
                    ),
                }
            if task.task_type is MLTaskType.APPLY:
                result = ApplyTaskResult.model_validate(payload)
                return {
                    "trained_model_id": result.trained_model_id,
                    "model_key": result.model_key,
                    "summary": result.summary.model_dump(mode="json"),
                    "source_dataset_ids": list(result.source_dataset_ids),
                    "source_artifact_ids": list(result.source_artifact_ids),
                    "result_dataset_id": payload.get("result_dataset_id"),
                    "text_classification_apply_facts": (
                        result.text_classification_apply_facts.model_dump(mode="json")
                        if result.text_classification_apply_facts
                        else None
                    ),
                    "text_clustering_apply_facts": (
                        self._text_discovery_payload(result.text_clustering_apply_facts)
                        if result.text_clustering_apply_facts
                        else None
                    ),
                    "text_topic_apply_facts": (
                        self._text_discovery_payload(result.text_topic_apply_facts)
                        if result.text_topic_apply_facts
                        else None
                    ),
                    "text_retrieval_apply_facts": (
                        self._text_discovery_payload(result.text_retrieval_apply_facts)
                        if result.text_retrieval_apply_facts
                        else None
                    ),
                }
        except PydanticValidationError:
            return {"contract_status": "stored_result_invalid"}
        return {"contract_status": "unsupported_task_type"}

    def _training_result_summary(
        self,
        result: FitTaskResult | HyperparameterTuningTaskResult,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "trained_model_id": payload.get("trained_model_id"),
            "model_key": result.model_key,
            "evaluation_kind": result.evaluation_kind.value,
            "split_facts": (
                result.split_facts.model_dump(mode="json") if result.split_facts else None
            ),
            "preparation_facts": (
                result.preparation_facts.model_dump(mode="json")
                if result.preparation_facts
                else None
            ),
            "recommendation_split_facts": (
                result.recommendation_split_facts.model_dump(mode="json")
                if result.recommendation_split_facts
                else None
            ),
            "recommendation_preparation_facts": (
                result.recommendation_preparation_facts.model_dump(mode="json")
                if result.recommendation_preparation_facts
                else None
            ),
            "text_preparation_specification": (
                result.text_preparation_specification.model_dump(mode="json")
                if result.text_preparation_specification
                else None
            ),
            "text_preparation_facts": (
                result.text_preparation_facts.model_dump(mode="json")
                if result.text_preparation_facts
                else None
            ),
            "text_leakage_facts": (
                result.text_leakage_facts.model_dump(mode="json")
                if result.text_leakage_facts
                else None
            ),
            "text_vectorization_facts": (
                result.text_vectorization_facts.model_dump(mode="json")
                if result.text_vectorization_facts
                else None
            ),
            "text_clustering_evaluation": (
                self._text_discovery_payload(result.text_clustering_evaluation)
                if result.text_clustering_evaluation
                else None
            ),
            "text_topic_evaluation": (
                self._text_discovery_payload(result.text_topic_evaluation)
                if result.text_topic_evaluation
                else None
            ),
            "text_retrieval_evaluation": (
                self._text_discovery_payload(result.text_retrieval_evaluation)
                if result.text_retrieval_evaluation
                else None
            ),
            "training_scope": {
                "evaluation_model": (
                    result.training_scopes.evaluation_model
                    if result.training_scopes
                    else (
                        "holdout_train_split"
                        if result.final_model_artifact_path
                        else None
                    )
                ),
                "apply_model": (
                    result.training_scopes.apply_model
                    if result.training_scopes
                    else (
                        "all_eligible_rows"
                        if result.final_model_artifact_path
                        else None
                    )
                ),
            },
            "result_dataset_id": payload.get("result_dataset_id"),
        }

    def _candidate_metrics_payload(self, metrics: CandidateMetrics) -> dict[str, Any]:
        ordered_metrics = sorted(metrics.metrics.items())
        details = metrics.details
        payload: dict[str, Any] = {
            "primary_metric_name": metrics.primary_metric_name,
            "primary_metric_value": metrics.primary_metric_value,
            "metrics": dict(ordered_metrics[:MAX_MODEL_METRICS]),
            "metric_count": len(ordered_metrics),
            "metrics_truncated": len(ordered_metrics) > MAX_MODEL_METRICS,
        }
        prediction_digest = details.get("prediction_digest")
        if isinstance(prediction_digest, str):
            payload["prediction_digest"] = prediction_digest
        probability_metrics = details.get("probability_metrics")
        if isinstance(probability_metrics, dict):
            payload["probability_metrics"] = {
                "available": probability_metrics.get("available"),
                "reason": self._bounded_status_message(probability_metrics.get("reason")),
            }
        return payload

    def _forecast_evaluation_payload(self, facts: Any) -> dict[str, Any]:
        """Project bounded temporal facts without group values or raw forecasts."""

        payload = facts.model_dump(mode="json")
        preparation = payload.get("preparation")
        if isinstance(preparation, dict):
            # Column names are already role-bound schema facts; group values never
            # enter this contract.
            payload["preparation"] = preparation
        return payload

    def _text_discovery_payload(self, facts: Any) -> dict[str, Any]:
        """Project typed bounded discovery facts without raw text or document ids."""

        payload = facts.model_dump(mode="json")
        limitations = payload.get("limitations")
        if isinstance(limitations, list):
            payload["limitations"] = [
                self._bounded_status_message(value) for value in limitations[:8]
            ]
        return payload

    def _clustering_evaluation_payload(self, facts: Any) -> dict[str, Any]:
        payload = facts.model_dump(mode="json")
        sizes = payload.get("sizes")
        if isinstance(sizes, list):
            payload["sizes"] = sizes[:24]
            payload["size_fact_count"] = len(sizes)
            payload["sizes_truncated"] = len(sizes) > 24
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            bounded_profiles: list[dict[str, Any]] = []
            for raw_profile in profiles[:12]:
                if not isinstance(raw_profile, dict):
                    continue
                profile = dict(raw_profile)
                for key in ("numeric", "categorical"):
                    values = profile.get(key)
                    if isinstance(values, list):
                        bounded_values = []
                        for raw_value in values[:12]:
                            if not isinstance(raw_value, dict):
                                continue
                            value = dict(raw_value)
                            if key == "categorical" and isinstance(
                                value.get("top_value"), str
                            ):
                                value["top_value"] = value["top_value"][:120]
                            bounded_values.append(value)
                        profile[key] = bounded_values
                bounded_profiles.append(profile)
            payload["profiles"] = bounded_profiles
            payload["profile_count"] = len(profiles)
            payload["profiles_truncated"] = len(profiles) > 12
        label_map = payload.get("label_map")
        if isinstance(label_map, dict) and isinstance(label_map.get("entries"), list):
            entries = label_map["entries"]
            label_map["entries"] = entries[:24]
            label_map["entry_count"] = len(entries)
            label_map["entries_truncated"] = len(entries) > 24
        limitations = payload.get("limitations")
        if isinstance(limitations, list):
            payload["limitations"] = [
                self._bounded_status_message(value) for value in limitations[:10]
            ]
        return payload

    def _recommendation_evaluation_payload(self, facts: Any) -> dict[str, Any]:
        """Project ranking evidence without held-out truth or user/item values."""

        payload = facts.model_dump(mode="json")
        limitations = payload.get("limitations")
        if isinstance(limitations, list):
            payload["limitations"] = [
                self._bounded_status_message(value) for value in limitations[:10]
            ]
        cold_start = payload.get("cold_start")
        if isinstance(cold_start, dict) and isinstance(
            cold_start.get("limitations"), list
        ):
            cold_start["limitations"] = [
                self._bounded_status_message(value)
                for value in cold_start["limitations"][:10]
            ]
        return payload

    def _model_command_summary(
        self,
        value: Any,
        *,
        parameter_field: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        parameters = value.get(parameter_field)
        parameter_names = sorted(str(key) for key in parameters) if isinstance(parameters, dict) else []
        return {
            "model_key": value.get("model_key"),
            "parameter_names": parameter_names[:32],
            "parameter_count": len(parameter_names),
            "parameters_truncated": len(parameter_names) > 32,
        }

    def _model_reference_summary(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {
            key: value[key]
            for key in ("trained_model_id", "model_key")
            if isinstance(value.get(key), str)
        }

    def _bounded_parameter_mapping(self, value: dict[str, Any]) -> dict[str, Any]:
        items = sorted(value.items())
        parameters = {
            str(key)[:MAX_MODEL_COLUMN_NAME_CHARS]: scalar
            for key, scalar in items[:32]
            if isinstance(scalar, str | int | float | bool) or scalar is None
        }
        return {
            "values": parameters,
            "parameter_count": len(items),
            "parameters_truncated": len(items) > 32,
        }

    def _bounded_role_bindings(self, value: list[Any]) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        for binding in value[:MAX_MODEL_ROLE_BINDINGS]:
            if not isinstance(binding, dict):
                continue
            columns = binding.get("columns")
            bounded_columns = (
                [
                    str(column)[:MAX_MODEL_COLUMN_NAME_CHARS]
                    for column in columns[:MAX_MODEL_ROLE_COLUMNS]
                ]
                if isinstance(columns, list)
                else []
            )
            column_count = len(columns) if isinstance(columns, list) else 0
            bindings.append(
                {
                    "role": str(binding.get("role") or "")[:MAX_MODEL_COLUMN_NAME_CHARS],
                    "columns": bounded_columns,
                    "column_count": column_count,
                    "columns_truncated": column_count > MAX_MODEL_ROLE_COLUMNS,
                }
            )
        return bindings

    def _bounded_status_message(self, value: Any) -> str | None:
        if value is None:
            return None
        message = str(value).replace(str(self._paths.home), "[app-home]")
        message = _LOCAL_PATH_PATTERN.sub("[local-path]", message)
        if len(message) > MAX_MODEL_TASK_LOG_CHARS:
            return message[: MAX_MODEL_TASK_LOG_CHARS - 1] + "…"
        return message

    def _model_key_from_task_payload(self, request_payload: dict[str, Any]) -> str | None:
        for key in ("manual_training", "hyperparameter_tuning", "evaluate_model", "apply_model"):
            value = request_payload.get(key)
            if isinstance(value, dict) and isinstance(value.get("model_key"), str):
                return cast(str, value["model_key"])
        return None

    def _follow_up_task_ids(self, task: MLTaskRow) -> list[str]:
        if task.task_type not in {MLTaskType.FIT, MLTaskType.HYPERPARAMETER_TUNING}:
            return []
        model = self._ml_service.get_trained_model_by_ml_task(task.id)
        if model is None:
            return []
        evaluation_task_id = self._evaluation_task_id_for_model(model)
        return [evaluation_task_id] if evaluation_task_id else []

    def _trained_model_payload(self, model: TrainedModelRow) -> dict[str, Any]:
        metadata = parse_trained_model_metadata(model.metadata_payload)
        payload: dict[str, Any] = {
            "trained_model_id": model.id,
            "dataset_id": model.dataset_id,
            "model_key": model.model_key,
        }
        if metadata is None:
            payload["metadata_contract_status"] = "unavailable"
            return payload
        payload.update(
            {
                "evaluation_kind": metadata.evaluation_kind,
                "model_family": metadata.model_family,
                "model_task_kind": metadata.model_task_kind,
                "supports_evaluation": metadata.supports_evaluation,
                "supports_apply": metadata.supports_apply,
                "apply_mode": metadata.apply_mode,
                "forecast_options": (
                    self._bounded_parameter_mapping(metadata.forecast_options)
                    if metadata.forecast_options
                    else None
                ),
                "train_role_bindings": self._bounded_role_bindings(
                    metadata.train_role_bindings
                ),
                "training_scope": {
                    "evaluation_model": metadata.evaluation_model_training_scope,
                    "apply_model": metadata.apply_model_training_scope,
                },
                "evaluation_task_id": metadata.evaluation_ml_task_id,
                "evaluation_facts_authority": metadata.evaluation_facts_authority,
            }
        )
        return payload

