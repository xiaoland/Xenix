from __future__ import annotations

from sqlmodel import Session

from ..models import DatasetColumnSelectionRow


class DatasetColumnSelectionRepository:
    def create(self, session: Session, row: DatasetColumnSelectionRow) -> DatasetColumnSelectionRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, selection_id: str) -> DatasetColumnSelectionRow | None:
        return session.get(DatasetColumnSelectionRow, selection_id)
