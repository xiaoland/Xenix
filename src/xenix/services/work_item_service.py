from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..exceptions import NotFoundError, ValidationError
from .storage.models import WorkItemRow
from .storage.repositories import ProjectRepository, WorkItemRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateWorkItemInput(SQLModel):
    project_id: str
    name: str
    description: str | None = None


class WorkItemService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()

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
