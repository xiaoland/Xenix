from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from ...exceptions import ValidationError, report_exception
from ..artifact_service import ArtifactService, RegisterArtifactInput
from ..knowledge_content_store import KnowledgeContentStore
from ..knowledge_pipeline import MAX_SOURCE_BYTES, FileProbe, FileProbeResult
from ..storage.models import ArtifactKind, ArtifactRow, utc_now
from ..storage.repositories import KnowledgeRepository

LOGGER = logging.getLogger(__name__)


def prepare_source_snapshot(
    import_id: int,
    *,
    session_factory: sessionmaker[Any],
    knowledge_repo: KnowledgeRepository,
    artifacts: ArtifactService,
    store: KnowledgeContentStore,
    probe: FileProbe,
    take_source_path: Callable[[int], Path | None],
    advance: Callable[..., None],
    log_event: Callable[..., None],
    raise_if_cancelled: Callable[[int], None],
    next_attempt_number: Callable[..., int],
    corpus_changed_notifier: Callable[[str], object] | None,
) -> tuple[Path, FileProbeResult, dict[str, Any]] | None:
    advance(import_id, status="running", phase="snapshot")
    log_event(
        import_id,
        phase="snapshot",
        event_code="source_snapshot_started",
    )
    with session_factory() as session:
        row = knowledge_repo.get_import(session, import_id)
        if row is None or row.status == "cancelled":
            return None
        artifact = session.get(ArtifactRow, row.source_artifact_id) if row.source_artifact_id else None
        existing_artifact_path = Path(artifact.absolute_path) if artifact is not None else None
        expected_sha256 = row.source_sha256

    if artifact is None:
        source_reference = take_source_path(import_id)
        if source_reference is None:
            raise ValidationError(
                "Select the source file again to retry this import.",
                error_code="knowledge_source_reselection_required",
                retryable=True,
            )
        raise_if_cancelled(import_id)
        snapshot = store.snapshot_source(
            source_reference,
            maximum_bytes=MAX_SOURCE_BYTES,
        )
        authoritative = probe.probe(snapshot.path)
        raise_if_cancelled(import_id)
        with session_factory() as session:
            row = knowledge_repo.get_import(session, import_id)
            if row is None or row.status == "cancelled":
                return None
            existing = knowledge_repo.get_document_by_source_sha256(
                session,
                library_id=row.library_id,
                source_sha256=snapshot.sha256,
                include_inactive=True,
            )
            if existing is not None:
                was_inactive = not existing.active
                if was_inactive:
                    existing.active = True
                    existing.updated_at = utc_now()
                    session.add(existing)
                row.attempt_number = next_attempt_number(
                    session,
                    planned_document_id=existing.id,
                    excluding_import_id=row.id,
                )
                row.status = "reused"
                row.phase = "completed"
                row.source_sha256 = snapshot.sha256
                row.source_format = authoritative.source_format
                row.planned_document_id = existing.id
                row.document_id = existing.id
                row.source_artifact_id = existing.source_artifact_id
                row.canonical_generation_id = existing.canonical_generation_id
                row.reused_existing = True
                row.retryable = False
                row.updated_at = utc_now()
                knowledge_repo.save_import(session, row)
                session.commit()
                log_event(
                    import_id,
                    phase="completed",
                    event_code=(
                        "document_reactivated"
                        if was_inactive
                        else "document_reused"
                    ),
                )
                if was_inactive and corpus_changed_notifier is not None:
                    try:
                        corpus_changed_notifier(row.library_id)
                    except Exception as exc:
                        report_exception(exc)
                        LOGGER.warning(
                            "Knowledge index notification deferred to startup recovery",
                            extra={
                                "event_name": "knowledge.index.notification_deferred"
                            },
                        )
                return None
            artifact = artifacts.register_artifact_in_session(
                session,
                RegisterArtifactInput(
                    title=row.original_file_name,
                    absolute_path=str(snapshot.path),
                    kind=ArtifactKind.FILE,
                    mime_type=authoritative.media_type,
                    metadata_payload={
                        "knowledge_source_sha256": snapshot.sha256,
                        "original_file_name": row.original_file_name,
                        "source_format": authoritative.source_format,
                    },
                ),
            )
            row.source_sha256 = snapshot.sha256
            row.source_format = authoritative.source_format
            row.source_artifact_id = artifact.id
            row.phase = "probing"
            row.updated_at = utc_now()
            knowledge_repo.save_import(session, row)
            session.commit()
        log_event(
            import_id,
            phase="snapshot",
            event_code="source_snapshot_published",
        )
        source_path = snapshot.path
        probed = authoritative
    else:
        if expected_sha256 is None or existing_artifact_path is None:
            raise ValidationError("Knowledge import identity is incomplete.")
        source = store.verify_source_snapshot(
            existing_artifact_path,
            expected_sha256=expected_sha256,
        )
        source_path = source.path
        probed = probe.probe(source_path)
        log_event(
            import_id,
            phase="snapshot",
            event_code="source_snapshot_verified",
        )

    advance(import_id, status="running", phase="probing")
    log_event(import_id, phase="probing", event_code="source_probed")
    with session_factory() as session:
        row = knowledge_repo.get_import(session, import_id)
        if row is None or row.status == "cancelled" or not row.source_artifact_id:
            return None
        identity_values = {
            "library_id": row.library_id,
            "document_id": row.planned_document_id,
            "import_id": row.id,
            "source_artifact_id": row.source_artifact_id,
            "source_sha256": row.source_sha256,
            "source_format": row.source_format,
            "display_name": row.original_file_name,
            "attempt_number": row.attempt_number,
        }
    if not identity_values["document_id"] or not identity_values["source_sha256"]:
        raise ValidationError("Knowledge import identity is incomplete.")
    return source_path, probed, identity_values
