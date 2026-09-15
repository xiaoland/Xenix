from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from sqlmodel import Session, col, select

from .job_scheduler import JobCapabilities, JobOutcome
from .job_status import knowledge_job_status
from .storage.models import JobDomain, JobRow, JobStatus, utc_now

if TYPE_CHECKING:
    from .knowledge_derivation_service import KnowledgeDerivationService
    from .knowledge_import_service import KnowledgeImportService
    from .knowledge_index_service import KnowledgeIndexService


class KnowledgeJobService(Protocol):
    def recover_pending(self) -> list[int]: ...

    def run_unit(self, reference: int) -> None: ...

    def job_outcome(self, reference: int) -> tuple[str, str | None]: ...


def _reconcile(
    session: "Session",
    jobs: list[JobRow],
    requeue_refs: list[int],
    *,
    kind: str,
) -> list[int]:
    """Reconcile persisted JobRows with the domain's requeue decision.

    Running rows for requeued units return to queued; newly materialized domain
    units (e.g. a derivation job created during recovery) get a fresh JobRow.
    """
    requeue = set(requeue_refs)
    existing_jobs = {job.reference: job for job in jobs}
    missing = requeue - existing_jobs.keys()
    if missing:
        # A prior routing failure can leave a terminal JobRow while the domain
        # still owns queued work. Reuse its durable identity when the domain
        # explicitly requests replay instead of violating the unique constraint.
        existing_jobs.update(
            {
                job.reference: job
                for job in session.exec(
                    select(JobRow).where(
                        JobRow.domain == JobDomain.KNOWLEDGE,
                        JobRow.kind == kind,
                        col(JobRow.reference).in_(missing),
                    )
                )
            }
        )
    for job in existing_jobs.values():
        if job.reference in requeue:
            job.status = JobStatus.QUEUED
            job.started_at = None
            job.finished_at = None
            job.error_summary = None
            job.updated_at = utc_now()
            session.add(job)
    for reference in requeue_refs:
        if reference not in existing_jobs:
            now = utc_now()
            session.add(
                JobRow(
                    domain=JobDomain.KNOWLEDGE,
                    kind=kind,
                    reference=reference,
                    status=JobStatus.QUEUED,
                    phase="queued",
                    created_at=now,
                    updated_at=now,
                )
            )
    return requeue_refs


class _KnowledgeHandler:
    domain = JobDomain.KNOWLEDGE
    concurrency_limit = 1
    kind: str
    _can_cancel = False
    _can_view_log = False

    def __init__(self, service: KnowledgeJobService) -> None:
        self._service = service

    def recover(self, session: "Session", jobs: list[JobRow]) -> list[int]:
        return _reconcile(
            session,
            jobs,
            self._service.recover_pending(),
            kind=self.kind,
        )

    def run(self, job: JobRow) -> JobOutcome:
        self._service.run_unit(job.reference)
        status, summary = self._service.job_outcome(job.reference)
        return JobOutcome(knowledge_job_status(status), summary)

    def request_cancel(self, job: JobRow) -> None:
        """Only import has a cancellation command; derived work is not cancellable."""

    def capabilities(self, job: JobRow) -> JobCapabilities:
        return JobCapabilities(
            can_cancel=self._can_cancel,
            can_view_log=self._can_view_log,
        )


class KnowledgeImportHandler(_KnowledgeHandler):
    kind = "import"
    _can_cancel = True
    _can_view_log = True

    def __init__(self, service: "KnowledgeImportService") -> None:
        super().__init__(service)
        self._cancel = service.cancel_unit

    def request_cancel(self, job: JobRow) -> None:
        self._cancel(job.reference)


class KnowledgeDerivationHandler(_KnowledgeHandler):
    kind = "content_preparation"

    def __init__(self, service: "KnowledgeDerivationService") -> None:
        super().__init__(service)


class KnowledgeIndexHandler(_KnowledgeHandler):
    kind = "index_build"

    def __init__(self, service: "KnowledgeIndexService") -> None:
        super().__init__(service)


__all__ = [
    "KnowledgeDerivationHandler",
    "KnowledgeImportHandler",
    "KnowledgeIndexHandler",
]
