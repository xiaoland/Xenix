"""Model tool handlers, ML task waiting, and summary projection."""

from __future__ import annotations

import re
from pathlib import Path


from ...exceptions import NotFoundError, ValidationError
from ..ml.registry import get_model_catalog_entry, list_model_catalog
from ..ml.contracts import (
    ApplyTaskResult,
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
)
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
        training_result = self._ml_service.wait_for_training_models(
            created_task_ids,
            cancel_requested=context.cancel_requested,
            timeout_seconds=MODEL_TRAIN_GRACE_SECONDS,
        )
        if training_result is None:
            raise ValidationError(
                "ML training did not complete in time. Query the tasks with model.task.query."
            )
        tasks, trained_models = training_result
        payload = {
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "trained_model_ids": [model.id for model in trained_models],
            "results": [task.result_payload for task in tasks],
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
        training_result = self._ml_service.wait_for_training_models(
            created_task_ids,
            cancel_requested=context.cancel_requested,
            timeout_seconds=MODEL_HYPER_TRAIN_GRACE_SECONDS,
        )
        if training_result is None:
            raise ValidationError(
                "ML hyperparameter tuning did not complete in time. Query the tasks with model.task.query."
            )
        tasks, trained_models = training_result
        payload = {
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "trained_model_ids": [model.id for model in trained_models],
            "results": [task.result_payload for task in tasks],
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
        completed_task = self._ml_service.wait_for_task(
            task.id,
            cancel_requested=context.cancel_requested,
            timeout_seconds=MODEL_APPLY_GRACE_SECONDS,
        )
        if completed_task is None:
            raise ValidationError(
                "ML apply did not complete in time. Query the task with model.task.query."
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
        typed_result = ApplyTaskResult.model_validate(details.task.result_payload or {})
        return ToolSuccess(
            value={
                "ml_task_id": task.id,
                "artifact_id": output_artifact.artifact_id,
                "result": typed_result.model_dump(mode="json"),
            },
        )

    def _model_task_query(
        self,
        input_data: ModelTaskQueryInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        tasks = []
        for task_id in input_data.task_ids:
            details = self._ml_service.get_task_details(task_id)
            tasks.append(
                {
                    "task": details.task.model_dump(mode="json"),
                    "artifacts": [artifact.model_dump(mode="json") for artifact in details.artifacts],
                    "logs": (
                        [log.model_dump(mode="json") for log in details.logs[: input_data.max_log_entries]]
                        if input_data.include_logs
                        else []
                    ),
                }
            )
        return ToolSuccess(value={"task_ids": input_data.task_ids, "tasks": tasks})

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





























