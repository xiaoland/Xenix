from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from ...config import AppPaths
from ...exceptions import NotFoundError, ValidationError
from ..artifact_service import ArtifactService, RegisterArtifactInput, build_artifact_markdown_link
from ..dataset_inspection import InspectDatasetInput, detect_source_format, load_dataframe
from ..dataset_service import DatasetService, RegisterDatasetInput
from ..ml.registry import get_model_catalog_entry
from ..ml_service import FitWithEvaluateInput, InferWithFilesInput, MLService, TuneWithEvaluateInput
from ..project_service import CreateProjectInput, ProjectService
from ..storage.models import ArtifactKind, MLTaskArtifactKind, MLTaskStatus, TrainedModelRow
from .providers import AgentToolSpec


@dataclass(frozen=True)
class ToolExecutionContext:
    thread_id: str
    turn_id: str
    tool_call_id: str
    attached_files: list[str]
    cancel_requested: Callable[[], bool] = lambda: False


class ToolExecutionResult(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    content_blocks: list[dict[str, Any]] = Field(default_factory=list)


ToolHandler = Callable[[dict[str, Any], ToolExecutionContext], ToolExecutionResult]


@dataclass(frozen=True)
class AgentTool:
    spec: AgentToolSpec
    handler: ToolHandler


class AgentToolRegistry:
    def __init__(
        self,
        *,
        paths: AppPaths,
        project_service: ProjectService,
        dataset_service: DatasetService,
        ml_service: MLService,
        artifact_service: ArtifactService,
    ) -> None:
        self._paths = paths
        self._project_service = project_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._artifact_service = artifact_service
        self._tools = {
            tool.spec.name: tool
            for tool in (
                self._build_data_peek_tool(),
                self._build_data_integrate_tool(),
                self._build_data_clean_tool(),
                self._build_data_feature_select_tool(),
                self._build_model_train_tool(),
                self._build_model_hyper_train_tool(),
                self._build_model_inference_tool(),
            )
        }

    def list_specs(self) -> list[AgentToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ValidationError(f"Tool '{tool_name}' is not registered.")
        result = tool.handler(arguments, context)
        self._raise_if_cancelled(context)
        return result

    def _build_data_peek_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="data.peek",
                provider_name="data_peek",
                description="Inspect a CSV/XLS/XLSX file and register it as a dataset artifact.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string"},
                        "project_id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            handler=self._data_peek,
        )

    def _build_data_integrate_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="data.integrate",
                provider_name="data_integrate",
                description="Combine one or more CSV/XLS/XLSX files into a registered dataset artifact.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "source_paths": {"type": "array", "items": {"type": "string"}},
                        "project_id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["source_paths"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_integrate,
        )

    def _build_data_clean_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="data.clean",
                provider_name="data_clean",
                description="Create a cleaned dataset by dropping duplicates and filling missing values.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "name": {"type": "string"},
                        "drop_duplicates": {"type": "boolean"},
                    },
                    "required": ["dataset_id"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_clean,
        )

    def _build_data_feature_select_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="data.feature.select",
                provider_name="data_feature_select",
                description="Validate and return a feature/target column selection for a dataset.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "feature_columns": {"type": "array", "items": {"type": "string"}},
                        "target_columns": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["dataset_id", "feature_columns"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_feature_select,
        )

    def _build_model_train_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="model.train",
                provider_name="model_train",
                description="Train and evaluate one or more models for a dataset and explicit column selection.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "feature_columns": {"type": "array", "items": {"type": "string"}},
                        "target_columns": {"type": "array", "items": {"type": "string"}},
                        "models": {"type": "array", "items": {"type": "string"}},
                        "params_by_model": {"type": "object"},
                        "run_name": {"type": "string"},
                    },
                    "required": ["dataset_id", "feature_columns", "models"],
                    "additionalProperties": False,
                },
            ),
            handler=self._model_train,
        )

    def _build_model_hyper_train_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="model.hyper_train",
                provider_name="model_hyper_train",
                description="Run hyperparameter training for one or more models.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "feature_columns": {"type": "array", "items": {"type": "string"}},
                        "target_columns": {"type": "array", "items": {"type": "string"}},
                        "param_grids_by_model": {"type": "object"},
                        "run_name": {"type": "string"},
                    },
                    "required": ["dataset_id", "feature_columns", "param_grids_by_model"],
                    "additionalProperties": False,
                },
            ),
            handler=self._model_hyper_train,
        )

    def _build_model_inference_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="model.inference",
                provider_name="model_inference",
                description="Run inference with a trained model and one or more input files.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "feature_columns": {"type": "array", "items": {"type": "string"}},
                        "trained_model_id": {"type": "string"},
                        "input_files": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["dataset_id", "feature_columns", "trained_model_id", "input_files"],
                    "additionalProperties": False,
                },
            ),
            handler=self._model_inference,
        )

    def _data_peek(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        source_path = self._resolve_source_path(arguments.get("source_path"), context)
        project_id = self._resolve_project_id(arguments.get("project_id"))
        name = str(arguments.get("name") or source_path.stem)
        dataset = self._dataset_service.register_dataset(
            RegisterDatasetInput(
                project_id=project_id,
                source_path=str(source_path),
                name=name,
            )
        )
        inspection = self._dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=dataset.source_path)
        )
        artifact = self._register_dataset_artifact(
            context,
            title=dataset.name,
            path=Path(dataset.source_path),
            dataset_id=dataset.id,
            preview_payload=inspection.model_dump(mode="json"),
        )
        link = build_artifact_markdown_link(artifact)
        return ToolExecutionResult(
            payload={
                "dataset_id": dataset.id,
                "artifact_id": artifact.id,
                "artifact_link": link,
                "inspection": inspection.model_dump(mode="json"),
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": (
                        f"Dataset `{dataset.name}` is ready: {link}\n\n"
                        f"Rows: {inspection.row_count}; columns: {', '.join(inspection.preview_columns)}"
                    ),
                }
            ],
        )

    def _data_integrate(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        raw_paths = arguments.get("source_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValidationError("data.integrate requires at least one source path.")
        frames = [self._load_frame(Path(str(path)).expanduser().resolve()) for path in raw_paths]
        output_dir = self._paths.artifacts / "datasets" / "integrated"
        output_dir.mkdir(parents=True, exist_ok=True)
        name = str(arguments.get("name") or "Integrated dataset").strip() or "Integrated dataset"
        output_path = output_dir / f"{self._slug(name)}-{int(time.time())}.csv"
        pd.concat(frames, ignore_index=True).to_csv(output_path, index=False)
        return self._register_generated_dataset_result(
            arguments,
            context,
            output_path=output_path,
            name=name,
            summary="Integrated dataset created.",
        )

    def _data_clean(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        dataset = self._dataset_service.get_dataset(dataset_id)
        frame = self._load_frame(Path(dataset.source_path))
        before_rows = int(len(frame.index))
        if bool(arguments.get("drop_duplicates", True)):
            frame = frame.drop_duplicates()
        for column in frame.columns:
            if frame[column].isna().any():
                if pd.api.types.is_numeric_dtype(frame[column]):
                    frame[column] = frame[column].fillna(frame[column].median())
                else:
                    mode = frame[column].dropna().mode()
                    frame[column] = frame[column].fillna("" if mode.empty else mode.iloc[0])
        output_dir = self._paths.artifacts / "datasets" / "cleaned"
        output_dir.mkdir(parents=True, exist_ok=True)
        name = str(arguments.get("name") or f"{dataset.name} cleaned").strip() or f"{dataset.name} cleaned"
        output_path = output_dir / f"{self._slug(name)}-{int(time.time())}.csv"
        frame.to_csv(output_path, index=False)
        result = self._register_generated_dataset_result(
            arguments,
            context,
            output_path=output_path,
            name=name,
            summary=f"Cleaned dataset created. Rows: {before_rows} -> {len(frame.index)}.",
            parent_dataset_id=dataset.id,
        )
        result.payload["row_count_before"] = before_rows
        result.payload["row_count_after"] = int(len(frame.index))
        return result

    def _data_feature_select(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        feature_columns = self._require_string_list(arguments, "feature_columns")
        target_columns = self._optional_string_list(arguments, "target_columns")
        dataset = self._dataset_service.get_dataset(dataset_id)
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        available = {column.name for column in inspection.columns}
        if not set(feature_columns).issubset(available) or not set(target_columns).issubset(available):
            raise ValidationError("Selected columns must exist in the dataset.")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")
        return ToolExecutionResult(
            payload={
                "dataset_id": dataset_id,
                "feature_columns": feature_columns,
                "target_columns": target_columns,
            },
            content_blocks=[
                {
                    "type": "markdown",
                    "text": (
                        f"Selected features: {', '.join(feature_columns)}\n\n"
                        f"Selected targets: {', '.join(target_columns) if target_columns else 'none'}"
                    ),
                }
            ],
        )

    def _model_train(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        feature_columns = self._require_string_list(arguments, "feature_columns")
        target_columns = self._optional_string_list(arguments, "target_columns")
        models = self._require_string_list(arguments, "models")
        params_by_model = arguments.get("params_by_model") if isinstance(arguments.get("params_by_model"), dict) else {}
        before_ids = {task.id for task in self._ml_service.list_dataset_tasks(dataset_id)}
        created_task_ids: list[str] = []
        for model_key in models:
            self._raise_if_cancelled(context)
            created = self._ml_service.fit_with_evaluate(
                FitWithEvaluateInput(
                    dataset_id=dataset_id,
                    feature_columns=feature_columns,
                    target_columns=target_columns,
                    run_name=str(arguments.get("run_name") or ""),
                    model_key=model_key,
                    params=dict(params_by_model.get(model_key) or {}),
                )
            )
            created_task_ids.append(created.id)
        tasks = self._wait_for_new_dataset_tasks(dataset_id, before_ids, created_task_ids, context=context)
        trained_models = self._ml_service.list_dataset_trained_models(dataset_id)
        payload = {
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "trained_models": [self._trained_model_payload(model) for model in trained_models],
        }
        return ToolExecutionResult(
            payload=payload,
            content_blocks=[{"type": "markdown", "text": self._training_summary_markdown(payload)}],
        )

    def _model_hyper_train(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        feature_columns = self._require_string_list(arguments, "feature_columns")
        target_columns = self._optional_string_list(arguments, "target_columns")
        grids = arguments.get("param_grids_by_model")
        if not isinstance(grids, dict) or not grids:
            raise ValidationError("model.hyper_train requires param_grids_by_model.")
        before_ids = {task.id for task in self._ml_service.list_dataset_tasks(dataset_id)}
        created_task_ids: list[str] = []
        for model_key, grid in grids.items():
            self._raise_if_cancelled(context)
            created = self._ml_service.tune_with_evaluate(
                TuneWithEvaluateInput(
                    dataset_id=dataset_id,
                    feature_columns=feature_columns,
                    target_columns=target_columns,
                    run_name=str(arguments.get("run_name") or ""),
                    model_key=str(model_key),
                    param_grid=dict(grid),
                )
            )
            created_task_ids.append(created.id)
        tasks = self._wait_for_new_dataset_tasks(dataset_id, before_ids, created_task_ids, context=context)
        trained_models = self._ml_service.list_dataset_trained_models(dataset_id)
        payload = {
            "dataset_id": dataset_id,
            "task_ids": [task.id for task in tasks],
            "trained_models": [self._trained_model_payload(model) for model in trained_models],
        }
        return ToolExecutionResult(
            payload=payload,
            content_blocks=[{"type": "markdown", "text": self._training_summary_markdown(payload)}],
        )

    def _model_inference(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        feature_columns = self._require_string_list(arguments, "feature_columns")
        trained_model_id = self._require_string(arguments, "trained_model_id")
        input_files = self._require_string_list(arguments, "input_files")
        task = self._ml_service.infer(
            InferWithFilesInput(
                dataset_id=dataset_id,
                feature_columns=feature_columns,
                trained_model_id=trained_model_id,
                input_files=input_files,
            )
        )
        task = self._wait_for_task(task.id, context=context)
        details = self._ml_service.get_task_details(task.id)
        output_artifact = next(
            artifact
            for artifact in details.artifacts
            if artifact.artifact_kind is MLTaskArtifactKind.INFERENCE_RESULT
        )
        generic_artifact = self._artifact_service.register_artifact(
            RegisterArtifactInput(
                thread_id=context.thread_id,
                turn_id=context.turn_id,
                tool_call_id=context.tool_call_id,
                kind=ArtifactKind.PREDICTION,
                title="Prediction results",
                absolute_path=output_artifact.absolute_path,
                mime_type="text/csv",
                metadata_payload={"ml_task_id": task.id, "dataset_id": dataset_id},
            )
        )
        link = build_artifact_markdown_link(generic_artifact)
        return ToolExecutionResult(
            payload={
                "ml_task_id": task.id,
                "result_dataset_id": details.task.result_payload.get("result_dataset_id") if details.task.result_payload else None,
                "artifact_id": generic_artifact.id,
                "artifact_link": link,
                "row_count": details.task.result_payload.get("row_count") if details.task.result_payload else None,
            },
            content_blocks=[{"type": "markdown", "text": f"Prediction results are ready: {link}"}],
        )

    def _register_generated_dataset_result(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
        *,
        output_path: Path,
        name: str,
        summary: str,
        parent_dataset_id: str | None = None,
    ) -> ToolExecutionResult:
        project_id = self._resolve_project_id(arguments.get("project_id"))
        dataset = self._dataset_service.register_dataset(
            RegisterDatasetInput(
                project_id=project_id,
                source_path=str(output_path.resolve()),
                name=name,
            )
        )
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        artifact = self._register_dataset_artifact(
            context,
            title=dataset.name,
            path=Path(dataset.source_path),
            dataset_id=dataset.id,
            preview_payload=inspection.model_dump(mode="json"),
            metadata_payload={"parent_dataset_id": parent_dataset_id} if parent_dataset_id else {},
        )
        link = build_artifact_markdown_link(artifact)
        return ToolExecutionResult(
            payload={
                "dataset_id": dataset.id,
                "artifact_id": artifact.id,
                "artifact_link": link,
                "inspection": inspection.model_dump(mode="json"),
            },
            content_blocks=[{"type": "markdown", "text": f"{summary} {link}"}],
        )

    def _register_dataset_artifact(
        self,
        context: ToolExecutionContext,
        *,
        title: str,
        path: Path,
        dataset_id: str,
        preview_payload: dict[str, Any],
        metadata_payload: dict[str, Any] | None = None,
    ):
        return self._artifact_service.register_artifact(
            RegisterArtifactInput(
                thread_id=context.thread_id,
                turn_id=context.turn_id,
                tool_call_id=context.tool_call_id,
                kind=ArtifactKind.DATASET,
                title=title,
                absolute_path=str(path.resolve()),
                mime_type="text/csv" if path.suffix.lower() == ".csv" else None,
                preview_payload=preview_payload,
                metadata_payload={"dataset_id": dataset_id, **(metadata_payload or {})},
            )
        )

    def _resolve_source_path(self, raw_path: Any, context: ToolExecutionContext) -> Path:
        value = str(raw_path or "").strip()
        if not value and context.attached_files:
            value = context.attached_files[0]
        if not value:
            raise ValidationError("A source path is required.")
        path = Path(value).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ValidationError("Source path must point to an existing file.")
        return path

    def _resolve_project_id(self, raw_project_id: Any) -> str:
        project_id = str(raw_project_id or "").strip()
        if project_id:
            return self._project_service.get_project(project_id).id
        projects = self._project_service.list_projects()
        if projects:
            return projects[0].id
        return self._project_service.create_project(CreateProjectInput(name="Agent Analysis")).id

    def _load_frame(self, path: Path) -> pd.DataFrame:
        source_format = detect_source_format(path)
        if source_format.value == "unknown":
            raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")
        return load_dataframe(path, source_format)

    def _wait_for_new_dataset_tasks(
        self,
        dataset_id: str,
        before_ids: set[str],
        created_task_ids: list[str],
        *,
        context: ToolExecutionContext,
        timeout_seconds: float = 120.0,
    ) -> list:
        expected_count = 0
        for task_id in created_task_ids:
            details = self._ml_service.get_task_details(task_id)
            catalog = get_model_catalog_entry(details.task.request_payload.get("manual_training", {}).get("model_key") or details.task.request_payload.get("hyperparameter_tuning", {}).get("model_key"))
            expected_count += 2 if catalog.requires_target else 1
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            self._raise_if_cancelled(context, ml_task_ids=created_task_ids)
            new_tasks = [task for task in self._ml_service.list_dataset_tasks(dataset_id) if task.id not in before_ids]
            if len(new_tasks) >= expected_count and all(task.status in self._terminal_statuses() for task in new_tasks):
                failed = [task for task in new_tasks if task.status is not MLTaskStatus.SUCCEEDED]
                if failed:
                    raise ValidationError(f"ML task '{failed[0].id}' finished with status '{failed[0].status.value}'.")
                return new_tasks
            time.sleep(0.1)
        raise ValidationError("Timed out waiting for ML training tasks.")

    def _wait_for_task(self, task_id: str, *, context: ToolExecutionContext, timeout_seconds: float = 120.0):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            self._raise_if_cancelled(context, ml_task_ids=[task_id])
            task = self._ml_service.get_task_details(task_id).task
            if task.status in self._terminal_statuses():
                if task.status is not MLTaskStatus.SUCCEEDED:
                    raise ValidationError(f"ML task '{task.id}' finished with status '{task.status.value}'.")
                return task
            time.sleep(0.1)
        raise ValidationError(f"Timed out waiting for ML task '{task_id}'.")

    def _raise_if_cancelled(self, context: ToolExecutionContext, *, ml_task_ids: list[str] | None = None) -> None:
        if not context.cancel_requested():
            return
        if ml_task_ids:
            for task_id in ml_task_ids:
                try:
                    self._ml_service.cancel_task(task_id)
                except Exception:
                    continue
        raise ValidationError("Agent run was cancelled.")

    def _terminal_statuses(self) -> set[MLTaskStatus]:
        return {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}

    def _trained_model_payload(self, model: TrainedModelRow) -> dict[str, Any]:
        return {
            "trained_model_id": model.id,
            "dataset_id": model.dataset_id,
            "model_key": model.model_key,
            "artifact_path": model.artifact_path,
            "metadata": dict(model.metadata_payload),
        }

    def _training_summary_markdown(self, payload: dict[str, Any]) -> str:
        models = payload.get("trained_models", [])
        lines = ["Training completed."]
        for model in models:
            lines.append(f"- `{model['model_key']}` trained model id: `{model['trained_model_id']}`")
        return "\n".join(lines)

    def _require_string(self, arguments: dict[str, Any], key: str) -> str:
        value = str(arguments.get(key) or "").strip()
        if not value:
            raise ValidationError(f"{key} is required.")
        return value

    def _require_string_list(self, arguments: dict[str, Any], key: str) -> list[str]:
        values = arguments.get(key)
        if not isinstance(values, list):
            raise ValidationError(f"{key} must be a list.")
        normalized = [str(value).strip() for value in values if str(value).strip()]
        if not normalized:
            raise ValidationError(f"{key} cannot be empty.")
        return normalized

    def _optional_string_list(self, arguments: dict[str, Any], key: str) -> list[str]:
        values = arguments.get(key)
        if values is None:
            return []
        if not isinstance(values, list):
            raise ValidationError(f"{key} must be a list.")
        return [str(value).strip() for value in values if str(value).strip()]

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "dataset"
