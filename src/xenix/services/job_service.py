from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from .audit_contracts import AuditScope
from .job_status import knowledge_job_status, ml_job_status
from .knowledge_task_query import KnowledgeTaskQueryService
from .storage.models import JobDomain, JobStatus
from .storage.repositories.ml_tasks import MLTaskRepository


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
        self._ml_tasks = MLTaskRepository()

    def list_jobs(
        self,
        *,
        domain: JobDomain | str | None = None,
        status: JobStatus | str | None = None,
        search: str = "",
        limit: int = 200,
        scope: AuditScope | None = None,
    ) -> list[JobItem]:
        current_thread_only = scope is not None and not scope.all_threads
        thread_id = scope.thread_id if scope is not None and current_thread_only else None
        if current_thread_only and thread_id is None:
            return []
        bounded_limit = max(1, int(limit))
        jobs: list[JobItem] = []
        # Knowledge tasks belong to a library, with no conversation provenance.
        if not current_thread_only and domain in {None, JobDomain.KNOWLEDGE}:
            jobs.extend(self._knowledge_jobs())
        if domain in {None, JobDomain.ML}:
            jobs.extend(self._ml_jobs(thread_id))

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
                # Import items always carry their import row's primary key, even when retry belongs to a derivation.
                raw_reference=cast(int, task.import_id) if task.kind == "import" else task.owner_id,
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

    def _ml_jobs(self, thread_id: int | None) -> list[JobItem]:
        with self._session_factory() as session:
            tasks = self._ml_tasks.list_for_job_feed(session, origin_thread_id=thread_id)

        return [
            JobItem(
                reference=f"ml:{task.id}",
                raw_reference=task.id,
                domain=JobDomain.ML,
                kind=task.task_type.value,
                target=(
                    dataset_name if dataset_name is not None
                    else str(task.dataset_id if task.dataset_id is not None else task.project_id)
                ),
                status=ml_job_status(task.status.value),
                phase=task.status.value,
                updated_at=task.updated_at,
                error_summary=task.error_summary,
                thread_id=task.origin_thread_id,
                thread_title=(title or f"#{joined_thread_id}") if joined_thread_id is not None else None,
                started_at=task.started_at,
                finished_at=task.finished_at,
            )
            for task, dataset_name, joined_thread_id, title in tasks
        ]


__all__ = ["JobDomain", "JobItem", "JobQueryService", "JobStatus"]
