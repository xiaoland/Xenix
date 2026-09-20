from threading import Event

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget

from scripts.ui_lab.audit_scenarios import SyntheticAudit
from tests.ui.scenario_adapter import attach_scenario
from xenix.services.audit_contracts import AuditReference
from xenix.ui.async_read import AsyncRead
from xenix.ui.audit_center import AuditCenterDialog


def test_read_channel_coalesces_and_discards_late_results(qtbot):
    owner = QWidget()
    qtbot.addWidget(owner)
    channel = AsyncRead(owner)
    entered, release = Event(), Event()
    delivered, executed = [], []
    channel.loaded.connect(delivered.append)

    def slow():
        entered.set()
        release.wait(3)
        return "old"

    try:
        channel.submit(slow)
        qtbot.waitUntil(entered.is_set)
        channel.submit(lambda: executed.append("obsolete"))
        channel.submit(lambda: "current")
        release.set()
        qtbot.waitUntil(lambda: delivered == ["current"])
        assert executed == []
    finally:
        release.set()
        channel.shutdown()


def test_explanation_evidence_back_and_missing_file(qtbot):
    service = SyntheticAudit()
    dialog = AuditCenterDialog(service=service, thread_id=201)
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(lambda: dialog._detail is not None)
        assert "平均偏差约 12 件" in dialog._pages[0].toPlainText()
        original = dialog._detail.summary.reference
        dialog._activate(QUrl("audit:dataset:102"))
        qtbot.waitUntil(lambda: dialog._detail is not None and dialog._detail.summary.reference.kind == "dataset")
        assert dialog._back.isVisible()
        dialog._back.click()
        qtbot.waitUntil(lambda: dialog._detail is not None and dialog._detail.summary.reference == original)
        service.details["model:105"].files[0].available = False
        dialog.refresh()
        qtbot.waitUntil(lambda: not dialog._open.isEnabled())
        dialog.set_thread_id(None)
        assert dialog._list.rowCount() == 0
        assert not dialog._open.isEnabled()
        assert dialog._pages[0].toPlainText() == ""
        dialog._scope.setCurrentIndex(1)
        qtbot.waitUntil(lambda: dialog._list.rowCount() == 2)
    finally:
        dialog.shutdown()


def test_center_navigation_routes_through_production_coordinator(qapp, qtbot):
    _spec, handle = attach_scenario(qapp, qtbot, "centers.navigation")
    jobs = handle.root
    jobs.show()
    qtbot.waitUntil(lambda: jobs._table.rowCount() == 3)
    coordinator = jobs._scenario_coordinator
    jobs.focus_task(103)
    qtbot.waitUntil(lambda: jobs._selected_reference() == "ml:103" and jobs._outputs_button.isEnabled())
    jobs._outputs_button.click()
    audit = coordinator._audit_center_dialog
    qtbot.waitUntil(lambda: audit._detail is not None)
    assert audit._detail.summary.reference == AuditReference(kind="model", id=105)
    opened = []
    coordinator.artifact_requested.connect(opened.append)
    audit._open.click()
    assert opened == ["artifact://111"]
    audit._job.click()
    assert coordinator._job_center_dialog is jobs
    assert jobs._search.text() == "ml:103"
    audit.hide()
    assert not audit._timer.isActive()
    handle.cleanup()


def test_failed_partial_output_and_read_retry_remain_distinct(qtbot, monkeypatch):
    service = SyntheticAudit("awaiting-interpretation")
    service.details["model:105"].summary.status = "failed"
    service.details["model:105"].evidence["error"] = "Evaluation failed after the model was saved."
    monkeypatch.setattr("xenix.ui.audit_center.report_exception", lambda exc: None)
    dialog = AuditCenterDialog(service=service, thread_id=201)
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(lambda: dialog._detail is not None)
        assert dialog.tr("Failed") in dialog._state.text()
        assert dialog.tr("Output available; the Agent has not interpreted it yet.") in dialog._state.text()
        assert dialog._open.isEnabled()
        service.fail = True
        dialog.refresh()
        qtbot.waitUntil(lambda: not dialog._timer.isActive())
        assert dialog.tr("Outputs could not be loaded. Retry with Refresh.") == dialog._state.text()
        service.fail = False
        dialog._refresh.click()
        qtbot.waitUntil(dialog._timer.isActive)
        qtbot.waitUntil(lambda: dialog.tr("Output available; the Agent has not interpreted it yet.") in dialog._state.text())
    finally:
        dialog.shutdown()


def test_live_task_log_refresh_preserves_reading_position(qtbot):
    from xenix.services.ml.contracts import TaskLogEntry
    from xenix.ui.widgets.task_log_view import TaskLogView

    view = TaskLogView()
    qtbot.addWidget(view)
    view.resize(500, 180)
    view.show()
    logs = [TaskLogEntry(level="INFO", message=f"Record {index}") for index in range(100)]
    view.set_logs(logs)
    scrollbar = view._text.verticalScrollBar()
    scrollbar.setValue(10)
    view.set_logs([*logs, TaskLogEntry(level="INFO", message="New record")])
    assert scrollbar.value() == 10
