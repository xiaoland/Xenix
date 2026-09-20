from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QFrame, QPlainTextEdit, QVBoxLayout, QWidget

from ...services.ml.contracts import TaskLogEntry


class TaskLogView(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        layout.addWidget(self._text)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._text.setPlaceholderText(self.tr("Task logs will appear here."))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def set_logs(self, logs: list[TaskLogEntry]) -> None:
        if not logs:
            self._text.clear()
            return
        text = "\n".join(f"[{entry.timestamp}] {entry.level}: {entry.message}" for entry in logs)
        if self._text.toPlainText() == text:
            return
        scroll = self._text.verticalScrollBar()
        previous, following = scroll.value(), scroll.value() == scroll.maximum()
        self._text.setPlainText(text)
        scroll.setValue(scroll.maximum() if following else previous)

    def clear(self) -> None:
        self._text.clear()
