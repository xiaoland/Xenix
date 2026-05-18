from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from ...config import AppPaths
from ...exceptions import ValidationError
from ..artifact_service import ArtifactService, RegisterArtifactInput, build_artifact_markdown_link
from ..data_cleaning import CleanDatasetInput, DataCleaningService
from ..data_transform import (
    DataQueryInput,
    DataQueryTransformService,
    DataTransformInput,
    DatasetSqlBinding,
)
from ..dataset_inspection import InspectDatasetInput, detect_source_format, load_dataframe
from ..dataset_service import DatasetService, RegisterDatasetInput
from ..ml.registry import get_model_catalog_entry, list_model_catalog, list_model_keys
from ..ml_service import FitWithEvaluateInput, InferWithFilesInput, MLService, TuneWithEvaluateInput
from ..storage.models import ArtifactKind, MLTaskArtifactKind, MLTaskStatus, ProblemKind, TrainedModelRow
from .providers import AgentToolSpec


_MODEL_ALIAS_SUFFIXES = {
    "classification",
    "classifier",
    "clustering",
    "regression",
    "regressor",
}
_MODEL_KEY_ALIAS_OVERRIDES = {
    "k_neighbors": "regression.knn",
    "kneighbors": "regression.knn",
    "k_neighbors_classifier": "classification.knn",
    "kneighborsclassifier": "classification.knn",
    "k_neighbors_regressor": "regression.knn",
    "kneighborsregressor": "regression.knn",
}


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
        dataset_service: DatasetService,
        data_cleaning_service: DataCleaningService,
        data_transform_service: DataQueryTransformService,
        ml_service: MLService,
        artifact_service: ArtifactService,
    ) -> None:
        self._paths = paths
        self._dataset_service = dataset_service
        self._data_cleaning_service = data_cleaning_service
        self._data_transform_service = data_transform_service
        self._ml_service = ml_service
        self._artifact_service = artifact_service
        self._model_key_aliases = self._build_model_key_aliases()
        self._tools = {
            tool.spec.name: tool
            for tool in (
                self._build_data_peek_tool(),
                self._build_data_integrate_tool(),
                self._build_data_clean_tool(),
                self._build_data_query_tool(),
                self._build_data_transform_tool(),
                self._build_data_feature_select_tool(),
                self._build_model_metadata_tool(),
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
                description=(
                    "Create a new derived dataset by applying atomic predefined cleaning operations "
                    "to one registered dataset."
                ),
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "name": {"type": "string"},
                        "drop_duplicates": {"type": "boolean"},
                        "duplicate_policy": {
                            "type": "object",
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "enum": ["none", "exact_rows", "key_columns"],
                                },
                                "columns": {"type": "array", "items": {"type": "string"}},
                                "keep": {"type": "string", "enum": ["first", "last", "false"]},
                            },
                            "additionalProperties": False,
                        },
                        "missing_policy": {
                            "type": "object",
                            "properties": {
                                "default_numeric": {
                                    "type": "string",
                                    "enum": ["none", "mean", "median", "mode", "constant", "forward_fill", "drop_rows"],
                                },
                                "default_text": {
                                    "type": "string",
                                    "enum": ["none", "mode", "constant", "forward_fill", "drop_rows"],
                                },
                                "fill_values": {"type": "object"},
                                "rules": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "columns": {"type": "array", "items": {"type": "string"}},
                                            "strategy": {
                                                "type": "string",
                                                "enum": [
                                                    "none",
                                                    "mean",
                                                    "median",
                                                    "mode",
                                                    "constant",
                                                    "forward_fill",
                                                    "drop_rows",
                                                ],
                                            },
                                            "value": {},
                                        },
                                        "required": ["columns", "strategy"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "additionalProperties": False,
                        },
                        "type_corrections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "target_type": {
                                        "type": "string",
                                        "enum": ["numeric", "integer", "datetime", "text", "boolean"],
                                    },
                                    "date_format": {"type": "string"},
                                },
                                "required": ["column", "target_type"],
                                "additionalProperties": False,
                            },
                        },
                        "text_standardization": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "columns": {"type": "array", "items": {"type": "string"}},
                                    "trim": {"type": "boolean"},
                                    "lowercase": {"type": "boolean"},
                                    "uppercase": {"type": "boolean"},
                                    "collapse_whitespace": {"type": "boolean"},
                                    "empty_to_null": {"type": "boolean"},
                                    "value_map": {"type": "object"},
                                },
                                "required": ["columns"],
                                "additionalProperties": False,
                            },
                        },
                        "validation_rules": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "column": {"type": "string"},
                                    "rule": {
                                        "type": "string",
                                        "enum": ["not_null", "non_negative", "min", "max", "allowed_values", "regex"],
                                    },
                                    "action": {"type": "string", "enum": ["report_only", "drop_rows"]},
                                    "value": {},
                                    "values": {"type": "array"},
                                },
                                "required": ["column", "rule"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["dataset_id"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_clean,
        )

    def _build_data_query_tool(self) -> AgentTool:
        binding_schema = {
            "type": "object",
            "properties": {
                "alias": {
                    "type": "string",
                    "description": "SQL table alias for this registered dataset, such as orders or customers.",
                },
                "dataset_id": {"type": "string"},
            },
            "required": ["alias", "dataset_id"],
            "additionalProperties": False,
        }
        return AgentTool(
            spec=AgentToolSpec(
                name="data.query",
                provider_name="data_query",
                description=(
                    "Run a read-only SELECT/CTE query over registered datasets. "
                    "Use dataset_id for one input aliased as input, or bindings for multiple inputs. "
                    "Returns bounded rows and does not create a dataset artifact."
                ),
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "bindings": {"type": "array", "items": binding_schema},
                        "sql": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_query,
        )

    def _build_data_transform_tool(self) -> AgentTool:
        binding_schema = {
            "type": "object",
            "properties": {
                "alias": {
                    "type": "string",
                    "description": "SQL table alias for this registered dataset, such as orders or customers.",
                },
                "dataset_id": {"type": "string"},
            },
            "required": ["alias", "dataset_id"],
            "additionalProperties": False,
        }
        return AgentTool(
            spec=AgentToolSpec(
                name="data.transform",
                provider_name="data_transform",
                description=(
                    "Create a new derived dataset artifact from a SELECT/CTE query over registered datasets. "
                    "Use dataset_id for one input aliased as input, or bindings for multiple inputs."
                ),
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "bindings": {"type": "array", "items": binding_schema},
                        "sql": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            ),
            handler=self._data_transform,
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

    def _build_model_metadata_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="model.metadata",
                provider_name="model_metadata",
                description=(
                    "List available model keys, capabilities, and optional parameter schemas. "
                    "Call this before model.train or model.hyper_train when model keys or parameters are unclear."
                ),
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "model_keys": {
                            "type": "array",
                            "items": {"type": "string", "enum": list_model_keys()},
                        },
                        "problem_kind": {
                            "type": "string",
                            "enum": [kind.value for kind in ProblemKind],
                        },
                        "capability": {
                            "type": "string",
                            "enum": ["fit", "hyperparameter_tuning"],
                        },
                        "include_param_schema": {"type": "boolean"},
                        "include_param_grid_schema": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            ),
            handler=self._model_metadata,
        )

    def _build_model_train_tool(self) -> AgentTool:
        return AgentTool(
            spec=AgentToolSpec(
                name="model.train",
                provider_name="model_train",
                description=(
                    "Train and evaluate one or more models for a dataset and explicit column selection. "
                    "Use model.metadata to inspect available canonical model keys and parameter schemas."
                ),
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
                description=(
                    "Run hyperparameter training for one or more models. "
                    "Use model.metadata with capability=hyperparameter_tuning to inspect supported models and grids."
                ),
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
        name = str(arguments.get("name") or source_path.stem)
        dataset = self._dataset_service.register_dataset(
            RegisterDatasetInput(
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
            context,
            output_path=output_path,
            name=name,
            summary="Integrated dataset created.",
        )

    def _data_clean(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        dataset = self._dataset_service.get_dataset(dataset_id)
        name = str(arguments.get("name") or f"{dataset.name} cleaned").strip() or f"{dataset.name} cleaned"
        clean_result = self._data_cleaning_service.clean_dataset(
            CleanDatasetInput(
                source_path=dataset.source_path,
                name=name,
                drop_duplicates=arguments.get("drop_duplicates"),
                duplicate_policy=arguments.get("duplicate_policy"),
                missing_policy=arguments.get("missing_policy"),
                type_corrections=arguments.get("type_corrections") or [],
                text_standardization=arguments.get("text_standardization") or [],
                validation_rules=arguments.get("validation_rules") or [],
            )
        )
        row_count_before = int(clean_result.report.get("row_count_before", 0))
        row_count_after = int(clean_result.report.get("row_count_after", 0))
        result = self._register_generated_dataset_result(
            context,
            output_path=Path(clean_result.output_path),
            name=name,
            summary=f"Cleaned dataset created. Rows: {row_count_before} -> {row_count_after}.",
            derived_from_dataset_id=dataset.id,
            metadata_payload={"cleaning_report": clean_result.report},
        )
        result.payload["row_count_before"] = row_count_before
        result.payload["row_count_after"] = row_count_after
        result.payload["cleaning_report"] = clean_result.report
        return result

    def _data_query(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        bindings = self._resolve_sql_bindings(arguments, tool_name="data.query")
        query_result = self._data_transform_service.query(
            DataQueryInput(
                bindings=bindings,
                sql=self._require_string(arguments, "sql"),
                limit=self._optional_integer(arguments, "limit", default=50),
            )
        )
        payload = query_result.model_dump(mode="json")
        payload["input_dataset_ids"] = [binding.dataset_id for binding in bindings]
        payload["bindings"] = [
            {"alias": binding.alias, "dataset_id": binding.dataset_id}
            for binding in bindings
        ]
        return ToolExecutionResult(
            payload=payload,
            content_blocks=[{"type": "markdown", "text": self._query_result_markdown(payload)}],
        )

    def _data_transform(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        bindings = self._resolve_sql_bindings(arguments, tool_name="data.transform")
        input_dataset_ids = [binding.dataset_id for binding in bindings]
        default_name = "Transformed dataset"
        if len(bindings) == 1:
            default_name = f"{self._dataset_service.get_dataset(bindings[0].dataset_id).name} transformed"
        name = str(arguments.get("name") or default_name).strip() or default_name
        transform_result = self._data_transform_service.transform(
            DataTransformInput(
                bindings=bindings,
                sql=self._require_string(arguments, "sql"),
                name=name,
            )
        )
        derived_from_dataset_id = input_dataset_ids[0] if len(set(input_dataset_ids)) == 1 else None
        result = self._register_generated_dataset_result(
            context,
            output_path=Path(transform_result.output_path),
            name=name,
            summary=f"Transformed dataset created. Rows: {transform_result.row_count}.",
            derived_from_dataset_id=derived_from_dataset_id,
            metadata_payload={
                "transform_report": transform_result.transform_report,
                "input_dataset_ids": input_dataset_ids,
            },
        )
        result.payload["row_count"] = transform_result.row_count
        result.payload["columns"] = transform_result.columns
        result.payload["transform_report"] = transform_result.transform_report
        result.payload["input_dataset_ids"] = input_dataset_ids
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

    def _model_metadata(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        raw_model_keys = self._optional_string_list(arguments, "model_keys")
        if raw_model_keys:
            model_keys = self._normalize_model_keys(raw_model_keys, field_name="model_keys")
            catalog_entries = [get_model_catalog_entry(model_key) for model_key in model_keys]
        else:
            catalog_entries = list_model_catalog()

        problem_kind = str(arguments.get("problem_kind") or "").strip()
        if problem_kind:
            try:
                selected_problem_kind = ProblemKind(problem_kind)
            except ValueError as exc:
                raise ValidationError(f"Unknown problem_kind '{problem_kind}'.") from exc
            catalog_entries = [
                entry for entry in catalog_entries if entry.problem_kind == selected_problem_kind
            ]

        capability = str(arguments.get("capability") or "").strip()
        if capability == "fit":
            catalog_entries = [entry for entry in catalog_entries if entry.supports_fit]
        elif capability == "hyperparameter_tuning":
            catalog_entries = [
                entry for entry in catalog_entries if entry.supports_hyperparameter_tuning
            ]
        elif capability:
            raise ValidationError(f"Unknown model capability '{capability}'.")

        catalog_entries = sorted(
            catalog_entries,
            key=lambda entry: (entry.problem_kind.value, entry.recommendation_tier, entry.model_key),
        )
        include_param_schema = bool(arguments.get("include_param_schema"))
        include_param_grid_schema = bool(arguments.get("include_param_grid_schema"))
        models = [
            self._model_catalog_payload(
                entry,
                include_param_schema=include_param_schema,
                include_param_grid_schema=include_param_grid_schema,
            )
            for entry in catalog_entries
        ]
        payload = {
            "model_keys": [model["model_key"] for model in models],
            "models": models,
        }
        return ToolExecutionResult(
            payload=payload,
            content_blocks=[{"type": "markdown", "text": self._model_metadata_markdown(models)}],
        )

    def _model_train(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        self._raise_if_cancelled(context)
        dataset_id = self._require_string(arguments, "dataset_id")
        feature_columns = self._require_string_list(arguments, "feature_columns")
        target_columns = self._optional_string_list(arguments, "target_columns")
        models = self._normalize_model_keys(
            self._require_string_list(arguments, "models"),
            field_name="models",
        )
        params_by_model = self._normalize_model_mapping(
            arguments.get("params_by_model"),
            field_name="params_by_model",
        )
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
        normalized_grids = self._normalize_model_mapping(
            grids,
            field_name="param_grids_by_model",
            require_hyperparameter_tuning=True,
        )
        before_ids = {task.id for task in self._ml_service.list_dataset_tasks(dataset_id)}
        created_task_ids: list[str] = []
        for model_key, grid in normalized_grids.items():
            self._raise_if_cancelled(context)
            created = self._ml_service.tune_with_evaluate(
                TuneWithEvaluateInput(
                    dataset_id=dataset_id,
                    feature_columns=feature_columns,
                    target_columns=target_columns,
                    run_name=str(arguments.get("run_name") or ""),
                    model_key=model_key,
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

    def _resolve_sql_bindings(self, arguments: dict[str, Any], *, tool_name: str) -> list[DatasetSqlBinding]:
        raw_bindings = arguments.get("bindings")
        raw_dataset_id = str(arguments.get("dataset_id") or "").strip()
        if raw_bindings:
            if raw_dataset_id:
                raise ValidationError(f"{tool_name} accepts dataset_id for one input or bindings for multiple inputs.")
            if not isinstance(raw_bindings, list):
                raise ValidationError(f"{tool_name} bindings must be a list.")
            bindings: list[DatasetSqlBinding] = []
            for raw_binding in raw_bindings:
                if not isinstance(raw_binding, dict):
                    raise ValidationError(f"{tool_name} bindings must contain objects.")
                alias = str(raw_binding.get("alias") or "").strip()
                dataset_id = str(raw_binding.get("dataset_id") or "").strip()
                if not alias or not dataset_id:
                    raise ValidationError(f"{tool_name} bindings require alias and dataset_id.")
                dataset = self._dataset_service.get_dataset(dataset_id)
                bindings.append(
                    DatasetSqlBinding(
                        alias=alias,
                        dataset_id=dataset.id,
                        source_path=dataset.source_path,
                    )
                )
            return bindings

        dataset_id = self._require_string(arguments, "dataset_id")
        dataset = self._dataset_service.get_dataset(dataset_id)
        return [
            DatasetSqlBinding(
                alias="input",
                dataset_id=dataset.id,
                source_path=dataset.source_path,
            )
        ]

    def _query_result_markdown(self, payload: dict[str, Any]) -> str:
        returned = int(payload.get("returned_row_count") or 0)
        limit = int(payload.get("limit") or 0)
        suffix = " (truncated)" if payload.get("truncated") else ""
        lines = [f"Query returned {returned} row(s) with limit {limit}{suffix}."]
        rows = payload.get("rows")
        columns = payload.get("columns")
        if not isinstance(rows, list) or not rows:
            return "\n".join(lines)
        if not isinstance(columns, list) or not columns:
            return "\n".join(lines)
        column_names = [str(column.get("name")) for column in columns if isinstance(column, dict)]
        preview_rows = rows[:10]
        lines.extend(
            [
                "",
                "| " + " | ".join(self._markdown_cell(column) for column in column_names) + " |",
                "| " + " | ".join("---" for _column in column_names) + " |",
            ]
        )
        for row in preview_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| "
                + " | ".join(self._markdown_cell(row.get(column)) for column in column_names)
                + " |"
            )
        return "\n".join(lines)

    def _markdown_cell(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\n", " ").replace("|", "\\|")

    def _register_generated_dataset_result(
        self,
        context: ToolExecutionContext,
        *,
        output_path: Path,
        name: str,
        summary: str,
        derived_from_dataset_id: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        dataset = self._dataset_service.register_dataset(
            RegisterDatasetInput(
                source_path=str(output_path.resolve()),
                name=name,
                derived_from_dataset_id=derived_from_dataset_id,
            )
        )
        inspection = self._dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
        artifact_metadata = dict(metadata_payload or {})
        if derived_from_dataset_id:
            artifact_metadata["derived_from_dataset_id"] = derived_from_dataset_id
        artifact = self._register_dataset_artifact(
            context,
            title=dataset.name,
            path=Path(dataset.source_path),
            dataset_id=dataset.id,
            preview_payload=inspection.model_dump(mode="json"),
            metadata_payload=artifact_metadata,
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

    def _model_catalog_payload(
        self,
        entry,
        *,
        include_param_schema: bool,
        include_param_grid_schema: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model_key": entry.model_key,
            "display_name": entry.display_name,
            "problem_kind": entry.problem_kind.value,
            "family": entry.family,
            "guidance": entry.guidance,
            "recommendation_tier": entry.recommendation_tier,
            "requires_target": entry.requires_target,
            "supports_fit": entry.supports_fit,
            "supports_hyperparameter_tuning": entry.supports_hyperparameter_tuning,
        }
        if include_param_schema:
            payload["param_schema"] = entry.param_schema
        if include_param_grid_schema:
            payload["param_grid_schema"] = entry.param_grid_schema
        return payload

    def _model_metadata_markdown(self, models: list[dict[str, Any]]) -> str:
        if not models:
            return "No models match the requested filters."
        lines = ["Available models:"]
        for model in models:
            capabilities = ["fit"] if model["supports_fit"] else []
            if model["supports_hyperparameter_tuning"]:
                capabilities.append("hyperparameter_tuning")
            lines.append(
                "- "
                f"`{model['model_key']}` ({model['display_name']}, {model['problem_kind']}); "
                f"capabilities: {', '.join(capabilities)}"
            )
        return "\n".join(lines)

    def _normalize_model_mapping(
        self,
        raw_mapping: Any,
        *,
        field_name: str,
        require_hyperparameter_tuning: bool = False,
    ) -> dict[str, Any]:
        if raw_mapping is None:
            return {}
        if not isinstance(raw_mapping, dict):
            raise ValidationError(f"{field_name} must be an object keyed by model key.")
        normalized: dict[str, Any] = {}
        failures: list[str] = []
        for raw_key, value in raw_mapping.items():
            model_key = self._canonical_model_key(str(raw_key))
            if model_key is None:
                failures.append(str(raw_key))
                continue
            if value is None:
                value = {}
            if not isinstance(value, dict):
                failures.append(f"{raw_key} must map to an object")
                continue
            if require_hyperparameter_tuning:
                catalog = get_model_catalog_entry(model_key)
                if not catalog.supports_hyperparameter_tuning:
                    failures.append(f"{raw_key} lacks hyperparameter_tuning support")
                    continue
            normalized[model_key] = value
        if failures:
            raise ValidationError(self._model_key_error_message(field_name, failures))
        return normalized

    def _normalize_model_keys(
        self,
        raw_keys: list[str],
        *,
        field_name: str,
        require_hyperparameter_tuning: bool = False,
    ) -> list[str]:
        normalized: list[str] = []
        failures: list[str] = []
        for raw_key in raw_keys:
            model_key = self._canonical_model_key(raw_key)
            if model_key is None:
                failures.append(raw_key)
                continue
            if require_hyperparameter_tuning:
                catalog = get_model_catalog_entry(model_key)
                if not catalog.supports_hyperparameter_tuning:
                    failures.append(f"{raw_key} lacks hyperparameter_tuning support")
                    continue
            if model_key not in normalized:
                normalized.append(model_key)
        if failures:
            raise ValidationError(self._model_key_error_message(field_name, failures))
        return normalized

    def _canonical_model_key(self, raw_key: str) -> str | None:
        value = raw_key.strip()
        available = set(list_model_keys())
        if value in available:
            return value
        lowered = value.lower()
        if lowered in available:
            return lowered
        for token in self._model_key_alias_tokens(value):
            aliased = self._model_key_aliases.get(token)
            if aliased in available:
                return aliased
        return None

    def _build_model_key_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        priorities: dict[str, int] = {}
        for entry in list_model_catalog():
            priority = self._model_alias_priority(entry.problem_kind)
            for token in self._model_entry_alias_tokens(entry):
                if priority < priorities.get(token, 100):
                    aliases[token] = entry.model_key
                    priorities[token] = priority
        aliases.update(_MODEL_KEY_ALIAS_OVERRIDES)
        return aliases

    def _model_entry_alias_tokens(self, entry) -> set[str]:
        leaf_key = entry.model_key.split(".", 1)[-1]
        values = {
            entry.model_key,
            entry.model_key.replace(".", "_"),
            leaf_key,
            entry.display_name,
            f"{entry.problem_kind.value}_{leaf_key}",
        }
        tokens: set[str] = set()
        for value in values:
            for token in self._model_key_alias_tokens(value):
                tokens.add(token)
                stripped = self._strip_model_alias_suffix(token)
                if stripped:
                    tokens.update(self._model_key_alias_tokens(stripped))
        return tokens

    def _model_alias_priority(self, problem_kind: ProblemKind) -> int:
        order = {
            ProblemKind.REGRESSION: 0,
            ProblemKind.CLASSIFICATION: 1,
            ProblemKind.CLUSTERING: 2,
            ProblemKind.ANOMALY_DETECTION: 3,
        }
        return order[problem_kind]

    def _model_key_alias_tokens(self, value: str) -> list[str]:
        token = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
        while "__" in token:
            token = token.replace("__", "_")
        if not token:
            return []
        compact = token.replace("_", "")
        return [token] if compact == token else [token, compact]

    def _strip_model_alias_suffix(self, token: str) -> str:
        parts = token.split("_")
        if len(parts) > 1 and parts[-1] in _MODEL_ALIAS_SUFFIXES:
            return "_".join(parts[:-1])
        return ""

    def _model_key_error_message(self, field_name: str, failures: list[str]) -> str:
        return (
            f"{field_name} contains unsupported model keys: {', '.join(failures)}. "
            "Call model.metadata to inspect available canonical model keys. "
            f"Available keys: {', '.join(list_model_keys())}."
        )

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

    def _optional_integer(self, arguments: dict[str, Any], key: str, *, default: int) -> int:
        value = arguments.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{key} must be an integer.") from exc

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "dataset"
