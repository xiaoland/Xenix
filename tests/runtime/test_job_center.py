from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.job_detail_query import JobDetailQueryService
from xenix.services.job_scheduler import JobCapabilities
from xenix.services.job_service import JobDomain, JobItem, JobQueryService, JobStatus
from xenix.services.knowledge_task_logs import KnowledgeTaskLogStore
from xenix.services.ml.contracts import TaskLogEntry
from xenix.services.storage import StorageBootstrapService
from xenix.ui.job_center import JOB_PAGE_SIZE, JobCenterDialog


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


def test_job_center_filters_status_domain_and_search_through_qt(qtbot, storage, monkeypatch):
    service = JobQueryService(storage.session_factory)
    jobs = [replace(_job_item(), reference=f"ml:{status.value}", status=status) for status in JobStatus]
    knowledge = replace(
        _job_item(), reference="knowledge:failed", domain=JobDomain.KNOWLEDGE,
        status=JobStatus.FAILED, target="Policy.pdf",
    )
    monkeypatch.setattr(service, "_ml_jobs", lambda _thread_id: jobs)
    monkeypatch.setattr(service, "_knowledge_jobs", lambda: [knowledge])
    dialog = JobCenterDialog(service)
    qtbot.addWidget(dialog)

    def references():
        return {
            dialog._table.item(row, 0).data(Qt.ItemDataRole.UserRole).reference
            for row in range(dialog._table.rowCount())
        }

    from PySide6.QtCore import Qt
    try:
        dialog._scope_filter.setCurrentIndex(1)
        dialog.show()
        qtbot.waitUntil(lambda: dialog._table.rowCount() == 6)
        for status in JobStatus:
            dialog._status_filter.setCurrentIndex(dialog._status_filter.findData(status.value))
            expected = {f"ml:{status.value}"}
            if status == JobStatus.FAILED:
                expected.add(knowledge.reference)
            qtbot.waitUntil(lambda expected=expected: references() == expected)
        dialog._status_filter.setCurrentIndex(dialog._status_filter.findData(JobStatus.FAILED.value))
        dialog._domain_filter.setCurrentIndex(dialog._domain_filter.findData(JobDomain.KNOWLEDGE.value))
        dialog._search.setText("  POLICY  ")
        qtbot.waitUntil(lambda: references() == {knowledge.reference})
        dialog._search.setText("sales")
        qtbot.waitUntil(lambda: references() == set())
        dialog._domain_filter.setCurrentIndex(0)
        qtbot.waitUntil(lambda: references() == {"ml:failed"})
        dialog.retranslate_ui()
        qtbot.waitUntil(lambda: dialog._load is None)
        assert dialog._status_filter.currentData() == JobStatus.FAILED.value
        assert references() == {"ml:failed"}
        dialog._search.clear()
        dialog._status_filter.setCurrentIndex(0)
        qtbot.waitUntil(lambda: len(references()) == 6)
    finally:
        dialog.shutdown()


@pytest.mark.parametrize("kind", ["import", "content_preparation", "index_build"])
def test_job_center_reads_knowledge_and_ml_logs_through_the_same_view(qtbot, storage, monkeypatch, kind):
    service = JobQueryService(storage.session_factory)
    store = KnowledgeTaskLogStore(storage.paths)
    store.append(101, kind=kind, phase="work_phase", event_code="work_failed", level="error")
    [event] = store.read(101, kind=kind)
    knowledge = replace(
        _job_item(), reference=f"knowledge:{kind}:101", raw_reference=101, domain=JobDomain.KNOWLEDGE,
        kind=kind, status=JobStatus.FAILED, error_summary="Work failed.",
    )
    ml = replace(_job_item(), reference="ml:101", raw_reference=101, updated_at=knowledge.updated_at)
    ml_log = TaskLogEntry(timestamp=event.timestamp, level="WARNING", message="ML warning")
    details = JobDetailQueryService(
        storage.session_factory,
        read_ml_details=lambda _: SimpleNamespace(artifacts=[1], logs=[ml_log]),
        knowledge_logs=store,
    )
    monkeypatch.setattr(service, "_knowledge_jobs", lambda: [knowledge])
    monkeypatch.setattr(service, "_ml_jobs", lambda _: [ml])
    dialog = JobCenterDialog(service, read_details=details.read)
    qtbot.addWidget(dialog)
    log_text = dialog._logs._text.toPlainText
    try:
        dialog._scope_filter.setCurrentIndex(1)
        dialog.show()
        qtbot.waitUntil(lambda: log_text() == f"[{event.timestamp}] WARNING: ML warning")
        assert dialog._outputs_button.isEnabled()

        dialog._search.setText(knowledge.reference)
        qtbot.waitUntil(lambda: log_text() == f"[{event.timestamp}] ERROR: work phase — work failed")
        assert not dialog._outputs_button.isEnabled()
        assert "Work failed." in dialog._detail.toPlainText()

        store.append(101, kind=kind, phase="work_phase", event_code="new_event")
        dialog.refresh()
        qtbot.waitUntil(lambda: "INFO: work phase — new event" in log_text())
    finally:
        dialog.shutdown()


def test_job_center_cancel_routes_to_scheduler(qapp, monkeypatch, tmp_path) -> None:
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


def test_job_center_disables_cancel_when_not_cancellable(qapp, monkeypatch, tmp_path) -> None:
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


def test_job_center_load_more_reveals_lazy_page(qapp, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    dialog = JobCenterDialog(JobQueryService(storage.session_factory))

    # Below a full page the lazy-load control stays hidden.
    dialog._render_jobs([_job_item()])
    assert dialog._load_more_button.isHidden()

    # An exact full page has no extra result to load.
    dialog._render_jobs([_job_item() for _ in range(JOB_PAGE_SIZE)])
    assert dialog._load_more_button.isHidden()
    dialog._render_jobs([_job_item() for _ in range(JOB_PAGE_SIZE + 1)])
    assert not dialog._load_more_button.isHidden()
    assert dialog._table.rowCount() == JOB_PAGE_SIZE

    before = dialog._limit
    dialog._load_more()
    assert dialog._limit == before + JOB_PAGE_SIZE

    dialog.shutdown()
    storage.engine.dispose()
