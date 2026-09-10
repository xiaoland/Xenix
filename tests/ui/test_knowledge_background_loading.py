from concurrent.futures import Future
from threading import Event, get_ident
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer

from xenix.services.knowledge_index_service import KnowledgeIndexOverview
from xenix.services.knowledge_task_query import KnowledgeTaskSummary
from xenix.services.knowledge_workspace_service import (
    KnowledgeWorkspaceDocuments,
    KnowledgeWorkspaceDocumentsState,
    KnowledgeWorkspaceStatus,
)
from xenix.services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from xenix.ui.knowledge_index_ui import KnowledgeIndexRebuildDialog
from xenix.ui.knowledge_workspace.workspace_dialog import KnowledgeWorkspaceDialog
from xenix.ui.knowledge_workspace.task_queue_dialog import KnowledgeTaskQueueDialog


def _overview(count):
    return KnowledgeIndexOverview("ready", "ready", True, count, 1, None, None, None)


def test_rebuild_status_is_async_and_ignores_result_from_closed_dialog(qtbot):
    requests = []

    def request_status():
        future = Future()
        future.set_running_or_notify_cancel()
        requests.append(future)
        return future

    dialog = KnowledgeIndexRebuildDialog(SimpleNamespace(request_status=request_status))
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(requests) == 1
    assert not dialog._rebuild_button.isEnabled()
    heartbeat = []
    QTimer.singleShot(0, lambda: heartbeat.append(True))
    qtbot.waitUntil(lambda: bool(heartbeat))
    dialog.close()
    dialog.show()
    dialog.refresh()
    assert len(requests) == 1
    requests[0].set_result(_overview(111))
    qtbot.waitUntil(lambda: len(requests) == 2)
    assert "111" not in dialog._summary.text()
    requests[1].set_result(_overview(222))
    qtbot.waitUntil(lambda: dialog._rebuild_button.isEnabled())
    assert "222" in dialog._summary.text()
    dialog._keyword_checkbox.setChecked(False)
    dialog.retranslate_ui()
    dialog._render_status()
    assert not dialog._keyword_checkbox.isChecked()
    dialog.refresh()
    assert not dialog._rebuild_button.isEnabled()
    requests[2].set_exception(RuntimeError("status unavailable"))
    qtbot.waitUntil(lambda: dialog._status_failed)
    assert not dialog._rebuild_button.isEnabled()


@pytest.mark.parametrize("surface", ["workspace", "queue"])
@pytest.mark.parametrize("dismiss", ["hide", "close"])
def test_knowledge_window_dismissal_does_not_join_background_reads(qtbot, surface, dismiss):
    entered, release, finished = Event(), Event(), Event()
    worker_threads = []
    calls = []
    main_thread = get_ident()

    def load():
        calls.append(True)
        worker_threads.append(get_ident())
        entered.set()
        # The timeout bounds a broken implementation that joins this worker from
        # hideEvent. A correct UI returns while the worker remains blocked.
        release.wait(3)
        finished.set()
        if surface == "queue":
            return []
        return KnowledgeWorkspaceStatus(
            KnowledgeTaskSummary(0, 0, 0),
            PaddleOcrStatus(PaddleOcrState.NOT_INSTALLED, "not_installed"),
            _overview(111 if len(calls) == 1 else 222),
        )

    if surface == "workspace":
        service = SimpleNamespace(
            load_status=load,
            load_documents=lambda: KnowledgeWorkspaceDocuments(KnowledgeWorkspaceDocumentsState.EMPTY, ()),
        )
        dialog = KnowledgeWorkspaceDialog(import_service=None, workspace_service=service)
    else:
        dialog = KnowledgeTaskQueueDialog(
            task_query=SimpleNamespace(list_tasks=load), import_service=None,
            derivation_service=None, index_service=None,
        )
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(entered.is_set)
        assert worker_threads[0] != main_thread
        if surface == "workspace":
            qtbot.waitUntil(lambda: dialog._last_documents is not None)
        getattr(dialog, dismiss)()
        assert not finished.is_set()
        dialog.show()
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        assert len(calls) == 1
        release.set()
        qtbot.waitUntil(lambda: len(calls) == 2)
        if surface == "workspace":
            qtbot.waitUntil(lambda: dialog._last_status is not None)
            assert dialog._last_status.indexes.unit_count == 222
    finally:
        release.set()
        dialog.shutdown()
