from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.knowledge_import_service import KnowledgeImportService
from ..services.knowledge_index_service import KnowledgeIndexService
from ..services.knowledge_service import KnowledgeService
from ..services.knowledge_pipeline import (
    SUPPORTED_KNOWLEDGE_SUFFIXES,
    knowledge_file_dialog_filter,
)
from ..services.knowledge_derivation_service import KnowledgeDerivationService
from ..services.paddle_ocr_service import (
    PaddleOcrDeploymentService,
    PaddleOcrStatus,
)
from .ocr_deployment_tasks import OcrStatusTask
from .knowledge_index_ui import KnowledgeIndexRebuildDialog


IMPORT_POLL_INTERVAL_MS = 500


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
        self._refresh_timer.setInterval(IMPORT_POLL_INTERVAL_MS)
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
            "{timestamp}  {phase} — {event}".format(
                timestamp=entry.timestamp,
                phase=self._translated_phase(entry.phase),
                event=self._translated_event(entry.event_code),
            )
            for entry in entries
        ]
        self._content.setPlainText(
            "\n".join(lines) if lines else self.tr("No import events have been recorded yet.")
        )
        cursor = self._content.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._content.setTextCursor(cursor)

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
            "needs_attention": self.tr("Needs attention"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
        }
        return translations.get(phase, phase)

    def _translated_event(self, event_code: str) -> str:
        translations = {
            "import_queued": self.tr("Import queued"),
            "import_retry_queued": self.tr("Retry queued"),
            "source_snapshot_started": self.tr("Source snapshot started"),
            "source_snapshot_published": self.tr("Source snapshot published"),
            "source_snapshot_verified": self.tr("Source snapshot verified"),
            "source_probed": self.tr("Source format verified"),
            "worker_started": self.tr("Import worker started"),
            "normalization_started": self.tr("Normalization started"),
            "routing_started": self.tr("Parser selected"),
            "parsing_started": self.tr("Document parsing started"),
            "canonical_write_started": self.tr("Canonical content write started"),
            "worker_succeeded": self.tr("Import worker completed"),
            "worker_failed": self.tr("Import worker reported a failure"),
            "worker_cancelled": self.tr("Import worker cancelled"),
            "worker_interrupted_for_shutdown": self.tr(
                "Import paused while Xenix was closing"
            ),
            "import_completed": self.tr("Import completed"),
            "document_reused": self.tr("Existing document reused"),
            "cancellation_requested": self.tr("Cancellation requested"),
            "import_cancelled": self.tr("Import cancelled"),
        }
        return translations.get(event_code, event_code.replace("_", " "))

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


class KnowledgeImportQueueDialog(QDialog):
    def __init__(
        self,
        import_service: KnowledgeImportService,
        derivation_service: KnowledgeDerivationService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._service = import_service
        self._derivation_service = derivation_service
        self._log_dialog: KnowledgeImportLogDialog | None = None
        self._list = QListWidget(self)
        self._list.currentItemChanged.connect(self._sync_actions)
        self._retry_button = QPushButton(self)
        self._retry_button.clicked.connect(self._retry_selected)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._cancel_selected)
        self._view_log_button = QPushButton(self)
        self._view_log_button.clicked.connect(self._view_selected_log)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(IMPORT_POLL_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        actions = QHBoxLayout()
        actions.addWidget(self._retry_button)
        actions.addWidget(self._cancel_button)
        actions.addWidget(self._view_log_button)
        actions.addStretch(1)
        actions.addWidget(self._close_button)
        layout.addLayout(actions)
        self.resize(620, 360)
        self.retranslate_ui()

    def refresh(self) -> None:
        selected = self._selected_import_id()
        self._list.clear()
        for item in self._service.list_imports():
            status = self._translated_status(getattr(item, "status", None))
            phase = self._translated_phase(getattr(item, "phase", None))
            details = [
                self.tr("Status: %1").replace("%1", status),
                self.tr("Phase: %1").replace("%1", phase),
            ]
            if bool(getattr(item, "reused_existing", False)):
                details.append(self.tr("Reused existing document"))
            error_code = getattr(item, "error_code", None)
            if isinstance(error_code, str) and error_code:
                details.append(self._translated_error(error_code))
            derivation = (
                self._derivation_service.status_for_import(str(item.import_id))
                if self._derivation_service is not None
                else None
            )
            if derivation is not None:
                details.append(
                    self.tr("Search index: %1").replace(
                        "%1",
                        self._translated_derivation(derivation.status, derivation.phase),
                    )
                )
                if derivation.error_code:
                    details.append(self._translated_error(derivation.error_code))
            file_name = str(getattr(item, "file_name", self.tr("Knowledge document")))
            row = QListWidgetItem(f"{file_name} — {' · '.join(details)}")
            row.setData(Qt.UserRole, str(getattr(item, "import_id", "")))
            row.setData(Qt.UserRole + 1, str(getattr(item, "status", "")))
            row.setData(Qt.UserRole + 2, str(error_code or ""))
            row.setData(Qt.UserRole + 3, bool(getattr(item, "retryable", False)))
            row.setData(
                Qt.UserRole + 4,
                bool(derivation is not None and derivation.retryable),
            )
            self._list.addItem(row)
            if selected and selected == str(getattr(item, "import_id", "")):
                self._list.setCurrentItem(row)
        self._sync_actions()

    def _selected_import_id(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = str(item.data(Qt.UserRole) or "")
        return value or None

    def _view_selected_log(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        import_id = str(item.data(Qt.UserRole) or "")
        if not import_id:
            return
        if self._log_dialog is None:
            self._log_dialog = KnowledgeImportLogDialog(self._service, self)
        text = item.text()
        file_name = text.split(" — ", 1)[0]
        self._log_dialog.show_import(import_id, file_name)

    def _retry_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        import_id = str(item.data(Qt.UserRole) or "")
        error_code = str(item.data(Qt.UserRole + 2) or "")
        if not import_id:
            return
        if bool(item.data(Qt.UserRole + 4)) and self._derivation_service is not None:
            try:
                self._derivation_service.retry_for_import(import_id)
            except Exception:
                QMessageBox.warning(
                    self,
                    self.tr("Knowledge Import Failed"),
                    self.tr("The search index could not be retried."),
                )
            self.refresh()
            return
        password: str | None = None
        source_path: Path | None = None
        if error_code in {"knowledge_password_required", "knowledge_password_invalid"}:
            password, accepted = QInputDialog.getText(
                self,
                self.tr("Document password"),
                self.tr("Enter the password for this document. It will not be saved."),
                QLineEdit.Password,
            )
            if not accepted or not password:
                return
        if error_code == "knowledge_source_reselection_required":
            selected, _filter = QFileDialog.getOpenFileName(
                self,
                self.tr("Select Knowledge Source"),
                "",
                knowledge_file_dialog_filter(self.tr("Knowledge documents")),
            )
            if not selected:
                return
            source_path = Path(selected)
        try:
            self._service.retry_import(
                import_id,
                password=password,
                source_path=source_path,
            )
        except Exception:
            QMessageBox.warning(
                self,
                self.tr("Knowledge Import Failed"),
                self.tr("The import could not be retried."),
            )
        self.refresh()

    def _cancel_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        import_id = str(item.data(Qt.UserRole) or "")
        if import_id:
            self._service.cancel_import(import_id)
        self.refresh()

    def _sync_actions(self, *_args) -> None:
        item = self._list.currentItem()
        status = str(item.data(Qt.UserRole + 1) or "") if item is not None else ""
        retryable = bool(item.data(Qt.UserRole + 3)) if item is not None else False
        derivation_retryable = (
            bool(item.data(Qt.UserRole + 4)) if item is not None else False
        )
        self._retry_button.setEnabled(
            bool(item is not None and (retryable or derivation_retryable))
        )
        self._cancel_button.setEnabled(status in {"queued", "running"})
        self._view_log_button.setEnabled(item is not None)

    def _translated_status(self, status: object) -> str:
        translations = {
            "pending": self.tr("Pending"),
            "queued": self.tr("Queued"),
            "running": self.tr("In progress"),
            "canonical_ready": self.tr("Canonical content ready"),
            "retrieval_ready": self.tr("Ready for retrieval"),
            "needs_attention": self.tr("Needs attention"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
            "reused": self.tr("Reused"),
        }
        return translations.get(status, self.tr("Unknown status"))

    def _translated_phase(self, phase: object) -> str:
        translations = {
            "queued": self.tr("Waiting in queue"),
            "snapshot": self.tr("Copying source"),
            "probing": self.tr("Checking file"),
            "normalizing": self.tr("Normalizing document"),
            "routing": self.tr("Selecting parser"),
            "parsing": self.tr("Reading document"),
            "publishing_canonical": self.tr("Saving canonical content"),
            "derivation_queued": self.tr("Waiting to build search index"),
            "deriving": self.tr("Building search index"),
            "completed": self.tr("Completed"),
            "no_text_projection": self.tr(
                "Canonical content contains no searchable text"
            ),
            "derivation_failed": self.tr("Search index build failed"),
            "needs_attention": self.tr("Needs attention"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
            "source_snapshot_unavailable": self.tr("Source snapshot unavailable"),
            "source_reselection_required": self.tr("Select the source file again"),
        }
        return translations.get(phase, self.tr("Unknown phase"))

    def _translated_derivation(self, status: str, phase: str) -> str:
        if status == "succeeded" and phase == "no_text_projection":
            return self.tr("No searchable text")
        translations = {
            "queued": self.tr("Waiting"),
            "running": self.tr("In progress"),
            "succeeded": self.tr("Ready"),
            "failed": self.tr("Failed"),
        }
        return translations.get(status, self.tr("Unknown status"))

    def _translated_error(self, error_code: str) -> str:
        translations = {
            "knowledge_password_required": self.tr(
                "A password is required to continue this import."
            ),
            "knowledge_password_invalid": self.tr(
                "The document password was not accepted."
            ),
            "knowledge_office_converter_unavailable": self.tr(
                "LibreOffice is required to import this DOC file."
            ),
            "knowledge_office_conversion_failed": self.tr(
                "The DOC file could not be converted."
            ),
            "knowledge_format_unsupported": self.tr(
                "This file type is not supported by the Knowledge Library."
            ),
            "knowledge_format_mismatch": self.tr(
                "The file signature does not match its extension."
            ),
            "knowledge_pdf_invalid": self.tr("The PDF is structurally invalid."),
            "knowledge_source_size_unsupported": self.tr(
                "The file size is outside the supported range."
            ),
            "knowledge_text_encoding_unknown": self.tr(
                "The TXT encoding could not be identified safely."
            ),
            "knowledge_text_encoding_invalid": self.tr(
                "The TXT content is invalid for its encoding."
            ),
            "knowledge_text_controls_invalid": self.tr(
                "The TXT file contains unsupported control characters."
            ),
            "knowledge_text_line_too_long": self.tr(
                "The TXT file contains a line that is too long."
            ),
            "knowledge_docx_package_invalid": self.tr(
                "The DOCX file is not a valid Office document."
            ),
            "knowledge_docx_entry_limit": self.tr(
                "The DOCX package contains too many entries."
            ),
            "knowledge_docx_entries_ambiguous": self.tr(
                "The DOCX package contains ambiguous entries."
            ),
            "knowledge_docx_entry_encrypted": self.tr(
                "The DOCX package contains an unsupported encrypted entry."
            ),
            "knowledge_docx_entry_unsafe": self.tr(
                "The DOCX package contains an unsafe entry."
            ),
            "knowledge_docx_path_unsafe": self.tr(
                "The DOCX package contains an unsafe path."
            ),
            "knowledge_docx_size_invalid": self.tr(
                "The DOCX package contains invalid size metadata."
            ),
            "knowledge_docx_entry_too_large": self.tr(
                "The DOCX package contains an entry that is too large."
            ),
            "knowledge_docx_expansion_limit": self.tr(
                "The expanded DOCX package is too large."
            ),
            "knowledge_docx_compression_ratio": self.tr(
                "The DOCX package compression ratio is unsafe."
            ),
            "knowledge_docling_parse_failed": self.tr(
                "The document could not be parsed into canonical content."
            ),
            "knowledge_canonical_integrity_failed": self.tr(
                "Canonical content failed integrity validation."
            ),
            "knowledge_canonical_generation_missing": self.tr(
                "Canonical content is unavailable for indexing."
            ),
            "knowledge_derivation_failed": self.tr(
                "The search index could not be built."
            ),
            "knowledge_document_missing": self.tr(
                "The imported document is unavailable for indexing."
            ),
            "knowledge_import_cancelled": self.tr("The import was cancelled."),
            "knowledge_source_snapshot_unavailable": self.tr(
                "The app-owned source snapshot is unavailable."
            ),
            "knowledge_source_integrity_failed": self.tr(
                "The app-owned source snapshot failed integrity validation."
            ),
            "knowledge_source_reselection_required": self.tr(
                "Select the source file again to retry this import."
            ),
            "knowledge_import_failed": self.tr("The file could not be imported."),
        }
        return translations.get(error_code, self.tr("The file could not be imported."))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Knowledge Import Queue"))
        self._retry_button.setText(self.tr("Retry"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._view_log_button.setText(self.tr("View log"))
        self._close_button.setText(self.tr("Close"))
        if self._log_dialog is not None:
            self._log_dialog.retranslate_ui()

    def showEvent(self, event) -> None:
        self.refresh()
        self._refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._refresh_timer.stop()
        if self._log_dialog is not None:
            self._log_dialog.hide()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._refresh_timer.stop()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)


class KnowledgeWorkspaceDialog(QDialog):
    def __init__(
        self,
        *,
        import_service: KnowledgeImportService,
        derivation_service: KnowledgeDerivationService | None = None,
        knowledge_service: KnowledgeService | None = None,
        knowledge_index_service: KnowledgeIndexService | None = None,
        ocr_deployment: PaddleOcrDeploymentService | None = None,
        open_knowledge_settings: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._import_service = import_service
        self._derivation_service = derivation_service
        self._knowledge_service = knowledge_service
        self._knowledge_index_service = knowledge_index_service
        self._ocr_deployment = ocr_deployment
        self._open_knowledge_settings = open_knowledge_settings
        self._queue_dialog: KnowledgeImportQueueDialog | None = None
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._lifecycle_generation = 0
        self._active = False
        self._cached_ocr_status: PaddleOcrStatus | None = None
        self._ocr_status_task: OcrStatusTask | None = None

        self._description = QLabel(self)
        self._description.setWordWrap(True)
        self._ocr_status = QLabel(self)
        self._index_status = QLabel(self)
        self._empty_state = QLabel(self)
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._documents = QTableWidget(self)
        self._documents.setColumnCount(4)
        self._documents.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._documents.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._documents.setSelectionMode(QAbstractItemView.SingleSelection)
        self._documents.verticalHeader().setVisible(False)
        self._documents.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        for column in (1, 2, 3):
            self._documents.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeToContents
            )
        self._import_button = QPushButton(self)
        self._queue_button = QPushButton(self)
        self._rebuild_button = QPushButton(self)
        self._settings_button = QPushButton(self)
        self._import_button.clicked.connect(self._choose_files)
        self._queue_button.clicked.connect(self.open_import_queue)
        self._rebuild_button.clicked.connect(self._open_index_rebuild)
        self._settings_button.clicked.connect(self._open_settings)
        self._settings_button.setEnabled(self._open_knowledge_settings is not None)
        self._rebuild_button.setEnabled(self._knowledge_index_service is not None)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1_000)
        self._refresh_timer.timeout.connect(self.refresh_documents)
        buttons = QHBoxLayout()
        buttons.addWidget(self._import_button)
        buttons.addWidget(self._queue_button)
        buttons.addWidget(self._rebuild_button)
        buttons.addStretch(1)
        buttons.addWidget(self._settings_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._description)
        layout.addWidget(self._ocr_status)
        layout.addWidget(self._index_status)
        layout.addLayout(buttons)
        layout.addWidget(self._documents, 1)
        layout.addWidget(self._empty_state, 1)
        self.resize(860, 520)
        self.retranslate_ui()
        self.refresh_documents()

    def open_import_queue(self) -> None:
        if self._queue_dialog is None:
            self._queue_dialog = KnowledgeImportQueueDialog(
                self._import_service,
                self._derivation_service,
                self,
            )
        self._queue_dialog.show()
        self._queue_dialog.raise_()
        self._queue_dialog.activateWindow()

    def _choose_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            self.tr("Import Knowledge"),
            "",
            knowledge_file_dialog_filter(self.tr("Knowledge documents")),
        )
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
            self.open_import_queue()
        if failed_count:
            QMessageBox.warning(
                self,
                self.tr("Knowledge Import Failed"),
                self.tr("%1 file(s) could not be queued for import.").replace(
                    "%1", str(failed_count)
                ),
            )

    def _open_settings(self) -> None:
        if self._open_knowledge_settings is not None:
            self._open_knowledge_settings()

    def _open_index_rebuild(self) -> None:
        if self._knowledge_index_service is None:
            return
        if self._index_dialog is None:
            self._index_dialog = KnowledgeIndexRebuildDialog(
                self._knowledge_index_service,
                self,
            )
            self._index_dialog.submitted.connect(
                lambda _task_id: self.refresh_documents()
            )
        self._index_dialog.open()

    def refresh_documents(self) -> None:
        documents_unavailable = False
        try:
            documents = (
                self._knowledge_service.list_documents()
                if self._knowledge_service is not None
                else []
            )
        except Exception:
            documents = []
            documents_unavailable = True
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
            if documents_unavailable
            else self.tr("No Knowledge documents yet. Import a file to get started.")
        )
        self._render_index_status()

    def _render_index_status(self) -> None:
        if self._knowledge_index_service is None:
            self._index_status.setText(self.tr("Knowledge index status is unavailable"))
            return
        try:
            status = self._knowledge_index_service.status()
        except Exception:
            self._index_status.setText(self.tr("Knowledge index status is unavailable"))
            return
        self._index_status.setText(
            self.tr("Keyword: %1  ·  Text vectors: %2")
            .replace("%1", self._translated_index_state(status.keyword_state))
            .replace(
                "%2", self._translated_index_state(status.text_vector_state)
            )
        )

    def _translated_index_state(self, state: str) -> str:
        translations = {
            "ready": self.tr("Ready"),
            "building": self.tr("Building"),
            "needs_rebuild": self.tr("Needs rebuild"),
            "unavailable": self.tr("Unavailable"),
            "needs_attention": self.tr("Needs attention"),
        }
        return translations.get(state, self.tr("Unknown status"))

    def _translated_content_state(self, state: str) -> str:
        translations = {
            "ready": self.tr("Searchable"),
            "processing": self.tr("Preparing search content"),
            "no_searchable_text": self.tr("No searchable text"),
            "needs_attention": self.tr("Needs attention"),
        }
        return translations.get(state, self.tr("Unknown status"))

    def _schedule_ocr_status_probe(self) -> None:
        if (
            not self._active
            or self._ocr_status_task is not None
            or self._ocr_deployment is None
        ):
            return
        generation = self._lifecycle_generation
        task = OcrStatusTask(self._ocr_deployment, generation)
        task.signals.finished.connect(self._on_ocr_status_finished)
        self._ocr_status_task = task
        self._thread_pool.start(task)

    def _on_ocr_status_finished(self, generation: int, status: PaddleOcrStatus) -> None:
        self._ocr_status_task = None
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._schedule_ocr_status_probe()
            return
        self._cached_ocr_status = status
        self._render_ocr_status()

    def _render_ocr_status(self) -> None:
        status = self._cached_ocr_status
        if self._ocr_deployment is None:
            text = self.tr("OCR settings are unavailable")
        elif status is None:
            text = self.tr("Checking local PaddleOCR status")
        elif status.installed and status.models_ready:
            text = self.tr("Local PaddleOCR is ready")
        elif status.installed:
            text = self.tr("Local PaddleOCR runtime is installed; models are not ready")
        else:
            text = self.tr("Local PaddleOCR is not installed")
        self._ocr_status.setText(text)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Knowledge Workspace"))
        self._description.setText(
            self.tr(
                "Import TXT, DOC, DOCX, PDF, JPEG, or PNG files. "
                "Xenix indexes bounded evidence for Agent analysis."
            )
        )
        self._import_button.setText(self.tr("Import documents"))
        self._queue_button.setText(self.tr("Import queue"))
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
        self._empty_state.setText(
            self.tr("No Knowledge documents yet. Import a file to get started.")
        )
        self._render_ocr_status()
        self.refresh_documents()
        if self._queue_dialog is not None:
            self._queue_dialog.retranslate_ui()
            self._queue_dialog.refresh()
        if self._index_dialog is not None:
            self._index_dialog.retranslate_ui()

    def showEvent(self, event) -> None:
        self._active = True
        self._lifecycle_generation += 1
        self._render_ocr_status()
        super().showEvent(event)
        self.refresh_documents()
        self._refresh_timer.start()
        self._schedule_ocr_status_probe()

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
