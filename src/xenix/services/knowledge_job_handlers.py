from __future__ import annotations

from typing import TYPE_CHECKING

from .job_scheduler import JobCapabilities, JobOutcome
from .storage.models import JobDomain, JobRow, JobStatus, utc_now

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .knowledge_derivation_service import KnowledgeDerivationService
    from .knowledge_import_service import KnowledgeImportService
    from .knowledge_index_service import KnowledgeIndexService


_KNOWLEDGE_STATUS_TO_JOB: dict[str, JobStatus] = {
    "queued": JobStatus.QUEUED,
    "pending": JobStatus.QUEUED,
    "running": JobStatus.RUNNING,
    "succeeded": JobStatus.SUCCEEDED,
    "canonical_ready": JobStatus.SUCCEEDED,
    "retrieval_ready": JobStatus.SUCCEEDED,
    "reused": JobStatus.SUCCEEDED,
    "failed": JobStatus.FAILED,
    "needs_attention": JobStatus.FAILED,
    "cancelled": JobStatus.CANCELLED,
}


def _reconcile(
    session: "Session",
    jobs: list[JobRow],
    requeue_refs: list[str],
    *,
    kind: str,
) -> list[str]:
    """Reconcile persisted JobRows with the domain's requeue decision.

    Running rows for requeued units return to queued; newly materialized domain
    units (e.g. a derivation job created during recovery) get a fresh JobRow.
    """
    requeue = set(requeue_refs)
    existing = {job.reference for job in jobs}
    for job in jobs:
        if job.reference in requeue and job.status is JobStatus.RUNNING:
            job.status = JobStatus.QUEUED
            job.updated_at = utc_now()
            session.add(job)
    for reference in requeue_refs:
        if reference not in existing:
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
    _kind: str
    _can_cancel = False
    _can_view_log = False

    def __init__(self, service: object) -> None:
        self._service = service

    def recover(self, session: "Session", jobs: list[JobRow]) -> list[str]:
        return _reconcile(
            session,
            jobs,
            self._service.recover_pending(),  # type: ignore[attr-defined]
            kind=self._kind,
        )

    def run(self, job: JobRow) -> JobOutcome:
        try:
            self._service.run_unit(job.reference)  # type: ignore[attr-defined]
        except Exception as exc:
            return JobOutcome(JobStatus.FAILED, str(exc))
        status, summary = self._service.job_outcome(job.reference)  # type: ignore[attr-defined]
        return JobOutcome(
            _KNOWLEDGE_STATUS_TO_JOB.get(status, JobStatus.FAILED),
            summary,
        )

    def request_cancel(self, job: JobRow) -> None:
        cancel = getattr(self._service, "cancel_unit", None)
        if cancel is not None:
            cancel(job.reference)

    def capabilities(self, job: JobRow) -> JobCapabilities:
        return JobCapabilities(
            can_cancel=self._can_cancel,
            can_view_log=self._can_view_log,
        )


class KnowledgeImportHandler(_KnowledgeHandler):
    _kind = "import"
    _can_cancel = True
    _can_view_log = True

    def __init__(self, service: "KnowledgeImportService") -> None:
        super().__init__(service)


class KnowledgeDerivationHandler(_KnowledgeHandler):
    _kind = "content_preparation"

    def __init__(self, service: "KnowledgeDerivationService") -> None:
        super().__init__(service)


class KnowledgeIndexHandler(_KnowledgeHandler):
    _kind = "index_build"

    def __init__(self, service: "KnowledgeIndexService") -> None:
        super().__init__(service)


__all__ = [
    "KnowledgeDerivationHandler",
    "KnowledgeImportHandler",
    "KnowledgeIndexHandler",
]
