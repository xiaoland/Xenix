from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..data_tokenization_contracts import TextPreparationInput
from ..trained_model_metadata import TrainedModelContextPayload
from .clustering_evidence import ClusteringEvaluationFacts
from .recommendation_evidence import (
    RecommendationEvaluationFacts,
    RecommendationPreparationFacts,
    RecommendationSplitFacts,
)
from .text_preparation import (
    TextClassificationApplyFacts,
    TextClassificationEvaluationFacts,
    TextLeakageFacts,
    TextPreparationQualityFacts,
    TextPreparationSpecification,
    TextVectorizationFacts,
)
from .text_discovery import (
    TextClusteringApplyFacts,
    TextClusteringEvaluationFacts,
    TextRetrievalApplyFacts,
    TextRetrievalEvaluationFacts,
    TextTopicApplyFacts,
    TextTopicEvaluationFacts,
)
from .types import EvaluationKind


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetricDirection(StrEnum):
    MAX = "max"
    MIN = "min"


class EvaluationVerdict(StrEnum):
    CANDIDATE_BETTER = "candidate_better"
    BASELINE_BETTER = "baseline_better"
    TIED = "tied"


class TaskContinuationPlan(BaseModel):
    next_operation: str


class ColumnSelection(BaseModel):
    feature_columns: list[str]
    target_columns: list[str]


class DatasetSnapshotFact(BaseModel):
    schema_version: int = 1
    dataset_id: str
    source_sha256: str
    source_byte_size: int
    schema_digest: str


def _role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            raw_columns = binding.get("columns")
            if isinstance(raw_columns, list):
                return [str(column) for column in raw_columns]
    return []


class EvaluationPolicySnapshot(BaseModel):
    policy_key: str
    evaluation_kind: EvaluationKind
    primary_metric_name: str
    primary_metric_direction: MetricDirection
    tie_breaker_metrics: list[str]
    split_strategy: str
    test_size: float
    cv_folds: int | None = None
    random_state: int


class ForecastOptions(BaseModel):
    """Comparable temporal evidence shared by every forecast model task."""

    model_config = ConfigDict(extra="ignore")

    horizon: int = Field(default=4, ge=1, le=365)
    seasonal_period: int = Field(default=4, ge=2, le=365)
    frequency: Literal["auto", "daily", "weekly", "monthly"] = "auto"
    interval_level: float = Field(default=0.8, ge=0.5, le=0.99)
    rolling_windows: int = Field(default=3, ge=2, le=5)


class TaskRequestBase(BaseModel):
    task_id: str
    project_id: str
    dataset_id: str
    dataset_source_path: str
    evaluation_kind: EvaluationKind
    train_role_bindings: list[dict[str, Any]]
    evaluation_policy: EvaluationPolicySnapshot
    dataset_snapshot: DatasetSnapshotFact
    forecast_options: ForecastOptions | None = None
    text_preparation: TextPreparationInput | None = None

    @property
    def column_selection(self) -> ColumnSelection:
        return ColumnSelection(
            feature_columns=_role_columns(self.train_role_bindings, "feature"),
            target_columns=_role_columns(self.train_role_bindings, "target"),
        )

    @property
    def group_columns(self) -> list[str]:
        return _role_columns(self.train_role_bindings, "group")

    @property
    def time_columns(self) -> list[str]:
        return _role_columns(self.train_role_bindings, "time")


class ManualTrainingPayload(BaseModel):
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class HyperparameterTuningPayload(BaseModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class EvaluateModelPayload(BaseModel):
    trained_model_id: str
    model_key: str
    trained_model_artifact_path: str
    holdout_artifact_path: str


class FitTaskRequest(TaskRequestBase):
    continuation_plan: TaskContinuationPlan | None = None
    manual_training: ManualTrainingPayload
    trained_model_context: TrainedModelContextPayload | None = None


class HyperparameterTuningTaskRequest(TaskRequestBase):
    continuation_plan: TaskContinuationPlan | None = None
    hyperparameter_tuning: HyperparameterTuningPayload
    trained_model_context: TrainedModelContextPayload | None = None


class EvaluateTaskRequest(TaskRequestBase):
    evaluate_model: EvaluateModelPayload


class ApplyInputFile(BaseModel):
    absolute_path: str
    file_name: str
    source_kind: str
    dataset_id: str | None = None
    artifact_id: str | None = None


class ApplyModelPayload(BaseModel):
    trained_model_id: str
    model_key: str
    trained_model_artifact_path: str


class ApplyTaskRequest(BaseModel):
    """Apply a retained model.

    Exactly one input mode must be supplied: input_files (row-based apply) or
    forecast_horizon (future-period forecast for forecasting models) — never both
    and never neither; the validator raises ValueError otherwise.
    """

    task_id: str
    project_id: str
    dataset_id: str
    dataset_source_path: str
    feature_columns: list[str] = Field(default_factory=list)
    apply_model: ApplyModelPayload
    input_files: list[ApplyInputFile] = Field(default_factory=list)
    forecast_horizon: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _has_exactly_one_apply_mode(self) -> "ApplyTaskRequest":
        has_rows = bool(self.input_files)
        has_horizon = self.forecast_horizon is not None
        if has_rows == has_horizon:
            raise ValueError(
                "Apply requires exactly one input mode: input files or forecast_horizon."
            )
        return self


class CandidateMetrics(BaseModel):
    primary_metric_name: str
    primary_metric_value: float
    metrics: dict[str, float]
    details: dict[str, Any] = Field(default_factory=dict)


class SplitFacts(BaseModel):
    schema_version: int = 1
    policy_key: str
    requested_strategy: str
    realized_strategy: str
    source_dataset_snapshot_digest: str
    eligible_row_count: int
    train_row_count: int
    holdout_row_count: int
    eligible_group_count: int | None = None
    train_group_count: int | None = None
    holdout_group_count: int | None = None
    train_membership_digest: str
    holdout_membership_digest: str
    group_overlap_count: int = 0
    random_state: int
    evaluation_scope: str = "holdout"


class PreparationFacts(BaseModel):
    schema_version: int = 1
    policy_key: str = "sklearn_pipeline.v1"
    fit_scope: str = "outer_train_split"
    fit_row_count: int
    raw_feature_count: int
    transformed_feature_count: int
    numeric_feature_count: int = 0
    categorical_feature_count: int = 0
    text_feature_count: int = 0
    unknown_category_handling: str
    output_schema_digest: str


class TrainingScopeFacts(BaseModel):
    evaluation_model: str | None = None
    apply_model: str | None = None


class ForecastFoldFact(BaseModel):
    fold_index: int = Field(ge=0)
    train_end: str
    holdout_start: str
    holdout_end: str
    train_observation_count: int = Field(ge=1)
    holdout_observation_count: int = Field(ge=1)


class ForecastSplitFacts(BaseModel):
    schema_version: int = 1
    policy_key: str = "rolling_origin.v1"
    source_dataset_snapshot_digest: str
    frequency: Literal["daily", "weekly", "monthly"]
    seasonal_period: int = Field(ge=2)
    horizon: int = Field(ge=1)
    rolling_windows: int = Field(ge=2)
    group_count: int = Field(ge=1, le=24)
    observation_count: int = Field(ge=1)
    evaluation_observation_count: int = Field(ge=1)
    aligned_group_cutoff: str
    folds: list[ForecastFoldFact] = Field(min_length=2, max_length=5)
    fold_identity_digest: str
    future_overlap_count: int = 0
    evaluation_scope: str = "rolling_origin_holdouts"


class ForecastPreparationFacts(BaseModel):
    schema_version: int = 1
    policy_key: str = "regular_forecast_panel.v1"
    fit_scope: str = "chronological_training_prefixes"
    time_column: str
    target_column: str
    group_column: str | None = None
    frequency: Literal["daily", "weekly", "monthly"]
    seasonal_period: int = Field(ge=2)
    group_count: int = Field(ge=1, le=24)
    observation_count: int = Field(ge=1)
    duplicate_key_count: int = 0
    missing_period_count: int = 0
    non_finite_target_count: int = 0
    preparation_digest: str


class ForecastGroupMetrics(BaseModel):
    group_index: int = Field(ge=1, le=24)
    metrics: dict[str, float]
    baseline_metrics: dict[str, float]


class ForecastIntervalFacts(BaseModel):
    method: str = "residual_quantile.v1"
    interval_level: float = Field(ge=0.5, le=0.99)
    calibration_count: int = Field(ge=1)
    empirical_coverage: float = Field(ge=0.0, le=1.0)
    mean_width: float = Field(ge=0.0)
    coverage_guaranteed: bool = False


class ForecastSarimaSelectionFact(BaseModel):
    group_index: int = Field(ge=1, le=24)
    policy_key: str
    selected_order: tuple[int, int, int]
    selected_seasonal_order: tuple[int, int, int, int]
    inner_fold_count: int = Field(ge=2)
    attempted_fit_count: int = Field(ge=1)
    converged_fit_count: int = Field(ge=1)


class ForecastSarimaBudgetFacts(BaseModel):
    policy_key: str
    attempted_fit_count: int = Field(ge=0)
    converged_fit_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    max_fits_per_group: int = Field(ge=1)
    max_total_fits: int = Field(ge=1)
    max_wall_seconds: float = Field(gt=0.0)
    budget_exhausted: bool = False


class ForecastEvaluationFacts(BaseModel):
    split: ForecastSplitFacts
    preparation: ForecastPreparationFacts
    per_group: list[ForecastGroupMetrics] = Field(min_length=1, max_length=24)
    intervals: ForecastIntervalFacts
    forecast_digest: str
    interval_digest: str
    sarima_selection: list[ForecastSarimaSelectionFact] = Field(
        default_factory=list,
        max_length=24,
    )
    sarima_budget: ForecastSarimaBudgetFacts | None = None


class EvaluationComparison(BaseModel):
    primary_metric_name: str
    direction: MetricDirection
    candidate_value: float
    baseline_value: float
    verdict: EvaluationVerdict


class TuningSummary(BaseModel):
    best_params: dict[str, Any]
    cv_summary: dict[str, Any] = Field(default_factory=dict)


class TaskResultBase(BaseModel):
    task_id: str
    evaluation_kind: EvaluationKind
    evaluation_policy: EvaluationPolicySnapshot
    error_summary: str | None = None


class FitTaskResult(TaskResultBase):
    model_key: str
    params: dict[str, Any]
    model_artifact_path: str
    final_model_artifact_path: str | None = None
    holdout_artifact_path: str | None = None
    export_artifact_path: str | None = None
    report_artifact_path: str | None = None
    split_facts: SplitFacts | None = None
    preparation_facts: PreparationFacts | None = None
    training_scopes: TrainingScopeFacts | None = None
    forecast_split_facts: ForecastSplitFacts | None = None
    forecast_preparation_facts: ForecastPreparationFacts | None = None
    recommendation_split_facts: RecommendationSplitFacts | None = None
    recommendation_preparation_facts: RecommendationPreparationFacts | None = None
    text_preparation_facts: TextPreparationQualityFacts | None = None
    text_preparation_specification: TextPreparationSpecification | None = None
    text_leakage_facts: TextLeakageFacts | None = None
    text_vectorization_facts: TextVectorizationFacts | None = None
    text_clustering_evaluation: TextClusteringEvaluationFacts | None = None
    text_topic_evaluation: TextTopicEvaluationFacts | None = None
    text_retrieval_evaluation: TextRetrievalEvaluationFacts | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)


class HyperparameterTuningTaskResult(TaskResultBase):
    model_key: str
    best_params: dict[str, Any]
    model_artifact_path: str
    final_model_artifact_path: str | None = None
    holdout_artifact_path: str | None = None
    export_artifact_path: str | None = None
    report_artifact_path: str | None = None
    split_facts: SplitFacts | None = None
    preparation_facts: PreparationFacts | None = None
    training_scopes: TrainingScopeFacts | None = None
    forecast_split_facts: ForecastSplitFacts | None = None
    forecast_preparation_facts: ForecastPreparationFacts | None = None
    text_preparation_facts: TextPreparationQualityFacts | None = None
    text_preparation_specification: TextPreparationSpecification | None = None
    text_leakage_facts: TextLeakageFacts | None = None
    text_vectorization_facts: TextVectorizationFacts | None = None
    text_clustering_evaluation: TextClusteringEvaluationFacts | None = None
    text_topic_evaluation: TextTopicEvaluationFacts | None = None
    text_retrieval_evaluation: TextRetrievalEvaluationFacts | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    tuning_summary: TuningSummary


class EvaluateTaskResult(TaskResultBase):
    trained_model_id: str
    model_key: str
    evaluation: CandidateMetrics | None = None
    baseline_evaluation: CandidateMetrics | None = None
    comparison: EvaluationComparison | None = None
    split_facts: SplitFacts | None = None
    preparation_facts: PreparationFacts | None = None
    forecast_evaluation: ForecastEvaluationFacts | None = None
    clustering_evaluation: ClusteringEvaluationFacts | None = None
    recommendation_evaluation: RecommendationEvaluationFacts | None = None
    text_classification_evaluation: TextClassificationEvaluationFacts | None = None
    text_clustering_evaluation: TextClusteringEvaluationFacts | None = None
    text_topic_evaluation: TextTopicEvaluationFacts | None = None
    text_retrieval_evaluation: TextRetrievalEvaluationFacts | None = None


class ApplySummary(BaseModel):
    row_count: int
    input_file_count: int
    prediction_column_name: str = "prediction"
    apply_mode: Literal["rows", "future_horizon"] = "rows"
    horizon: int | None = Field(default=None, ge=1, le=365)
    group_count: int | None = Field(default=None, ge=1, le=24)


class ApplyTaskResult(BaseModel):
    task_id: str
    trained_model_id: str
    model_key: str
    output_file_path: str
    summary: ApplySummary
    source_dataset_ids: list[str] = Field(default_factory=list)
    source_artifact_ids: list[str] = Field(default_factory=list)
    text_classification_apply_facts: TextClassificationApplyFacts | None = None
    text_clustering_apply_facts: TextClusteringApplyFacts | None = None
    text_topic_apply_facts: TextTopicApplyFacts | None = None
    text_retrieval_apply_facts: TextRetrievalApplyFacts | None = None
    error_summary: str | None = None


class TaskLogEntry(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    level: str
    message: str
