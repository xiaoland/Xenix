"""Knowledge-tab index status and rebuild card."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QPushButton, QWidget

from ...services.knowledge_index_service import (
    KnowledgeIndexOverview,
    KnowledgeIndexService,
)
from ..knowledge_index_status import KnowledgeIndexStatusRequest
from ..knowledge_index_ui import KnowledgeIndexRebuildDialog
from ..semantic_identity import identify


class KnowledgeIndexStatusCard(QFrame):
    """Knowledge index status presentation plus its status polling and rebuild."""

    def __init__(
        self,
        knowledge_index_service: KnowledgeIndexService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._service = knowledge_index_service
        self._shutdown = False
        self._active = False
        self._lifecycle_generation = 0
        self._cached_status: KnowledgeIndexOverview | None = None
        self._status_request: KnowledgeIndexStatusRequest | None = None
        self._status_failed = False
        self._refresh_pending = False
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1_000)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._schedule_status_probe)

        self._title_label = QLabel()
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._rebuild_button = QPushButton()
        identify(self._rebuild_button, "settings.knowledge.indexes.rebuild")

        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addRow(self._title_label)
        layout.addRow(self._status_label)
        layout.addRow(self._rebuild_button)
        self._rebuild_button.clicked.connect(self._open_index_rebuild)
        self.retranslate_ui()

    def activate(self) -> None:
        if self._shutdown:
            return
        self._active = True
        self._lifecycle_generation += 1
        self._render_status()
        self.refresh()

    def deactivate(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._refresh_pending = False
        self._refresh_timer.stop()
        if self._status_request is not None:
            self._status_request.cancel()
            self._status_request = None
        if self._index_dialog is not None:
            self._index_dialog.hide()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self.deactivate()

    def refresh(self, *, delay_ms: int = 0) -> None:
        if self._shutdown or not self._active or self._service is None:
            return
        if self._status_request is not None:
            self._refresh_pending = True
            return
        if self._cached_status is None:
            self._status_failed = False
            self._render_status()
        self._refresh_timer.start(max(0, delay_ms))

    def retranslate_ui(self) -> None:
        self._title_label.setText(QCoreApplication.translate("SettingsDialog", "Indexes"))
        self._rebuild_button.setText(QCoreApplication.translate("SettingsDialog", "Rebuild indexes..."))
        self._render_status()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_index_rebuild(self) -> None:
        if self._service is None:
            return
        if self._index_dialog is None:
            self._index_dialog = KnowledgeIndexRebuildDialog(self._service, self)
            self._index_dialog.submitted.connect(lambda _task_id: self.refresh())
        self._index_dialog.open()

    def _schedule_status_probe(self) -> None:
        if self._shutdown or not self._active or self._service is None:
            return
        if self._status_request is not None:
            self._refresh_pending = True
            return
        generation = self._lifecycle_generation
        request = KnowledgeIndexStatusRequest(generation)
        request.finished.connect(
            self._on_status_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._status_request = request
        request.start(self._service)

    def _on_status_finished(self, request: object, generation: int, result: object) -> None:
        if request is not self._status_request:
            return
        self._status_request = None
        if self._shutdown:
            return
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._refresh_pending = False
                self.refresh()
            return

        refresh_pending = self._refresh_pending
        self._refresh_pending = False
        if refresh_pending:
            self.refresh()
            return

        if isinstance(result, KnowledgeIndexOverview):
            self._cached_status = result
            self._status_failed = False
        else:
            self._cached_status = None
            self._status_failed = True
        self._render_status()

        if (
            isinstance(result, KnowledgeIndexOverview)
            and result.active_task_status in {"queued", "running"}
        ):
            self.refresh(delay_ms=1_000)

    def _render_status(self) -> None:
        if self._service is None:
            self._status_label.setText(
                QCoreApplication.translate("SettingsDialog", "Knowledge index service is unavailable")
            )
            self._rebuild_button.setEnabled(False)
            return
        status = self._cached_status
        if status is None:
            text = (
                QCoreApplication.translate("SettingsDialog", "Knowledge index status is unavailable")
                if self._status_failed
                else QCoreApplication.translate("SettingsDialog", "Checking Knowledge index status")
            )
            self._status_label.setText(text)
            self._rebuild_button.setEnabled(False)
            return
        self._status_label.setText(
            QCoreApplication.translate("SettingsDialog", "Keyword: %1\nText vectors: %2")
            .replace("%1", self._translated_index_state(status.keyword_state))
            .replace("%2", self._translated_index_state(status.text_vector_state))
        )
        self._rebuild_button.setEnabled(status.unit_count > 0)

    @staticmethod
    def _translated_index_state(state: str) -> str:
        translations = {
            "ready": QCoreApplication.translate("SettingsDialog", "Ready"),
            "building": QCoreApplication.translate("SettingsDialog", "Building"),
            "needs_rebuild": QCoreApplication.translate("SettingsDialog", "Needs rebuild"),
            "unavailable": QCoreApplication.translate("SettingsDialog", "Unavailable"),
            "needs_attention": QCoreApplication.translate("SettingsDialog", "Needs attention"),
        }
        return translations.get(state, QCoreApplication.translate("SettingsDialog", "Unknown status"))
