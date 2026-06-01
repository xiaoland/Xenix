from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, Enum as SQLAlchemyEnum, JSON
from sqlmodel import Field, SQLModel

DEFAULT_AGENT_THREAD_SYSTEM_PROMPT = """You are Xenix, a data analysis agent for non-technical users.

Your job is to help users complete practical data analysis tasks through conversation, including inspecting data, cleaning data, binding dataset roles, training models, evaluating models, and applying trained models through the tools provided by Xenix.

Communicate in the user's language. Prefer clear explanations and concrete next steps.

Tool results may include artifact_id values for service-managed files, tables, charts, models, or apply outputs. Reference artifacts through artifact:// URIs only; never invent local filesystem paths. Use [label](artifact://<artifact_id>) for ordinary artifacts, and use Markdown image syntax such as ![descriptive alt](artifact://<artifact_id>) for image artifacts that should be shown inline.

Ask concise follow-up questions when you need further user input to continue."""


def generate_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MLTaskType(StrEnum):
    FIT = "fit"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    EVALUATE = "evaluate"
    APPLY = "apply"


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
    APPLY_RESULT = "apply_result"
    EXPORT_FILE = "export_file"
    OTHER = "other"


class AgentTurnStatus(StrEnum):
    OPEN = "open"
    ENDED = "ended"
    CANCELLED = "cancelled"


class AgentMessageKind(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_CALL_RESULT = "tool_call_result"


class AgentMessageStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMessageAuthor(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentToolCallStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentProviderRequestKind(StrEnum):
    PRIMARY = "primary"
    GUARD = "guard"


class AgentProviderRequestStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(StrEnum):
    DATASET = "dataset"
    MODEL = "model"
    METRICS = "metrics"
    REPORT = "report"
    IMAGE = "image"
    PREDICTION = "prediction"
    FILE = "file"
    OTHER = "other"


class ProjectRow(SQLModel, table=True):
    __tablename__ = "project"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
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
    derived_from_dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    ml_task_id: str | None = Field(default=None, foreign_key="ml_task.id", index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DatasetColumnBindingRow(SQLModel, table=True):
    __tablename__ = "dataset_column_binding"

    id: str = Field(default_factory=generate_id, primary_key=True)
    dataset_id: str = Field(foreign_key="dataset.id", index=True)
    role_bindings: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    model_key: str | None = Field(default=None, index=True)
    model_family: str | None = Field(default=None, index=True)
    model_task_kind: str | None = Field(default=None, index=True)
    schema_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=utc_now)


class MLTaskRow(SQLModel, table=True):
    __tablename__ = "ml_task"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    task_type: MLTaskType = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                MLTaskType,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
    status: MLTaskStatus = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                MLTaskStatus,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
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
    artifact_kind: MLTaskArtifactKind = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                MLTaskArtifactKind,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
    absolute_path: str
    ready_to_open: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class AgentThreadRow(SQLModel, table=True):
    __tablename__ = "agent_thread"

    id: str = Field(default_factory=generate_id, primary_key=True)
    title: str | None = Field(default=None, index=True)
    system_prompt: str = Field(default=DEFAULT_AGENT_THREAD_SYSTEM_PROMPT)
    selected_fq_model_key: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentTurnRow(SQLModel, table=True):
    __tablename__ = "agent_turn"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str = Field(foreign_key="agent_thread.id", index=True)
    sequence_index: int = Field(index=True)
    status: AgentTurnStatus = Field(default=AgentTurnStatus.OPEN, index=True)
    user_message_id: str | None = Field(default=None, foreign_key="agent_message.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class AgentMessageRow(SQLModel, table=True):
    __tablename__ = "agent_message"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str = Field(foreign_key="agent_thread.id", index=True)
    turn_id: str | None = Field(default=None, foreign_key="agent_turn.id", index=True)
    sequence_index: int = Field(index=True)
    kind: AgentMessageKind = Field(index=True)
    ui_author: AgentMessageAuthor = Field(index=True)
    content_blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    provider_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    status: AgentMessageStatus = Field(
        default=AgentMessageStatus.COMPLETED,
        sa_column=Column(
            SQLAlchemyEnum(
                AgentMessageStatus,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    finalized_at: datetime | None = None


class AgentRunRow(SQLModel, table=True):
    __tablename__ = "agent_run"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str = Field(foreign_key="agent_thread.id", index=True)
    turn_id: str = Field(foreign_key="agent_turn.id", index=True)
    status: AgentRunStatus = Field(default=AgentRunStatus.RUNNING, index=True)
    provider_name: str | None = Field(default=None, index=True)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    error_summary: str | None = None
    usage_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )


class AgentToolCallRow(SQLModel, table=True):
    __tablename__ = "agent_tool_call"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str = Field(foreign_key="agent_thread.id", index=True)
    turn_id: str = Field(foreign_key="agent_turn.id", index=True)
    request_message_id: str = Field(foreign_key="agent_message.id", index=True)
    result_message_id: str | None = Field(default=None, foreign_key="agent_message.id", index=True)
    tool_name: str = Field(index=True)
    status: AgentToolCallStatus = Field(default=AgentToolCallStatus.REQUESTED, index=True)
    arguments_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    result_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    error_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentTurnCompletionGuardRow(SQLModel, table=True):
    __tablename__ = "agent_turn_completion_guard"

    id: str = Field(default_factory=generate_id, primary_key=True)
    turn_id: str = Field(foreign_key="agent_turn.id", index=True)
    attempt_index: int
    input: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    output: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now)


class AgentProviderRequestRow(SQLModel, table=True):
    __tablename__ = "agent_provider_request"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str = Field(foreign_key="agent_thread.id", index=True)
    turn_id: str = Field(foreign_key="agent_turn.id", index=True)
    run_id: str | None = Field(default=None, foreign_key="agent_run.id", index=True)
    provider_name: str | None = Field(default=None, index=True)
    model: str | None = Field(default=None, index=True)
    request_kind: AgentProviderRequestKind = Field(
        default=AgentProviderRequestKind.PRIMARY,
        sa_column=Column(
            SQLAlchemyEnum(
                AgentProviderRequestKind,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
    status: AgentProviderRequestStatus = Field(
        default=AgentProviderRequestStatus.RUNNING,
        sa_column=Column(
            SQLAlchemyEnum(
                AgentProviderRequestStatus,
                values_callable=lambda enum_class: [member.value for member in enum_class],
            ),
            nullable=False,
            index=True,
        ),
    )
    input_message_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    output_message_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    usage_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class ArtifactRow(SQLModel, table=True):
    __tablename__ = "artifact"

    id: str = Field(default_factory=generate_id, primary_key=True)
    thread_id: str | None = Field(default=None, foreign_key="agent_thread.id", index=True)
    turn_id: str | None = Field(default=None, foreign_key="agent_turn.id", index=True)
    message_id: str | None = Field(default=None, foreign_key="agent_message.id", index=True)
    tool_call_id: str | None = Field(default=None, foreign_key="agent_tool_call.id", index=True)
    kind: ArtifactKind = Field(default=ArtifactKind.OTHER, index=True)
    title: str = Field(index=True)
    absolute_path: str
    mime_type: str | None = Field(default=None, index=True)
    summary: str | None = None
    preview_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    metadata_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    ready_to_open: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class TrainedModelRow(SQLModel, table=True):
    __tablename__ = "trained_model"

    id: str = Field(default_factory=generate_id, primary_key=True)
    dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    ml_task_id: str = Field(foreign_key="ml_task.id", index=True, unique=True)
    model_key: str = Field(index=True)
    problem_kind: ProblemKind | None = Field(default=None, index=True)
    artifact_path: str
    metadata_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
