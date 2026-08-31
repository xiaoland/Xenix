from __future__ import annotations

import threading
import weakref
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ..icons import plus_icon
from ..semantic_identity import identify, identify_repeated_item

if TYPE_CHECKING:
    from ...services.agent.harness_service import AgentHarnessService


@dataclass(frozen=True)
class HistoryThreadSummary:
    id: str
    title: str | None


class HistoryPort(Protocol):
    def list_threads(self) -> Sequence[HistoryThreadSummary]: ...

    def rename_thread(self, thread_id: str, title: str | None) -> HistoryThreadSummary: ...

    def delete_thread(self, thread_id: str) -> None: ...

    def has_title_provider(self) -> bool: ...

    def generate_thread_title(self, thread_id: str) -> str: ...


TitleExecutor = Callable[
    [str, Callable[[str], None], Callable[[Exception], None]], None
]


class HarnessHistoryAdapter:
    """Production adapter keeping Agent Harness outside the widget contract."""

    def __init__(self, service: AgentHarnessService) -> None:
        self._service = service

    def list_threads(self) -> Sequence[HistoryThreadSummary]:
        return tuple(
            HistoryThreadSummary(id=thread.id, title=thread.title)
            for thread in self._service.list_threads()  # type: ignore[no-untyped-call]
        )

    def rename_thread(self, thread_id: str, title: str | None) -> HistoryThreadSummary:
        snapshot = self._service.rename_thread(thread_id, title)
        return HistoryThreadSummary(id=snapshot.thread.id, title=snapshot.thread.title)

    def delete_thread(self, thread_id: str) -> None:
        self._service.delete_thread(thread_id)

    def has_title_provider(self) -> bool:
        return self._service.has_thread_title_provider()

    def generate_thread_title(self, thread_id: str) -> str:
        return self._service.generate_thread_title(thread_id)


class _HistoryThreadRow(QWidget):
    def __init__(self, thread_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = QLabel(title, self)
        self._label.setWordWrap(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._label)
        identify_repeated_item(
            self,
            role="main.history.thread-item",
            item_reference=thread_id,
        )
        self.setMinimumHeight(24)

    def set_title(self, title: str) -> None:
        self._label.setText(title)


class HistoryPanel(QFrame):
    thread_open_requested = Signal(str)
    new_thread_requested = Signal()
    thread_deleted = Signal(str)
    _title_succeeded = Signal(int, str, str)
    _title_failed = Signal(int, str, str)

    def __init__(
        self,
        port: HistoryPort,
        *,
        is_thread_running: Callable[[str], bool],
        title_executor: TitleExecutor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._port = port
        self._is_thread_running = is_thread_running
        self._title_executor = title_executor or self._run_title_in_thread
        self._threads: dict[str, HistoryThreadSummary] = {}
        self._selected_thread_id: str | None = None
        self._shutdown = False
        self._generation = 0
        self._active_title: tuple[int, str] | None = None
        self._title_progress: QProgressDialog | None = None

        self.setObjectName("historySidebar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._label = QLabel(self)
        self._label.setObjectName("historySidebarTitle")
        self._new_button = QPushButton(self)
        self._new_button.setObjectName("newThreadButton")
        self._new_button.setIcon(plus_icon())
        self._new_button.setFixedSize(28, 28)
        self._new_button.setIconSize(QSize(14, 14))
        self._new_button.clicked.connect(self._request_new_thread)
        self._list = QListWidget(self)
        self._list.setObjectName("historyList")
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._open_context_menu)
        identify(self, "main.history.panel")
        identify(self._new_button, "main.history.new-thread")
        identify(self._list, "main.history.thread-list")

        layout = QVBoxLayout(self)
        layout.setObjectName("historySidebarLayout")
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setObjectName("historyHeaderLayout")
        header.addWidget(self._label)
        header.addStretch(1)
        header.addWidget(self._new_button)
        layout.addLayout(header)
        layout.addWidget(self._list, 1)
        self.setFixedWidth(248)
        self.retranslate_ui()

        self._title_succeeded.connect(self._finish_title)
        self._title_failed.connect(self._fail_title)

    @property
    def selected_thread_id(self) -> str | None:
        return self._selected_thread_id

    @property
    def first_thread_id(self) -> str | None:
        return next(iter(self._threads), None)

    def refresh(self, selected_thread_id: str | None = None) -> None:
        if self._shutdown:
            return
        requested = selected_thread_id if selected_thread_id is not None else self._selected_thread_id
        summaries = tuple(self._port.list_threads())
        self._threads = {summary.id: summary for summary in summaries}
        if self._active_title is not None and self._active_title[1] not in self._threads:
            self._invalidate_title()
        self._list.clear()
        for summary in summaries:
            title = summary.title or QCoreApplication.translate(
                "MainWindow", "Untitled conversation"
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, summary.id)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
            self._list.addItem(item)
            row = _HistoryThreadRow(summary.id, title, self._list)
            item.setSizeHint(row.sizeHint())
            self._list.setItemWidget(item, row)
        self._selected_thread_id = requested if requested in self._threads else None
        if self._selected_thread_id is not None:
            self._select_item(self._selected_thread_id)

    def open_thread(self, thread_id: str) -> None:
        if self._shutdown or thread_id not in self._threads:
            return
        self._selected_thread_id = thread_id
        self._select_item(thread_id)
        self.thread_open_requested.emit(thread_id)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._invalidate_title()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        super().closeEvent(event)

    def retranslate_ui(self) -> None:
        self._label.setText(QCoreApplication.translate("MainWindow", "History"))
        self._new_button.setText("")
        self._new_button.setToolTip(QCoreApplication.translate("MainWindow", "New thread"))
        self._new_button.setAccessibleName(QCoreApplication.translate("MainWindow", "New thread"))
        for index in range(self._list.count()):
            item = self._list.item(index)
            thread_id = self._thread_id(item)
            if thread_id is not None:
                summary = self._threads.get(thread_id)
                if summary is not None and not summary.title:
                    title = QCoreApplication.translate("MainWindow", "Untitled conversation")
                    item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
                    row = self._list.itemWidget(item)
                    if isinstance(row, _HistoryThreadRow):
                        row.set_title(title)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        thread_id = self._thread_id(item)
        if thread_id is not None:
            self.open_thread(thread_id)

    def _request_new_thread(self) -> None:
        if not self._shutdown:
            self.new_thread_requested.emit()

    def _open_context_menu(self, position: QPoint) -> None:
        if self._shutdown:
            return
        item = self._list.itemAt(position)
        thread_id = self._thread_id(item)
        if thread_id is None:
            return
        menu = QMenu(self)
        rename = menu.addAction(QCoreApplication.translate("MainWindow", "Rename"))
        generate = menu.addAction(QCoreApplication.translate("MainWindow", "Generate title..."))
        copy_id = menu.addAction(QCoreApplication.translate("MainWindow", "Copy thread ID"))
        delete = menu.addAction(QCoreApplication.translate("MainWindow", "Delete"))
        chosen = menu.exec(self._list.viewport().mapToGlobal(position))
        if chosen is rename:
            self._rename(thread_id)
        elif chosen is generate:
            self._start_title(thread_id)
        elif chosen is copy_id:
            QApplication.clipboard().setText(thread_id)
        elif chosen is delete:
            self._delete(thread_id)

    def _rename(self, thread_id: str) -> None:
        if self._shutdown:
            return
        summary = self._threads.get(thread_id)
        if summary is None:
            return
        title, accepted = QInputDialog.getText(
            self, QCoreApplication.translate("MainWindow", "Rename Thread"),
            QCoreApplication.translate("MainWindow", "Thread name"),
            text=summary.title or QCoreApplication.translate("MainWindow", "Untitled conversation"),
        )
        if not accepted:
            return
        renamed = self._port.rename_thread(thread_id, title.strip() or None)
        self.refresh(renamed.id)

    def _delete(self, thread_id: str) -> None:
        if self._shutdown:
            return
        if thread_id not in self._threads:
            return
        if self._is_thread_running(thread_id):
            QMessageBox.information(
                self, QCoreApplication.translate("MainWindow", "Delete Thread"),
                QCoreApplication.translate("MainWindow", "Stop the current run before deleting this thread."),
            )
            return
        title = self._threads[thread_id].title or QCoreApplication.translate(
            "MainWindow", "Untitled conversation"
        )
        response = QMessageBox.question(
            self, QCoreApplication.translate("MainWindow", "Delete Thread"),
            QCoreApplication.translate(
                "MainWindow", 'Delete "{title}"? This action cannot be undone.'
            ).format(title=title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self._port.delete_thread(thread_id)
        if self._active_title is not None and self._active_title[1] == thread_id:
            self._invalidate_title()
        was_selected = self._selected_thread_id == thread_id
        self._threads.pop(thread_id, None)
        self.refresh(None if was_selected else self._selected_thread_id)
        self.thread_deleted.emit(thread_id)

    def _start_title(self, thread_id: str) -> None:
        if self._shutdown or thread_id not in self._threads or self._active_title is not None:
            return
        if not self._port.has_title_provider():
            QMessageBox.information(
                self, QCoreApplication.translate("MainWindow", "Generate Thread Title"),
                QCoreApplication.translate("MainWindow", "Thread title model is not configured."),
            )
            return
        self._generation += 1
        generation = self._generation
        self._active_title = (generation, thread_id)
        self._show_title_progress()
        panel_ref = weakref.ref(self)

        def succeeded(title: str) -> None:
            panel = panel_ref()
            if panel is None:
                return
            try:
                if isValid(panel):
                    panel._title_succeeded.emit(generation, thread_id, title)
            except RuntimeError:
                return

        def failed(error: Exception) -> None:
            panel = panel_ref()
            if panel is None:
                return
            try:
                if isValid(panel):
                    panel._title_failed.emit(generation, thread_id, str(error))
            except RuntimeError:
                return

        try:
            self._title_executor(thread_id, succeeded, failed)
        except Exception as exc:
            self._close_title_progress()
            self._active_title = None
            QMessageBox.warning(
                self, QCoreApplication.translate("MainWindow", "Generate Thread Title"), str(exc)
            )

    def _run_title_in_thread(
        self, thread_id: str, succeeded: Callable[[str], None], failed: Callable[[Exception], None]
    ) -> None:
        def run() -> None:
            try:
                succeeded(self._port.generate_thread_title(thread_id))
            except Exception as exc:
                failed(exc)
        threading.Thread(target=run, name="xenix-thread-title-generation", daemon=True).start()

    def _finish_title(self, generation: int, thread_id: str, proposal: str) -> None:
        if not self._accept_title_result(generation, thread_id):
            return
        self._close_title_progress()
        title, accepted = QInputDialog.getText(
            self, QCoreApplication.translate("MainWindow", "Apply Generated Title"),
            QCoreApplication.translate("MainWindow", "Thread name"), text=proposal,
        )
        if not accepted:
            if self._active_title == (generation, thread_id):
                self._active_title = None
            return
        if not self._accept_title_result(generation, thread_id):
            return
        self._active_title = None
        try:
            renamed = self._port.rename_thread(thread_id, title.strip() or None)
        except Exception as exc:
            QMessageBox.warning(
                self, QCoreApplication.translate("MainWindow", "Generate Thread Title"), str(exc)
            )
            return
        self.refresh(renamed.id)

    def _fail_title(self, generation: int, thread_id: str, message: str) -> None:
        if not self._accept_title_result(generation, thread_id):
            return
        self._close_title_progress()
        self._active_title = None
        QMessageBox.warning(
            self, QCoreApplication.translate("MainWindow", "Generate Thread Title"), message
        )

    def _accept_title_result(self, generation: int, thread_id: str) -> bool:
        return not self._shutdown and self._active_title == (generation, thread_id) and thread_id in self._threads

    def _invalidate_title(self) -> None:
        self._generation += 1
        self._active_title = None
        self._close_title_progress()

    def _show_title_progress(self) -> None:
        self._close_title_progress()
        dialog = QProgressDialog(
            QCoreApplication.translate("MainWindow", "Generating thread title..."), "", 0, 0, self
        )
        dialog.setObjectName("threadTitleProgressDialog")
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Generate Thread Title"))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setCancelButton(None)
        self._title_progress = dialog
        dialog.show()

    def _close_title_progress(self) -> None:
        if self._title_progress is None:
            return
        dialog = self._title_progress
        self._title_progress = None
        dialog.close()
        dialog.deleteLater()

    def _select_item(self, thread_id: str) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if self._thread_id(item) == thread_id:
                self._list.setCurrentItem(item)
                return

    @staticmethod
    def _thread_id(item: QListWidgetItem | None) -> str | None:
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None
