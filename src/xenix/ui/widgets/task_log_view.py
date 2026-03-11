from __future__ import annotations

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
        self._text.setPlaceholderText("Task logs will appear here.")
        layout.addWidget(self._text)

    def set_logs(self, logs: list[TaskLogEntry]) -> None:
        if not logs:
            self._text.clear()
            return
        self._text.setPlainText(
            "\n".join(f"[{entry.timestamp}] {entry.level}: {entry.message}" for entry in logs)
        )

    def clear(self) -> None:
        self._text.clear()
