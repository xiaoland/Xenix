from __future__ import annotations

import csv
import codecs
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import NotFoundError, ValidationError
from .dataset_inspection import (
    DatasetInspection,
    InspectDatasetInput,
    detect_source_format,
    inspect_dataset_file,
    load_dataframe,
)
from .storage.models import DatasetRow, DatasetSourceFormat, ProjectRow
from .storage.repositories import DatasetRepository, ProjectRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegisterDatasetInput(SQLModel):
    source_path: str
    project_id: str | None = None
    name: str | None = None
    derived_from_dataset_id: str | None = None


class RenameDatasetInput(SQLModel):
    dataset_id: str
    new_name: str


class MaterializeManualInferenceCsvInput(SQLModel):
    feature_columns: list[str]
    rows: list[dict[str, str | None]]


class ExportDatasetCopyInput(SQLModel):
    dataset_id: str
    destination_path: str
    csv_encoding: str = "utf-8"


class DatasetService:
    def __init__(self, session_factory: sessionmaker, paths: AppPaths) -> None:
        self._session_factory = session_factory
        self._paths = paths
        self._projects = ProjectRepository()
        self._datasets = DatasetRepository()

    def register_dataset(self, input_data: RegisterDatasetInput) -> DatasetRow:
        source_path = Path(input_data.source_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source path must point to an existing file.")

        source_format = detect_source_format(source_path)
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")

        name = input_data.name.strip() if input_data.name else source_path.stem
        if not name:
            raise ValidationError("Dataset name cannot be empty.")

        with self._session_factory() as session:
            derived_from = None
            if input_data.derived_from_dataset_id:
                derived_from = self._datasets.get(session, input_data.derived_from_dataset_id)
                if derived_from is None:
                    raise NotFoundError(
                        f"Dataset '{input_data.derived_from_dataset_id}' was not found."
                    )
            project_id = self._resolve_project_id(
                session,
                input_data.project_id,
                derived_from=derived_from,
            )
            now = _utc_now()
            row = DatasetRow(
                project_id=project_id,
                name=name,
                source_path=str(source_path),
                source_format=source_format,
                copied_from=None,
                copied_at=None,
                derived_from_dataset_id=derived_from.id if derived_from else None,
                ml_task_id=None,
                created_at=now,
                updated_at=now,
            )
            self._datasets.create(session, row)
            session.commit()
            return row

    def inspect_source_file(self, input_data: InspectDatasetInput) -> DatasetInspection:
        source_path = Path(input_data.source_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source path must point to an existing file.")
        try:
            return inspect_dataset_file(source_path)
        except ValidationError:
            raise
        except Exception as exc:  # pragma: no cover - exercised by failure surface
            raise ValidationError("Unable to read dataset file.") from exc

    def rename_dataset(self, input_data: RenameDatasetInput) -> DatasetRow:
        new_name = input_data.new_name.strip()
        if not new_name:
            raise ValidationError("Dataset name cannot be empty.")

        with self._session_factory() as session:
            row = self._datasets.rename(session, input_data.dataset_id, new_name, _utc_now())
            if row is None:
                raise NotFoundError(f"Dataset '{input_data.dataset_id}' was not found.")
            session.commit()
            return row

    def list_datasets(self, project_id: str | None = None) -> list[DatasetRow]:
        with self._session_factory() as session:
            if project_id is None:
                return self._datasets.list_all(session)
            return self._datasets.list_by_project(session, project_id)

    def list_source_datasets(self, project_id: str | None = None) -> list[DatasetRow]:
        with self._session_factory() as session:
            if project_id is None:
                return self._datasets.list_sources(session)
            return self._datasets.list_source_by_project(session, project_id)

    def list_generated_datasets(self, project_id: str | None = None) -> list[DatasetRow]:
        with self._session_factory() as session:
            if project_id is None:
                return self._datasets.list_generated(session)
            return self._datasets.list_generated_by_project(session, project_id)

    def list_derived_datasets(self, source_dataset_id: str) -> list[DatasetRow]:
        with self._session_factory() as session:
            if self._datasets.get(session, source_dataset_id) is None:
                raise NotFoundError(f"Dataset '{source_dataset_id}' was not found.")
            return self._datasets.list_derived_by_source(session, source_dataset_id)

    def get_dataset(self, dataset_id: str) -> DatasetRow:
        with self._session_factory() as session:
            row = self._datasets.get(session, dataset_id)
            if row is None:
                raise NotFoundError(f"Dataset '{dataset_id}' was not found.")
            return row

    def get_dataset_by_ml_task(self, ml_task_id: str) -> DatasetRow | None:
        with self._session_factory() as session:
            return self._datasets.get_by_ml_task(session, ml_task_id)

    def materialize_manual_inference_csv(self, input_data: MaterializeManualInferenceCsvInput) -> Path:
        feature_columns = [column.strip() for column in input_data.feature_columns if column.strip()]
        if not feature_columns:
            raise ValidationError("Manual inference requires at least one feature column.")
        if not input_data.rows:
            raise ValidationError("Manual inference requires at least one row.")

        normalized_rows: list[dict[str, str]] = []
        expected_columns = set(feature_columns)
        for row in input_data.rows:
            if set(row) != expected_columns:
                raise ValidationError("Manual inference rows must match the selected feature columns exactly.")
            normalized_rows.append(
                {
                    column: "" if row.get(column) is None else str(row.get(column, ""))
                    for column in feature_columns
                }
            )

        directory = self._paths.temp / "manual-inference"
        directory.mkdir(parents=True, exist_ok=True)
        csv_path = directory / f"{uuid4().hex}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=feature_columns)
            writer.writeheader()
            writer.writerows(normalized_rows)
        return csv_path

    def export_dataset_copy(self, input_data: ExportDatasetCopyInput) -> Path:
        destination_path = Path(input_data.destination_path).expanduser()
        if not destination_path.is_absolute():
            raise ValidationError("Export destination path must be absolute.")

        dataset = self.get_dataset(input_data.dataset_id)
        source_path = Path(dataset.source_path)
        if not source_path.exists() or not source_path.is_file():
            raise ValidationError("Dataset source file is missing.")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_suffix = destination_path.suffix.lower()
        if destination_suffix not in {".csv", ".xlsx"}:
            raise ValidationError("Export destination must end with .csv or .xlsx.")

        source_format = self._resolve_export_source_format(source_path, dataset.source_format)
        dataframe = self._load_export_dataframe(source_path, source_format)
        if destination_suffix == ".csv":
            csv_encoding = self._normalize_csv_encoding(input_data.csv_encoding)
            dataframe.to_csv(destination_path, index=False, encoding=csv_encoding)
        else:
            dataframe.to_excel(destination_path, index=False)
        return destination_path

    def _resolve_export_source_format(self, source_path: Path, dataset_format: DatasetSourceFormat) -> DatasetSourceFormat:
        detected_format = detect_source_format(source_path)
        if detected_format is not DatasetSourceFormat.UNKNOWN:
            return detected_format
        if dataset_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Dataset source file format is not supported for export.")
        return dataset_format

    def _load_export_dataframe(self, source_path: Path, source_format: DatasetSourceFormat) -> pd.DataFrame:
        try:
            return load_dataframe(source_path, source_format)
        except Exception as exc:  # pragma: no cover - exercised by failure surface
            raise ValidationError("Unable to read dataset file for export.") from exc

    def _normalize_csv_encoding(self, encoding_name: str) -> str:
        normalized = encoding_name.strip()
        if not normalized:
            raise ValidationError("CSV export encoding cannot be empty.")
        try:
            return codecs.lookup(normalized).name
        except LookupError as exc:
            raise ValidationError(f"CSV export encoding '{encoding_name}' is not supported.") from exc

    def _resolve_project_id(
        self,
        session,
        project_id: str | None,
        *,
        derived_from: DatasetRow | None = None,
    ) -> str:
        normalized = project_id.strip() if project_id else ""
        if normalized:
            if self._projects.get(session, normalized) is None:
                raise NotFoundError(f"Project '{normalized}' was not found.")
            if derived_from is not None and derived_from.project_id != normalized:
                raise ValidationError("Derived dataset source does not belong to the provided project.")
            return normalized
        if derived_from is not None:
            return derived_from.project_id
        projects = self._projects.list_all(session)
        if projects:
            return projects[0].id
        row = ProjectRow(name="Agent Analysis")
        self._projects.create(session, row)
        return row.id
