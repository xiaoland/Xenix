from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def generate_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MLTaskType(StrEnum):
    INSPECT_DATASET = "inspect_dataset"
    FIT = "fit"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    EVALUATE = "evaluate"
    INFERENCE = "inference"


class MLTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetSourceFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"
    UNKNOWN = "unknown"


class ProblemKind(StrEnum):
    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"


class MLTaskArtifactKind(StrEnum):
    MODEL = "model"
    HOLDOUT_DATA = "holdout_data"
    TRAINING_REPORT = "training_report"
    EVALUATION_REPORT = "evaluation_report"
    INFERENCE_RESULT = "inference_result"
    EXPORT_FILE = "export_file"
    OTHER = "other"


class ProjectRow(SQLModel, table=True):
    __tablename__ = "project"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkItemRow(SQLModel, table=True):
    __tablename__ = "work_item"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str = Field(index=True)
    description: str | None = None
    dataset_id: str = Field(foreign_key="dataset.id", index=True)
    best_trained_model_id: str | None = Field(
        default=None,
        foreign_key="trained_model.id",
        index=True,
    )
    feature_columns: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    target_columns: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DatasetRow(SQLModel, table=True):
    __tablename__ = "dataset"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str = Field(index=True)
    source_path: str
    source_format: DatasetSourceFormat = Field(default=DatasetSourceFormat.UNKNOWN, index=True)
    copied_from: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    copied_at: datetime | None = None
    ml_task_id: str | None = Field(default=None, foreign_key="ml_task.id", index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MLTaskRow(SQLModel, table=True):
    __tablename__ = "ml_task"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    task_type: MLTaskType = Field(index=True)
    status: MLTaskStatus = Field(index=True)
    request_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    result_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    error_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class MLTaskArtifactRow(SQLModel, table=True):
    __tablename__ = "ml_task_artifact"

    id: str = Field(default_factory=generate_id, primary_key=True)
    ml_task_id: str = Field(foreign_key="ml_task.id", index=True)
    artifact_kind: MLTaskArtifactKind = Field(index=True)
    absolute_path: str
    ready_to_open: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class TrainedModelRow(SQLModel, table=True):
    __tablename__ = "trained_model"

    id: str = Field(default_factory=generate_id, primary_key=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    ml_task_id: str = Field(foreign_key="ml_task.id", index=True, unique=True)
    model_key: str = Field(index=True)
    problem_kind: ProblemKind = Field(index=True)
    artifact_path: str
    metadata_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
