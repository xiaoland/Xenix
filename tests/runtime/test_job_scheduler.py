from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from sqlmodel import select

from xenix.services.job_scheduler import JobCapabilities, JobOutcome, JobScheduler
from xenix.services.storage.models import JobDomain, JobRow, JobStatus, utc_now


class FakeHandler:
    def __init__(self, domain=JobDomain.ML, *, kind=None, replay=False):
        self.domain = domain
        self.kind = kind
        self.concurrency_limit = 1
        self.replay = replay
        self.runs = []
        self.cancels = []
        self.recovered_jobs = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.error = None

    def recover(self, session, jobs):
        self.recovered_jobs = [job.reference for job in jobs]
        if not self.replay:
            return []
        for job in jobs:
            job.status = JobStatus.QUEUED
            session.add(job)
        return list(self.recovered_jobs)

    def run(self, job):
        self.runs.append(job.reference)
        self.entered.set()
        assert self.release.wait(5), "Test did not release the admitted worker"
        if self.error:
            raise self.error
        return JobOutcome(JobStatus.CANCELLED if job.reference in self.cancels else JobStatus.SUCCEEDED)

    def request_cancel(self, job):
        self.cancels.append(job.reference)
        self.release.set()

    def capabilities(self, job):
        return JobCapabilities(can_cancel=True)


@pytest.fixture
def scheduler_factory(storage):
    schedulers = []

    def create(*handlers):
        scheduler = JobScheduler(storage.session_factory, handlers)
        schedulers.append((scheduler, handlers))
        return scheduler

    yield create
    for scheduler, handlers in reversed(schedulers):
        for handler in handlers:
            handler.release.set()
        scheduler.shutdown()


def _job(storage, domain, reference):
    with storage.session_factory() as session:
        return session.exec(select(JobRow).where(JobRow.domain == domain, JobRow.reference == reference)).one()


def test_fifo_and_concurrency_share_one_budget_across_kinds(storage, scheduler_factory):
    first = FakeHandler(JobDomain.KNOWLEDGE, kind="import")
    second = FakeHandler(JobDomain.KNOWLEDGE, kind="index_build")
    first.release.clear()
    scheduler = scheduler_factory(first, second)
    scheduler.enqueue(JobDomain.KNOWLEDGE, "index_build", "second")
    scheduler.enqueue(JobDomain.KNOWLEDGE, "import", "first")
    # Establish FIFO independently of wall-clock speed and randomly generated IDs.
    with storage.session_factory() as session:
        job = session.exec(select(JobRow).where(JobRow.reference == "first")).one()
        job.created_at = utc_now() - timedelta(days=1)
        session.add(job)
        session.commit()
    scheduler.start()
    assert first.entered.wait(5)
    assert _job(storage, JobDomain.KNOWLEDGE, "second").status is JobStatus.QUEUED
    assert not second.entered.is_set()
    first.release.set()
    assert scheduler.wait_idle(5)
    assert first.runs == ["first"]
    assert second.runs == ["second"]
    assert _job(storage, JobDomain.KNOWLEDGE, "second").status is JobStatus.SUCCEEDED


def test_cancel_is_scoped_to_domain_and_queued_work_never_runs(storage, scheduler_factory):
    ml = FakeHandler()
    knowledge = FakeHandler(JobDomain.KNOWLEDGE)
    scheduler = scheduler_factory(ml, knowledge)
    scheduler.enqueue(JobDomain.ML, "fit", "same-reference")
    scheduler.enqueue(JobDomain.KNOWLEDGE, "import", "same-reference")
    scheduler.request_cancel(JobDomain.ML, "same-reference")
    scheduler.start()
    assert scheduler.wait_idle(5)
    assert ml.runs == []
    assert ml.cancels == ["same-reference"]
    assert knowledge.runs == ["same-reference"]
    assert _job(storage, JobDomain.ML, "same-reference").status is JobStatus.CANCELLED
    assert _job(storage, JobDomain.KNOWLEDGE, "same-reference").status is JobStatus.SUCCEEDED


def test_cancel_running_work_persists_outcome_before_idle(storage, scheduler_factory):
    handler = FakeHandler()
    handler.release.clear()
    scheduler = scheduler_factory(handler)
    scheduler.start()
    scheduler.enqueue(JobDomain.ML, "fit", "running")
    assert handler.entered.wait(5)
    scheduler.request_cancel(JobDomain.ML, "running")
    assert scheduler.wait_idle(5)
    assert _job(storage, JobDomain.ML, "running").status is JobStatus.CANCELLED
    scheduler.request_cancel(JobDomain.ML, "running")
    assert handler.cancels == ["running"]


def test_recovery_routes_only_owned_kinds_and_preserves_ml_orphans(storage, scheduler_factory):
    ml = FakeHandler()
    imports = FakeHandler(JobDomain.KNOWLEDGE, kind="import", replay=True)
    index = FakeHandler(JobDomain.KNOWLEDGE, kind="index_build", replay=True)
    with storage.session_factory() as session:
        session.add_all(
            [
                JobRow(domain=JobDomain.ML, kind="fit", reference="ml-old", status=JobStatus.RUNNING),
                JobRow(domain=JobDomain.KNOWLEDGE, kind="import", reference="import-old", status=JobStatus.RUNNING),
                JobRow(domain=JobDomain.KNOWLEDGE, kind="index_build", reference="index-old", status=JobStatus.QUEUED),
            ]
        )
        session.commit()
    scheduler = scheduler_factory(ml, imports, index)
    scheduler.start()
    scheduler.start()
    assert scheduler.wait_idle(5)
    assert ml.runs == []
    assert imports.recovered_jobs == imports.runs == ["import-old"]
    assert index.recovered_jobs == index.runs == ["index-old"]
    assert _job(storage, JobDomain.ML, "ml-old").status is JobStatus.RUNNING


def test_new_work_is_not_starved_by_a_thousand_unarmed_orphans(storage, scheduler_factory):
    with storage.session_factory() as session:
        session.add_all(
            [
                JobRow(domain=JobDomain.ML, kind="fit", reference=f"orphan-{i}", status=JobStatus.QUEUED)
                for i in range(1001)
            ]
        )
        session.commit()
    handler = FakeHandler()
    scheduler = scheduler_factory(handler)
    scheduler.start()
    job_id = scheduler.enqueue(JobDomain.ML, "fit", "new-work")
    assert scheduler.enqueue(JobDomain.ML, "fit", "new-work") == job_id
    assert scheduler.wait_idle(5)
    assert handler.runs == ["new-work"]
    assert _job(storage, JobDomain.ML, "new-work").status is JobStatus.SUCCEEDED


def test_handler_failure_is_observable_and_does_not_block_later_work(storage, scheduler_factory, caplog):
    handler = FakeHandler()
    handler.error = RuntimeError("domain work failed")
    scheduler = scheduler_factory(handler)
    scheduler.start()
    scheduler.enqueue(JobDomain.ML, "fit", "failure")
    assert scheduler.wait_idle(5)
    failed = _job(storage, JobDomain.ML, "failure")
    assert failed.status is JobStatus.FAILED
    assert failed.error_summary == "domain work failed"
    assert "domain work failed" in caplog.text
    handler.error = None
    scheduler.enqueue(JobDomain.ML, "fit", "next")
    assert scheduler.wait_idle(5)
    assert _job(storage, JobDomain.ML, "next").status is JobStatus.SUCCEEDED
