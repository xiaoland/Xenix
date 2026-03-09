from __future__ import annotations

from sqlmodel import Session, select

from ..models import WorkItemRow


class WorkItemRepository:
    def create(self, session: Session, row: WorkItemRow) -> WorkItemRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, work_item_id: str) -> WorkItemRow | None:
        return session.get(WorkItemRow, work_item_id)

    def list_by_project(self, session: Session, project_id: str) -> list[WorkItemRow]:
        statement = (
            select(WorkItemRow)
            .where(WorkItemRow.project_id == project_id)
            .order_by(WorkItemRow.created_at)
        )
        return list(session.exec(statement))
