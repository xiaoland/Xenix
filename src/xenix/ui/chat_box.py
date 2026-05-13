from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..services.storage.models import AgentMessageAuthor, AgentMessageKind
from ..services.agent import ThreadSnapshot


class ChatMessageBubble(QFrame):
    def __init__(self, *, author: str, blocks: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatMessageBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        author_label = QLabel(author)
        author_label.setObjectName("chatMessageAuthor")
        layout.addWidget(author_label)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QFrame.NoFrame)
        browser.setMinimumHeight(36)
        browser.setMaximumHeight(260)
        browser.setMarkdown(self._render_blocks(blocks))
        layout.addWidget(browser)

    def _render_blocks(self, blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"text", "markdown"}:
                parts.append(str(block.get("text", "")))
            elif block_type == "file":
                parts.append(f"Attached file: `{block.get('path')}`")
            elif block_type == "turn_end":
                parts.append(f"---\n{block.get('summary', 'Turn ended.')}")
            elif block_type == "tool_call":
                parts.append(f"Calling `{block.get('tool_name')}`")
            elif block_type == "tool_call_result":
                parts.append(f"`{block.get('tool_name')}` completed.")
        return "\n\n".join(part for part in parts if part)


class ChatBox(QWidget):
    message_submitted = Signal(str, list)
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._attached_files: list[str] = []
        self._running = False

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(0, 0, 0, 0)
        self._message_layout.setSpacing(10)
        self._message_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._message_container)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._attachment_label = QLabel()
        self._attachment_label.setObjectName("chatAttachmentLabel")

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Ask Xenix to inspect data, train models, or run prediction...")
        self._editor.setMaximumHeight(96)

        self._send_button = QPushButton("Send")
        self._send_button.clicked.connect(self._handle_button_clicked)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.addWidget(self._editor, 1)
        input_row.addWidget(self._send_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(self._scroll, 1)
        root.addWidget(self._attachment_label)
        root.addLayout(input_row)
        self._update_attachment_label()
        self._apply_style()

    def render_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self.clear_messages()
        for message in snapshot.messages:
            if message.kind is AgentMessageKind.SYSTEM:
                continue
            if message.kind is AgentMessageKind.TOOL_CALL:
                continue
            self.add_message(self._author_label(message.ui_author), message.content_blocks)

    def clear_messages(self) -> None:
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_message(self, author: str, blocks: list[dict[str, Any]]) -> None:
        bubble = ChatMessageBubble(author=author, blocks=blocks, parent=self)
        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)
        self._scroll.verticalScrollBar().setValue(self._scroll.verticalScrollBar().maximum())

    def set_running(self, running: bool) -> None:
        self._running = running
        self._send_button.setText("Stop" if running else "Send")
        self._editor.setEnabled(not running)

    def show_error(self, message: str) -> None:
        self.add_message("System", [{"type": "markdown", "text": f"Error: {message}"}])

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        mime_data = event.mimeData()
        if mime_data is not None and any(url.isLocalFile() for url in mime_data.urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        mime_data = event.mimeData()
        if mime_data is None:
            event.ignore()
            return
        for url in mime_data.urls():
            if url.isLocalFile():
                path = str(Path(url.toLocalFile()).resolve())
                if path not in self._attached_files:
                    self._attached_files.append(path)
        self._update_attachment_label()
        event.acceptProposedAction()

    def _handle_button_clicked(self) -> None:
        if self._running:
            self.stop_requested.emit()
            return
        text = self._editor.toPlainText().strip()
        files = list(self._attached_files)
        if not text and not files:
            return
        self._editor.clear()
        self._attached_files.clear()
        self._update_attachment_label()
        self.message_submitted.emit(text, files)

    def _update_attachment_label(self) -> None:
        if not self._attached_files:
            self._attachment_label.setText("Drop CSV or Excel files anywhere in this chat.")
            return
        names = ", ".join(Path(path).name for path in self._attached_files)
        self._attachment_label.setText(f"Attached: {names}")

    def _author_label(self, author: AgentMessageAuthor) -> str:
        if author is AgentMessageAuthor.USER:
            return "You"
        if author is AgentMessageAuthor.TOOL:
            return "Tool"
        if author is AgentMessageAuthor.SYSTEM:
            return "System"
        return "Xenix"

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f7f8fb;
                color: #20242a;
                font-size: 14px;
            }
            QScrollArea {
                background: transparent;
            }
            #chatMessageBubble {
                background: #ffffff;
                border: 1px solid #d9dde5;
                border-radius: 8px;
            }
            #chatMessageAuthor {
                font-weight: 600;
                color: #343a42;
            }
            #chatAttachmentLabel {
                color: #667085;
            }
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #c9ced8;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton {
                background: #275db3;
                color: white;
                border: 0;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1f4d96;
            }
            """
        )

