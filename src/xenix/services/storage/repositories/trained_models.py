from __future__ import annotations

from sqlmodel import Session, select

from ..models import TrainedModelRow


class TrainedModelRepository:
    def create(self, session: Session, row: TrainedModelRow) -> TrainedModelRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, trained_model_id: str) -> TrainedModelRow | None:
        return session.get(TrainedModelRow, trained_model_id)

    def get_by_ml_task(self, session: Session, ml_task_id: str) -> TrainedModelRow | None:
        statement = select(TrainedModelRow).where(TrainedModelRow.ml_task_id == ml_task_id)
        return session.exec(statement).first()

    def list_by_work_item(self, session: Session, work_item_id: str) -> list[TrainedModelRow]:
        statement = (
            select(TrainedModelRow)
            .where(TrainedModelRow.work_item_id == work_item_id)
            .order_by(TrainedModelRow.created_at)
        )
        return list(session.exec(statement))
