"""Prepare an apply request from a retained model and rows, files, or a forecast horizon."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import DatasetSourceMissingError, ValidationError
from .audit_contracts import ExecutionOrigin
from .dataset_inspection import InspectDatasetInput
from .dataset_service import DatasetService, MaterializeManualApplyCsvInput
from .ml.contracts import ApplyInputFile, ApplyModelPayload, ApplyTaskRequest
from .ml.registry import get_model_catalog_entry
from .ml.trained_model_metadata import TrainedModelMetadata, parse_trained_model_metadata
from .ml.types import ApplyMode
from .storage.identity import reserve_ids
from .storage.models import DatasetRow, TrainedModelRow
from .storage.repositories import TrainedModelRepository


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
    def _has_one_apply_mode(self) -> "ApplyWithFilesInput":
        has_rows = bool(self.input_files or self.input_sources) or self.input_rows is not None
        has_horizon = self.horizon is not None
        if has_rows == has_horizon:
            raise ValueError(
                "Apply requires exactly one input mode: rows/files or a forecast horizon."
            )
        return self


@dataclass(frozen=True)
class _ApplyContext:
    project_id: int
    dataset: DatasetRow
    feature_columns: list[str]
    trained_model: TrainedModelRow
    apply_mode: ApplyMode


class ApplyInputPreparation:
    def __init__(
        self,
        paths: AppPaths,
        session_factory: sessionmaker,
        dataset_service: DatasetService,
        trained_models: TrainedModelRepository,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._dataset_service = dataset_service
        self._trained_models = trained_models

    def build_request(self, input_data: ApplyWithFilesInput) -> ApplyTaskRequest:
        apply_context = self._build_apply_context(input_data)
        input_sources = list(input_data.input_sources)
        input_sources.extend(
            ApplySourceInput(source_path=path)
            for path in input_data.input_files
        )
        inline_path = (
            self._materialize_inline_apply_rows(
                apply_context.feature_columns,
                input_data.input_rows,
            )
            if apply_context.apply_mode is ApplyMode.ROWS
            else None
        )
        if inline_path is not None:
            input_sources.append(ApplySourceInput(source_path=str(inline_path)))
        input_files = (
            self._build_apply_input_files(apply_context.feature_columns, input_sources)
            if apply_context.apply_mode is ApplyMode.ROWS
            else []
        )
        return ApplyTaskRequest(
            task_id=reserve_ids(self._session_factory)[0],
            project_id=apply_context.project_id,
            dataset_id=apply_context.dataset.id,
            dataset_source_path=apply_context.dataset.source_path,
            feature_columns=apply_context.feature_columns,
            apply_model=ApplyModelPayload(
                trained_model_id=apply_context.trained_model.id,
                model_key=apply_context.trained_model.model_key,
                trained_model_artifact_path=apply_context.trained_model.artifact_path,
            ),
            input_files=input_files,
            forecast_horizon=input_data.horizon,
        )

    def _build_apply_context(self, input_data: ApplyWithFilesInput) -> "_ApplyContext":
        trained_model_id = input_data.trained_model_id
        if not trained_model_id:
            raise ValidationError("Apply requires a trained model.")

        trained_model = self._resolve_apply_model(trained_model_id)
        catalog = get_model_catalog_entry(trained_model.model_key)
        if not catalog.supports_apply:
            raise ValidationError(
                f"Model '{trained_model.model_key}' does not support apply."
            )
        requested_mode = (
            ApplyMode.FUTURE_HORIZON
            if input_data.horizon is not None
            else ApplyMode.ROWS
        )
        if catalog.apply_mode is not requested_mode:
            raise ValidationError(
                f"Model '{trained_model.model_key}' requires {catalog.apply_mode.value} apply input."
            )
        if not trained_model.dataset_id:
            raise ValidationError("The selected trained model is not tied to a dataset.")
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        if metadata is None or not metadata.train_role_bindings:
            raise ValidationError("The selected trained model does not contain a train role-binding contract.")

        dataset = self._dataset_service.get_dataset(trained_model.dataset_id)
        apply_columns = (
            self._normalize_columns(
                self._apply_columns_from_metadata(metadata),
                "apply",
            )
            if requested_mode is ApplyMode.ROWS
            else []
        )
        if not Path(dataset.source_path).exists():
            raise DatasetSourceMissingError("Dataset source file is missing.")
        return _ApplyContext(
            project_id=dataset.project_id,
            dataset=dataset,
            feature_columns=apply_columns,
            trained_model=trained_model,
            apply_mode=requested_mode,
        )

    def _resolve_apply_model(
        self,
        trained_model_id: int,
    ) -> TrainedModelRow:
        with self._session_factory() as session:
            trained_model = self._trained_models.get(session, trained_model_id)
            if trained_model is None:
                raise ValidationError("The selected trained model is invalid for the current dataset.")
            if not Path(trained_model.artifact_path).exists():
                raise ValidationError("The selected trained model artifact is missing.")
            session.expunge(trained_model)
            return trained_model

    def _build_apply_input_files(
        self,
        feature_columns: list[str],
        input_sources: list[ApplySourceInput],
    ) -> list[ApplyInputFile]:
        if not input_sources:
            raise ValidationError("Select at least one apply input file or provide inline apply rows.")
        manual_root = (self._paths.temp / "manual-apply").resolve()
        files: list[ApplyInputFile] = []
        for input_source in input_sources:
            raw_path = input_source.source_path
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(Path(raw_path).resolve()))
            )
            available = {column.name for column in inspection.columns}
            if not set(feature_columns).issubset(available):
                raise ValidationError("Apply input file does not contain the required apply columns.")
            absolute_path = Path(inspection.source_path).resolve()
            source_kind = "manual_csv" if manual_root in absolute_path.parents else "user_file"
            files.append(
                ApplyInputFile(
                    absolute_path=str(absolute_path),
                    file_name=absolute_path.name,
                    source_kind=source_kind,
                    dataset_id=input_source.dataset_id,
                    artifact_id=input_source.artifact_id,
                )
            )
        return files

    def _materialize_inline_apply_rows(
        self,
        feature_columns: list[str],
        input_rows: InlineApplyRowsInput | None,
    ) -> Path | None:
        if input_rows is None:
            return None

        header_index_map = self._normalize_inline_header_index_map(input_rows.header_index_map)
        if set(header_index_map) != set(feature_columns):
            raise ValidationError("Inline apply columns must match the trained model apply columns exactly.")
        if not input_rows.data:
            raise ValidationError("Inline apply rows require at least one data row.")

        row_width = len(header_index_map)
        rows: list[dict[str, str | None]] = []
        for row in input_rows.data:
            if len(row) != row_width:
                raise ValidationError("Inline apply data rows must match the header index map width.")
            rows.append(
                {
                    column: self._normalize_inline_cell(row[header_index_map[column]])
                    for column in feature_columns
                }
            )

        return self._dataset_service.materialize_manual_apply_csv(
            MaterializeManualApplyCsvInput(
                feature_columns=feature_columns,
                rows=rows,
            )
        )

    def _normalize_inline_header_index_map(self, header_index_map: dict[str, int]) -> dict[str, int]:
        if not header_index_map:
            raise ValidationError("Inline apply rows require a header_index_map.")

        normalized: dict[str, int] = {}
        for raw_column, raw_index in header_index_map.items():
            column = str(raw_column).strip()
            if not column:
                raise ValidationError("Inline apply column names cannot be empty.")
            if column in normalized:
                raise ValidationError("Inline apply column names cannot be duplicated.")
            if not isinstance(raw_index, int) or isinstance(raw_index, bool) or raw_index < 0:
                raise ValidationError("Inline apply header indexes must be non-negative integers.")
            normalized[column] = raw_index

        indexes = list(normalized.values())
        if len(set(indexes)) != len(indexes):
            raise ValidationError("Inline apply header indexes cannot be duplicated.")
        if sorted(indexes) != list(range(len(indexes))):
            raise ValidationError("Inline apply header indexes must be contiguous and start at 0.")
        return normalized

    def _normalize_inline_cell(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        raise ValidationError("Inline apply row values must be scalar JSON values.")

    def _apply_columns_from_metadata(self, metadata: TrainedModelMetadata) -> list[str]:
        schema_roles = metadata.apply_role_schema.get("roles") if isinstance(metadata.apply_role_schema, dict) else None
        role_names = [
            str(role.get("name"))
            for role in schema_roles or []
            if isinstance(role, dict) and role.get("required", True)
        ]
        if not role_names:
            role_names = ["feature"]
        columns: list[str] = []
        for role_name in role_names:
            columns.extend(_role_columns(metadata.train_role_bindings, role_name))
        return columns

    def _normalize_columns(self, columns: list[str], label: str) -> list[str]:
        normalized = [column.strip() for column in columns if column.strip()]
        if not normalized:
            raise ValidationError(f"At least one {label} column must be selected.")
        if len(set(normalized)) != len(normalized):
            raise ValidationError(f"Duplicate {label} columns are not allowed.")
        return normalized


def _role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            columns = binding.get("columns")
            if isinstance(columns, list):
                return [str(column) for column in columns]
    return []
