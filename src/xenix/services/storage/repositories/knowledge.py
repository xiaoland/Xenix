from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlmodel import Session, select

from ..models import KnowledgeDocumentRow, KnowledgeUnitRow


class KnowledgeRepository:
    def create_document(self, session: Session, row: KnowledgeDocumentRow) -> KnowledgeDocumentRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_document(self, session: Session, document_id: str) -> KnowledgeDocumentRow | None:
        return session.get(KnowledgeDocumentRow, document_id)

    def get_document_by_source_sha256(
        self,
        session: Session,
        *,
        library_id: str,
        source_sha256: str,
    ) -> KnowledgeDocumentRow | None:
        return session.exec(
            select(KnowledgeDocumentRow).where(
                KnowledgeDocumentRow.library_id == library_id,
                KnowledgeDocumentRow.source_sha256 == source_sha256,
                KnowledgeDocumentRow.active.is_(True),
            )
        ).first()

    def replace_units(
        self,
        session: Session,
        *,
        document: KnowledgeDocumentRow,
        units: Sequence[KnowledgeUnitRow],
    ) -> None:
        old_ids = list(
            session.exec(
                select(KnowledgeUnitRow.id).where(KnowledgeUnitRow.document_id == document.id)
            )
        )
        if old_ids:
            for unit_id in old_ids:
                session.execute(
                    text("DELETE FROM knowledge_unit_fts WHERE unit_id=:unit_id"),
                    {"unit_id": unit_id},
                )
            for row in session.exec(
                select(KnowledgeUnitRow).where(KnowledgeUnitRow.document_id == document.id)
            ):
                session.delete(row)
        for unit in units:
            session.add(unit)
        session.flush()
        for unit in units:
            session.execute(
                text(
                    "INSERT INTO knowledge_unit_fts(unit_id, title, search_text) "
                    "VALUES (:unit_id, :title, :search_text)"
                ),
                {"unit_id": unit.id, "title": document.title, "search_text": unit.search_text},
            )

    def search_unit_ids(
        self,
        session: Session,
        *,
        fts_query: str,
        document_ids: Sequence[str],
        limit: int,
    ) -> list[str]:
        sql = (
            "SELECT f.unit_id FROM knowledge_unit_fts AS f "
            "JOIN knowledge_unit AS u ON u.id=f.unit_id "
            "JOIN knowledge_document AS d ON d.id=u.document_id "
            "WHERE knowledge_unit_fts MATCH :query AND d.active=1 "
            "AND u.canonical_generation_id=d.canonical_generation_id "
        )
        params: dict[str, object] = {"query": fts_query, "limit": limit}
        if document_ids:
            placeholders = ", ".join(f":document_{index}" for index in range(len(document_ids)))
            sql += f"AND d.id IN ({placeholders}) "
            params.update({f"document_{index}": value for index, value in enumerate(document_ids)})
        sql += "ORDER BY bm25(knowledge_unit_fts) LIMIT :limit"
        return [str(row[0]) for row in session.execute(text(sql), params)]

    def get_units(self, session: Session, unit_ids: Sequence[str]) -> list[KnowledgeUnitRow]:
        if not unit_ids:
            return []
        rows = list(session.exec(select(KnowledgeUnitRow).where(KnowledgeUnitRow.id.in_(unit_ids))))
        by_id = {row.id: row for row in rows}
        return [by_id[unit_id] for unit_id in unit_ids if unit_id in by_id]
