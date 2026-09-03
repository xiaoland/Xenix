from __future__ import annotations

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_job_handlers import (
    KnowledgeImportHandler,
    _reconcile,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import JobDomain, JobRow, JobStatus
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


def test_reconcile_creates_missing_job_rows_and_resets_running(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
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
        jobs = list(
            session.exec(
                select(JobRow).where(JobRow.domain == JobDomain.KNOWLEDGE)
            )
        )
        requeued = _reconcile(
            session,
            jobs,
            ["imp-running", "imp-new"],
            kind="import",
        )
        session.commit()

        assert requeued == ["imp-running", "imp-new"]
        rows = {
            row.reference: row
            for row in session.exec(
                select(JobRow).where(JobRow.domain == JobDomain.KNOWLEDGE)
            )
        }
        assert rows["imp-running"].status is JobStatus.QUEUED
        assert rows["imp-new"].status is JobStatus.QUEUED
        assert rows["imp-new"].kind == "import"
    storage.engine.dispose()
