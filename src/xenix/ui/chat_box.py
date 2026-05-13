from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
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

from ..services.agent import ThreadSnapshot
from ..services.storage.models import AgentMessageAuthor, AgentMessageKind


class ChatMessageBubble(QFrame):
    def __init__(self, *, author: str, blocks: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatMessageRow")

        card = QFrame(self)
        card.setObjectName(self._card_object_name(author, blocks))

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(7)

        if not self._is_turn_end(blocks):
            author_label = QLabel(author)
            author_label.setObjectName("chatMessageAuthor")
            card_layout.addWidget(author_label)

        browser = QTextBrowser()
        browser.setObjectName("chatMessageBody")
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QFrame.NoFrame)
        browser.setMinimumHeight(28)
        browser.setMaximumHeight(360)
        browser.setMarkdown(self._render_blocks(blocks))
        card_layout.addWidget(browser)

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if author == "You":
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0)
        else:
            row_layout.addWidget(card, 1)
            row_layout.addStretch(0)

    def _card_object_name(self, author: str, blocks: list[dict[str, Any]]) -> str:
        if self._is_turn_end(blocks):
            return "chatMessageDivider"
        if author == "You":
            return "chatMessageUser"
        if author == "Tool":
            return "chatMessageTool"
        if author == "System":
            return "chatMessageSystem"
        return "chatMessageAssistant"

    def _is_turn_end(self, blocks: list[dict[str, Any]]) -> bool:
        return bool(blocks) and all(block.get("type") == "turn_end" for block in blocks)

    def _render_blocks(self, blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"text", "markdown"}:
                parts.append(str(block.get("text", "")))
            elif block_type == "file":
                file_path = Path(str(block.get("path", "")))
                parts.append(f"`{file_path.name}`")
            elif block_type == "turn_end":
                parts.append(str(block.get("summary") or "Turn ended."))
            elif block_type == "tool_call_result":
                tool_name = str(block.get("tool_name") or "tool")
                parts.append(f"`{tool_name}` completed.")
        return "\n\n".join(part for part in parts if part)


class AttachmentChip(QFrame):
    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self.setObjectName("attachmentChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(6)
        name_label = QLabel(Path(path).name)
        name_label.setObjectName("attachmentChipLabel")
        layout.addWidget(name_label)


class ChatBox(QWidget):
    message_submitted = Signal(str, list)
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._attached_files: list[str] = []
        self._running = False

        self._message_container = QWidget()
        self._message_outer_layout = QHBoxLayout(self._message_container)
        self._message_outer_layout.setContentsMargins(0, 0, 0, 0)
        self._message_outer_layout.setSpacing(0)

        self._message_column = QWidget()
        self._message_column.setObjectName("chatMessageColumn")
        self._message_column.setMaximumWidth(920)
        self._message_layout = QVBoxLayout(self._message_column)
        self._message_layout.setContentsMargins(0, 20, 0, 20)
        self._message_layout.setSpacing(12)
        self._message_layout.addStretch(1)

        self._message_outer_layout.addStretch(1)
        self._message_outer_layout.addWidget(self._message_column, 4)
        self._message_outer_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._message_container)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._composer = QFrame()
        self._composer.setObjectName("chatComposer")
        composer_layout = QVBoxLayout(self._composer)
        composer_layout.setContentsMargins(10, 8, 10, 8)
        composer_layout.setSpacing(7)

        self._attachment_bar = QWidget()
        self._attachment_layout = QHBoxLayout(self._attachment_bar)
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(6)
        self._attachment_layout.addStretch(1)

        self._attach_button = QPushButton("+")
        self._attach_button.setObjectName("attachButton")
        self._attach_button.setFixedSize(34, 34)
        self._attach_button.setToolTip("Attach files")
        self._attach_button.clicked.connect(self._choose_files)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("chatComposerEditor")
        self._editor.setPlaceholderText("Message Xenix")
        self._editor.setMinimumHeight(46)
        self._editor.setMaximumHeight(120)

        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("sendButton")
        self._send_button.setMinimumWidth(76)
        self._send_button.clicked.connect(self._handle_button_clicked)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        input_row.addWidget(self._attach_button)
        input_row.addWidget(self._editor, 1)
        input_row.addWidget(self._send_button)

        composer_layout.addWidget(self._attachment_bar)
        composer_layout.addLayout(input_row)

        self._composer_shell = QWidget()
        composer_shell_layout = QHBoxLayout(self._composer_shell)
        composer_shell_layout.setContentsMargins(0, 0, 0, 0)
        composer_shell_layout.setSpacing(0)
        composer_shell_layout.addStretch(1)
        composer_shell_layout.addWidget(self._composer, 4)
        composer_shell_layout.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self._scroll, 1)
        root.addWidget(self._composer_shell, 0)

        self._refresh_attachment_chips()
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
        self._attach_button.setEnabled(not running)

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
        self._add_local_files([url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def _choose_files(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            "",
            "Data files (*.csv *.xlsx *.xls);;All files (*)",
        )
        self._add_local_files(paths)

    def _add_local_files(self, paths: list[str]) -> None:
        for raw_path in paths:
            path = str(Path(raw_path).resolve())
            if path not in self._attached_files:
                self._attached_files.append(path)
        self._refresh_attachment_chips()

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
        self._refresh_attachment_chips()
        self.message_submitted.emit(text, files)

    def _refresh_attachment_chips(self) -> None:
        while self._attachment_layout.count() > 1:
            item = self._attachment_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._attachment_bar.setVisible(bool(self._attached_files))
        for path in self._attached_files:
            self._attachment_layout.insertWidget(self._attachment_layout.count() - 1, AttachmentChip(path, self))

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
                background: #f6f7f9;
                color: #20242a;
                font-size: 14px;
            }
            #chatScrollArea {
                background: transparent;
            }
            #chatMessageColumn {
                background: transparent;
            }
            #chatMessageRow {
                background: transparent;
            }
            #chatMessageAssistant {
                background: transparent;
                border: 0;
            }
            #chatMessageUser {
                background: #e9f0ff;
                border: 1px solid #cbd9fb;
                border-radius: 8px;
                max-width: 520px;
            }
            #chatMessageTool {
                background: #ffffff;
                border: 1px solid #d8dde6;
                border-radius: 8px;
            }
            #chatMessageSystem {
                background: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 8px;
            }
            #chatMessageDivider {
                background: transparent;
                border-top: 1px solid #d7dce5;
                border-bottom: 0;
                border-left: 0;
                border-right: 0;
                color: #667085;
            }
            #chatMessageAuthor {
                background: transparent;
                font-weight: 600;
                color: #3a4048;
            }
            #chatMessageBody {
                background: transparent;
                color: #20242a;
            }
            #chatComposer {
                background: #ffffff;
                border: 1px solid #cfd5df;
                border-radius: 8px;
            }
            #chatComposerEditor {
                background: #ffffff;
                border: 0;
                padding: 6px;
            }
            #attachButton {
                background: #f1f3f6;
                border: 1px solid #d3d8e2;
                border-radius: 6px;
                color: #303640;
                font-weight: 700;
            }
            #attachButton:hover {
                background: #e8ebf0;
            }
            #sendButton {
                background: #244f9e;
                color: white;
                border: 0;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            #sendButton:hover {
                background: #1d4081;
            }
            #attachmentChip {
                background: #eef2f8;
                border: 1px solid #d4dae5;
                border-radius: 8px;
            }
            #attachmentChipLabel {
                background: transparent;
                color: #303640;
                font-size: 12px;
            }
            """
        )

