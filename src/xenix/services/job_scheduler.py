from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select

from .storage.models import JobDomain, JobRow, JobStatus, utc_now


@dataclass(frozen=True)
class JobCapabilities:
    can_cancel: bool = False
    can_retry: bool = False
    can_view_log: bool = False


@dataclass(frozen=True)
class JobOutcome:
    status: JobStatus
    error_summary: str | None = None


class JobHandler(Protocol):
    """Domain adapter executed by the JobScheduler.

    The scheduler owns queueing, dispatch, concurrency, and JobRow status. A
    handler owns its domain row lifecycle and reports a terminal JobOutcome.
    """

    domain: JobDomain
    concurrency_limit: int

    def recover(self, session: Session, jobs: list[JobRow]) -> list[str]:
        """Reconcile queued/running jobs after restart; return references to dispatch."""
        ...

    def run(self, job: JobRow) -> JobOutcome:
        """Execute one job's domain work and return its terminal outcome."""
        ...

    def request_cancel(self, job: JobRow) -> None:
        """Signal the domain to cancel this job's work."""
        ...

    def capabilities(self, job: JobRow) -> JobCapabilities:
        """Describe which management actions this job supports."""
        ...


_POLL_INTERVAL_SECONDS = 0.2


class JobScheduler:
    """Cross-domain job scheduler: owns the queue, dispatch, and lifecycle vocabulary."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handlers: Iterable[JobHandler],
    ) -> None:
        self._session_factory = session_factory
        self._handlers: dict[JobDomain, JobHandler] = {
            handler.domain: handler for handler in handlers
        }
        self._lock = threading.Condition()
        self._stop = threading.Event()
        self._armed: set[str] = set()
        self._active_counts: dict[JobDomain, int] = {
            domain: 0 for domain in self._handlers
        }
        self._dispatch_thread: threading.Thread | None = None
        self._worker_threads: set[threading.Thread] = set()

    def register_handler(self, handler: JobHandler) -> None:
        """Add or replace a domain handler after construction."""
        with self._lock:
            self._handlers[handler.domain] = handler
            self._active_counts.setdefault(handler.domain, 0)
            self._lock.notify()

    def start(self) -> None:
        """Recover persisted jobs, then begin dispatching armed queued work."""
        requeue = self._recover()
        with self._lock:
            self._armed.update(requeue)
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="xenix-job-dispatcher",
            daemon=True,
        )
        self._dispatch_thread.start()

    def enqueue(
        self,
        domain: JobDomain,
        kind: str,
        reference: str,
        *,
        phase: str = "queued",
        error_summary: str | None = None,
    ) -> str:
        """Register a unit of domain work as a queued job and arm it for dispatch."""
        if domain not in self._handlers:
            raise ValueError(f"No job handler registered for domain {domain.value!r}.")
        with self._session_factory() as session:
            existing = session.exec(
                select(JobRow).where(
                    JobRow.domain == domain,
                    JobRow.reference == reference,
                )
            ).first()
            if existing is not None:
                return existing.id
            job = JobRow(
                domain=domain,
                kind=kind,
                reference=reference,
                status=JobStatus.QUEUED,
                phase=phase,
                error_summary=error_summary,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(job)
            session.commit()
        with self._lock:
            self._armed.add(reference)
            self._lock.notify()
        return job.id

    def request_cancel(self, domain: JobDomain, reference: str) -> None:
        """Cancel a queued or running job through its domain handler."""
        handler = self._handlers.get(domain)
        if handler is None:
            return
        with self._session_factory() as session:
            job = self._find(session, domain, reference)
            if job is None:
                return
            if job.status is JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                job.updated_at = utc_now()
                job.finished_at = utc_now()
                session.add(job)
            session.commit()
        handler.request_cancel(job)
        with self._lock:
            self._armed.discard(reference)
            self._lock.notify()

    def shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            self._lock.notify_all()
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=5.0)
        for worker in list(self._worker_threads):
            worker.join(timeout=5.0)

    def _recover(self) -> list[str]:
        requeue: list[str] = []
        for handler in list(self._handlers.values()):
            requeue.extend(self._recover_handler_locked(handler))
        return requeue

    def _recover_handler_locked(self, handler: JobHandler) -> list[str]:
        requeue: list[str] = []
        with self._session_factory() as session:
            jobs = list(
                session.exec(
                    select(JobRow).where(
                        JobRow.domain == handler.domain,
                        JobRow.status.in_(
                            [JobStatus.QUEUED, JobStatus.RUNNING]
                        ),
                    )
                )
            )
            requeue.extend(handler.recover(session, jobs))
            session.commit()
        return requeue

    def recover_handler(self, handler: JobHandler) -> None:
        """Run recovery for a handler registered after startup and arm its jobs."""
        requeue = self._recover_handler_locked(handler)
        with self._lock:
            self._armed.update(requeue)
            self._lock.notify()

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            dispatched = self._dispatch_once()
            with self._lock:
                if not dispatched and not self._stop.is_set():
                    self._lock.wait(timeout=_POLL_INTERVAL_SECONDS)

    def _dispatch_once(self) -> bool:
        with self._lock:
            if not self._armed:
                return False
        dispatched = False
        for handler in self._handlers.values():
            limit = handler.concurrency_limit
            while self._active_counts.get(handler.domain, 0) < limit:
                job = self._claim_next(handler.domain)
                if job is None:
                    break
                self._start_worker(handler, job)
                dispatched = True
        return dispatched

    def _claim_next(self, domain: JobDomain) -> JobRow | None:
        with self._session_factory() as session:
            with self._lock:
                armed = set(self._armed)
            rows = list(
                session.exec(
                    select(JobRow)
                    .where(
                        JobRow.domain == domain,
                        JobRow.status == JobStatus.QUEUED,
                    )
                    .order_by(JobRow.created_at, JobRow.id)
                    .limit(1000)
                )
            )
            for row in rows:
                if row.reference not in armed:
                    continue
                row.status = JobStatus.RUNNING
                row.started_at = utc_now()
                row.updated_at = utc_now()
                session.add(row)
                session.commit()
                return row
            return None

    def _start_worker(self, handler: JobHandler, job: JobRow) -> None:
        with self._lock:
            self._active_counts[handler.domain] = (
                self._active_counts.get(handler.domain, 0) + 1
            )
        worker = threading.Thread(
            target=self._run_worker,
            args=(handler, job.domain, job.reference),
            name=f"xenix-job-{job.reference[:8]}",
            daemon=True,
        )
        self._worker_threads.add(worker)
        worker.start()

    def _run_worker(
        self,
        handler: JobHandler,
        domain: JobDomain,
        reference: str,
    ) -> None:
        try:
            with self._session_factory() as session:
                job = self._find(session, domain, reference)
                if job is None:
                    return
                try:
                    outcome = handler.run(job)
                except Exception as exc:  # pragma: no cover - exercised via fakes
                    outcome = JobOutcome(
                        status=JobStatus.FAILED,
                        error_summary=str(exc),
                    )
                job.status = outcome.status
                job.error_summary = outcome.error_summary
                job.finished_at = utc_now()
                job.updated_at = utc_now()
                session.add(job)
                session.commit()
        finally:
            with self._lock:
                self._active_counts[domain] = max(
                    0, self._active_counts.get(domain, 0) - 1
                )
                self._armed.discard(reference)
                self._lock.notify()
            self._worker_threads.discard(threading.current_thread())

    @staticmethod
    def _find(
        session: Session,
        domain: JobDomain,
        reference: str,
    ) -> JobRow | None:
        return session.exec(
            select(JobRow).where(
                JobRow.domain == domain,
                JobRow.reference == reference,
            )
        ).first()


__all__ = [
    "JobCapabilities",
    "JobHandler",
    "JobOutcome",
    "JobScheduler",
]
