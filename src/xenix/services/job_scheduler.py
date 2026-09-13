from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, col, select

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

    @property
    def domain(self) -> JobDomain: ...

    @property
    def kind(self) -> str | None: ...

    @property
    def concurrency_limit(self) -> int: ...

    def recover(self, session: Session, jobs: list[JobRow]) -> list[int]:
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


LOGGER = logging.getLogger(__name__)
_TERMINAL_STATUSES = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


class JobScheduler:
    """Cross-domain job scheduler: owns the queue, dispatch, and lifecycle vocabulary."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handlers: Iterable[JobHandler],
    ) -> None:
        self._session_factory = session_factory
        self._handlers: dict[tuple[JobDomain, str | None], JobHandler] = {}
        self._lock = threading.Condition()
        self._stop = threading.Event()
        self._armed: set[tuple[JobDomain, int]] = set()
        self._active_counts: dict[JobDomain, int] = {}
        self._dispatch_thread: threading.Thread | None = None
        self._worker_threads: set[threading.Thread] = set()
        for handler in handlers:
            self.register_handler(handler)

    def register_handler(self, handler: JobHandler) -> None:
        """Register a kind before start; ``kind=None`` owns the whole domain.

        Registration is frozen at start so recovery sees the complete graph.
        Multiple kinds share their domain's concurrency budget.
        """
        with self._lock:
            if self._dispatch_thread is not None or self._stop.is_set():
                raise RuntimeError("Job handlers must be registered before scheduler start.")
            key = (handler.domain, handler.kind)
            if key in self._handlers:
                if self._handlers[key] is handler:
                    return
                raise ValueError(f"Job handler already registered for {key!r}.")
            if any(
                domain == handler.domain and (kind is None or handler.kind is None) for domain, kind in self._handlers
            ):
                raise ValueError(f"Job handler overlaps the domain owner for {handler.domain.value!r}.")
            self._handlers[key] = handler
            self._active_counts.setdefault(handler.domain, 0)

    def start(self) -> None:
        """Recover persisted jobs, then begin dispatching armed queued work."""
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("A stopped JobScheduler cannot be restarted.")
            if self._dispatch_thread is not None:
                return
            for handler in self._handlers.values():
                self._recover_handler(handler)
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
        reference: int,
        *,
        phase: str = "queued",
        error_summary: str | None = None,
    ) -> int:
        """Register a unit of domain work as a queued job and arm it for dispatch."""
        # Serialize registration and claim/cancel in this process. The database
        # constraint remains the durable authority for (domain, reference).
        with self._lock, self._session_factory() as session:
            if self._stop.is_set():
                raise RuntimeError("Cannot enqueue work after scheduler shutdown.")
            if self._handler_for(domain, kind) is None:
                raise ValueError(f"No job handler registered for {domain.value!r}/{kind!r}.")
            existing = session.exec(
                select(JobRow).where(
                    JobRow.domain == domain,
                    JobRow.reference == reference,
                )
            ).first()
            if existing is not None:
                if existing.kind != kind:
                    raise ValueError("A job reference cannot change its kind.")
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
            self._armed.add((domain, reference))
            self._lock.notify_all()
        return job.id

    def capabilities(self, domain: JobDomain, reference: int) -> JobCapabilities:
        """Return the management capabilities for a specific job."""
        with self._session_factory() as session:
            job = self._find(session, domain, reference)
            if job is None:
                return JobCapabilities()
            handler = self._handler_for(domain, job.kind)
            return handler.capabilities(job) if handler is not None else JobCapabilities()

    def request_cancel(self, domain: JobDomain, reference: int) -> None:
        """Cancel a queued or running job through its domain handler."""
        with self._lock, self._session_factory() as session:
            job = self._find(session, domain, reference)
            if job is None or job.status in _TERMINAL_STATUSES:
                return
            handler = self._handler_for(domain, job.kind)
            if handler is None:
                return
            if job.status is JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                job.updated_at = utc_now()
                job.finished_at = utc_now()
                session.add(job)
            session.commit()
            self._armed.discard((domain, reference))
            self._lock.notify_all()
        handler.request_cancel(job)

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Wait for admitted workers and their runnable queue to become idle.

        Return False on timeout. Worker finalization precedes idle, but callers
        still inspect the persisted outcome to distinguish success from failure.
        Persisted jobs deliberately left unarmed by recovery do not prevent idle.
        This is a snapshot of quiescence, not a ban on later enqueue calls.
        """
        with self._lock:
            return self._lock.wait_for(
                lambda: not self._armed and not any(self._active_counts.values()),
                timeout=timeout,
            )

    def shutdown(self) -> None:
        with self._lock:
            self._stop.set()
            self._lock.notify_all()
            workers = tuple(self._worker_threads)
        deadline = time.monotonic() + 5.0
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=max(0.0, deadline - time.monotonic()))
        for worker in workers:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))
        pending = [worker.name for worker in workers if worker.is_alive()]
        if pending:
            LOGGER.warning("Job workers still running at shutdown: %s", pending)

    def _recover_handler(self, handler: JobHandler) -> None:
        with self._session_factory() as session:
            statement = select(JobRow).where(
                JobRow.domain == handler.domain,
                col(JobRow.status).in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            if handler.kind is not None:
                statement = statement.where(JobRow.kind == handler.kind)
            jobs = list(session.exec(statement))
            requeue = handler.recover(session, jobs)
            session.commit()
        self._armed.update((handler.domain, reference) for reference in requeue)

    def _dispatch_loop(self) -> None:
        # Test and wait under the same condition: enqueue/finish cannot lose a
        # wakeup between finding no work and sleeping. Idle needs no DB polling.
        with self._lock:
            while not self._stop.is_set():
                try:
                    if not self._dispatch_once():
                        self._lock.wait()
                except Exception:
                    LOGGER.exception("Job dispatch failed; retrying after a short delay")
                    self._lock.wait(timeout=0.2)

    def _dispatch_once(self) -> bool:
        dispatched = False
        for domain in self._active_counts:
            if not any(armed_domain == domain for armed_domain, _ in self._armed):
                continue
            limit = min(handler.concurrency_limit for handler in self._handlers.values() if handler.domain == domain)
            while self._active_counts[domain] < limit:
                job = self._claim_next(domain)
                if job is None:
                    break
                handler = self._handler_for(domain, job.kind)
                assert handler is not None
                self._start_worker(handler, job)
                dispatched = True
        return dispatched

    def _claim_next(self, domain: JobDomain) -> JobRow | None:
        with self._session_factory() as session:
            references = [reference for armed_domain, reference in self._armed if armed_domain == domain]
            if not references:
                return None
            row = session.exec(
                select(JobRow)
                .where(
                    JobRow.domain == domain,
                    JobRow.status == JobStatus.QUEUED,
                    col(JobRow.reference).in_(references),
                )
                .order_by(col(JobRow.created_at), col(JobRow.id))
                .limit(1)
            ).first()
            if row is not None:
                row.status = JobStatus.RUNNING
                row.started_at = utc_now()
                row.updated_at = utc_now()
                session.add(row)
                session.commit()
                self._armed.discard((domain, row.reference))
                return row
            self._armed.difference_update((domain, reference) for reference in references)
            return None

    def _start_worker(self, handler: JobHandler, job: JobRow) -> None:
        self._active_counts[handler.domain] += 1
        worker = threading.Thread(
            target=self._run_worker,
            args=(handler, job.domain, job.reference),
            name=f"xenix-job-{job.reference}",
            daemon=True,
        )
        self._worker_threads.add(worker)
        worker.start()

    def _run_worker(
        self,
        handler: JobHandler,
        domain: JobDomain,
        reference: int,
    ) -> None:
        try:
            with self._session_factory() as session:
                job = self._find(session, domain, reference)
                if job is None:
                    return
            try:
                outcome = handler.run(job)
                if outcome.status not in _TERMINAL_STATUSES:
                    raise ValueError(f"Job handler returned nonterminal outcome {outcome.status.value!r}.")
            except Exception as exc:
                LOGGER.exception("Job handler failed: %s/%s", domain.value, reference)
                outcome = JobOutcome(status=JobStatus.FAILED, error_summary=str(exc))
            with self._session_factory() as session:
                job = self._find(session, domain, reference)
                if job is None:
                    return
                job.status = outcome.status
                job.error_summary = outcome.error_summary
                job.finished_at = utc_now()
                job.updated_at = utc_now()
                session.add(job)
                session.commit()
        except Exception:
            LOGGER.exception("Unable to persist job outcome: %s/%s", domain.value, reference)
        finally:
            with self._lock:
                self._active_counts[domain] -= 1
                self._worker_threads.discard(threading.current_thread())
                self._lock.notify_all()

    def _handler_for(self, domain: JobDomain, kind: str) -> JobHandler | None:
        return self._handlers.get((domain, kind)) or self._handlers.get((domain, None))

    @staticmethod
    def _find(
        session: Session,
        domain: JobDomain,
        reference: int,
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
