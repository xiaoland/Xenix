from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import jieba
from sqlalchemy.orm import sessionmaker

from ..exceptions import ValidationError
from .storage.models import KnowledgeDocumentRow, KnowledgeUnitRow, generate_id, utc_now
from .storage.repositories.knowledge import KnowledgeRepository

MAX_KNOWLEDGE_QUERY_CHARS = 512
MAX_KNOWLEDGE_TOP_K = 8
MAX_KNOWLEDGE_QUOTE_CHARS = 1600


@dataclass(frozen=True)
class KnowledgeUnitInput:
    text: str
    locator: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeMatch:
    citation_id: str
    document_id: str
    document_generation_id: str
    source_artifact_id: str | None
    unit_id: str
    title: str
    locator: dict[str, Any]
    quote: str


class KnowledgeService:
    """Own the current searchable Knowledge Unit corpus and bounded lookup."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._repository = KnowledgeRepository()

    def index_document(
        self,
        *,
        title: str,
        units: list[KnowledgeUnitInput],
        document_id: str | None = None,
        source_artifact_id: str | None = None,
        library_id: str = "global",
        canonical_generation_id: str | None = None,
        source_sha256: str | None = None,
        source_format: str | None = None,
        canonical_path: str | None = None,
    ) -> KnowledgeDocumentRow:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValidationError("Knowledge document title is required.")
        normalized_units = [unit for unit in units if unit.text.strip()]
        if not normalized_units:
            raise ValidationError("Knowledge document must contain searchable text.")

        with self._session_factory() as session:
            document = self._repository.get_document(session, document_id) if document_id else None
            generation_id = canonical_generation_id or generate_id()
            if document is None:
                document = self._repository.create_document(
                    session,
                    KnowledgeDocumentRow(
                        id=document_id or generate_id(),
                        library_id=library_id,
                        title=normalized_title,
                        source_artifact_id=source_artifact_id,
                        source_sha256=source_sha256,
                        source_format=source_format,
                        canonical_path=canonical_path,
                        canonical_generation_id=generation_id,
                    ),
                )
            else:
                document.title = normalized_title
                document.source_artifact_id = source_artifact_id
                document.source_sha256 = source_sha256
                document.source_format = source_format
                document.canonical_path = canonical_path
                document.canonical_generation_id = generation_id
                document.active = True
                document.updated_at = utc_now()
                session.add(document)

            rows = [
                KnowledgeUnitRow(
                    document_id=document.id,
                    canonical_generation_id=generation_id,
                    ordinal=ordinal,
                    text=unit.text.strip(),
                    search_text=_search_text(unit.text),
                    locator_payload=dict(unit.locator),
                )
                for ordinal, unit in enumerate(normalized_units)
            ]
            self._repository.replace_units(session, document=document, units=rows)
            session.commit()
            session.refresh(document)
            return document

    def get_document_by_source_sha256(
        self,
        source_sha256: str,
        *,
        library_id: str = "global",
    ) -> KnowledgeDocumentRow | None:
        with self._session_factory() as session:
            return self._repository.get_document_by_source_sha256(
                session,
                library_id=library_id,
                source_sha256=source_sha256,
            )

    def index_plain_text(
        self,
        *,
        title: str,
        text: str,
        document_id: str | None = None,
        source_artifact_id: str | None = None,
    ) -> KnowledgeDocumentRow:
        passages = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        return self.index_document(
            title=title,
            units=[KnowledgeUnitInput(text=part, locator={"passage": index + 1}) for index, part in enumerate(passages)],
            document_id=document_id,
            source_artifact_id=source_artifact_id,
        )

    def lookup(
        self,
        query: str,
        *,
        document_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeMatch]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValidationError("Knowledge query is required.")
        if len(normalized_query) > MAX_KNOWLEDGE_QUERY_CHARS:
            raise ValidationError(f"Knowledge query must not exceed {MAX_KNOWLEDGE_QUERY_CHARS} characters.")
        if not 1 <= top_k <= MAX_KNOWLEDGE_TOP_K:
            raise ValidationError(f"top_k must be between 1 and {MAX_KNOWLEDGE_TOP_K}.")
        filters = list(dict.fromkeys(document_ids or ()))
        if len(filters) > 16:
            raise ValidationError("document_ids must contain at most 16 ids.")

        with self._session_factory() as session:
            unit_ids = self._repository.search_unit_ids(
                session,
                fts_query=_fts_query(normalized_query),
                document_ids=filters,
                limit=top_k,
            )
            units = self._repository.get_units(session, unit_ids)
            matches: list[KnowledgeMatch] = []
            for unit in units:
                document = self._repository.get_document(session, unit.document_id)
                if document is None or not document.active:
                    continue
                matches.append(
                    KnowledgeMatch(
                        citation_id=f"knowledge:{unit.id}",
                        document_id=document.id,
                        document_generation_id=unit.canonical_generation_id,
                        source_artifact_id=document.source_artifact_id,
                        unit_id=unit.id,
                        title=document.title,
                        locator=dict(unit.locator_payload),
                        quote=unit.text[:MAX_KNOWLEDGE_QUOTE_CHARS],
                    )
                )
            return matches


def _tokens(value: str) -> list[str]:
    tokens = [token.strip().lower() for token in jieba.cut_for_search(value) if token.strip()]
    return list(dict.fromkeys(tokens))


def _search_text(value: str) -> str:
    return " ".join(_tokens(value))


def _fts_query(value: str) -> str:
    tokens = _tokens(value)
    if not tokens:
        raise ValidationError("Knowledge query has no searchable terms.")
    return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
