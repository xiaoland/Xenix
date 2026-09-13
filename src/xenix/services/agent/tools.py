from __future__ import annotations

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
    ModelTaskStopInput,
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
            raise ValidationError(f"Provider tool name '{provider_name}' is already registered by '{owner}'.")
        indexed[tool_name] = tool
        provider_name_owners[provider_name] = tool_name
    return indexed


def _tool_input_error_message(exc: PydanticValidationError) -> str:
    error: dict[str, Any] = dict(next(iter(exc.errors(include_url=False)), {}))
    context = error.get("ctx")
    if isinstance(context, dict) and isinstance(context.get("error"), ValueError):
        return str(context["error"])
    location = error.get("loc")
    field_name = str(location[0]) if isinstance(location, tuple | list) and location else "Tool input"
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
                self._build_model_task_stop_tool(),
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
            description="Append rows from two or more Datasets into a derived Dataset.",
            input_model=DataIntegrateInput,
            handler=self._data_tools._data_integrate,
        )

    def _build_analysis_graph_tool(self) -> ConcreteAgentTool[AnalysisGraphInput]:
        return self._tool(
            name="analysis.graph",
            provider_name="analysis_graph",
            description=(
                "Render a chart or word cloud from a Dataset and return its image Artifact. Uses Vega-Lite JSON or term-frequency wordcloud_spec."
            ),
            input_model=AnalysisGraphInput,
            handler=self._analysis_tools._analysis_graph,
        )

    def _build_analysis_profile_tool(self) -> ConcreteAgentTool[AnalysisProfileInput]:
        return self._tool(
            name="analysis.profile",
            provider_name="analysis_profile",
            description=(
                "Summarize Dataset structure, missing values, duplicates, numeric distributions and correlations."
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
                "Apply ordered cleaning operations to a new Dataset; returns its ID, public Artifact and change summary. Transforms the whole Dataset; learned model preprocessing belongs inside training."
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
            description=("Describe data.clean operations and parameters, optionally filtered by group."),
            input_model=DataCleanMetadataInput,
            handler=self._data_tools._data_clean_metadata,
            provider_field_enums=(("groups", cleaning_operation_group_names()),),
        )

    def _build_data_tokenize_tool(self) -> ConcreteAgentTool[DataTokenizeInput]:
        return self._tool(
            name="data.tokenize",
            provider_name="data_tokenize",
            description=(
                "Tokenize text into a derived Dataset with optional stopwords and custom dictionaries. "
                "Raw-text models handle their own preparation."
            ),
            input_model=DataTokenizeInput,
            handler=self._data_tools._data_tokenize,
        )

    def _build_data_query_tool(self) -> ConcreteAgentTool[DataQueryToolInput]:
        return self._tool(
            name="data.query",
            provider_name="data_query",
            description=(
                "Query Datasets with DuckDB SQL; returns a row-limited result without saving a Dataset. Cast string dates for date arithmetic."
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
                "Save DuckDB SQL results as a derived Dataset and user-openable Artifact. Supports filters, joins, calculations and aggregates."
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
            description=("Save Dataset column roles for model training; returns a binding ID."),
            input_model=DataFeatureSelectInput,
            handler=self._data_tools._data_feature_select,
        )

    def _build_model_metadata_tool(self) -> ConcreteAgentTool[ModelMetadataInput]:
        return self._tool(
            name="model.metadata",
            provider_name="model_metadata",
            description=("Describe models, accepted column roles and parameters. Choose a model_key or model_family."),
            input_model=ModelMetadataInput,
            handler=self._model_tools._model_metadata,
        )

    def _build_model_train_tool(self) -> ConcreteAgentTool[ModelTrainInput]:
        return self._tool(
            name="model.train",
            provider_name="model_train",
            description=(
                "Train selected models and return saved model IDs, evaluation evidence and public Artifacts. Unfinished work returns task IDs."
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
                "Tune models over parameter grids; returns retained models, evaluation evidence and Artifacts, or task IDs while pending."
            ),
            input_model=ModelHyperTrainInput,
            handler=self._model_tools._model_hyper_train,
        )

    def _build_model_apply_tool(self) -> ConcreteAgentTool[ModelApplyInput]:
        return self._tool(
            name="model.apply",
            provider_name="model_apply",
            description=(
                "Apply a saved model to Datasets, Artifacts or inline rows, or forecast a future horizon. Returns a result Dataset and Artifact, or pending task IDs."
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
            description=(
                "Read task status, summaries, errors and Artifact links, including follow-up evaluations. Logs and full diagnostics are optional."
            ),
            input_model=ModelTaskQueryInput,
            handler=self._model_tools._model_task_query,
        )

    def _build_model_task_stop_tool(
        self,
    ) -> ConcreteAgentTool[ModelTaskStopInput]:
        return self._tool(
            name="model.task.stop",
            provider_name="model_task_stop",
            description=("Cancel the specified ML tasks."),
            input_model=ModelTaskStopInput,
            handler=self._model_tools._model_task_stop,
        )
