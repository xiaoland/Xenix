from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import load_only
from sqlmodel import Session, col, select

from ..models import ConversationThreadRow, DatasetRow, MLTaskArtifactRow, MLTaskRow, MLTaskStatus


class MLTaskRepository:
    def create(self, session: Session, row: MLTaskRow) -> MLTaskRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, ml_task_id: int) -> MLTaskRow | None:
        return session.get(MLTaskRow, ml_task_id)

    def list_by_dataset(self, session: Session, dataset_id: int) -> list[MLTaskRow]:
        statement = (
            select(MLTaskRow)
            .where(MLTaskRow.dataset_id == dataset_id)
            .order_by(col(MLTaskRow.created_at))
        )
        return list(session.exec(statement))

    def list_for_job_feed(
        self, session: Session, *, origin_thread_id: int | None
    ) -> list[tuple[MLTaskRow, str | None, int | None, str | None]]:
        """Load the list fields, dataset name, and surviving conversation identity/title."""
        statement = (
            select(
                MLTaskRow, col(DatasetRow.name), col(ConversationThreadRow.id), col(ConversationThreadRow.title)
            )
            .options(
                load_only(
                    col(MLTaskRow.id),
                    col(MLTaskRow.project_id),
                    col(MLTaskRow.origin_thread_id),
                    col(MLTaskRow.dataset_id),
                    col(MLTaskRow.task_type),
                    col(MLTaskRow.status),
                    col(MLTaskRow.error_summary),
                    col(MLTaskRow.updated_at),
                    col(MLTaskRow.started_at),
                    col(MLTaskRow.finished_at),
                    raiseload=True,
                )
            )
            .outerjoin(DatasetRow, col(MLTaskRow.dataset_id) == col(DatasetRow.id))
            .outerjoin(ConversationThreadRow, col(MLTaskRow.origin_thread_id) == col(ConversationThreadRow.id))
        )
        if origin_thread_id is not None:
            statement = statement.where(MLTaskRow.origin_thread_id == origin_thread_id)
        return list(session.exec(statement))

    def update_status(
        self,
        session: Session,
        ml_task_id: int,
        from_status: MLTaskStatus,
        to_status: MLTaskStatus,
        now: datetime,
    ) -> MLTaskRow | None:
        """Transition a task from from_status to to_status (compare-and-swap).

        Returns the refreshed row, or None when the task is missing OR its current
        status is no longer from_status (callers must re-read when the distinction
        matters). started_at is set only on first entry into RUNNING; finished_at is
        set on SUCCEEDED/FAILED/CANCELLED.
        """
        row = self.get(session, ml_task_id)
        if row is None or row.status != from_status:
            return None

        row.status = to_status
        row.updated_at = now
        if to_status is MLTaskStatus.RUNNING and row.started_at is None:
            row.started_at = now
        if to_status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
            row.finished_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def complete(
        self,
        session: Session,
        ml_task_id: int,
        result_payload: dict[str, Any],
        finished_at: datetime,
        artifacts: list[MLTaskArtifactRow],
    ) -> MLTaskRow | None:
        row = self.get(session, ml_task_id)
        if row is None:
            return None

        row.status = MLTaskStatus.SUCCEEDED
        row.result_payload = result_payload
        row.error_summary = None
        row.finished_at = finished_at
        row.updated_at = finished_at
        session.add(row)
        for artifact in artifacts:
            session.add(artifact)
        session.flush()
        session.refresh(row)
        return row

    def fail(self, session: Session, ml_task_id: int, error_summary: str, finished_at: datetime) -> MLTaskRow | None:
        row = self.get(session, ml_task_id)
        if row is None:
            return None

        row.status = MLTaskStatus.FAILED
        row.error_summary = error_summary
        row.finished_at = finished_at
        row.updated_at = finished_at
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def cancel(self, session: Session, ml_task_id: int, finished_at: datetime) -> MLTaskRow | None:
        row = self.get(session, ml_task_id)
        if row is None:
            return None

        row.status = MLTaskStatus.CANCELLED
        row.finished_at = finished_at
        row.updated_at = finished_at
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def list_artifacts(self, session: Session, ml_task_id: int) -> list[MLTaskArtifactRow]:
        statement = (
            select(MLTaskArtifactRow)
            .where(MLTaskArtifactRow.ml_task_id == ml_task_id)
            .order_by(col(MLTaskArtifactRow.created_at))
        )
        return list(session.exec(statement))
