from __future__ import annotations

from datetime import datetime, timezone

import pytest
from PySide6.QtWidgets import QApplication

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.job_scheduler import JobCapabilities
from xenix.services.job_service import JobDomain, JobItem, JobQueryService, JobStatus
from xenix.services.storage import StorageBootstrapService
from xenix.ui.job_center import JOB_PAGE_SIZE, JobCenterDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _FakeScheduler:
    def __init__(self, *, can_cancel: bool = True) -> None:
        self.can_cancel = can_cancel
        self.cancelled: list[tuple[JobDomain, str]] = []

    def capabilities(self, domain: JobDomain, reference: str) -> JobCapabilities:
        return JobCapabilities(can_cancel=self.can_cancel)

    def request_cancel(self, domain: JobDomain, reference: str) -> None:
        self.cancelled.append((domain, reference))


def _job_item() -> JobItem:
    return JobItem(
        reference="ml:ml-1",
        raw_reference="ml-1",
        domain=JobDomain.ML,
        kind="fit",
        target="Quarterly sales",
        status=JobStatus.QUEUED,
        phase="queued",
        updated_at=datetime.now(timezone.utc),
    )


def test_job_center_cancel_routes_to_scheduler(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    scheduler = _FakeScheduler(can_cancel=True)
    dialog = JobCenterDialog(
        JobQueryService(storage.session_factory),
        scheduler=scheduler,
    )

    dialog._render_jobs([_job_item()])
    dialog._table.selectRow(0)
    assert dialog._cancel_button.isEnabled()

    dialog._cancel_button.click()

    assert scheduler.cancelled == [(JobDomain.ML, "ml-1")]
    dialog.shutdown()
    storage.engine.dispose()


def test_job_center_disables_cancel_when_not_cancellable(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    scheduler = _FakeScheduler(can_cancel=False)
    dialog = JobCenterDialog(
        JobQueryService(storage.session_factory),
        scheduler=scheduler,
    )

    dialog._render_jobs([_job_item()])
    dialog._table.selectRow(0)

    assert not dialog._cancel_button.isEnabled()
    dialog._cancel_button.click()
    assert scheduler.cancelled == []
    dialog.shutdown()
    storage.engine.dispose()


def test_job_center_load_more_reveals_lazy_page(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    dialog = JobCenterDialog(JobQueryService(storage.session_factory))

    # Below a full page the lazy-load control stays hidden.
    dialog._render_jobs([_job_item()])
    assert dialog._load_more_button.isHidden()

    # A full page signals that more rows may exist.
    dialog._render_jobs([_job_item() for _ in range(JOB_PAGE_SIZE)])
    assert not dialog._load_more_button.isHidden()

    before = dialog._limit
    dialog._load_more()
    assert dialog._limit == before + JOB_PAGE_SIZE

    dialog.shutdown()
    storage.engine.dispose()
