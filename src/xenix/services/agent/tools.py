"""Build domain-backed Tool registrations; invocation belongs to the LLM registry."""

from __future__ import annotations

from typing import Any


from ...config import AppPaths
from ..analysis_graph import AnalysisGraphService
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
from ..dataset_service import (
    DatasetService,
)
from ..ml_service import (
    MLService,
)
from ..preprocessing_worker import LocalPreprocessingWorkerRunner, PreprocessingWorkerRunner
from ..llm.tool_protocol import AgentTool
from .tool_inputs import (
    AnalysisGraphInput,
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
from ._model_keys import (
    build_model_key_aliases,
)

from ._analysis_tools import AnalysisTools
from ._data_tools import DataTools
from ._model_tools import ModelTools


def build_agent_tools(
    *,
    paths: AppPaths,
    dataset_service: DatasetService,
    data_cleaning_service: DataCleaningService,
    data_transform_service: DataQueryTransformService,
    ml_service: MLService,
    artifact_service: ArtifactService,
    preprocessing_worker_runner: PreprocessingWorkerRunner | None = None,
    data_tokenization_service: DataTokenizationService | None = None,
    analysis_profile_service: AnalysisProfileService | None = None,
    analysis_graph_service: AnalysisGraphService | None = None,
) -> list[AgentTool[Any]]:
    """Bind each Tool to its domain services without creating another dispatcher."""
    data_tokenization_service = data_tokenization_service or DataTokenizationService(paths)
    analysis_profile_service = analysis_profile_service or AnalysisProfileService(dataset_service)
    analysis_graph_service = analysis_graph_service or AnalysisGraphService(paths)
    preprocessing_worker_runner = preprocessing_worker_runner or LocalPreprocessingWorkerRunner()
    model_key_aliases = build_model_key_aliases()
    data_tools = DataTools(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=data_cleaning_service,
        data_tokenization_service=data_tokenization_service,
        data_transform_service=data_transform_service,
        ml_service=ml_service,
        preprocessing_worker_runner=preprocessing_worker_runner,
    )
    analysis_tools = AnalysisTools(
        dataset_service=dataset_service,
        artifact_service=artifact_service,
        analysis_profile_service=analysis_profile_service,
        analysis_graph_service=analysis_graph_service,
        ml_service=ml_service,
    )
    model_tools = ModelTools(
        paths=paths,
        dataset_service=dataset_service,
        artifact_service=artifact_service,
        ml_service=ml_service,
        model_key_aliases=model_key_aliases,
    )
    return [
        AgentTool(
            name="data.integrate",
            provider_name="data_integrate",
            description="Append rows from two or more Datasets into a derived Dataset.",
            input_model=DataIntegrateInput,
            implementation=data_tools._data_integrate,
        ),
        AgentTool(
            name="analysis.profile",
            provider_name="analysis_profile",
            description=(
                "Summarize Dataset structure, missing values, duplicates, numeric distributions and correlations."
            ),
            input_model=AnalysisProfileInput,
            implementation=analysis_tools._analysis_profile,
        ),
        AgentTool(
            name="analysis.graph",
            provider_name="analysis_graph",
            description=(
                "Render a chart or word cloud from a Dataset and return its image Artifact. Uses Vega-Lite JSON or term-frequency wordcloud_spec."
            ),
            input_model=AnalysisGraphInput,
            implementation=analysis_tools._analysis_graph,
        ),
        AgentTool(
            name="data.clean",
            provider_name="data_clean",
            description=(
                "Apply ordered cleaning operations to a new Dataset; returns its ID, public Artifact and change summary. Transforms the whole Dataset; learned model preprocessing belongs inside training."
            ),
            input_model=DataCleanInput,
            implementation=data_tools._data_clean,
        ),
        AgentTool(
            name="data.clean.metadata",
            provider_name="data_clean_metadata",
            description=("Describe data.clean operations and parameters, optionally filtered by group."),
            input_model=DataCleanMetadataInput,
            implementation=data_tools._data_clean_metadata,
            provider_field_enums=(("groups", cleaning_operation_group_names()),),
        ),
        AgentTool(
            name="data.tokenize",
            provider_name="data_tokenize",
            description=(
                "Tokenize text into a derived Dataset with optional stopwords and custom dictionaries. "
                "Raw-text models handle their own preparation."
            ),
            input_model=DataTokenizeInput,
            implementation=data_tools._data_tokenize,
        ),
        AgentTool(
            name="data.query",
            provider_name="data_query",
            description=(
                "Query Datasets with DuckDB SQL; returns a row-limited result without saving a Dataset. Cast string dates for date arithmetic."
            ),
            input_model=DataQueryToolInput,
            implementation=data_tools._data_query,
        ),
        AgentTool(
            name="data.transform",
            provider_name="data_transform",
            description=(
                "Save DuckDB SQL results as a derived Dataset and user-openable Artifact. Supports filters, joins, calculations and aggregates."
            ),
            input_model=DataTransformToolInput,
            implementation=data_tools._data_transform,
        ),
        AgentTool(
            name="data.feature.select",
            provider_name="data_feature_select",
            description=("Save Dataset column roles for model training; returns a binding ID."),
            input_model=DataFeatureSelectInput,
            implementation=data_tools._data_feature_select,
        ),
        AgentTool(
            name="model.metadata",
            provider_name="model_metadata",
            description=("Describe models, accepted column roles and parameters. Choose a model_key or model_family."),
            input_model=ModelMetadataInput,
            implementation=model_tools._model_metadata,
        ),
        AgentTool(
            name="model.train",
            provider_name="model_train",
            description=(
                "Train selected models and return saved model IDs, evaluation evidence and public Artifacts. Unfinished work returns task IDs."
            ),
            input_model=ModelTrainInput,
            implementation=model_tools._model_train,
        ),
        AgentTool(
            name="model.hyper_train",
            provider_name="model_hyper_train",
            description=(
                "Tune models over parameter grids; returns retained models, evaluation evidence and Artifacts, or task IDs while pending."
            ),
            input_model=ModelHyperTrainInput,
            implementation=model_tools._model_hyper_train,
        ),
        AgentTool(
            name="model.apply",
            provider_name="model_apply",
            description=(
                "Apply a saved model to Datasets, Artifacts or inline rows, or forecast a future horizon. Returns a result Dataset and Artifact, or pending task IDs."
            ),
            input_model=ModelApplyInput,
            implementation=model_tools._model_apply,
        ),
        AgentTool(
            name="model.task.query",
            provider_name="model_task_query",
            description=(
                "Read task status, summaries, errors and Artifact links, including follow-up evaluations. Logs and full diagnostics are optional."
            ),
            input_model=ModelTaskQueryInput,
            implementation=model_tools._model_task_query,
        ),
        AgentTool(
            name="model.task.stop",
            provider_name="model_task_stop",
            description=("Cancel the specified ML tasks."),
            input_model=ModelTaskStopInput,
            implementation=model_tools._model_task_stop,
        ),
    ]
