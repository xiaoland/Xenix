from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.knowledge_formats import (
    SUPPORTED_KNOWLEDGE_SUFFIXES,
    knowledge_file_dialog_filter,
)

if TYPE_CHECKING:
    from ..services.knowledge_derivation_service import KnowledgeDerivationService
    from ..services.knowledge_import_service import KnowledgeImportService
    from ..services.knowledge_index_service import KnowledgeIndexService
    from ..services.knowledge_service import KnowledgeService
    from ..services.knowledge_task_query import KnowledgeTaskItem, KnowledgeTaskQueryService
    from ..services.knowledge_workspace_service import (
        KnowledgeWorkspaceService,
        KnowledgeWorkspaceSnapshot,
    )
    from ..services.paddle_ocr_service import PaddleOcrDeploymentService
    from .knowledge_index_ui import KnowledgeIndexRebuildDialog


TASK_POLL_INTERVAL_MS = 500
WORKSPACE_ACTIVE_POLL_INTERVAL_MS = 1_000


class _SnapshotSignals(QObject):
    finished = Signal(int, object)


class _SnapshotTask(QRunnable):
    def __init__(self, service: KnowledgeWorkspaceService, generation: int) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self.signals = _SnapshotSignals()

    def run(self) -> None:
        try:
            snapshot = self._service.snapshot()
        except Exception:
            snapshot = None
        self.signals.finished.emit(self._generation, snapshot)


class _TaskListSignals(QObject):
    finished = Signal(int, object)


class _TaskListLoad(QRunnable):
    def __init__(self, query: KnowledgeTaskQueryService, generation: int) -> None:
        super().__init__()
        self._query = query
        self._generation = generation
        self.signals = _TaskListSignals()

    def run(self) -> None:
        try:
            tasks = self._query.list_tasks()
        except Exception:
            tasks = []
        self.signals.finished.emit(self._generation, tasks)


class _KnowledgeFileDropAdapter(QObject):
    """Project local file URLs into one Workspace submission callback."""

    files_dropped = Signal(object)

    def attach(self, target: QObject) -> None:
        set_accept_drops = getattr(target, "setAcceptDrops", None)
        if callable(set_accept_drops):
            set_accept_drops(True)
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() not in {QEvent.DragEnter, QEvent.DragMove, QEvent.Drop}:
            return super().eventFilter(watched, event)
        mime_data = getattr(event, "mimeData", lambda: None)()
        paths = _local_file_drop_paths(mime_data)
        if not paths:
            event.ignore()
            return True
        event.acceptProposedAction()
        if event.type() == QEvent.Drop:
            self.files_dropped.emit(paths)
        return True


class KnowledgeImportLogDialog(QDialog):
    def __init__(self, import_service: KnowledgeImportService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._service = import_service
        self._import_id: str | None = None
        self._file_name = ""
        self._content = QPlainTextEdit(self)
        self._content.setReadOnly(True)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(TASK_POLL_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(self._content, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._close_button)
        layout.addLayout(actions)
        self.resize(700, 420)
        self.retranslate_ui()

    def show_import(self, import_id: str, file_name: str) -> None:
        self._import_id = import_id
        self._file_name = file_name
        self.retranslate_ui()
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        if not self._import_id:
            self._content.clear()
            return
        try:
            entries = self._service.read_import_logs(self._import_id)
        except Exception:
            self._content.setPlainText(self.tr("The import log could not be read."))
            return
        lines = [
            f"{entry.timestamp}  {self._translated_phase(entry.phase)} — "
            f"{entry.event_code.replace('_', ' ')}"
            for entry in entries
        ]
        self._content.setPlainText(
            "\n".join(lines) if lines else self.tr("No import events have been recorded yet.")
        )

    def _translated_phase(self, phase: str) -> str:
        translations = {
            "queued": self.tr("Queued"),
            "snapshot": self.tr("Source snapshot"),
            "probing": self.tr("File probe"),
            "normalizing": self.tr("Normalization"),
            "routing": self.tr("Parser routing"),
            "parsing": self.tr("Document parsing"),
            "publishing_canonical": self.tr("Canonical publication"),
            "completed": self.tr("Completed"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
        }
        return translations.get(phase, phase.replace("_", " "))

    def retranslate_ui(self) -> None:
        title = self.tr("Knowledge Import Log")
        if self._file_name:
            title = self.tr("Knowledge Import Log — %1").replace("%1", self._file_name)
        self.setWindowTitle(title)
        self._close_button.setText(self.tr("Close"))

    def showEvent(self, event) -> None:
        self.refresh()
        self._refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._refresh_timer.stop()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)


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
        self._thread_pool = QThreadPool.globalInstance()
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
        if not self._active:
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
        self._active = True
        self._lifecycle_generation += 1
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event) -> None:
        self._deactivate()
        if self._log_dialog is not None:
            self._log_dialog.hide()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate()
        super().closeEvent(event)

    def _deactivate(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._load_pending = False
        self._refresh_timer.stop()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)


# Transitional import name for callers/tests while the user-visible concept is unified.
KnowledgeImportQueueDialog = KnowledgeTaskQueueDialog


class KnowledgeWorkspaceDialog(QDialog):
    def __init__(
        self,
        *,
        import_service: KnowledgeImportService,
        derivation_service: KnowledgeDerivationService | None = None,
        knowledge_service: KnowledgeService | None = None,
        knowledge_index_service: KnowledgeIndexService | None = None,
        ocr_deployment: PaddleOcrDeploymentService | None = None,
        task_query_service: KnowledgeTaskQueryService | None = None,
        workspace_service: KnowledgeWorkspaceService | None = None,
        open_knowledge_settings: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._import_service = import_service
        self._derivation_service = derivation_service
        self._knowledge_index_service = knowledge_index_service
        self._task_query = task_query_service
        self._workspace_service = workspace_service
        self._open_knowledge_settings = open_knowledge_settings
        self._queue_dialog: KnowledgeTaskQueueDialog | None = None
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._lifecycle_generation = 0
        self._snapshot_task: _SnapshotTask | None = None
        self._snapshot_pending = False
        self._active = False
        self._last_snapshot: KnowledgeWorkspaceSnapshot | None = None
        self._drop_adapter = _KnowledgeFileDropAdapter(self)
        self._drop_adapter.files_dropped.connect(self._submit_import_paths)

        self._documents = QTableWidget(0, 4, self)
        self._documents.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._documents.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._documents.setSelectionMode(QAbstractItemView.SingleSelection)
        self._documents.verticalHeader().setVisible(False)
        self._documents.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self._documents.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self._empty_state = QLabel(self)
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._footer_status = QLabel(self)
        footer_font = self._footer_status.font()
        footer_font.setPointSize(max(8, footer_font.pointSize() - 1))
        self._footer_status.setFont(footer_font)
        footer_palette = self._footer_status.palette()
        footer_palette.setColor(QPalette.WindowText, footer_palette.color(QPalette.Mid))
        self._footer_status.setPalette(footer_palette)

        self._import_button = QPushButton(self)
        self._queue_button = QPushButton(self)
        self._rebuild_button = QPushButton(self)
        self._settings_button = QPushButton(self)
        self._import_button.clicked.connect(self._choose_files)
        self._queue_button.clicked.connect(self.open_task_queue)
        self._rebuild_button.clicked.connect(self._open_index_rebuild)
        self._settings_button.clicked.connect(self._open_settings)
        self._settings_button.setEnabled(self._open_knowledge_settings is not None)
        self._rebuild_button.setEnabled(self._knowledge_index_service is not None)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(WORKSPACE_ACTIVE_POLL_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_documents)

        buttons = QHBoxLayout()
        buttons.addWidget(self._import_button)
        buttons.addWidget(self._queue_button)
        buttons.addWidget(self._rebuild_button)
        buttons.addStretch(1)
        buttons.addWidget(self._settings_button)
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self._documents, 1)
        layout.addWidget(self._empty_state, 1)
        layout.addWidget(self._footer_status)
        for drop_target in (self, self._documents.viewport(), self._empty_state):
            self._drop_adapter.attach(drop_target)
        self.resize(860, 520)
        self.retranslate_ui()

    def open_task_queue(self) -> None:
        if self._task_query is None:
            return
        if self._queue_dialog is None:
            self._queue_dialog = KnowledgeTaskQueueDialog(
                task_query=self._task_query,
                import_service=self._import_service,
                derivation_service=self._derivation_service,
                index_service=self._knowledge_index_service,
                parent=self,
            )
        self._queue_dialog.show()
        self._queue_dialog.raise_()
        self._queue_dialog.activateWindow()
        self._queue_dialog.refresh()

    def open_import_queue(self) -> None:
        self.open_task_queue()

    def _choose_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            self.tr("Import Knowledge"),
            "",
            knowledge_file_dialog_filter(self.tr("Knowledge documents")),
        )
        self._submit_import_paths(paths)

    def _submit_import_paths(self, paths: list[str]) -> None:
        accepted = _accepted_import_paths(paths)
        if not accepted:
            return
        queued = False
        failed_count = 0
        for path in accepted:
            try:
                self._import_service.enqueue_file(path)
                queued = True
            except Exception:
                failed_count += 1
        if queued:
            self.open_task_queue()
            self.refresh_documents()
        if failed_count:
            QMessageBox.warning(
                self,
                self.tr("Knowledge Import Failed"),
                self.tr("%1 file(s) could not be queued for import.").replace("%1", str(failed_count)),
            )

    def _open_settings(self) -> None:
        if self._open_knowledge_settings is not None:
            self._open_knowledge_settings()

    def _open_index_rebuild(self) -> None:
        if self._knowledge_index_service is None:
            return
        if self._index_dialog is None:
            from .knowledge_index_ui import KnowledgeIndexRebuildDialog

            self._index_dialog = KnowledgeIndexRebuildDialog(self._knowledge_index_service, self)
            self._index_dialog.submitted.connect(lambda _task_id: self.refresh_documents())
        self._index_dialog.open()

    def refresh_documents(self) -> None:
        if not self._active or self._workspace_service is None:
            return
        if self._snapshot_task is not None:
            self._snapshot_pending = True
            return
        generation = self._lifecycle_generation
        task = _SnapshotTask(self._workspace_service, generation)
        task.signals.finished.connect(self._on_snapshot_finished)
        self._snapshot_task = task
        self._thread_pool.start(task)

    def _on_snapshot_finished(self, generation: int, snapshot: object) -> None:
        self._snapshot_task = None
        if generation != self._lifecycle_generation or not self._active:
            return
        if snapshot is not None:
            self._last_snapshot = snapshot
            self._render_snapshot(snapshot)
        if self._snapshot_pending:
            self._snapshot_pending = False
            self.refresh_documents()

    def _render_snapshot(self, snapshot: KnowledgeWorkspaceSnapshot) -> None:
        documents = snapshot.documents
        self._documents.setRowCount(len(documents))
        for row_index, document in enumerate(documents):
            values = (
                document.title,
                document.source_format.upper(),
                self._translated_content_state(document.content_state),
                document.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            )
            for column, value in enumerate(values):
                self._documents.setItem(row_index, column, QTableWidgetItem(value))
        has_documents = bool(documents)
        self._documents.setVisible(has_documents)
        self._empty_state.setVisible(not has_documents)
        self._empty_state.setText(
            self.tr("Knowledge content is temporarily unavailable.")
            if not snapshot.documents_available
            else self.tr("No Knowledge documents yet. Import a file to get started.")
        )
        index = snapshot.indexes
        keyword = self._translated_index_state(index.keyword_state) if index else self.tr("Unavailable")
        vector = self._translated_index_state(index.text_vector_state) if index else self.tr("Unavailable")
        ocr = self._translated_ocr_state(str(snapshot.ocr.state))
        self._footer_status.setText(
            self.tr("OCR: %1  ·  Keyword: %2  ·  Text vectors: %3")
            .replace("%1", ocr)
            .replace("%2", keyword)
            .replace("%3", vector)
        )
        if snapshot.has_active_work:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def _translated_ocr_state(self, state: str) -> str:
        return {
            "ready": self.tr("Ready"),
            "checking": self.tr("Checking"),
            "not_installed": self.tr("Not installed"),
            "repair_required": self.tr("Repair required"),
            "installing": self.tr("Installing"),
            "failed": self.tr("Needs attention"),
        }.get(state, self.tr("Unavailable"))

    def _translated_index_state(self, state: str) -> str:
        return {
            "ready": self.tr("Ready"),
            "building": self.tr("Building"),
            "needs_rebuild": self.tr("Needs rebuild"),
            "unavailable": self.tr("Unavailable"),
            "needs_attention": self.tr("Needs attention"),
        }.get(state, self.tr("Unknown status"))

    def _translated_content_state(self, state: str) -> str:
        return {
            "ready": self.tr("Searchable"),
            "processing": self.tr("Preparing search content"),
            "no_searchable_text": self.tr("No searchable text"),
            "needs_attention": self.tr("Needs attention"),
        }.get(state, self.tr("Unknown status"))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Knowledge Workspace"))
        self._import_button.setText(self.tr("Import documents"))
        self._queue_button.setText(self.tr("Task queue"))
        self._rebuild_button.setText(self.tr("Rebuild indexes"))
        self._settings_button.setText(self.tr("Settings"))
        self._documents.setHorizontalHeaderLabels(
            [
                self.tr("Document"),
                self.tr("Type"),
                self.tr("Content status"),
                self.tr("Updated"),
            ]
        )
        self._empty_state.setText(self.tr("No Knowledge documents yet. Import a file to get started."))
        if self._last_snapshot is not None:
            self._render_snapshot(self._last_snapshot)
        if self._queue_dialog is not None:
            self._queue_dialog.retranslate_ui()

    def showEvent(self, event) -> None:
        self._active = True
        self._lifecycle_generation += 1
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_documents)

    def hideEvent(self, event) -> None:
        self._deactivate()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate()
        super().closeEvent(event)

    def _deactivate(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._snapshot_pending = False
        self._refresh_timer.stop()
        if self._queue_dialog is not None:
            self._queue_dialog.hide()
        if self._index_dialog is not None:
            self._index_dialog.hide()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)


def _accepted_import_paths(paths: list[str]) -> list[Path]:
    accepted: list[Path] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        key = str(path).casefold()
        if path.suffix.casefold() not in SUPPORTED_KNOWLEDGE_SUFFIXES or key in seen:
            continue
        seen.add(key)
        accepted.append(path)
    return accepted


def _local_file_drop_paths(mime_data: object | None) -> list[str]:
    if mime_data is None:
        return []
    urls = getattr(mime_data, "urls", lambda: ())()
    return [
        url.toLocalFile()
        for url in urls
        if url.isLocalFile() and url.toLocalFile()
    ]


__all__ = [
    "KnowledgeImportLogDialog",
    "KnowledgeImportQueueDialog",
    "KnowledgeTaskQueueDialog",
    "KnowledgeWorkspaceDialog",
]
