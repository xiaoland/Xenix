from __future__ import annotations

from xenix.services.knowledge_job_handlers import (
    KnowledgeDerivationHandler,
    KnowledgeImportHandler,
    KnowledgeIndexHandler,
    _reconcile,
)
from xenix.services.storage.models import JobDomain, JobRow, JobStatus
from xenix.services.job_scheduler import JobScheduler
from sqlmodel import select


class _StubImportService:
    def __init__(self) -> None:
        self.recover_refs: list[str] = []
        self.statuses: dict[str, str] = {}
        self.errors: dict[str, str | None] = {}
        self.ran: list[str] = []
        self.cancelled: list[str] = []

    def recover_pending(self) -> list[str]:
        return list(self.recover_refs)

    def run_unit(self, reference: str) -> None:
        self.ran.append(reference)

    def job_outcome(self, reference: str) -> tuple[str, str | None]:
        return (self.statuses.get(reference, "succeeded"), self.errors.get(reference))

    def cancel_unit(self, reference: str) -> None:
        self.cancelled.append(reference)


def test_application_knowledge_handlers_coexist_and_recover_their_own_work(storage) -> None:
    imports, derivation, index = (_StubImportService() for _ in range(3))
    handlers = [KnowledgeImportHandler(imports), KnowledgeDerivationHandler(derivation), KnowledgeIndexHandler(index)]
    for service, reference in ((imports, "source"), (derivation, "content"), (index, "search")):
        service.recover_refs = [reference]
    # Earlier domain-only dispatch could fail the scheduling row without ever
    # running the import. Domain recovery must reuse that row, not insert a duplicate.
    with storage.session_factory() as session:
        failed = JobRow(domain=JobDomain.KNOWLEDGE, kind="import", reference="source", status=JobStatus.FAILED)
        session.add(failed)
        session.commit()
        original_job_id = failed.id
    scheduler = JobScheduler(storage.session_factory, [])
    try:
        for handler in handlers:
            scheduler.register_handler(handler)
        scheduler.start()
        assert scheduler.wait_idle(5)
        assert imports.ran == ["source"]
        assert derivation.ran == ["content"]
        assert index.ran == ["search"]
        with storage.session_factory() as session:
            rows = list(session.exec(select(JobRow)))
            assert {row.reference: row.kind for row in rows} == {
                "source": "import",
                "content": "content_preparation",
                "search": "index_build",
            }
            assert all(row.status is JobStatus.SUCCEEDED for row in rows)
            assert next(row for row in rows if row.reference == "source").id == original_job_id
        assert scheduler.capabilities(JobDomain.KNOWLEDGE, "source").can_view_log
        assert not scheduler.capabilities(JobDomain.KNOWLEDGE, "search").can_cancel
    finally:
        scheduler.shutdown()


def test_import_handler_maps_needs_attention_to_failed_and_forwards_summary() -> None:
    service = _StubImportService()
    service.statuses["imp-1"] = "needs_attention"
    service.errors["imp-1"] = "Please reselect the source file."
    handler = KnowledgeImportHandler(service)
    job = JobRow(
        domain=JobDomain.KNOWLEDGE,
        kind="import",
        reference="imp-1",
        status=JobStatus.RUNNING,
    )

    outcome = handler.run(job)

    assert service.ran == ["imp-1"]
    assert outcome.status is JobStatus.FAILED
    assert outcome.error_summary == "Please reselect the source file."
    assert handler.capabilities(job).can_cancel is True


def test_reconcile_creates_missing_job_rows_and_resets_running(storage) -> None:
    with storage.session_factory() as session:
        session.add(
            JobRow(
                domain=JobDomain.KNOWLEDGE,
                kind="import",
                reference="imp-running",
                status=JobStatus.RUNNING,
            )
        )
        session.commit()
        jobs = list(session.exec(select(JobRow).where(JobRow.domain == JobDomain.KNOWLEDGE)))
        requeued = _reconcile(
            session,
            jobs,
            ["imp-running", "imp-new"],
            kind="import",
        )
        session.commit()

        assert requeued == ["imp-running", "imp-new"]
        rows = {row.reference: row for row in session.exec(select(JobRow).where(JobRow.domain == JobDomain.KNOWLEDGE))}
        assert rows["imp-running"].status is JobStatus.QUEUED
        assert rows["imp-new"].status is JobStatus.QUEUED
        assert rows["imp-new"].kind == "import"
