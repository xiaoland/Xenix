from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from ..audit_contracts import ExecutionOrigin
from ..ml.contracts import ColumnSelection, DatasetSnapshotFact, TaskLogEntry
from ..ml.types import ApplyMode, ColumnRoleBinding
from ..storage.models import DatasetRow, MLTaskArtifactRow, MLTaskRow, TrainedModelRow


class CreateColumnBindingInput(SQLModel):
    dataset_id: int
    role_bindings: list[dict[str, Any]] = Field(default_factory=list)
    model_key: str | None = None


class FitWithEvaluateInput(SQLModel):
    origin: ExecutionOrigin | None = None
    binding_id: int
    run_name: str | None = None
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class TuneWithEvaluateInput(SQLModel):
    origin: ExecutionOrigin | None = None
    binding_id: int
    run_name: str | None = None
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuningSelection(SQLModel):
    model_key: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class BulkTuneWithEvaluateInput(SQLModel):
    binding_id: int
    run_name: str | None = None
    selections: list[BulkTuningSelection] = Field(default_factory=list)


class InlineApplyRowsInput(SQLModel):
    header_index_map: dict[str, int] = Field(default_factory=dict)
    data: list[list[Any]] = Field(default_factory=list)


class ApplySourceInput(SQLModel):
    source_path: str
    dataset_id: int | None = None
    artifact_id: int | None = None


class ApplyWithFilesInput(SQLModel):
    origin: ExecutionOrigin | None = None
    trained_model_id: int
    input_files: list[str] = Field(default_factory=list)
    input_sources: list[ApplySourceInput] = Field(default_factory=list)
    input_rows: InlineApplyRowsInput | None = None
    horizon: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _has_one_apply_mode(self) -> ApplyWithFilesInput:
        has_rows = bool(self.input_files or self.input_sources) or self.input_rows is not None
        has_horizon = self.horizon is not None
        if has_rows == has_horizon:
            raise ValueError(
                "Apply requires exactly one input mode: rows/files or a forecast horizon."
            )
        return self


@dataclass(frozen=True)
class MLTaskDetails:
    task: MLTaskRow
    artifacts: list[MLTaskArtifactRow]
    logs: list[TaskLogEntry]


@dataclass(frozen=True)
class _TrainingContext:
    project_id: int
    dataset: Any
    run_name: str
    catalog: Any
    train_role_bindings: list[ColumnRoleBinding]
    column_selection: ColumnSelection
    evaluation_policy: Any
    inspection: Any
    dataset_snapshot: DatasetSnapshotFact


@dataclass(frozen=True)
class _ResolvedColumnBinding:
    dataset: DatasetRow
    role_bindings: list[ColumnRoleBinding]
    feature_columns: list[str]
    target_columns: list[str]
    inspection: Any
    dataset_snapshot: DatasetSnapshotFact


@dataclass(frozen=True)
class _ApplyContext:
    project_id: int
    dataset: Any
    feature_columns: list[str]
    trained_model: TrainedModelRow
    apply_mode: ApplyMode
