from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.orm import sessionmaker

from ..config import AppPaths
from ..exceptions import ValidationError
from .artifact_service import ArtifactService
from .knowledge_task_logs import KnowledgeTaskLogStore
from .storage.layout import knowledge_root
from .storage.models import ArtifactKind, ArtifactRow, utc_now
from .storage.repositories.knowledge import KnowledgeRepository

if TYPE_CHECKING:
    from .knowledge_index_service import KnowledgeIndexService


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeDocumentRemovalReceipt:
    document_id: str
    title: str
    removed_import_count: int
    invalidated_vector_generation_count: int
    vector_rebuild_task_id: str | None


class KnowledgeDocumentRemovalError(ValidationError):
    pass


class KnowledgeDocumentNotFound(KnowledgeDocumentRemovalError):
    def __init__(self) -> None:
        super().__init__(
            "The Knowledge document was not found.",
            error_code="knowledge_document_not_found",
            retryable=False,
        )


class KnowledgeDocumentBusy(KnowledgeDocumentRemovalError):
    def __init__(self) -> None:
        super().__init__(
            "The Knowledge document is still being imported or prepared.",
            error_code="knowledge_document_busy",
            retryable=True,
        )


class KnowledgeDocumentLifecycleService:
    """Own destructive lifecycle commands for logical Knowledge documents."""

    def __init__(
        self,
        *,
        paths: AppPaths,
        session_factory: sessionmaker,
        artifact_service: ArtifactService,
        index_service: KnowledgeIndexService | None = None,
        content_cleanup: Callable[[], None] | None = None,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._artifacts = artifact_service
        self._indexes = index_service
        self._content_cleanup = content_cleanup
        self._repository = KnowledgeRepository()
        self._task_logs = KnowledgeTaskLogStore(paths)

    def remove_document(
        self,
        document_id: str,
        *,
        library_id: str = "global",
    ) -> KnowledgeDocumentRemovalReceipt:
        normalized_document_id = _required_identity(document_id)
        normalized_library_id = _required_identity(library_id)

        with self._session_factory() as session:
            document = self._repository.get_document(
                session,
                normalized_document_id,
            )
            if (
                document is None
                or document.library_id != normalized_library_id
                or not document.active
            ):
                raise KnowledgeDocumentNotFound()
            title = document.title

            claimed = self._repository.claim_document_for_removal(
                session,
                library_id=normalized_library_id,
                document_id=normalized_document_id,
                updated_at=utc_now(),
            )
            if not claimed:
                if self._repository.document_has_active_work(
                    session,
                    document_id=normalized_document_id,
                ):
                    raise KnowledgeDocumentBusy()
                raise KnowledgeDocumentNotFound()

            lineage = self._repository.remove_claimed_document(
                session,
                library_id=normalized_library_id,
                document_id=normalized_document_id,
            )
            for artifact_id in lineage.source_artifact_ids:
                if self._repository.artifact_is_referenced(
                    session,
                    artifact_id=artifact_id,
                ):
                    continue
                artifact = session.get(ArtifactRow, artifact_id)
                if artifact is not None and _is_owned_knowledge_source(
                    artifact,
                    root=knowledge_root(self._paths),
                ):
                    self._artifacts.unregister_artifact_in_session(
                        session,
                        artifact_id,
                    )
            session.commit()

        for import_id in lineage.import_ids:
            try:
                removed = self._task_logs.remove(import_id)
            except Exception:
                removed = False
            if not removed:
                LOGGER.warning(
                    "Knowledge task log cleanup was deferred after document removal",
                    extra={
                        "event_name": "knowledge.document.task_log_cleanup_deferred",
                        "knowledge.import_id": import_id,
                    },
                )
        if self._content_cleanup is not None:
            try:
                self._content_cleanup()
            except Exception:
                LOGGER.warning(
                    "Knowledge content cleanup was deferred after document removal",
                    extra={
                        "event_name": "knowledge.document.content_cleanup_deferred"
                    },
                )

        rebuild_task_id: str | None = None
        if self._indexes is not None:
            try:
                rebuild_task_id = self._indexes.reconcile_removed_corpus(
                    normalized_library_id
                )
            except Exception:
                LOGGER.warning(
                    "Knowledge index convergence was deferred after document removal",
                    extra={
                        "event_name": "knowledge.document.index_convergence_deferred"
                    },
                )
        return KnowledgeDocumentRemovalReceipt(
            document_id=normalized_document_id,
            title=title,
            removed_import_count=len(lineage.import_ids),
            invalidated_vector_generation_count=len(
                lineage.vector_generation_ids
            ),
            vector_rebuild_task_id=rebuild_task_id,
        )


def _required_identity(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise KnowledgeDocumentNotFound()
    return normalized


def _is_owned_knowledge_source(artifact: ArtifactRow, *, root: Path) -> bool:
    if artifact.kind != ArtifactKind.FILE:
        return False
    digest = artifact.metadata_payload.get("knowledge_source_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        return False
    try:
        absolute_root = Path(os.path.abspath(root.expanduser()))
        absolute_path = Path(os.path.abspath(Path(artifact.absolute_path).expanduser()))
        relative = absolute_path.relative_to(absolute_root)
    except (OSError, ValueError):
        return False
    parts = relative.parts
    return bool(
        len(parts) == 6
        and parts[:2] == ("objects", "source")
        and parts[2] == digest[:2]
        and parts[3] == digest[2:4]
        and parts[4] == digest
        and (parts[5] == "source" or parts[5].startswith("source."))
    )


__all__ = [
    "KnowledgeDocumentBusy",
    "KnowledgeDocumentLifecycleService",
    "KnowledgeDocumentNotFound",
    "KnowledgeDocumentRemovalError",
    "KnowledgeDocumentRemovalReceipt",
]
