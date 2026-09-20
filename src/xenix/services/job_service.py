from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, col, select

from .job_status import knowledge_job_status, ml_job_status
from .knowledge_task_query import KnowledgeTaskQueryService
from .storage.models import ConversationThreadRow, DatasetRow, JobDomain, JobStatus, MLTaskRow
from .audit_contracts import AuditScope


@dataclass(frozen=True)
class JobItem:
    """Stable presentation projection over a domain-owned unit of work."""

    reference: str
    raw_reference: int
    domain: JobDomain
    kind: str
    target: str
    status: JobStatus
    phase: str
    updated_at: datetime
    error_summary: str | None = None
    thread_id: int | None = None
    thread_title: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.status in {JobStatus.QUEUED, JobStatus.RUNNING}


class JobQueryService:
    """Read-only, cross-domain job feed.

    Lifecycle authority deliberately remains with the originating Knowledge or ML
    service. This service provides one vocabulary for consumers such as the GUI.
    """

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
        domain: JobDomain | str | None = None,
        status: JobStatus | str | None = None,
        search: str = "",
        limit: int = 200,
        scope: AuditScope | None = None,
    ) -> list[JobItem]:
        if scope is not None and not scope.all_threads and scope.thread_id is None:
            return []
        bounded_limit = max(1, int(limit))
        jobs: list[JobItem] = []
        if domain in {None, JobDomain.KNOWLEDGE}:
            jobs.extend(self._knowledge_jobs())
        if domain in {None, JobDomain.ML}:
            jobs.extend(self._ml_jobs())

        if scope is not None and not scope.all_threads:
            jobs = [job for job in jobs if job.thread_id == scope.thread_id]
        normalized_search = search.strip().casefold()
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
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
                raw_reference=(task.import_id if task.kind == "import" else task.owner_id),
                domain=JobDomain.KNOWLEDGE,
                kind=task.kind,
                target=task.target,
                status=knowledge_job_status(task.status),
                phase=task.phase,
                updated_at=task.updated_at,
                error_summary=task.error_summary or task.error_code,
            )
            for task in self._knowledge_tasks.list_tasks(limit=None)
        ]

    def _ml_jobs(self) -> list[JobItem]:
        with self._session_factory() as session:
            tasks = list(
                session.exec(
                    select(MLTaskRow)
                    .order_by(col(MLTaskRow.updated_at).desc(), col(MLTaskRow.id).desc())
                )
            )
            threads = {row.id: row.title for row in session.exec(select(ConversationThreadRow))}
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
                raw_reference=task.id,
                domain=JobDomain.ML,
                kind=task.task_type.value,
                target=(
                    datasets.get(task.dataset_id, str(task.dataset_id)) if task.dataset_id is not None else str(task.project_id)
                ),
                status=ml_job_status(task.status.value),
                phase=task.status.value,
                updated_at=task.updated_at,
                error_summary=task.error_summary,
                thread_id=task.origin_thread_id, thread_title=(threads.get(task.origin_thread_id) or f"#{task.origin_thread_id}") if task.origin_thread_id in threads else None,
                started_at=task.started_at, finished_at=task.finished_at,
            )
            for task in tasks
        ]


__all__ = ["JobDomain", "JobItem", "JobQueryService", "JobStatus"]
