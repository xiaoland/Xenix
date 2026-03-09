from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from ..models import DatasetRow


class DatasetRepository:
    def create(self, session: Session, row: DatasetRow) -> DatasetRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, dataset_id: str) -> DatasetRow | None:
        return session.get(DatasetRow, dataset_id)

    def list_by_project(self, session: Session, project_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(DatasetRow.project_id == project_id)
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def rename(self, session: Session, dataset_id: str, new_name: str, now: datetime) -> DatasetRow | None:
        row = self.get(session, dataset_id)
        if row is None:
            return None

        row.name = new_name
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row
