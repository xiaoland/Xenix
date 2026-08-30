from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, col, select

from .knowledge_task_query import KnowledgeTaskQueryService
from .storage.models import DatasetRow, JobDomain, JobStatus, MLTaskRow


@dataclass(frozen=True)
class JobItem:
    """Stable presentation projection over a domain-owned unit of work."""

    reference: str
    domain: JobDomain
    kind: str
    target: str
    status: JobStatus
    phase: str
    updated_at: datetime
    error_summary: str | None = None

    @property
    def active(self) -> bool:
        return self.status in {JobStatus.QUEUED, JobStatus.RUNNING}


class JobQueryService:
    """Read-only, cross-domain job feed.

    Lifecycle authority deliberately remains with the originating Knowledge or ML
    service. This service provides one vocabulary for consumers such as the GUI.
    """

    _MAX_LIMIT = 500

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        knowledge_tasks: KnowledgeTaskQueryService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._knowledge_tasks = knowledge_tasks or KnowledgeTaskQueryService(session_factory)

    def list_jobs(
        self,
        *,
        domain: JobDomain | None = None,
        status: JobStatus | None = None,
        search: str = "",
        limit: int = 200,
    ) -> list[JobItem]:
        bounded_limit = max(1, min(int(limit), self._MAX_LIMIT))
        jobs: list[JobItem] = []
        if domain in {None, JobDomain.KNOWLEDGE}:
            jobs.extend(self._knowledge_jobs())
        if domain in {None, JobDomain.ML}:
            jobs.extend(self._ml_jobs())

        normalized_search = search.strip().casefold()
        if status is not None:
            jobs = [job for job in jobs if job.status is status]
        if normalized_search:
            jobs = [
                job
                for job in jobs
                if normalized_search
                in " ".join((job.reference, job.domain.value, job.kind, job.target, job.phase)).casefold()
            ]
        jobs.sort(key=lambda job: (job.updated_at, job.reference), reverse=True)
        return jobs[:bounded_limit]

    def _knowledge_jobs(self) -> list[JobItem]:
        return [
            JobItem(
                reference=f"knowledge:{task.reference}",
                domain=JobDomain.KNOWLEDGE,
                kind=task.kind,
                target=task.target,
                status=_knowledge_status(task.status),
                phase=task.phase,
                updated_at=task.updated_at,
                error_summary=task.error_summary or task.error_code,
            )
            for task in self._knowledge_tasks.list_tasks(limit=self._MAX_LIMIT)
        ]

    def _ml_jobs(self) -> list[JobItem]:
        with self._session_factory() as session:
            tasks = list(
                session.exec(
                    select(MLTaskRow)
                    .order_by(col(MLTaskRow.updated_at).desc(), col(MLTaskRow.id).desc())
                    .limit(self._MAX_LIMIT)
                )
            )
            dataset_ids = {task.dataset_id for task in tasks if task.dataset_id}
            datasets = (
                {
                    row.id: row.name
                    for row in session.exec(select(DatasetRow).where(col(DatasetRow.id).in_(dataset_ids)))
                }
                if dataset_ids
                else {}
            )

        return [
            JobItem(
                reference=f"ml:{task.id}",
                domain=JobDomain.ML,
                kind=task.task_type.value,
                target=(
                    datasets.get(task.dataset_id, task.dataset_id) if task.dataset_id is not None else task.project_id
                ),
                status=_ml_status(task.status.value),
                phase=task.status.value,
                updated_at=task.updated_at,
                error_summary=task.error_summary,
            )
            for task in tasks
        ]


_KNOWLEDGE_SUCCESS_STATUSES = frozenset(
    {"succeeded", "canonical_ready", "retrieval_ready", "reused"}
)


def _knowledge_status(status: str) -> JobStatus:
    if status in {"pending", "queued"}:
        return JobStatus.QUEUED
    if status == "running":
        return JobStatus.RUNNING
    if status in {"failed", "needs_attention"}:
        return JobStatus.FAILED
    if status == "cancelled":
        return JobStatus.CANCELLED
    if status in _KNOWLEDGE_SUCCESS_STATUSES:
        return JobStatus.SUCCEEDED
    raise ValueError(f"Unrecognized Knowledge task status: {status!r}")


def _ml_status(status: str) -> JobStatus:
    if status == "pending":
        return JobStatus.QUEUED
    if status in {"running", "succeeded", "failed", "cancelled"}:
        return JobStatus(status)
    raise ValueError(f"Unrecognized ML task status: {status!r}")


__all__ = ["JobDomain", "JobItem", "JobQueryService", "JobStatus"]
