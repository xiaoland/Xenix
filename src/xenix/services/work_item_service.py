from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import DatasetSourceMissingError, NotFoundError, ValidationError
from .dataset_inspection import inspect_dataset_file
from .storage.layout import work_item_dataset_dir
from .storage.models import DatasetRow, generate_id
from .storage.models import WorkItemRow
from .storage.repositories import DatasetRepository, ProjectRepository, WorkItemRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateWorkItemInput(SQLModel):
    project_id: str
    name: str
    source_dataset_id: str
    feature_columns: list[str]
    target_columns: list[str] = Field(default_factory=list)
    description: str | None = None


class WorkItemService:
    def __init__(self, session_factory: sessionmaker, paths: AppPaths) -> None:
        self._session_factory = session_factory
        self._paths = paths
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()
        self._datasets = DatasetRepository()

    def create_work_item(self, input_data: CreateWorkItemInput) -> WorkItemRow:
        name = input_data.name.strip()
        if not name:
            raise ValidationError("Work item name cannot be empty.")
        feature_columns = [column.strip() for column in input_data.feature_columns if column.strip()]
        target_columns = [column.strip() for column in input_data.target_columns if column.strip()]
        if not feature_columns:
            raise ValidationError("At least one feature column must be selected.")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")

        now = _utc_now()
        work_item_id = generate_id()
        copied_path: Path | None = None

        try:
            with self._session_factory() as session:
                if self._projects.get(session, input_data.project_id) is None:
                    raise NotFoundError(f"Project '{input_data.project_id}' was not found.")

                source_dataset = self._datasets.get(session, input_data.source_dataset_id)
                if source_dataset is None:
                    raise NotFoundError(f"Dataset '{input_data.source_dataset_id}' was not found.")
                if source_dataset.project_id != input_data.project_id:
                    raise ValidationError("Dataset does not belong to the provided project.")

                source_path = Path(source_dataset.source_path)
                if not source_path.exists() or not source_path.is_file():
                    raise DatasetSourceMissingError("Dataset source file is missing.")

                try:
                    inspection = inspect_dataset_file(source_path)
                except ValidationError:
                    raise
                except Exception as exc:  # pragma: no cover - exercised by failure surface
                    raise ValidationError("Unable to read dataset file.") from exc

                available_columns = {column.name for column in inspection.columns}
                if not set(feature_columns).issubset(available_columns):
                    raise ValidationError("Selected feature columns are invalid.")
                if not set(target_columns).issubset(available_columns):
                    raise ValidationError("Selected target columns are invalid.")

                copied_path = self._copy_dataset_for_work_item(work_item_id, source_path)
                copied_dataset = DatasetRow(
                    project_id=input_data.project_id,
                    name=source_dataset.name,
                    source_path=str(copied_path),
                    source_format=source_dataset.source_format,
                    copied_from=source_dataset.id,
                    copied_at=now,
                    ml_task_id=None,
                    created_at=now,
                    updated_at=now,
                )
                self._datasets.create(session, copied_dataset)

                row = WorkItemRow(
                    id=work_item_id,
                    project_id=input_data.project_id,
                    name=name,
                    description=input_data.description,
                    dataset_id=copied_dataset.id,
                    feature_columns=feature_columns,
                    target_columns=target_columns,
                    created_at=now,
                    updated_at=now,
                )
                self._work_items.create(session, row)
                session.commit()
                return row
        except Exception:
            if copied_path is not None and copied_path.exists():
                copied_path.unlink(missing_ok=True)
            raise

    def list_work_items(self, project_id: str) -> list[WorkItemRow]:
        with self._session_factory() as session:
            return self._work_items.list_by_project(session, project_id)

    def get_work_item(self, work_item_id: str) -> WorkItemRow:
        with self._session_factory() as session:
            row = self._work_items.get(session, work_item_id)
            if row is None:
                raise NotFoundError(f"Work item '{work_item_id}' was not found.")
            return row

    def _copy_dataset_for_work_item(self, work_item_id: str, source_path: Path) -> Path:
        destination_dir = work_item_dataset_dir(self._paths, work_item_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        return destination_path
