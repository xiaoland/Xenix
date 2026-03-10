from __future__ import annotations

from datetime import datetime

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

    def set_dataset_selection(
        self,
        session: Session,
        work_item_id: str,
        dataset_id: str,
        feature_columns: list[str],
        target_columns: list[str],
        now: datetime,
    ) -> WorkItemRow | None:
        row = self.get(session, work_item_id)
        if row is None:
            return None

        row.dataset_id = dataset_id
        row.feature_columns = list(feature_columns)
        row.target_columns = list(target_columns)
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row
