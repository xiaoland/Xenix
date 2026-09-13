from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..exceptions import report_exception
from ..services.knowledge_index_service import (
    KnowledgeIndexKind,
    KnowledgeIndexOverview,
    KnowledgeIndexService,
)
from .knowledge_index_status import KnowledgeIndexStatusRequest


class KnowledgeIndexRebuildDialog(QDialog):
    submitted = Signal(object)

    def __init__(
        self,
        index_service: KnowledgeIndexService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModal)
        self._service = index_service
        self._active = False
        self._generation = 0
        self._status_request: KnowledgeIndexStatusRequest | None = None
        self._status: KnowledgeIndexOverview | None = None
        self._status_failed = False
        self._summary = QLabel(self)
        self._summary.setWordWrap(True)
        self._keyword_checkbox = QCheckBox(self)
        self._text_vector_checkbox = QCheckBox(self)
        self._buttons = QDialogButtonBox(parent=self)
        self._rebuild_button = self._buttons.addButton(
            "",
            QDialogButtonBox.AcceptRole,
        )
        self._cancel_button = self._buttons.addButton(
            "",
            QDialogButtonBox.RejectRole,
        )
        self._buttons.accepted.connect(self._submit)
        self._buttons.rejected.connect(self.reject)
        self._keyword_checkbox.toggled.connect(self._sync_submit_state)
        self._text_vector_checkbox.toggled.connect(self._sync_submit_state)
        layout = QVBoxLayout(self)
        layout.addWidget(self._summary)
        layout.addWidget(self._keyword_checkbox)
        layout.addWidget(self._text_vector_checkbox)
        layout.addWidget(self._buttons)
        self.resize(520, 240)
        self.retranslate_ui()

    def refresh(self) -> None:
        if not self._active or self._status_request is not None:
            return
        self._status = None
        self._status_failed = False
        self._render_status()
        request = KnowledgeIndexStatusRequest(self._generation)
        request.finished.connect(self._on_status_finished, Qt.ConnectionType.QueuedConnection)
        self._status_request = request
        request.start(self._service)

    def _on_status_finished(self, request: object, generation: int, result: object) -> None:
        if request is not self._status_request:
            return
        self._status_request = None
        if not self._active or generation != self._generation:
            if self._active:
                self.refresh()
            return
        self._status = result if isinstance(result, KnowledgeIndexOverview) else None
        self._status_failed = self._status is None
        self._render_status(reset_selection=True)
        if isinstance(result, Exception):
            report_exception(result)

    def _render_status(self, *, reset_selection: bool = False) -> None:
        status = self._status
        if status is None:
            self._summary.setText(
                self.tr("Knowledge index status is unavailable.")
                if self._status_failed
                else QCoreApplication.translate("SettingsDialog", "Checking Knowledge index status")
            )
            self._keyword_checkbox.setEnabled(False)
            self._text_vector_checkbox.setEnabled(False)
            self._keyword_checkbox.setChecked(False)
            self._text_vector_checkbox.setChecked(False)
            self._sync_submit_state()
            return
        self._summary.setText(
            self.tr(
                "%1 searchable unit(s). A text vector rebuild is estimated to use "
                "%2 provider request(s)."
            )
            .replace("%1", str(status.unit_count))
            .replace("%2", str(status.estimated_vector_requests))
        )
        self._keyword_checkbox.setEnabled(status.unit_count > 0)
        self._text_vector_checkbox.setEnabled(
            status.vector_configured and status.unit_count > 0
        )
        if reset_selection:
            self._keyword_checkbox.setChecked(status.unit_count > 0)
            self._text_vector_checkbox.setChecked(
                status.vector_configured and status.unit_count > 0
            )
        self._sync_submit_state()

    def _submit(self) -> None:
        if not self._rebuild_button.isEnabled():
            return
        selected: list[KnowledgeIndexKind] = []
        if self._keyword_checkbox.isChecked():
            selected.append(KnowledgeIndexKind.KEYWORD)
        if self._text_vector_checkbox.isChecked():
            selected.append(KnowledgeIndexKind.TEXT_VECTOR)
        if not selected:
            return
        try:
            task_id = self._service.enqueue_rebuild(selected, trigger="manual")
        except Exception as exc:
            report_exception(exc)
            return
        self.submitted.emit(task_id)
        self.accept()

    def _sync_submit_state(self) -> None:
        self._rebuild_button.setEnabled(
            (self._keyword_checkbox.isEnabled() and self._keyword_checkbox.isChecked())
            or (self._text_vector_checkbox.isEnabled() and self._text_vector_checkbox.isChecked())
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Rebuild Knowledge Indexes"))
        self._keyword_checkbox.setText(self.tr("Keyword index"))
        self._text_vector_checkbox.setText(self.tr("Text semantic vector index"))
        self._rebuild_button.setText(self.tr("Rebuild"))
        self._cancel_button.setText(self.tr("Cancel"))

    def showEvent(self, event) -> None:
        self._active = True
        self._generation += 1
        self.refresh()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._active = False
        self._generation += 1
        if self._status_request is not None:
            self._status_request.cancel()
        super().hideEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self._render_status()


__all__ = ["KnowledgeIndexRebuildDialog"]
