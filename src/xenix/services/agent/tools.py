from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import ValidationError as PydanticValidationError

from ...config import AppPaths
from ...exceptions import ValidationError
from ..analysis_graph import AnalysisGraphService
from ..analysis_lambda import AnalysisLambdaService
from ..analysis_profile import AnalysisProfileService
from ..artifact_service import (
    ArtifactService,
)
from ..data_cleaning import (
    DataCleaningService,
    cleaning_operation_group_names,
)
from ..data_tokenization import DataTokenizationService
from ..data_transform import (
    DataQueryTransformService,
)
from ..dataset_export_service import DatasetExportService
from ..dataset_service import (
    DatasetService,
)
from ..ml_service import (
    MLService,
)
from ..preprocessing_worker import LocalPreprocessingWorkerRunner, PreprocessingWorkerRunner
from ..llm.tooling import (
    AgentTool as TypedAgentTool,
    AgentToolRegistry as LLMToolRegistry,
    AgentToolSpec,
    ToolExecutionContext,
    ToolSuccess,
)
from .tool_inputs import (
    AgentToolInput,
    AnalysisGraphInput,
    AnalysisLambdaInput as AnalysisLambdaToolInput,
    AnalysisProfileInput,
    DataCleanInput,
    DataCleanMetadataInput,
    DataFeatureSelectInput,
    DataIntegrateInput,
    DataQueryInput as DataQueryToolInput,
    DataTokenizeInput,
    DataTransformInput as DataTransformToolInput,
    ModelApplyInput,
    ModelHyperTrainInput,
    ModelMetadataInput,
    ModelTaskQueryInput,
    ModelTrainInput,
)
from .tool_presentations import DEFAULT_TOOL_PRESENTATION, ToolPresentation, tool_presentation_for_name
from ._model_keys import (
    build_model_key_aliases,
)

from ._analysis_tools import AnalysisTools
from ._data_tools import DataTools
from ._model_tools import ModelTools
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


ToolInputT = TypeVar("ToolInputT", bound=AgentToolInput)
ToolHandler = Callable[[ToolInputT, ToolExecutionContext], ToolSuccess]


@dataclass(frozen=True)
class ConcreteAgentTool(Generic[ToolInputT]):
    registration: TypedAgentTool[ToolInputT]
    presentation: ToolPresentation = DEFAULT_TOOL_PRESENTATION

    @property
    def spec(self) -> AgentToolSpec:
        return self.registration.spec


def _index_agent_tools(
    tools: Iterable[ConcreteAgentTool[Any]],
) -> dict[str, ConcreteAgentTool[Any]]:
    """Build the concrete Tool index without permitting identity collisions."""

    indexed: dict[str, ConcreteAgentTool[Any]] = {}
    provider_name_owners: dict[str, str] = {}
    for tool in tools:
        tool_name = tool.spec.name
        if tool_name in indexed:
            raise ValidationError(f"Tool '{tool_name}' is already registered.")
        provider_name = tool.spec.provider_name
        owner = provider_name_owners.get(provider_name)
        if owner is not None:
            raise ValidationError(
                f"Provider tool name '{provider_name}' is already registered by '{owner}'."
            )
        indexed[tool_name] = tool
        provider_name_owners[provider_name] = tool_name
    return indexed


def _tool_input_error_message(exc: PydanticValidationError) -> str:
    error: dict[str, Any] = dict(next(iter(exc.errors(include_url=False)), {}))
    context = error.get("ctx")
    if isinstance(context, dict) and isinstance(context.get("error"), ValueError):
        return str(context["error"])
    location = error.get("loc")
    field_name = (
        str(location[0])
        if isinstance(location, tuple | list) and location
        else "Tool input"
    )
    message = str(error.get("msg") or "is invalid.")
    if field_name == "id_columns":
        return "data.tokenize id_columns must be a list of strings."
    if field_name == "text_column_index":
        return "data.tokenize text_column_index must be a zero-based integer."
    if field_name == "id_column_indexes":
        return "data.tokenize id_column_indexes must contain zero-based integers."
    return f"{field_name}: {message}"


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
        dataset_export_service: DatasetExportService | None = None,
        preprocessing_worker_runner: PreprocessingWorkerRunner | None = None,
        data_tokenization_service: DataTokenizationService | None = None,
        analysis_profile_service: AnalysisProfileService | None = None,
        analysis_graph_service: AnalysisGraphService | None = None,
        analysis_lambda_service: AnalysisLambdaService | None = None,
    ) -> None:
        data_tokenization_service = data_tokenization_service or DataTokenizationService(paths)
        analysis_profile_service = analysis_profile_service or AnalysisProfileService(dataset_service)
        analysis_graph_service = analysis_graph_service or AnalysisGraphService(paths)
        analysis_lambda_service = analysis_lambda_service or AnalysisLambdaService(paths)
        preprocessing_worker_runner = preprocessing_worker_runner or LocalPreprocessingWorkerRunner()
        model_key_aliases = build_model_key_aliases()
        self._data_tools = DataTools(
            paths=paths,
            dataset_service=dataset_service,
            data_cleaning_service=data_cleaning_service,
            data_tokenization_service=data_tokenization_service,
            data_transform_service=data_transform_service,
            ml_service=ml_service,
            preprocessing_worker_runner=preprocessing_worker_runner,
        )
        self._analysis_tools = AnalysisTools(
            dataset_service=dataset_service,
            artifact_service=artifact_service,
            analysis_profile_service=analysis_profile_service,
            analysis_graph_service=analysis_graph_service,
            analysis_lambda_service=analysis_lambda_service,
            ml_service=ml_service,
        )
        self._model_tools = ModelTools(
            paths=paths,
            dataset_service=dataset_service,
            artifact_service=artifact_service,
            ml_service=ml_service,
            model_key_aliases=model_key_aliases,
        )
        self._ml_service = ml_service
        _ = dataset_export_service
        self._tools = _index_agent_tools(
            (
                self._build_data_integrate_tool(),
                self._build_analysis_profile_tool(),
                self._build_analysis_graph_tool(),
                # analysis.lambda is intentionally retained in code but not registered
                # in the Agent-facing tool set.
                # self._build_analysis_lambda_tool(),
                self._build_data_clean_tool(),
                self._build_data_clean_metadata_tool(),
                self._build_data_tokenize_tool(),
                self._build_data_query_tool(),
                self._build_data_transform_tool(),
                self._build_data_feature_select_tool(),
                self._build_model_metadata_tool(),
                self._build_model_train_tool(),
                self._build_model_hyper_train_tool(),
                self._build_model_apply_tool(),
                self._build_model_task_query_tool(),
            )
        )

    def list_specs(self) -> list[AgentToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def register_with_llm(self, registry: LLMToolRegistry) -> None:
        """Inject concrete implementations into the LLM-owned registry.

        This class remains a composition-time factory for domain-backed
        handlers and UI presentation.  It is not a second dispatch authority.
        """

        for tool in self._tools.values():
            registry.register(tool.registration)

    def tool_presentation(self, tool_name: str) -> ToolPresentation:
        tool = self._tools.get(tool_name)
        if tool is None:
            return tool_presentation_for_name(tool_name)
        return tool.presentation

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        _raise_if_cancelled(self._ml_service, context)
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ValidationError(f"Tool '{tool_name}' is not registered.")
        try:
            input_data = tool.registration.input_model.model_validate(arguments)
        except PydanticValidationError as exc:
            raise ValidationError(_tool_input_error_message(exc)) from None
        result = tool.registration.implementation(input_data, context)
        _raise_if_cancelled(self._ml_service, context)
        if not isinstance(result, ToolSuccess):
            raise ValidationError("Concrete Agent Tool returned an unsupported outcome.")
        return result

    def _tool(
        self,
        *,
        name: str,
        provider_name: str,
        description: str,
        input_model: type[ToolInputT],
        handler: ToolHandler[ToolInputT],
        provider_field_enums: tuple[tuple[str, tuple[str, ...]], ...] = (),
    ) -> ConcreteAgentTool[ToolInputT]:
        return ConcreteAgentTool(
            registration=TypedAgentTool(
                name=name,
                provider_name=provider_name,
                description=description,
                input_model=input_model,
                implementation=handler,
                provider_field_enums=provider_field_enums,
            ),
            presentation=tool_presentation_for_name(name),
        )

    def _build_data_integrate_tool(self) -> ConcreteAgentTool[DataIntegrateInput]:
        return self._tool(
            name="data.integrate",
            provider_name="data_integrate",
            description="Combine two or more registered datasets into a generated derived dataset.",
            input_model=DataIntegrateInput,
            handler=self._data_tools._data_integrate,
        )

    def _build_analysis_graph_tool(self) -> ConcreteAgentTool[AnalysisGraphInput]:
        return self._tool(
            name="analysis.graph",
            provider_name="analysis_graph",
            description=(
                "Draw one bounded static SVG artifact for a registered dataset. Pass exactly one graph mode: "
                "`spec` for ordinary Vega-Lite charts, or `wordcloud_spec` for the dedicated word-cloud path. "
                "`wordcloud_spec` is the dedicated word-cloud path and expects an upstream chart-ready "
                "frequency table from data.query or data.transform."
            ),
            input_model=AnalysisGraphInput,
            handler=self._analysis_tools._analysis_graph,
        )

    def _build_analysis_profile_tool(self) -> ConcreteAgentTool[AnalysisProfileInput]:
        return self._tool(
            name="analysis.profile",
            provider_name="analysis_profile",
            description=(
                "Return typed, bounded quality facts for one registered Dataset with scope=whole_dataset. "
                "The read-only result includes ordered field structure, missingness, cardinality, bounded "
                "numeric/date summaries, correlations, and explicit truncation. It returns no sample rows, "
                "category/group values, identifier values, Dataset, or Artifact. Use one focused data.query "
                "only when a material business-role ambiguity remains after this profile."
            ),
            input_model=AnalysisProfileInput,
            handler=self._analysis_tools._analysis_profile,
        )

    def _build_analysis_lambda_tool(
        self,
    ) -> ConcreteAgentTool[AnalysisLambdaToolInput]:
        return self._tool(
            name="analysis.lambda",
            provider_name="analysis_lambda",
            description=(
                "Run a one-off Python analysis function over registered datasets. "
                "The code must define analyze(ctx, inputs, params) and return any JSON-serializable dict. "
                "inputs is a mapping from dataset alias to pandas DataFrame; inputs[alias].read() also returns "
                "that DataFrame. Supported imports: pandas/pd, numpy/np, matplotlib/plt, scipy, statsmodels, "
                "sklearn, xgboost, lightgbm, math, statistics, datetime, json, io, collections, itertools, "
                "functools, and typing. Do not import seaborn or arbitrary packages. Use ctx.artifact.create(...) "
                "for generated artifacts: ctx.artifact.create(name, content), ctx.artifact.create(content, name=...), "
                "or ctx.artifact.create(name=..., content=...); content may be a pandas DataFrame, SVG/text string, "
                "bytes/io.BytesIO, or matplotlib Figure. value=... is accepted as an alias for content=...."
            ),
            input_model=AnalysisLambdaToolInput,
            handler=self._analysis_tools._analysis_lambda,
        )

    def _build_data_clean_tool(self) -> ConcreteAgentTool[DataCleanInput]:
        return self._tool(
            name="data.clean",
            provider_name="data_clean",
            description=(
                "Create a new whole-Dataset derived dataset by applying atomic predefined business-cleaning "
                "operations to one registered dataset. Operations execute strictly left-to-right against the "
                "current intermediate dataset; each operation sees every earlier change. Use advertised "
                "validation operations for supported row checks or rejection, including non-negative, min/max, "
                "not-null, allowed-values, and regex rules. Use data.transform for a filter only when no atomic "
                "data.clean operation can express its predicate. Stateful imputation, encoding, and scaling here fit "
                "the whole Dataset and are not holdout-safe learned model preparation. Prefer zero-based "
                "column_index or column_indexes from analysis.profile; make one focused data.query only when "
                "exact values are materially required. Use data.clean.metadata only for unfamiliar operations "
                "or parameters. "
                "After missing.drop_high_missing_columns or encoding.one_hot, use names or a new "
                "data.query/data.clean call before using indexes."
            ),
            input_model=DataCleanInput,
            handler=self._data_tools._data_clean,
        )

    def _build_data_clean_metadata_tool(
        self,
    ) -> ConcreteAgentTool[DataCleanMetadataInput]:
        return self._tool(
            name="data.clean.metadata",
            provider_name="data_clean_metadata",
            description=(
                "Return a compact data.clean operation catalog. Request only relevant groups when an "
                "operation or parameter is uncertain."
            ),
            input_model=DataCleanMetadataInput,
            handler=self._data_tools._data_clean_metadata,
            provider_field_enums=(
                ("groups", cleaning_operation_group_names()),
            ),
        )

    def _build_data_tokenize_tool(self) -> ConcreteAgentTool[DataTokenizeInput]:
        return self._tool(
            name="data.tokenize",
            provider_name="data_tokenize",
            description=(
                "Create a derived token Dataset with legacy zh_business_v1 or retained "
                "multilingual_business_v1 preparation. The multilingual profile can use bounded "
                "registered one-column custom-dictionary/stopword Datasets. Use output=token_text to keep source rows and append "
                "token_text for downstream text models, or output=token_rows to explode one token per row. "
                "Select the text and optional identifier columns by names or zero-based source indexes; "
                "do not mix the two forms for one selector."
            ),
            input_model=DataTokenizeInput,
            handler=self._data_tools._data_tokenize,
        )

    def _build_data_query_tool(self) -> ConcreteAgentTool[DataQueryToolInput]:
        return self._tool(
            name="data.query",
            provider_name="data_query",
            description=(
                "Run a read-only SELECT/CTE query over registered datasets. "
                "Pass either dataset_id for one input aliased as input, or bindings for explicit SQL aliases. "
                "At least one input source is required. If both are present, bindings wins. "
                "When column_reference=indexes, each bound relation exposes zero-based c0, c1, ... SQL "
                "columns instead of source names; use this for punctuation-heavy or Unicode headers. "
                "During a cleaning pass, emit at most one data.query call per model response; batch related "
                "evidence in one compact query and wait for its result before any focused follow-up. "
                "Returns bounded rows and does not create a derived dataset or artifact."
            ),
            input_model=DataQueryToolInput,
            handler=self._data_tools._data_query,
        )

    def _build_data_transform_tool(
        self,
    ) -> ConcreteAgentTool[DataTransformToolInput]:
        return self._tool(
            name="data.transform",
            provider_name="data_transform",
            description=(
                "Create a new derived dataset from bounded DuckDB SQL over registered datasets. "
                "For cleaning filters, use an advertised atomic data.clean validation operation when it can "
                "express the rule; use data.transform only for unsupported predicates or for SQL-derived columns, "
                "joins, aggregates, reshaping, and grain changes. "
                "Use dataset_id for one input aliased as input, or bindings for explicit aliases. "
                "At least one input source is required. If both are present, bindings wins. "
                "When column_reference=indexes, each bound relation exposes zero-based c0, c1, ... SQL "
                "columns instead of source names; use this for punctuation-heavy or Unicode headers. "
                "For multi-statement scripts, create or leave a final TEMP relation named output; "
                "Xenix materializes SELECT * FROM output."
            ),
            input_model=DataTransformToolInput,
            handler=self._data_tools._data_transform,
        )

    def _build_data_feature_select_tool(
        self,
    ) -> ConcreteAgentTool[DataFeatureSelectInput]:
        return self._tool(
            name="data.feature.select",
            provider_name="data_feature_select",
            description=(
                "Bind registered dataset columns to semantic roles required by a model/analyzer. "
                "Prefer per-role zero-based column_indexes from data.query; Xenix resolves them against the "
                "current dataset schema and persists canonical names."
            ),
            input_model=DataFeatureSelectInput,
            handler=self._data_tools._data_feature_select,
        )

    def _build_model_metadata_tool(self) -> ConcreteAgentTool[ModelMetadataInput]:
        return self._tool(
            name="model.metadata",
            provider_name="model_metadata",
            description=(
                "Browse a lightweight model directory by model_family, or inspect one chosen model's role "
                "and parameter schema with model_key."
            ),
            input_model=ModelMetadataInput,
            handler=self._model_tools._model_metadata,
        )

    def _build_model_train_tool(self) -> ConcreteAgentTool[ModelTrainInput]:
        return self._tool(
            name="model.train",
            provider_name="model_train",
            description=(
                "Train and evaluate one or more models for a persisted dataset column role binding. "
                "Use model.metadata with model_family to browse candidates, then inspect one model_key for "
                "parameter detail."
            ),
            input_model=ModelTrainInput,
            handler=self._model_tools._model_train,
        )

    def _build_model_hyper_train_tool(
        self,
    ) -> ConcreteAgentTool[ModelHyperTrainInput]:
        return self._tool(
            name="model.hyper_train",
            provider_name="model_hyper_train",
            description=(
                "Run hyperparameter training for one or more models. "
                "Use model.metadata with model_family to browse candidates, then inspect one model_key with "
                "include_param_grid_schema=true."
            ),
            input_model=ModelHyperTrainInput,
            handler=self._model_tools._model_hyper_train,
        )

    def _build_model_apply_tool(self) -> ConcreteAgentTool[ModelApplyInput]:
        return self._tool(
            name="model.apply",
            provider_name="model_apply",
            description=(
                "Apply a retained model to registered dataset/artifact inputs or inline rows, "
                "or pass horizon alone to create a native future forecast."
            ),
            input_model=ModelApplyInput,
            handler=self._model_tools._model_apply,
        )

    def _build_model_task_query_tool(
        self,
    ) -> ConcreteAgentTool[ModelTaskQueryInput]:
        return self._tool(
            name="model.task.query",
            provider_name="model_task_query",
            description="Query ML task status, metadata, artifacts, errors, and logs by explicit task ids.",
            input_model=ModelTaskQueryInput,
            handler=self._model_tools._model_task_query,
        )
