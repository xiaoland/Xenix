from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ..storage.models import ProblemKind
from ..trained_model_metadata import TrainedModelContextPayload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetricDirection(StrEnum):
    MAX = "max"
    MIN = "min"


class TaskContinuationPlan(BaseModel):
    next_operation: str


class ColumnSelection(BaseModel):
    feature_columns: list[str]
    target_columns: list[str]


def _role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            raw_columns = binding.get("columns")
            if isinstance(raw_columns, list):
                return [str(column) for column in raw_columns]
    return []


class EvaluationPolicySnapshot(BaseModel):
    policy_key: str
    problem_kind: ProblemKind
    primary_metric_name: str
    primary_metric_direction: MetricDirection
    tie_breaker_metrics: list[str]
    split_strategy: str
    test_size: float
    cv_folds: int | None = None
    random_state: int


class TaskRequestBase(BaseModel):
    task_id: str
    project_id: str
    dataset_id: str
    dataset_source_path: str
    problem_kind: ProblemKind
    train_role_bindings: list[dict[str, Any]]
    evaluation_policy: EvaluationPolicySnapshot

    @property
    def column_selection(self) -> ColumnSelection:
        return ColumnSelection(
            feature_columns=_role_columns(self.train_role_bindings, "feature"),
            target_columns=_role_columns(self.train_role_bindings, "target"),
        )


class ManualTrainingPayload(BaseModel):
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class HyperparameterTuningPayload(BaseModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class EvaluateModelPayload(BaseModel):
    trained_model_id: str
    model_key: str
    source_ml_task_id: str
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


class InferenceInputFile(BaseModel):
    absolute_path: str
    file_name: str
    source_kind: str


class InferenceModelPayload(BaseModel):
    trained_model_id: str
    model_key: str
    trained_model_artifact_path: str


class InferenceTaskRequest(BaseModel):
    task_id: str
    project_id: str
    dataset_id: str
    dataset_source_path: str
    feature_columns: list[str]
    inference_model: InferenceModelPayload
    input_files: list[InferenceInputFile]


class CandidateMetrics(BaseModel):
    primary_metric_name: str
    primary_metric_value: float
    metrics: dict[str, float]


class TuningSummary(BaseModel):
    best_params: dict[str, Any]
    cv_summary: dict[str, Any] = Field(default_factory=dict)


class TaskResultBase(BaseModel):
    task_id: str
    problem_kind: ProblemKind
    evaluation_policy: EvaluationPolicySnapshot
    error_summary: str | None = None


class FitTaskResult(TaskResultBase):
    model_key: str
    params: dict[str, Any]
    model_artifact_path: str
    holdout_artifact_path: str | None = None
    export_artifact_path: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)


class HyperparameterTuningTaskResult(TaskResultBase):
    model_key: str
    best_params: dict[str, Any]
    model_artifact_path: str
    holdout_artifact_path: str | None = None
    export_artifact_path: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    tuning_summary: TuningSummary


class EvaluateTaskResult(TaskResultBase):
    trained_model_id: str
    model_key: str
    evaluation: CandidateMetrics


class InferenceSummary(BaseModel):
    row_count: int
    input_file_count: int
    prediction_column_name: str = "prediction"


class InferenceTaskResult(BaseModel):
    task_id: str
    trained_model_id: str
    model_key: str
    output_file_path: str
    summary: InferenceSummary
    error_summary: str | None = None


class TaskLogEntry(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    level: str
    message: str
