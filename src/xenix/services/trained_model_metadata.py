from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_SAVE_LABEL_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_SAVE_FILE_DATETIME_FORMAT = "%Y%m%d-%H%M%S"
_SLUG_PATTERN = re.compile(r"[^\w]+", re.UNICODE)


class TrainedModelContextPayload(BaseModel):
    work_item_name: str
    dataset_name: str
    dataset_file_name: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    dataset_row_count: int
    dataset_column_count: int
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)


class TrainedModelMetadata(BaseModel):
    schema_version: int = 1
    model_key: str
    model_display_name: str
    display_name: str
    saved_name: str
    artifact_file_name: str
    save_note: str
    training_operation: str
    source_work_item_name: str
    source_dataset_name: str
    source_dataset_file_name: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    dataset_row_count: int = 0
    dataset_column_count: int = 0
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)
    training_params: dict[str, Any] = Field(default_factory=dict)
    best_params: dict[str, Any] = Field(default_factory=dict)
    tuning_grid: dict[str, list[Any]] = Field(default_factory=dict)
    evaluation_primary_metric_name: str | None = None
    evaluation_primary_metric_value: float | None = None
    evaluation_metrics: dict[str, float] = Field(default_factory=dict)


def parse_trained_model_metadata(payload: dict[str, Any] | None) -> TrainedModelMetadata | None:
    if not isinstance(payload, dict) or not payload:
        return None
    try:
        return TrainedModelMetadata.model_validate(payload)
    except Exception:
        return None


def build_saved_name(
    work_item_name: str,
    model_display_name: str,
    created_at: datetime,
) -> str:
    timestamp = created_at.strftime(_SAVE_LABEL_DATETIME_FORMAT)
    return f"{work_item_name} · {model_display_name} · {timestamp}"


def build_artifact_file_name(
    work_item_name: str,
    model_display_name: str,
    created_at: datetime,
    ml_task_id: str,
) -> str:
    work_item_slug = _slugify(work_item_name)
    model_slug = _slugify(model_display_name)
    timestamp = created_at.strftime(_SAVE_FILE_DATETIME_FORMAT)
    task_suffix = ml_task_id[:8]
    return f"{work_item_slug}-{model_slug}-{timestamp}-{task_suffix}.joblib"


def build_save_note(model_display_name: str) -> str:
    return (
        f"The saved {model_display_name} model remains available for comparison, "
        "inference reuse, and later review."
    )


def with_evaluation(
    metadata: TrainedModelMetadata,
    evaluation: Any,
) -> TrainedModelMetadata:
    return metadata.model_copy(
        update={
            "evaluation_primary_metric_name": evaluation.primary_metric_name,
            "evaluation_primary_metric_value": float(evaluation.primary_metric_value),
            "evaluation_metrics": {
                str(metric_name): float(metric_value)
                for metric_name, metric_value in evaluation.metrics.items()
            },
        }
    )


def artifact_file_name_from_path(artifact_path: str) -> str:
    return Path(artifact_path).name


def _slugify(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("-", value.strip().lower()).strip("-_")
    return normalized or "model"
