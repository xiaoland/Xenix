from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..exceptions import DatasetSourceMissingError, NotFoundError, ValidationError
from .dataset_inspection import inspect_dataset_file
from .storage.models import WorkItemRow
from .storage.repositories import DatasetRepository, ProjectRepository, WorkItemRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateWorkItemInput(SQLModel):
    project_id: str
    name: str
    description: str | None = None


class AttachDatasetSelectionInput(SQLModel):
    work_item_id: str
    dataset_id: str
    feature_columns: list[str]
    target_columns: list[str]


class WorkItemService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()
        self._datasets = DatasetRepository()

    def create_work_item(self, input_data: CreateWorkItemInput) -> WorkItemRow:
        name = input_data.name.strip()
        if not name:
            raise ValidationError("Work item name cannot be empty.")

        now = _utc_now()
        row = WorkItemRow(
            project_id=input_data.project_id,
            name=name,
            description=input_data.description,
            created_at=now,
            updated_at=now,
        )

        with self._session_factory() as session:
            if self._projects.get(session, input_data.project_id) is None:
                raise NotFoundError(f"Project '{input_data.project_id}' was not found.")
            self._work_items.create(session, row)
            session.commit()
            return row

    def list_work_items(self, project_id: str) -> list[WorkItemRow]:
        with self._session_factory() as session:
            return self._work_items.list_by_project(session, project_id)

    def get_work_item(self, work_item_id: str) -> WorkItemRow:
        with self._session_factory() as session:
            row = self._work_items.get(session, work_item_id)
            if row is None:
                raise NotFoundError(f"Work item '{work_item_id}' was not found.")
            return row

    def attach_dataset_selection(self, input_data: AttachDatasetSelectionInput) -> WorkItemRow:
        feature_columns = [column.strip() for column in input_data.feature_columns if column.strip()]
        target_columns = [column.strip() for column in input_data.target_columns if column.strip()]
        if not feature_columns:
            raise ValidationError("At least one feature column must be selected.")
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Feature and target columns cannot overlap.")

        with self._session_factory() as session:
            work_item = self._work_items.get(session, input_data.work_item_id)
            if work_item is None:
                raise NotFoundError(f"Work item '{input_data.work_item_id}' was not found.")

            dataset = self._datasets.get(session, input_data.dataset_id)
            if dataset is None:
                raise NotFoundError(f"Dataset '{input_data.dataset_id}' was not found.")
            if dataset.project_id != work_item.project_id:
                raise ValidationError("Dataset does not belong to the work item's project.")

            source_path = Path(dataset.source_path)
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

            updated = self._work_items.set_dataset_selection(
                session,
                work_item.id,
                dataset.id,
                feature_columns,
                target_columns,
                _utc_now(),
            )
            if updated is None:
                raise NotFoundError(f"Work item '{input_data.work_item_id}' was not found.")
            session.commit()
            return updated
