"""Task queue dialog for Knowledge import/derivation/index work."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...services.knowledge_formats import knowledge_file_dialog_filter
from ._tasks import TASK_POLL_INTERVAL_MS, _TaskListLoad
from .import_log_dialog import KnowledgeImportLogDialog

if TYPE_CHECKING:
    from ...services.knowledge_derivation_service import KnowledgeDerivationService
    from ...services.knowledge_import_service import KnowledgeImportService
    from ...services.knowledge_index_service import KnowledgeIndexService
    from ...services.knowledge_task_query import KnowledgeTaskItem, KnowledgeTaskQueryService


class KnowledgeTaskQueueDialog(QDialog):
    def __init__(
        self,
        *,
        task_query: KnowledgeTaskQueryService,
        import_service: KnowledgeImportService,
        derivation_service: KnowledgeDerivationService | None,
        index_service: KnowledgeIndexService | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._query = task_query
        self._imports = import_service
        self._derivation = derivation_service
        self._indexes = index_service
        self._log_dialog: KnowledgeImportLogDialog | None = None
        self._thread_pool = QThreadPool(self)
        self._shutdown = False
        self._lifecycle_generation = 0
        self._load_task: _TaskListLoad | None = None
        self._load_pending = False
        self._active = False
        self._table = QTableWidget(0, 4, self)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (0, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self._table.currentItemChanged.connect(self._sync_actions)
        self._retry_button = QPushButton(self)
        self._retry_button.clicked.connect(self._retry_selected)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._cancel_selected)
        self._view_log_button = QPushButton(self)
        self._view_log_button.clicked.connect(self._view_selected_log)
        self._details_button = QPushButton(self)
        self._details_button.clicked.connect(self._view_selected_details)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(TASK_POLL_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(self._table, 1)
        actions = QHBoxLayout()
        for button in (
            self._retry_button,
            self._cancel_button,
            self._view_log_button,
            self._details_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self._close_button)
        layout.addLayout(actions)
        self.resize(780, 420)
        self.retranslate_ui()

    def refresh(self) -> None:
        if self._shutdown or not self._active:
            return
        if self._load_task is not None:
            self._load_pending = True
            return
        task = _TaskListLoad(self._query, self._lifecycle_generation)
        task.signals.finished.connect(self._on_tasks_loaded)
        self._load_task = task
        self._thread_pool.start(task)

    def _on_tasks_loaded(self, generation: int, tasks: object) -> None:
        self._load_task = None
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._load_pending = False
                self.refresh()
            return
        self._render_tasks(tasks if isinstance(tasks, list) else [])
        if self._load_pending:
            self._load_pending = False
            self.refresh()

    def _render_tasks(self, tasks: list[KnowledgeTaskItem]) -> None:
        selected = self._selected_reference()
        self._table.setRowCount(len(tasks))
        selected_row = -1
        for row_index, task in enumerate(tasks):
            values = (
                self._translated_kind(task.kind),
                task.target,
                self._translated_status(task.status),
                task.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.UserRole, task)
                self._table.setItem(row_index, column, cell)
            if task.reference == selected:
                selected_row = row_index
        if selected_row >= 0:
            self._table.selectRow(selected_row)
        self._sync_actions()
        if self._active:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def _selected_task(self) -> KnowledgeTaskItem | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        value = item.data(Qt.UserRole) if item is not None else None
        return value if value is not None else None

    def _selected_reference(self) -> str | None:
        task = self._selected_task()
        return task.reference if task is not None else None

    def _retry_selected(self) -> None:
        task = self._selected_task()
        if task is None or not task.can_retry:
            return
        try:
            if task.owner == "derivation" and self._derivation is not None and task.import_id:
                self._derivation.retry_for_import(task.import_id)
            elif task.owner == "index" and self._indexes is not None:
                self._indexes.enqueue_rebuild(task.index_kinds, trigger="manual")
            elif task.import_id:
                self._retry_import(task)
        except Exception:
            QMessageBox.warning(
                self,
                self.tr("Task Failed"),
                self.tr("The selected task could not be retried."),
            )
        self.refresh()

    def _retry_import(self, task: KnowledgeTaskItem) -> None:
        password: str | None = None
        source_path: Path | None = None
        if task.error_code in {"knowledge_password_required", "knowledge_password_invalid"}:
            password, accepted = QInputDialog.getText(
                self,
                self.tr("Document password"),
                self.tr("Enter the password for this document. It will not be saved."),
                QLineEdit.Password,
            )
            if not accepted or not password:
                return
        if task.error_code == "knowledge_source_reselection_required":
            selected, _filter = QFileDialog.getOpenFileName(
                self,
                self.tr("Select Knowledge Source"),
                "",
                knowledge_file_dialog_filter(self.tr("Knowledge documents")),
            )
            if not selected:
                return
            source_path = Path(selected)
        self._imports.retry_import(task.import_id, password=password, source_path=source_path)

    def _cancel_selected(self) -> None:
        task = self._selected_task()
        if task is not None and task.can_cancel and task.import_id:
            self._imports.cancel_import(task.import_id)
        self.refresh()

    def _view_selected_log(self) -> None:
        task = self._selected_task()
        if task is None or not task.can_view_log or not task.import_id:
            return
        if self._log_dialog is None:
            self._log_dialog = KnowledgeImportLogDialog(self._imports, self)
        self._log_dialog.show_import(task.import_id, task.target)

    def _view_selected_details(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        details = self.tr("Phase: %1\nTrigger: %2").replace(
            "%1", task.phase.replace("_", " ")
        ).replace("%2", task.trigger.replace("_", " "))
        if task.error_code:
            details += "\n" + self.tr("Error: %1").replace("%1", task.error_code)
        if task.error_summary:
            details += "\n" + self.tr("Details: %1").replace(
                "%1", task.error_summary
            )
        QMessageBox.information(self, self.tr("Task Details"), details)

    def _sync_actions(self, *_args) -> None:
        task = self._selected_task()
        self._retry_button.setEnabled(bool(task and task.can_retry))
        self._cancel_button.setEnabled(bool(task and task.can_cancel))
        self._view_log_button.setEnabled(bool(task and task.can_view_log))
        self._details_button.setEnabled(bool(task and task.can_view_details))

    def _translated_kind(self, kind: str) -> str:
        return {
            "import": self.tr("Import"),
            "content_preparation": self.tr("Content preparation"),
            "index_build": self.tr("Index build"),
        }.get(kind, kind)

    def _translated_status(self, status: str) -> str:
        return {
            "pending": self.tr("Pending"),
            "queued": self.tr("Queued"),
            "running": self.tr("In progress"),
            "canonical_ready": self.tr("Preparing content"),
            "retrieval_ready": self.tr("Ready"),
            "succeeded": self.tr("Completed"),
            "needs_attention": self.tr("Needs attention"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
            "reused": self.tr("Reused"),
        }.get(status, self.tr("Unknown status"))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Task queue"))
        self._table.setHorizontalHeaderLabels(
            [self.tr("Type"), self.tr("Target"), self.tr("Status"), self.tr("Updated")]
        )
        self._retry_button.setText(self.tr("Retry"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._view_log_button.setText(self.tr("View log"))
        self._details_button.setText(self.tr("Details"))
        self._close_button.setText(self.tr("Close"))

    def showEvent(self, event) -> None:
        if self._shutdown:
            super().showEvent(event)
            self.hide()
            return
        self._active = True
        self._lifecycle_generation += 1
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event) -> None:
        self._deactivate()
        if self._log_dialog is not None:
            self._log_dialog.hide()
        self._thread_pool.waitForDone()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate()
        self._thread_pool.waitForDone()
        super().closeEvent(event)

    def _deactivate(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._load_pending = False
        self._refresh_timer.stop()

    def shutdown(self) -> None:
        """Quiesce UI-owned tasks before their application services are closed."""
        if self._shutdown:
            return
        self._shutdown = True
        self._deactivate()
        if self._log_dialog is not None:
            self._log_dialog.hide()
        self._thread_pool.waitForDone()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)


# Transitional import name for callers/tests while the user-visible concept is unified.
KnowledgeImportQueueDialog = KnowledgeTaskQueueDialog
