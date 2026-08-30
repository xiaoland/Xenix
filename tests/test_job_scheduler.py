from __future__ import annotations

import threading
import time
from collections.abc import Callable

from sqlmodel import select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.job_scheduler import (
    JobCapabilities,
    JobOutcome,
    JobScheduler,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import JobDomain, JobRow, JobStatus


def _wait_until(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class FakeHandler:
    def __init__(self, domain: JobDomain, concurrency_limit: int = 1) -> None:
        self.domain = domain
        self.concurrency_limit = concurrency_limit
        self.recover_result: list[str] = []
        self.outcomes: dict[str, JobOutcome] = {}
        self.runs: list[str] = []
        self.cancels: list[str] = []
        self.recovered_jobs: list[list[str]] = []
        self._gate: threading.Event | None = None
        self._cancel_event: threading.Event | None = None

    def recover(self, session, jobs: list[JobRow]) -> list[str]:
        self.recovered_jobs.append([job.reference for job in jobs])
        return list(self.recover_result)

    def run(self, job: JobRow) -> JobOutcome:
        self.runs.append(job.reference)
        if self._gate is not None:
            while True:
                if self._cancel_event is not None and self._cancel_event.is_set():
                    return JobOutcome(JobStatus.CANCELLED)
                if self._gate.wait(timeout=0.01):
                    break
        return self.outcomes.get(job.reference, JobOutcome(JobStatus.SUCCEEDED))

    def request_cancel(self, job: JobRow) -> None:
        self.cancels.append(job.reference)
        if self._cancel_event is not None:
            self._cancel_event.set()

    def capabilities(self, job: JobRow) -> JobCapabilities:
        return JobCapabilities(can_cancel=True)


class KnowledgeRecoverHandler(FakeHandler):
    def recover(self, session, jobs: list[JobRow]) -> list[str]:
        references = []
        for job in jobs:
            if job.status is JobStatus.RUNNING:
                job.status = JobStatus.QUEUED
                job.updated_at = job.updated_at
                session.add(job)
            references.append(job.reference)
        return references


def _bootstrap(monkeypatch, tmp_path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    return StorageBootstrapService().initialize(paths)


def _seed_job(session, domain: JobDomain, reference: str, status: JobStatus) -> None:
    session.add(
        JobRow(
            domain=domain,
            kind="test",
            reference=reference,
            status=status,
            phase=status.value,
        )
    )
    session.commit()


def _job_status(storage, domain: JobDomain, reference: str) -> JobStatus:
    with storage.session_factory() as session:
        job = session.exec(
            select(JobRow).where(
                JobRow.domain == domain,
                JobRow.reference == reference,
            )
        ).first()
        return job.status


def test_scheduler_dispatches_fifo_within_domain(monkeypatch, tmp_path) -> None:
    storage = _bootstrap(monkeypatch, tmp_path)
    handler = FakeHandler(JobDomain.ML)
    scheduler = JobScheduler(storage.session_factory, [handler])
    scheduler.start()
    for reference in ("ml-a", "ml-b", "ml-c"):
        scheduler.enqueue(JobDomain.ML, "fit", reference)
        time.sleep(0.02)

    assert _wait_until(lambda: len(handler.runs) == 3)
    assert handler.runs == ["ml-a", "ml-b", "ml-c"]
    for reference in handler.runs:
        assert _job_status(storage, JobDomain.ML, reference) is JobStatus.SUCCEEDED
    scheduler.shutdown()
    storage.engine.dispose()


def test_per_domain_concurrency_limit_blocks_second_job(monkeypatch, tmp_path) -> None:
    storage = _bootstrap(monkeypatch, tmp_path)
    handler = FakeHandler(JobDomain.ML, concurrency_limit=1)
    handler._gate = threading.Event()
    scheduler = JobScheduler(storage.session_factory, [handler])
    scheduler.start()
    scheduler.enqueue(JobDomain.ML, "fit", "ml-first")
    scheduler.enqueue(JobDomain.ML, "fit", "ml-second")

    assert _wait_until(lambda: len(handler.runs) == 1)
    assert handler.runs == ["ml-first"]

    handler._gate.set()
    assert _wait_until(lambda: len(handler.runs) == 2)
    assert handler.runs == ["ml-first", "ml-second"]
    scheduler.shutdown()
    storage.engine.dispose()


def test_cancel_queued_job_never_runs(monkeypatch, tmp_path) -> None:
    storage = _bootstrap(monkeypatch, tmp_path)
    handler = FakeHandler(JobDomain.ML)
    scheduler = JobScheduler(storage.session_factory, [handler])
    scheduler.enqueue(JobDomain.ML, "fit", "ml-queued")

    scheduler.request_cancel(JobDomain.ML, "ml-queued")

    assert handler.runs == []
    assert handler.cancels == ["ml-queued"]
    assert _job_status(storage, JobDomain.ML, "ml-queued") is JobStatus.CANCELLED
    scheduler.shutdown()
    storage.engine.dispose()


def test_cancel_running_job_reports_cancelled(monkeypatch, tmp_path) -> None:
    storage = _bootstrap(monkeypatch, tmp_path)
    handler = FakeHandler(JobDomain.ML)
    handler._gate = threading.Event()
    handler._cancel_event = threading.Event()
    scheduler = JobScheduler(storage.session_factory, [handler])
    scheduler.start()
    scheduler.enqueue(JobDomain.ML, "fit", "ml-running")

    assert _wait_until(lambda: len(handler.runs) == 1)
    scheduler.request_cancel(JobDomain.ML, "ml-running")

    assert _wait_until(
        lambda: _job_status(storage, JobDomain.ML, "ml-running")
        is JobStatus.CANCELLED
    )
    assert handler.cancels == ["ml-running"]
    scheduler.shutdown()
    storage.engine.dispose()


def test_recovery_applies_per_domain_policy(monkeypatch, tmp_path) -> None:
    storage = _bootstrap(monkeypatch, tmp_path)
    ml_handler = FakeHandler(JobDomain.ML)
    kb_handler = KnowledgeRecoverHandler(JobDomain.KNOWLEDGE)
    with storage.session_factory() as session:
        _seed_job(session, JobDomain.ML, "ml-queued", JobStatus.QUEUED)
        _seed_job(session, JobDomain.ML, "ml-running", JobStatus.RUNNING)
        _seed_job(session, JobDomain.KNOWLEDGE, "kb-queued", JobStatus.QUEUED)
        _seed_job(session, JobDomain.KNOWLEDGE, "kb-running", JobStatus.RUNNING)

    scheduler = JobScheduler(storage.session_factory, [ml_handler, kb_handler])
    scheduler.start()

    assert _wait_until(lambda: len(kb_handler.runs) == 2)
    assert set(kb_handler.runs) == {"kb-queued", "kb-running"}
    assert ml_handler.runs == []

    # ML jobs remain permanent orphans: untouched by recovery and never dispatched.
    assert _job_status(storage, JobDomain.ML, "ml-queued") is JobStatus.QUEUED
    assert _job_status(storage, JobDomain.ML, "ml-running") is JobStatus.RUNNING
    assert _job_status(storage, JobDomain.KNOWLEDGE, "kb-queued") is JobStatus.SUCCEEDED
    assert _job_status(storage, JobDomain.KNOWLEDGE, "kb-running") is JobStatus.SUCCEEDED
    scheduler.shutdown()
    storage.engine.dispose()
