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

    def list_by_kind(self, session: Session, kind) -> list[ArtifactRow]:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.kind == kind)
            .order_by(ArtifactRow.created_at.desc())
        )
        return list(session.exec(statement))
