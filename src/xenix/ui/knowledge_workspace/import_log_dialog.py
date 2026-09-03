"""Read-only log viewer for one Knowledge import."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ._tasks import TASK_POLL_INTERVAL_MS

if TYPE_CHECKING:
    from ...services.knowledge_import_service import KnowledgeImportService


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
