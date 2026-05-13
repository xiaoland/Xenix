from __future__ import annotations

from sqlmodel import Session, select

from ..models import ArtifactRow


class ArtifactRepository:
    def create(self, session: Session, row: ArtifactRow) -> ArtifactRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, artifact_id: str) -> ArtifactRow | None:
        return session.get(ArtifactRow, artifact_id)

    def list_by_thread(self, session: Session, thread_id: str) -> list[ArtifactRow]:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.thread_id == thread_id)
            .order_by(ArtifactRow.created_at)
        )
        return list(session.exec(statement))

    def list_by_message(self, session: Session, message_id: str) -> list[ArtifactRow]:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.message_id == message_id)
            .order_by(ArtifactRow.created_at)
        )
        return list(session.exec(statement))

    def list_by_tool_call(self, session: Session, tool_call_id: str) -> list[ArtifactRow]:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.tool_call_id == tool_call_id)
            .order_by(ArtifactRow.created_at)
        )
        return list(session.exec(statement))

