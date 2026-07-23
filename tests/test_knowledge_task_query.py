from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import event

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_task_query import KnowledgeTaskQueryService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    KnowledgeCanonicalGenerationRow,
    KnowledgeDerivationRow,
    KnowledgeDocumentRow,
    KnowledgeImportRow,
    KnowledgeIndexTaskRow,
)


def _storage(monkeypatch, tmp_path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))


def _seed_document_attempt(session, *, now: datetime) -> None:
    document = KnowledgeDocumentRow(
        id="document-1",
        title="品牌经营规则",
        source_format="pdf",
        canonical_generation_id="generation-1",
    )
    import_row = KnowledgeImportRow(
        id="import-1",
        original_file_name="经营规则.pdf",
        source_format="pdf",
        status="canonical_ready",
        phase="completed",
        planned_document_id=document.id,
        document_id=document.id,
        canonical_generation_id="generation-1",
        created_at=now,
        updated_at=now,
    )
    canonical = KnowledgeCanonicalGenerationRow(
        id="generation-1",
        document_id=document.id,
        import_id=import_row.id,
        source_sha256="a" * 64,
        source_format="pdf",
        display_name="经营规则.pdf",
        envelope_sha256="b" * 64,
        content_ir_sha256="c" * 64,
        relative_path="objects/aa/canonical.json.zst",
        created_at=now,
    )
    session.add(document)
    session.flush()
    session.add(import_row)
    session.flush()
    session.add(canonical)
    session.flush()


def test_initial_content_preparation_is_folded_into_import_task(
    monkeypatch,
    tmp_path,
) -> None:
    storage = _storage(monkeypatch, tmp_path)
    now = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    with storage.session_factory() as session:
        _seed_document_attempt(session, now=now)
        session.add(
            KnowledgeDerivationRow(
                id="derivation-1",
                document_id="document-1",
                canonical_generation_id="generation-1",
                import_id="import-1",
                status="failed",
                phase="publishing",
                error_code="knowledge_derivation_failed",
                retryable=True,
                created_at=now + timedelta(seconds=1),
                updated_at=now + timedelta(seconds=1),
            )
        )
        session.add(
            KnowledgeIndexTaskRow(
                id="index-1",
                index_kinds_payload=["keyword", "text_vector"],
                trigger="manual",
                status="queued",
                phase="queued",
                error_summary="Embedding provider rejected the request.",
                created_at=now + timedelta(seconds=2),
                updated_at=now + timedelta(seconds=2),
            )
        )
        session.commit()

    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.casefold())

    event.listen(storage.engine, "before_cursor_execute", record_statement)
    try:
        tasks = KnowledgeTaskQueryService(storage.session_factory).list_tasks()
    finally:
        event.remove(storage.engine, "before_cursor_execute", record_statement)

    assert [task.kind for task in tasks] == ["index_build", "import"]
    assert tasks[0].error_summary == "Embedding provider rejected the request."
    folded = tasks[1]
    assert folded.status == "failed"
    assert folded.owner == "derivation"
    assert folded.can_retry
    assert folded.can_view_log
    assert not any("knowledge_unit" in statement for statement in statements)


def test_later_compatibility_derivation_is_an_independent_task(
    monkeypatch,
    tmp_path,
) -> None:
    storage = _storage(monkeypatch, tmp_path)
    now = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    with storage.session_factory() as session:
        _seed_document_attempt(session, now=now)
        session.add(
            KnowledgeDerivationRow(
                id="derivation-1",
                document_id="document-1",
                canonical_generation_id="generation-1",
                import_id="import-1",
                status="succeeded",
                phase="completed",
                attempt_number=1,
                created_at=now + timedelta(seconds=1),
                updated_at=now + timedelta(seconds=1),
            )
        )
        session.add(
            KnowledgeDerivationRow(
                id="derivation-2",
                document_id="document-1",
                canonical_generation_id="generation-1",
                import_id="import-1",
                status="failed",
                phase="publishing",
                attempt_number=2,
                retry_of="derivation-1",
                retryable=True,
                created_at=now + timedelta(seconds=2),
                updated_at=now + timedelta(seconds=2),
            )
        )
        session.commit()

    tasks = KnowledgeTaskQueryService(storage.session_factory).list_tasks()

    assert [task.kind for task in tasks] == ["content_preparation", "import"]
    compatibility = tasks[0]
    assert compatibility.target == "品牌经营规则"
    assert compatibility.trigger == "compatibility"
    assert compatibility.can_retry
    assert tasks[1].status == "canonical_ready"
