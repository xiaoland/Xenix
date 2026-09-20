"""Strict typed inputs for production Agent Tools.

These models are the authority for call validation.  Provider JSON Schema is a
portable projection produced by the LLM tooling boundary, never a separately
maintained contract.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints, model_validator

from ..analysis_profile import (
    DEFAULT_CORRELATION_COLUMN_LIMIT,
    DEFAULT_NUMERIC_SUMMARY_LIMIT,
    DEFAULT_PROFILE_FIELD_LIMIT,
    MAX_CORRELATION_COLUMN_LIMIT,
    MAX_NUMERIC_SUMMARY_LIMIT,
    MAX_PROFILE_FIELD_LIMIT,
)
from ..knowledge_service import MAX_KNOWLEDGE_QUERY_CHARS
from ..audit_contracts import ExplanationText


RequiredString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalString = Annotated[str, StringConstraints(strip_whitespace=True)]
NonNegativeInteger = Annotated[int, Field(ge=0)]


class AgentToolInput(BaseModel):
    """Closed, immutable, strict base for provider-authored Tool arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DataIntegrateInput(AgentToolInput):
    explanation: ExplanationText = Field(description="Explain the business purpose, important choices and limitations in the user's language. Saved with the output; interpret actual results afterwards with audit.explain.")
    dataset_ids: Annotated[list[PositiveInt], Field(min_length=2)]
    name: OptionalString | None = None


class WordCloudSpec(AgentToolInput):
    title: str | None = None
    word_field: str | None = Field(
        default=None,
        description="Term column; defaults to word.",
    )
    count_field: str | None = Field(
        default=None,
        description="Positive frequency column; defaults to count.",
    )
    top_n: Annotated[int, Field(ge=20, le=80)] | None = Field(
        default=None,
        description="Number of top terms; defaults to 80.",
    )
    width: Annotated[int, Field(ge=200, le=1600)] | None = Field(
        default=None,
        description="Width in pixels.",
    )
    height: Annotated[int, Field(ge=160, le=1200)] | None = Field(
        default=None,
        description="Height in pixels.",
    )
    prefer_horizontal: Annotated[float, Field(ge=0.8, le=1.0)] | None = Field(
        default=None,
        description="Horizontal term fraction; defaults to 0.85.",
    )
    font_size_range: Annotated[list[float], Field(min_length=2, max_length=2)] | None = Field(
        default=None,
        description="[min, max] font size; defaults to [12, 56], or [10, 42] for dense clouds.",
    )
    color_mode: Literal["rank_tier", "field"] | None = Field(
        default=None,
        description="rank_tier colors by frequency; field colors by an existing category column.",
    )
    color_field: str | None = Field(
        default=None,
        description="Category column required for field coloring.",
    )
    palette: list[str] | None = Field(
        default=None,
        description="Colors for rank tiers or categories.",
    )


class AnalysisGraphInput(AgentToolInput):
    explanation: ExplanationText = Field(description="Explain the business purpose, important choices and limitations in the user's language. Saved with the output; interpret actual results afterwards with audit.explain.")
    dataset_id: PositiveInt
    spec: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Vega-Lite JSON. Xenix supplies data; omit data and datasets."
        ),
    )
    wordcloud_spec: WordCloudSpec | None = Field(
        default=None,
        description=(
            "Word cloud from term-frequency columns, not raw sentences. Use exactly one of spec or wordcloud_spec."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_graph_mode(self) -> AnalysisGraphInput:
        if (self.spec is None) == (self.wordcloud_spec is None):
            raise ValueError("analysis.graph requires exactly one of spec or wordcloud_spec.")
        return self


class AnalysisProfileInput(AgentToolInput):
    dataset_id: PositiveInt
    field_limit: Annotated[int, Field(ge=1, le=MAX_PROFILE_FIELD_LIMIT)] = Field(
        default=DEFAULT_PROFILE_FIELD_LIMIT,
    )
    numeric_summary_limit: Annotated[
        int,
        Field(ge=1, le=MAX_NUMERIC_SUMMARY_LIMIT),
    ] = Field(
        default=DEFAULT_NUMERIC_SUMMARY_LIMIT,
        description="Excludes identifiers.",
    )
    correlation_column_limit: Annotated[
        int,
        Field(ge=2, le=MAX_CORRELATION_COLUMN_LIMIT),
    ] = Field(
        default=DEFAULT_CORRELATION_COLUMN_LIMIT,
        description="Numeric columns only.",
    )


class CleaningOperationInput(AgentToolInput):
    operation: RequiredString = Field(description="Operation name from data.clean.metadata.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Operation parameters for the current intermediate table. Select columns by names or indexes, not both."
        ),
    )


class DataCleanInput(AgentToolInput):
    explanation: ExplanationText = Field(description="Explain the business purpose, important choices and limitations in the user's language. Saved with the output; interpret actual results afterwards with audit.explain.")
    dataset_id: PositiveInt
    name: OptionalString | None = None
    operations: list[CleaningOperationInput] = Field(
        default_factory=list,
        description="Runs left-to-right on the preceding operation's result.",
    )


class DataCleanMetadataInput(AgentToolInput):
    groups: list[RequiredString] | None = None


class DataTokenizeInput(AgentToolInput):
    explanation: ExplanationText = Field(description="Explain the business purpose, important choices and limitations in the user's language. Saved with the output; interpret actual results afterwards with audit.explain.")
    dataset_id: PositiveInt
    name: OptionalString | None = None
    text_column: RequiredString | None = Field(
        default=None,
        description="Supply text_column or text_column_index, not both.",
    )
    text_column_index: NonNegativeInteger | None = Field(
        default=None,
        description="Zero-based source-column position.",
    )
    id_columns: list[RequiredString] | None = Field(
        default=None,
        description="Identifier columns kept in token_rows. Supply names or id_column_indexes, not both.",
    )
    id_column_indexes: list[NonNegativeInteger] | None = Field(
        default=None,
        description="Zero-based source-column positions for identifiers.",
    )
    output: Literal["token_text", "token_rows"] = Field(
        default="token_text",
        description="token_text appends segmented text to source rows; token_rows emits one token per row.",
    )
    tokenizer_profile: Literal["zh_business_v1", "multilingual_business_v1"] = Field(
        default="zh_business_v1",
        description="Chinese or multilingual preparation; only multilingual supports phrases and resource Datasets.",
    )
    phrase_mode: Literal["unigram", "unigram_bigram"] = "unigram"
    custom_dictionary_dataset_ids: Annotated[
        list[PositiveInt],
        Field(max_length=4),
    ] = Field(
        default_factory=list,
        description="One-column custom term Datasets.",
    )
    stopword_dataset_ids: Annotated[
        list[PositiveInt],
        Field(max_length=4),
    ] = Field(
        default_factory=list,
        description="One-column stopword Datasets.",
    )

    @model_validator(mode="after")
    def _selector_forms_do_not_overlap(self) -> DataTokenizeInput:
        if self.text_column is not None and self.text_column_index is not None:
            raise ValueError("data.tokenize accepts either text_column or text_column_index, not both.")
        if self.text_column is None and self.text_column_index is None:
            raise ValueError("data.tokenize requires text_column or text_column_index.")
        if self.id_columns is not None and self.id_column_indexes is not None:
            raise ValueError("data.tokenize accepts either id_columns or id_column_indexes, not both.")
        if len(set(self.custom_dictionary_dataset_ids)) != len(self.custom_dictionary_dataset_ids) or len(
            set(self.stopword_dataset_ids)
        ) != len(self.stopword_dataset_ids):
            raise ValueError("Text preparation Dataset references cannot contain duplicates.")
        if set(self.custom_dictionary_dataset_ids) & set(self.stopword_dataset_ids):
            raise ValueError("A Dataset cannot be both a custom dictionary and a stopword list.")
        if self.tokenizer_profile == "zh_business_v1" and (
            self.phrase_mode != "unigram" or self.custom_dictionary_dataset_ids or self.stopword_dataset_ids
        ):
            raise ValueError("The legacy zh_business_v1 profile does not accept phrase mode or text resources.")
        return self


class DataQueryInput(AgentToolInput):
    datasets: Annotated[dict[RequiredString, PositiveInt], Field(min_length=1)] = Field(
        description="SQL table aliases mapped to Dataset IDs.",
    )
    sql: RequiredString = Field(description="DuckDB SELECT or CTE.")
    column_reference: Literal["names", "indexes"] = Field(
        default="names",
        description="names uses source headers; indexes uses c0, c1, ... in source-column order.",
    )
    limit: Annotated[int, Field(ge=1, le=200)] = Field(
        default=50,
        description="Maximum returned rows.",
    )


class DataTransformInput(AgentToolInput):
    datasets: Annotated[dict[RequiredString, PositiveInt], Field(min_length=1)] = Field(
        description="SQL table aliases mapped to Dataset IDs.",
    )
    sql: RequiredString = Field(
        description="DuckDB script. Saves the final SELECT, or the TEMP relation named output if there is no final query."
    )
    column_reference: Literal["names", "indexes"] = Field(
        default="names",
        description="names uses source headers; indexes uses c0, c1, ... in source-column order.",
    )
    name: OptionalString | None = None
    explanation: ExplanationText = Field(description="Business rationale and important tradeoffs saved in the audit. Interpret actual results afterwards with audit.explain.")


class RoleBindingInput(AgentToolInput):
    role: RequiredString = Field(description="Model role, e.g. feature, target, text or group.")
    columns: list[RequiredString] | None = Field(
        default=None,
        description="Exact source-column names. Supply columns or column_indexes, not both.",
    )
    column_indexes: list[NonNegativeInteger] | None = Field(
        default=None,
        description="Zero-based source-column positions.",
    )


class DataFeatureSelectInput(AgentToolInput):
    dataset_id: PositiveInt
    model_key: RequiredString | None = Field(
        default=None,
        description="Model key for role validation.",
    )
    role_bindings: list[RoleBindingInput]


ModelFamilyValue = Literal[
    "supervised",
    "clustering",
    "anomaly_detection",
    "association_rules",
    "recommendation",
    "text_analysis",
    "forecasting",
]


class ModelMetadataInput(AgentToolInput):
    include_details: bool = Field(
        default=False,
        description="Include each family candidate's roles and parameter schema.",
    )
    model_key: RequiredString | None = Field(
        default=None,
        description="Single model key or alias; returns roles and parameter schema.",
    )
    model_family: ModelFamilyValue | None = None
    include_param_grid_schema: bool = Field(
        default=False,
        description="Include tuning-grid schemas and model details.",
    )

    @model_validator(mode="after")
    def _has_model_selector(self) -> ModelMetadataInput:
        if self.model_key is None and self.model_family is None:
            raise ValueError("model.metadata requires model_key or model_family.")
        return self


class ModelTrainInput(AgentToolInput):
    explanations_by_model: dict[str, ExplanationText] = Field(description="One business explanation per selected model key, explaining why this model and important parameters fit the goal. Interpret results afterwards with audit.explain.")
    binding_id: PositiveInt = Field(description="Role binding returned by data.feature.select.")
    models: Annotated[list[RequiredString], Field(min_length=1)] = Field(
        description=(
            "Distinct model keys sharing this binding. Multiple parameterizations of one key need separate calls."
        )
    )
    params_by_model: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Keys match models.",
    )
    run_name: OptionalString = ""


class ModelHyperTrainInput(AgentToolInput):
    explanations_by_model: dict[str, ExplanationText] = Field(description="One business explanation per selected model key, explaining why this model and important parameters fit the goal. Interpret results afterwards with audit.explain.")
    binding_id: PositiveInt = Field(description="Role binding returned by data.feature.select.")
    param_grids_by_model: Annotated[
        dict[str, dict[str, Any]],
        Field(min_length=1),
    ]
    run_name: OptionalString = ""


InlineCell = str | int | float | bool | None


class InlineApplyRowsInput(AgentToolInput):
    header_index_map: dict[str, NonNegativeInteger] = Field(
        description="Column name to zero-based position in each row."
    )
    data: list[list[InlineCell]] = Field(description="Rows in the mapped column order.")


class ModelApplyInput(AgentToolInput):
    explanation: ExplanationText = Field(description="Explain the business purpose, important choices and limitations in the user's language. Saved with the output; interpret actual results afterwards with audit.explain.")
    trained_model_id: PositiveInt
    input_sources: list[int | str] = Field(
        default_factory=list,
        description="Dataset IDs as integers or artifact://<artifact_id> URIs.",
    )
    input_rows: InlineApplyRowsInput | None = None
    horizon: Annotated[int, Field(ge=1, le=365)] | None = Field(
        default=None,
        description="Future periods for a forecasting model; omit input_sources and input_rows.",
    )

    @model_validator(mode="after")
    def _has_apply_input(self) -> ModelApplyInput:
        has_rows = bool(self.input_sources) or self.input_rows is not None
        has_horizon = self.horizon is not None
        if has_rows == has_horizon:
            raise ValueError(
                "model.apply requires exactly one input mode: input_sources/input_rows or a future horizon."
            )
        return self


class ModelTaskQueryInput(AgentToolInput):
    task_ids: Annotated[list[PositiveInt], Field(min_length=1, max_length=20)]
    include_logs: bool = False
    include_details: bool = Field(
        default=False,
        description="Full persisted requests/results and artifact records; summaries already include evaluations and links.",
    )


class ModelTaskStopInput(AgentToolInput):
    task_ids: Annotated[list[PositiveInt], Field(min_length=1, max_length=20)]


class KnowledgeLookupInput(AgentToolInput):
    query: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=MAX_KNOWLEDGE_QUERY_CHARS,
        ),
    ] = Field(description="Business question or search terms.")
    mode: Literal["auto", "keyword", "semantic", "hybrid"] = Field(
        default="auto",
        description="auto selects an available retrieval mode.",
    )


class AgentToolsActivateInput(AgentToolInput):
    names: Annotated[list[RequiredString], Field(min_length=1)] = Field(
        description="Tool names or namespaces; each selects itself and dot-separated descendants.",
    )


class AgentSkillActivateInput(AgentToolInput):
    name: RequiredString = Field(description="Skill name from the directory.")


class AgentSkillResourceInput(AgentToolInput):
    skill_name: RequiredString = Field(description="Active skill owning the resource.")
    path: RequiredString = Field(description="Path from the skill's resource index.")
