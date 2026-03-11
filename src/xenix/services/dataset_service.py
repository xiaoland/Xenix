from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..exceptions import NotFoundError, ValidationError
from .dataset_inspection import (
    DatasetInspection,
    InspectDatasetInput,
    detect_source_format,
    inspect_dataset_file,
)
from .storage.models import DatasetRow, DatasetSourceFormat
from .storage.repositories import DatasetRepository, ProjectRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegisterDatasetInput(SQLModel):
    project_id: str
    source_path: str
    name: str | None = None


class RenameDatasetInput(SQLModel):
    dataset_id: str
    new_name: str


class DatasetService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
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

        now = _utc_now()
        row = DatasetRow(
            project_id=input_data.project_id,
            name=name,
            source_path=str(source_path),
            source_format=source_format,
            created_at=now,
            updated_at=now,
        )

        with self._session_factory() as session:
            if self._projects.get(session, input_data.project_id) is None:
                raise NotFoundError(f"Project '{input_data.project_id}' was not found.")
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

    def list_datasets(self, project_id: str) -> list[DatasetRow]:
        with self._session_factory() as session:
            return self._datasets.list_by_project(session, project_id)

    def get_dataset(self, dataset_id: str) -> DatasetRow:
        with self._session_factory() as session:
            row = self._datasets.get(session, dataset_id)
            if row is None:
                raise NotFoundError(f"Dataset '{dataset_id}' was not found.")
            return row
