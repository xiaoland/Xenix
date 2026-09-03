"""Model tool handlers: validate input, call MLService, return domain results."""

from __future__ import annotations

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
    ModelTaskStopInput,
    ModelTrainInput,
)
from ._model_keys import (
    model_catalog_payload,
    normalize_model_keys,
    normalize_model_mapping,
)
from ._tool_common import _raise_if_cancelled


# Synchronous wait window for ML fit/tune/apply. The tool blocks up to this
# window so fast tasks return results inline. When the window elapses the tool
# reports pending task status and recent logs instead of raising; the task keeps
# running in the background, so the LLM can stop it with model.task.stop or
# query it later with model.task.query.
MODEL_APPLY_GRACE_SECONDS = 30.0
MODEL_TRAIN_GRACE_SECONDS = 60.0
MODEL_HYPER_TRAIN_GRACE_SECONDS = 60.0
MODEL_TIMEOUT_LOG_ENTRIES = 20


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
            return self._in_progress_result(
                created_task_ids,
                message=(
                    "ML training is still running after "
                    f"{int(MODEL_TRAIN_GRACE_SECONDS)}s. The task keeps running in the "
                    "background; stop it with model.task.stop, or query it later with "
                    "model.task.query."
                ),
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
            return self._in_progress_result(
                created_task_ids,
                message=(
                    "ML hyperparameter tuning is still running after "
                    f"{int(MODEL_HYPER_TRAIN_GRACE_SECONDS)}s. The task keeps running in the "
                    "background; stop it with model.task.stop, or query it later with "
                    "model.task.query."
                ),
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
            return self._in_progress_result(
                [task.id],
                message=(
                    "ML apply is still running after "
                    f"{int(MODEL_APPLY_GRACE_SECONDS)}s. The task keeps running in the "
                    "background; stop it with model.task.stop, or query it later with "
                    "model.task.query."
                ),
            )
        return self._apply_completion(completed_task.id)

    def _apply_completion(self, task_id: str) -> ToolSuccess:
        details = self._ml_service.get_task_details(task_id)
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
                "ml_task_id": task_id,
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
                        [log.model_dump(mode="json") for log in details.logs]
                        if input_data.include_logs
                        else []
                    ),
                }
            )
        return ToolSuccess(value={"task_ids": input_data.task_ids, "tasks": tasks})

    def _model_task_stop(
        self,
        input_data: ModelTaskStopInput,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        stopped = []
        for task_id in input_data.task_ids:
            task = self._ml_service.cancel_task(task_id)
            stopped.append({"task_id": task_id, "status": task.status.value})
        return ToolSuccess(value={"task_ids": input_data.task_ids, "tasks": stopped})

    def _in_progress_result(self, task_ids: list[str], *, message: str) -> ToolSuccess:
        tasks = []
        for task_id in task_ids:
            details = self._ml_service.get_task_details(task_id)
            tasks.append(
                {
                    "task_id": task_id,
                    "status": details.task.status.value,
                    "logs": [
                        log.model_dump(mode="json")
                        for log in details.logs[-MODEL_TIMEOUT_LOG_ENTRIES:]
                    ],
                }
            )
        return ToolSuccess(
            value={
                "timed_out": True,
                "task_ids": task_ids,
                "tasks": tasks,
                "message": message,
            }
        )

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

