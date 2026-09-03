"""Main Knowledge Workspace dialog: document library, status, and import entry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...services.knowledge_formats import (
    SUPPORTED_KNOWLEDGE_SUFFIXES,
    knowledge_file_dialog_filter,
)
from ._tasks import (
    WORKSPACE_ACTIVE_POLL_INTERVAL_MS,
    _DocumentsLoadTask,
    _DocumentRemovalTask,
    _DocumentViewportState,
    _KnowledgeFileDropAdapter,
    _StatusLoadTask,
)
from .task_queue_dialog import KnowledgeTaskQueueDialog

if TYPE_CHECKING:
    from ...services.knowledge_document_lifecycle_service import (
        KnowledgeDocumentLifecycleService,
    )
    from ...services.knowledge_derivation_service import KnowledgeDerivationService
    from ...services.knowledge_import_service import KnowledgeImportService
    from ...services.knowledge_index_service import KnowledgeIndexService
    from ...services.knowledge_service import KnowledgeService
    from ...services.knowledge_task_query import KnowledgeTaskQueryService
    from ...services.knowledge_workspace_service import (
        KnowledgeWorkspaceDocument,
        KnowledgeWorkspaceDocuments,
        KnowledgeWorkspaceService,
        KnowledgeWorkspaceStatus,
    )
    from ...services.paddle_ocr_service import PaddleOcrDeploymentService
    from ..knowledge_index_ui import KnowledgeIndexRebuildDialog


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
        document_lifecycle_service: KnowledgeDocumentLifecycleService | None = None,
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
        self._document_lifecycle = document_lifecycle_service
        self._open_knowledge_settings = open_knowledge_settings
        self._queue_dialog: KnowledgeTaskQueueDialog | None = None
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._thread_pool = QThreadPool(self)
        self._shutdown = False
        self._lifecycle_generation = 0
        self._request_sequence = 0
        self._documents_request_id: int | None = None
        self._status_request_id: int | None = None
        self._document_tasks: dict[int, _DocumentsLoadTask] = {}
        self._status_tasks: dict[int, _StatusLoadTask] = {}
        self._documents_pending = False
        self._status_pending = False
        self._removal_task: _DocumentRemovalTask | None = None
        self._removing_document_id: str | None = None
        self._active = False
        self._document_state = _DocumentViewportState.COLD
        self._last_documents: KnowledgeWorkspaceDocuments | None = None
        self._last_status: KnowledgeWorkspaceStatus | None = None
        self._drop_adapter = _KnowledgeFileDropAdapter(self)
        self._drop_adapter.files_dropped.connect(self._submit_import_paths)

        self._documents = QTableWidget(0, 4, self)
        self._documents.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._documents.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._documents.setSelectionMode(QAbstractItemView.SingleSelection)
        self._documents.verticalHeader().setVisible(False)
        self._documents.setContextMenuPolicy(Qt.CustomContextMenu)
        self._documents.customContextMenuRequested.connect(
            self._show_document_context_menu
        )
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
            from ..knowledge_index_ui import KnowledgeIndexRebuildDialog

            self._index_dialog = KnowledgeIndexRebuildDialog(self._knowledge_index_service, self)
            self._index_dialog.submitted.connect(lambda _task_id: self.refresh_documents())
        self._index_dialog.open()

    def refresh_documents(self) -> None:
        if self._shutdown or not self._active or self._workspace_service is None:
            return
        self._refresh_document_list()
        self._refresh_workspace_status()

    def _next_request_id(self) -> int:
        self._request_sequence += 1
        return self._request_sequence

    def _refresh_document_list(self) -> None:
        if self._documents_request_id is not None:
            self._documents_pending = True
            return
        if self._last_documents is None:
            self._document_state = _DocumentViewportState.LOADING
            self._render_document_state()
        generation = self._lifecycle_generation
        request_id = self._next_request_id()
        task = _DocumentsLoadTask(
            self._workspace_service,
            generation,
            request_id,
        )
        task.signals.finished.connect(self._on_documents_finished)
        self._documents_request_id = request_id
        self._document_tasks[request_id] = task
        self._thread_pool.start(task)

    def _refresh_workspace_status(self) -> None:
        if self._status_request_id is not None:
            self._status_pending = True
            return
        generation = self._lifecycle_generation
        request_id = self._next_request_id()
        task = _StatusLoadTask(
            self._workspace_service,
            generation,
            request_id,
        )
        task.signals.finished.connect(self._on_status_finished)
        self._status_request_id = request_id
        self._status_tasks[request_id] = task
        self._thread_pool.start(task)

    def _on_documents_finished(
        self,
        generation: int,
        request_id: int,
        result: object,
    ) -> None:
        self._document_tasks.pop(request_id, None)
        if request_id != self._documents_request_id:
            return
        self._documents_request_id = None
        if generation != self._lifecycle_generation or not self._active:
            return
        from ...services.knowledge_workspace_service import (
            KnowledgeWorkspaceDocuments,
            KnowledgeWorkspaceDocumentsState,
        )

        if isinstance(result, KnowledgeWorkspaceDocuments):
            if result.state is KnowledgeWorkspaceDocumentsState.UNAVAILABLE:
                self._document_state = _DocumentViewportState.UNAVAILABLE
            elif result.items:
                self._last_documents = result
                self._document_state = _DocumentViewportState.READY
            else:
                self._last_documents = result
                self._document_state = _DocumentViewportState.EMPTY
        else:
            self._document_state = _DocumentViewportState.UNAVAILABLE
        self._render_document_state()
        if self._documents_pending:
            self._documents_pending = False
            self._refresh_document_list()

    def _on_status_finished(
        self,
        generation: int,
        request_id: int,
        result: object,
    ) -> None:
        self._status_tasks.pop(request_id, None)
        if request_id != self._status_request_id:
            return
        self._status_request_id = None
        if generation != self._lifecycle_generation or not self._active:
            return
        from ...services.knowledge_workspace_service import KnowledgeWorkspaceStatus

        if isinstance(result, KnowledgeWorkspaceStatus):
            self._last_status = result
        self._render_status()
        if self._status_pending:
            self._status_pending = False
            self._refresh_workspace_status()

    def _render_document_state(self) -> None:
        documents = self._last_documents.items if self._last_documents is not None else ()
        selected_document_id = self._selected_document_id()
        self._documents.setRowCount(len(documents))
        selected_row = -1
        for row_index, document in enumerate(documents):
            values = (
                document.title,
                document.source_format.upper(),
                (
                    self.tr("Removing…")
                    if document.document_id == self._removing_document_id
                    else self._translated_content_state(document.content_state)
                ),
                document.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, document)
                self._documents.setItem(row_index, column, item)
            if document.document_id == selected_document_id:
                selected_row = row_index
        if selected_row >= 0:
            self._documents.selectRow(selected_row)

        has_stale_documents = bool(documents)
        show_documents = (
            self._document_state is _DocumentViewportState.READY
            or (
                self._document_state
                in {
                    _DocumentViewportState.LOADING,
                    _DocumentViewportState.UNAVAILABLE,
                }
                and has_stale_documents
            )
        )
        self._documents.setVisible(show_documents)
        self._empty_state.setVisible(not show_documents)
        if self._document_state in {
            _DocumentViewportState.COLD,
            _DocumentViewportState.LOADING,
        }:
            self._empty_state.setText(self.tr("Loading Knowledge documents…"))
        elif self._document_state is _DocumentViewportState.UNAVAILABLE:
            self._empty_state.setText(
                self.tr("Knowledge content is temporarily unavailable.")
            )
        else:
            self._empty_state.setText(
                self.tr("No Knowledge documents yet. Import a file to get started.")
            )

    def _render_status(self) -> None:
        status = self._last_status
        if status is None:
            self._footer_status.setText(self.tr("Loading Knowledge status…"))
            self._refresh_timer.stop()
            return
        index = status.indexes
        keyword = self._translated_index_state(index.keyword_state) if index else self.tr("Unavailable")
        vector = self._translated_index_state(index.text_vector_state) if index else self.tr("Unavailable")
        ocr = self._translated_ocr_state(str(status.ocr.state))
        self._footer_status.setText(
            self.tr("OCR: %1  ·  Keyword: %2  ·  Text vectors: %3")
            .replace("%1", ocr)
            .replace("%2", keyword)
            .replace("%3", vector)
        )
        if status.has_active_work and self._active:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def _selected_document_id(self) -> str | None:
        document = self._selected_document()
        return document.document_id if document is not None else None

    def _selected_document(self) -> KnowledgeWorkspaceDocument | None:
        row = self._documents.currentRow()
        return self._document_at_row(row)

    def _document_at_row(self, row: int) -> KnowledgeWorkspaceDocument | None:
        if row < 0:
            return None
        item = self._documents.item(row, 0)
        document = item.data(Qt.UserRole) if item is not None else None
        return document if document is not None else None

    def _show_document_context_menu(self, position) -> None:
        item = self._documents.itemAt(position)
        if item is None or self._document_lifecycle is None:
            return
        document = self._document_at_row(item.row())
        if document is None:
            return
        self._documents.selectRow(item.row())
        menu = QMenu(self)
        delete_action = menu.addAction(self.tr("Delete"))
        delete_action.setEnabled(self._removal_task is None)
        selected_action = self._exec_document_context_menu(
            menu,
            self._documents.viewport().mapToGlobal(position)
        )
        if selected_action is delete_action:
            self._confirm_document_removal(document)

    @staticmethod
    def _exec_document_context_menu(menu: QMenu, global_position):
        return menu.exec(global_position)

    def _confirm_document_removal(
        self,
        document: KnowledgeWorkspaceDocument,
    ) -> None:
        if self._removal_task is not None:
            return
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle(self.tr("Delete document"))
        message.setText(
            self.tr('Delete “%1” from the Knowledge Library?').replace(
                "%1",
                document.title,
            )
        )
        message.setInformativeText(
            self.tr(
                "Xenix will remove its imported copy, search data, and related "
                "task entries. The original file will remain unchanged. "
                "This action cannot be undone."
            )
        )
        delete_button = message.addButton(
            self.tr("Delete"),
            QMessageBox.DestructiveRole,
        )
        cancel_button = message.addButton(QMessageBox.Cancel)
        message.setDefaultButton(cancel_button)
        message.exec()
        if message.clickedButton() is delete_button:
            self._start_document_removal(document)

    def _start_document_removal(
        self,
        document: KnowledgeWorkspaceDocument,
    ) -> None:
        if self._document_lifecycle is None or self._removal_task is not None:
            return
        self._removing_document_id = document.document_id
        self._render_document_state()
        task = _DocumentRemovalTask(
            self._document_lifecycle,
            self._lifecycle_generation,
            document.document_id,
        )
        task.signals.finished.connect(self._on_document_removal_finished)
        self._removal_task = task
        self._thread_pool.start(task)

    def _on_document_removal_finished(
        self,
        generation: int,
        result: object,
    ) -> None:
        self._removal_task = None
        self._removing_document_id = None
        if not self._active:
            return
        if generation != self._lifecycle_generation:
            self.refresh_documents()
            return
        if isinstance(result, Exception):
            self._render_document_state()
            error_code = getattr(result, "error_code", None)
            if error_code == "knowledge_document_busy":
                text = self.tr(
                    "This document is still being imported or prepared. "
                    "Wait for the task to finish, then try again."
                )
            elif error_code == "knowledge_document_not_found":
                text = self.tr(
                    "This document is no longer in the Knowledge Library."
                )
                self.refresh_documents()
            else:
                text = self.tr("The document could not be deleted.")
            QMessageBox.warning(
                self,
                self.tr("Delete document"),
                text,
            )
            return
        self.refresh_documents()
        if self._queue_dialog is not None and self._queue_dialog.isVisible():
            self._queue_dialog.refresh()

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
        self._render_document_state()
        self._render_status()
        if self._queue_dialog is not None:
            self._queue_dialog.retranslate_ui()

    def showEvent(self, event) -> None:
        if self._shutdown:
            super().showEvent(event)
            self.hide()
            return
        self._active = True
        self._lifecycle_generation += 1
        if self._last_documents is None:
            self._document_state = _DocumentViewportState.LOADING
            self._render_document_state()
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_documents)

    def hideEvent(self, event) -> None:
        self._deactivate()
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
        self._documents_request_id = None
        self._status_request_id = None
        self._documents_pending = False
        self._status_pending = False
        self._refresh_timer.stop()
        if self._queue_dialog is not None:
            self._queue_dialog.hide()
        if self._index_dialog is not None:
            self._index_dialog.hide()

    def shutdown(self) -> None:
        """Quiesce UI-owned tasks before their application services are closed."""
        if self._shutdown:
            return
        self._shutdown = True
        self._deactivate()
        if self._queue_dialog is not None:
            self._queue_dialog.shutdown()
        self._thread_pool.waitForDone()

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
