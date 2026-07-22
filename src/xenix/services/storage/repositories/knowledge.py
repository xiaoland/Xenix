from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlmodel import Session, select

from ..models import (
    KnowledgeCanonicalGenerationRow,
    KnowledgeDerivationRow,
    KnowledgeDocumentRow,
    KnowledgeImportRow,
    KnowledgeIndexTaskRow,
    KnowledgeUnitRow,
    KnowledgeVectorGenerationRow,
)


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

    def list_documents(
        self,
        session: Session,
        *,
        library_id: str,
    ) -> list[KnowledgeDocumentRow]:
        return list(
            session.exec(
                select(KnowledgeDocumentRow)
                .where(
                    KnowledgeDocumentRow.library_id == library_id,
                    KnowledgeDocumentRow.active.is_(True),
                )
                .order_by(
                    KnowledgeDocumentRow.updated_at.desc(),
                    KnowledgeDocumentRow.title,
                    KnowledgeDocumentRow.id,
                )
            )
        )

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
        library_id: str,
        document_ids: Sequence[str],
        limit: int,
    ) -> list[str]:
        sql = (
            "SELECT f.unit_id FROM knowledge_unit_fts AS f "
            "JOIN knowledge_unit AS u ON u.id=f.unit_id "
            "JOIN knowledge_document AS d ON d.id=u.document_id "
            "WHERE knowledge_unit_fts MATCH :query AND d.active=1 "
            "AND d.library_id=:library_id "
            "AND d.retrieval_status='ready' "
            "AND u.canonical_generation_id=d.retrieval_generation_id "
        )
        params: dict[str, object] = {
            "query": fts_query,
            "library_id": library_id,
            "limit": limit,
        }
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

    def get_documents(
        self,
        session: Session,
        document_ids: Sequence[str],
    ) -> dict[str, KnowledgeDocumentRow]:
        if not document_ids:
            return {}
        rows = session.exec(
            select(KnowledgeDocumentRow).where(
                KnowledgeDocumentRow.id.in_(list(dict.fromkeys(document_ids)))
            )
        )
        return {row.id: row for row in rows}

    def list_current_units(
        self,
        session: Session,
        *,
        library_id: str,
    ) -> list[KnowledgeUnitRow]:
        return list(
            session.exec(
                select(KnowledgeUnitRow)
                .join(
                    KnowledgeDocumentRow,
                    KnowledgeDocumentRow.id == KnowledgeUnitRow.document_id,
                )
                .where(
                    KnowledgeDocumentRow.library_id == library_id,
                    KnowledgeDocumentRow.active.is_(True),
                    KnowledgeDocumentRow.retrieval_status == "ready",
                    KnowledgeUnitRow.canonical_generation_id
                    == KnowledgeDocumentRow.retrieval_generation_id,
                )
                .order_by(
                    KnowledgeUnitRow.document_id,
                    KnowledgeUnitRow.ordinal,
                    KnowledgeUnitRow.id,
                )
            )
        )

    def keyword_index_counts(
        self,
        session: Session,
        *,
        library_id: str,
    ) -> tuple[int, int]:
        params = {"library_id": library_id}
        current = int(
            session.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge_unit AS u "
                    "JOIN knowledge_document AS d ON d.id=u.document_id "
                    "WHERE d.library_id=:library_id AND d.active=1 "
                    "AND d.retrieval_status='ready' "
                    "AND u.canonical_generation_id=d.retrieval_generation_id"
                ),
                params,
            ).scalar_one()
        )
        indexed = int(
            session.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge_unit_fts AS f "
                    "JOIN knowledge_unit AS u ON u.id=f.unit_id "
                    "JOIN knowledge_document AS d ON d.id=u.document_id "
                    "WHERE d.library_id=:library_id AND d.active=1 "
                    "AND d.retrieval_status='ready' "
                    "AND u.canonical_generation_id=d.retrieval_generation_id"
                ),
                params,
            ).scalar_one()
        )
        return current, indexed

    def rebuild_keyword_index(
        self,
        session: Session,
        *,
        library_id: str,
    ) -> int:
        session.execute(
            text(
                "DELETE FROM knowledge_unit_fts WHERE unit_id IN ("
                "SELECT u.id FROM knowledge_unit AS u "
                "JOIN knowledge_document AS d ON d.id=u.document_id "
                "WHERE d.library_id=:library_id)"
            ),
            {"library_id": library_id},
        )
        result = session.execute(
            text(
                "INSERT INTO knowledge_unit_fts(unit_id, title, search_text) "
                "SELECT u.id, d.title, u.search_text "
                "FROM knowledge_unit AS u "
                "JOIN knowledge_document AS d ON d.id=u.document_id "
                "WHERE d.library_id=:library_id AND d.active=1 "
                "AND d.retrieval_status='ready' "
                "AND u.canonical_generation_id=d.retrieval_generation_id"
            ),
            {"library_id": library_id},
        )
        return max(0, int(result.rowcount or 0))

    def list_vector_generations(
        self,
        session: Session,
        *,
        library_id: str,
        profile_fingerprint: str,
        corpus_fingerprint: str,
    ) -> list[KnowledgeVectorGenerationRow]:
        return list(
            session.exec(
                select(KnowledgeVectorGenerationRow)
                .where(
                    KnowledgeVectorGenerationRow.library_id == library_id,
                    KnowledgeVectorGenerationRow.profile_fingerprint
                    == profile_fingerprint,
                    KnowledgeVectorGenerationRow.corpus_fingerprint
                    == corpus_fingerprint,
                )
                .order_by(KnowledgeVectorGenerationRow.created_at.desc())
            )
        )

    def create_vector_generation(
        self,
        session: Session,
        row: KnowledgeVectorGenerationRow,
    ) -> KnowledgeVectorGenerationRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def list_all_vector_generations(
        self,
        session: Session,
    ) -> list[KnowledgeVectorGenerationRow]:
        return list(
            session.exec(
                select(KnowledgeVectorGenerationRow).order_by(
                    KnowledgeVectorGenerationRow.created_at,
                    KnowledgeVectorGenerationRow.id,
                )
            )
        )

    def delete_vector_generation(
        self,
        session: Session,
        generation_id: str,
    ) -> bool:
        row = session.get(KnowledgeVectorGenerationRow, generation_id)
        if row is None:
            return False
        session.delete(row)
        session.flush()
        return True

    def create_index_task(
        self,
        session: Session,
        row: KnowledgeIndexTaskRow,
    ) -> KnowledgeIndexTaskRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_index_task(
        self,
        session: Session,
        task_id: str,
    ) -> KnowledgeIndexTaskRow | None:
        return session.get(KnowledgeIndexTaskRow, task_id)

    def save_index_task(
        self,
        session: Session,
        row: KnowledgeIndexTaskRow,
    ) -> KnowledgeIndexTaskRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def list_index_tasks(
        self,
        session: Session,
        *,
        library_id: str | None,
        statuses: Sequence[str] | None = None,
    ) -> list[KnowledgeIndexTaskRow]:
        statement = select(KnowledgeIndexTaskRow)
        if library_id is not None:
            statement = statement.where(
                KnowledgeIndexTaskRow.library_id == library_id
            )
        if statuses:
            statement = statement.where(KnowledgeIndexTaskRow.status.in_(statuses))
        return list(
            session.exec(
                statement.order_by(
                    KnowledgeIndexTaskRow.created_at.desc(),
                    KnowledgeIndexTaskRow.id.desc(),
                )
            )
        )

    def create_import(
        self,
        session: Session,
        row: KnowledgeImportRow,
    ) -> KnowledgeImportRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_import(self, session: Session, import_id: str) -> KnowledgeImportRow | None:
        return session.get(KnowledgeImportRow, import_id)

    def list_imports(
        self,
        session: Session,
        *,
        library_id: str,
    ) -> list[KnowledgeImportRow]:
        return list(
            session.exec(
                select(KnowledgeImportRow)
                .where(KnowledgeImportRow.library_id == library_id)
                .order_by(KnowledgeImportRow.created_at.desc())
            )
        )

    def list_imports_by_status(
        self,
        session: Session,
        *,
        statuses: Sequence[str],
    ) -> list[KnowledgeImportRow]:
        normalized = list(dict.fromkeys(str(status) for status in statuses if str(status)))
        if not normalized:
            return []
        return list(
            session.exec(
                select(KnowledgeImportRow)
                .where(KnowledgeImportRow.status.in_(normalized))
                .order_by(KnowledgeImportRow.created_at, KnowledgeImportRow.id)
            )
        )

    def save_import(
        self,
        session: Session,
        row: KnowledgeImportRow,
    ) -> KnowledgeImportRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_canonical_generation(
        self,
        session: Session,
        row: KnowledgeCanonicalGenerationRow,
    ) -> KnowledgeCanonicalGenerationRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_canonical_generation(
        self,
        session: Session,
        generation_id: str,
    ) -> KnowledgeCanonicalGenerationRow | None:
        return session.get(KnowledgeCanonicalGenerationRow, generation_id)

    def get_current_canonical_generation(
        self,
        session: Session,
        *,
        document_id: str,
    ) -> KnowledgeCanonicalGenerationRow | None:
        document = self.get_document(session, document_id)
        if document is None:
            return None
        return self.get_canonical_generation(session, document.canonical_generation_id)

    def list_canonical_generations(
        self,
        session: Session,
        *,
        document_id: str,
    ) -> list[KnowledgeCanonicalGenerationRow]:
        return list(
            session.exec(
                select(KnowledgeCanonicalGenerationRow)
                .where(KnowledgeCanonicalGenerationRow.document_id == document_id)
                .order_by(KnowledgeCanonicalGenerationRow.created_at.desc())
            )
        )

    def create_derivation(
        self,
        session: Session,
        row: KnowledgeDerivationRow,
    ) -> KnowledgeDerivationRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_derivation(
        self,
        session: Session,
        derivation_id: str,
    ) -> KnowledgeDerivationRow | None:
        return session.get(KnowledgeDerivationRow, derivation_id)

    def list_derivations(
        self,
        session: Session,
        *,
        document_id: str,
        canonical_generation_id: str | None = None,
    ) -> list[KnowledgeDerivationRow]:
        statement = select(KnowledgeDerivationRow).where(
            KnowledgeDerivationRow.document_id == document_id
        )
        if canonical_generation_id is not None:
            statement = statement.where(
                KnowledgeDerivationRow.canonical_generation_id
                == canonical_generation_id
            )
        return list(
            session.exec(
                statement.order_by(
                    KnowledgeDerivationRow.created_at.desc(),
                    KnowledgeDerivationRow.id,
                )
            )
        )

    def save_derivation(
        self,
        session: Session,
        row: KnowledgeDerivationRow,
    ) -> KnowledgeDerivationRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def set_document_retrieval_state(
        self,
        session: Session,
        *,
        document: KnowledgeDocumentRow,
        generation_id: str | None,
        status: str,
    ) -> KnowledgeDocumentRow:
        document.retrieval_generation_id = generation_id
        document.retrieval_status = status
        session.add(document)
        session.flush()
        session.refresh(document)
        return document
