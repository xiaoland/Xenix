from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot
from shiboken6 import isValid

from xenix.ui.history import HistoryPanel, HistoryThreadSummary
from xenix.ui.semantic_identity import item_reference


class _Port:
    def __init__(self) -> None:
        self.threads = [HistoryThreadSummary("thread-a", "Alpha"), HistoryThreadSummary("thread-b", None)]
        self.deleted: list[str] = []
        self.renamed: list[tuple[str, str | None]] = []

    def list_threads(self) -> Sequence[HistoryThreadSummary]: return tuple(self.threads)
    def rename_thread(self, thread_id: str, title: str | None) -> HistoryThreadSummary:
        self.renamed.append((thread_id, title))
        summary = HistoryThreadSummary(thread_id, title)
        self.threads = [summary if thread.id == thread_id else thread for thread in self.threads]
        return summary
    def delete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)
        self.threads = [thread for thread in self.threads if thread.id != thread_id]
    def has_title_provider(self) -> bool: return True
    def generate_thread_title(self, thread_id: str) -> str: return "Generated"


def test_rows_expose_static_and_repeated_semantic_identity(qtbot: QtBot) -> None:
    panel = HistoryPanel(_Port(), is_thread_running=lambda _id: False)
    qtbot.addWidget(panel)
    panel.refresh()
    assert panel.first_thread_id == "thread-a"
    assert panel._list.objectName() == "historyList"
    assert panel._list.accessibleIdentifier() == "main.history.thread-list"
    rows = panel._list.findChildren(type(panel._list.itemWidget(panel._list.item(0))))
    assert {item_reference(row) for row in rows} == {"thread-a", "thread-b"}
    assert all(row.accessibleIdentifier() == "main.history.thread-item" for row in rows)


def test_open_and_refresh_preserve_only_existing_selection(qtbot: QtBot) -> None:
    port = _Port()
    panel = HistoryPanel(port, is_thread_running=lambda _id: False)
    qtbot.addWidget(panel)
    panel.refresh()
    with qtbot.waitSignal(panel.thread_open_requested) as signal:
        panel.open_thread("thread-b")
    assert signal.args == ["thread-b"]
    assert panel.selected_thread_id == "thread-b"
    port.threads = [port.threads[0]]
    panel.refresh()
    assert panel.selected_thread_id is None


def test_row_overlay_keeps_list_clickable(qtbot: QtBot) -> None:
    panel = HistoryPanel(_Port(), is_thread_running=lambda _id: False)
    qtbot.addWidget(panel)
    panel.refresh()
    panel.show()
    item = panel._list.item(1)
    with qtbot.waitSignal(panel.thread_open_requested) as signal:
        qtbot.mouseClick(panel._list.viewport(), Qt.MouseButton.LeftButton, pos=panel._list.visualItemRect(item).center())
    assert signal.args == ["thread-b"]


def test_late_title_completion_after_shutdown_has_no_service_effect(qtbot: QtBot) -> None:
    port = _Port()
    callbacks: dict[str, Callable] = {}
    def executor(_id, succeeded, failed):
        callbacks["succeeded"] = succeeded
        callbacks["failed"] = failed
    panel = HistoryPanel(port, is_thread_running=lambda _id: False, title_executor=executor)
    qtbot.addWidget(panel)
    panel.refresh()
    panel._start_title("thread-a")
    panel.shutdown()
    callbacks["succeeded"]("Late")
    qtbot.wait(10)
    assert port.renamed == []


def test_delete_invalidates_late_title_completion(qtbot: QtBot, monkeypatch) -> None:
    port = _Port()
    callbacks: dict[str, Callable] = {}

    def executor(_id, succeeded, failed):
        callbacks["succeeded"] = succeeded
        callbacks["failed"] = failed

    panel = HistoryPanel(port, is_thread_running=lambda _id: False, title_executor=executor)
    qtbot.addWidget(panel)
    panel.refresh()
    panel._start_title("thread-a")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    panel._delete("thread-a")
    callbacks["succeeded"]("Late")
    qtbot.wait(10)
    assert port.deleted == ["thread-a"]
    assert port.renamed == []


def test_true_cpp_deletion_ignores_late_title_callback(qtbot: QtBot) -> None:
    callbacks: dict[str, Callable] = {}

    def executor(_id, succeeded, failed):
        callbacks["succeeded"] = succeeded
        callbacks["failed"] = failed

    panel = HistoryPanel(_Port(), is_thread_running=lambda _id: False, title_executor=executor)
    qtbot.addWidget(panel)
    panel.refresh()
    panel._start_title("thread-a")
    panel.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(panel)
    callbacks["succeeded"]("Late")


def test_retranslate_does_not_query_port(qtbot: QtBot) -> None:
    port = _Port()
    panel = HistoryPanel(port, is_thread_running=lambda _id: False)
    qtbot.addWidget(panel)
    panel.refresh()
    original = port.list_threads
    port.list_threads = lambda: (_ for _ in ()).throw(AssertionError("unexpected service call"))  # type: ignore[method-assign]
    panel.retranslate_ui()
    port.list_threads = original  # type: ignore[method-assign]


def test_running_thread_delete_is_guarded_before_confirmation(qtbot: QtBot, monkeypatch) -> None:
    port = _Port()
    panel = HistoryPanel(port, is_thread_running=lambda thread_id: thread_id == "thread-a")
    qtbot.addWidget(panel)
    panel.refresh()
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: messages.append("blocked"))
    panel._delete("thread-a")
    assert messages == ["blocked"]
    assert port.deleted == []
