from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QTextOption
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ..services.agent import ThreadSnapshot
from ..services.storage.models import AgentMessageAuthor, AgentMessageKind

USER_MESSAGE_BACKGROUND = QColor("#000000")
USER_MESSAGE_FOREGROUND = QColor("#ffffff")


class AutoHeightTextBrowser(QTextBrowser):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        self.viewport().setAutoFillBackground(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().contentsChanged.connect(self._sync_height)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())
        self._sync_height()

    def _sync_height(self) -> None:
        self.document().setTextWidth(self.viewport().width())
        document_height = self.document().size().height()
        margins = self.contentsMargins()
        height = int(document_height + margins.top() + margins.bottom() + self.frameWidth() * 2 + 2)
        self.setFixedHeight(max(1, height))
        _propagate_geometry_change(self)


class AutoGrowingTextEdit(QPlainTextEdit):
    multiline_changed = Signal(bool)
    submit_requested = Signal()

    def __init__(self, *, max_lines: int = 6, min_height: int = 34, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_lines = max(1, max_lines)
        self._min_height = min_height
        self._multiline = False
        self._viewport_insets = (0, 0)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)
        self.document().setDocumentMargin(0)
        self.textChanged.connect(self._sync_height)
        self._sync_height()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_height()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)

    def _sync_height(self) -> None:
        font_metrics = self.fontMetrics()
        line_height = max(1, font_metrics.lineSpacing())
        document = self.document()
        document.setTextWidth(max(1, self.viewport().width()))
        document.adjustSize()
        visual_line_count = self._visual_line_count()
        document_height = max(document.size().height(), visual_line_count * line_height)
        frame = self.frameWidth() * 2
        vertical_padding = frame + 12
        min_height = max(self._min_height, line_height + vertical_padding)
        max_height = line_height * self._max_lines + vertical_padding
        desired_height = int(max(min_height, min(max_height, document_height + vertical_padding)))
        self.setFixedHeight(desired_height)
        should_scroll = document_height + vertical_padding > max_height
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if should_scroll else Qt.ScrollBarAlwaysOff)
        self._sync_viewport_insets(
            visual_line_count=visual_line_count,
            line_height=line_height,
            editor_height=desired_height,
            should_scroll=should_scroll,
        )
        _propagate_geometry_change(self)

        is_multiline = visual_line_count > 1
        if is_multiline != self._multiline:
            self._multiline = is_multiline
            self.multiline_changed.emit(is_multiline)

    def _visual_line_count(self) -> int:
        document = self.document()
        count = 0
        block = document.firstBlock()
        while block.isValid():
            layout = block.layout()
            count += max(1, layout.lineCount() if layout is not None else 1)
            block = block.next()
        return max(1, count)

    def _sync_viewport_insets(
        self,
        *,
        visual_line_count: int,
        line_height: int,
        editor_height: int,
        should_scroll: bool,
    ) -> None:
        if visual_line_count <= 1 and not should_scroll:
            top = max(0, (editor_height - line_height) // 2)
            bottom = 0
        else:
            top = 6
            bottom = 6 if not should_scroll else 0
        insets = (top, bottom)
        if insets != self._viewport_insets:
            self._viewport_insets = insets
            self.setViewportMargins(0, top, 0, bottom)


def _propagate_geometry_change(widget: QWidget) -> None:
    current: QWidget | None = widget
    while current is not None:
        current.updateGeometry()
        current = current.parentWidget()


class ChatMessageBubble(QFrame):
    link_activated = Signal(str)

    def __init__(self, *, author: str, blocks: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatMessageRow")

        card = QFrame(self)
        self._card = card
        card.setObjectName(self._card_object_name(author, blocks))
        card.setFrameShape(QFrame.StyledPanel)

        card_layout = QVBoxLayout(card)
        card_layout.setObjectName("chatMessageCardLayout")
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(7)

        if self._shows_author(author, blocks):
            author_label = QLabel(author)
            author_label.setObjectName("chatMessageAuthor")
            author_font = QFont(author_label.font())
            author_font.setBold(True)
            author_label.setFont(author_font)
            card_layout.addWidget(author_label)

        browser = AutoHeightTextBrowser()
        self._browser = browser
        self._blocks = list(blocks)
        browser.setObjectName("chatMessageBody")
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QFrame.NoFrame)
        browser.anchorClicked.connect(self._handle_link_activated)
        self._apply_message_palette(author, card, browser)
        browser.setMarkdown(self._render_blocks(blocks))
        card_layout.addWidget(browser)

        row_layout = QHBoxLayout(self)
        row_layout.setObjectName("chatMessageRowLayout")
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if author == "You":
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0)
        else:
            row_layout.addWidget(card, 1)
            row_layout.addStretch(0)

    def _card_object_name(self, author: str, blocks: list[dict[str, Any]]) -> str:
        if author == "You":
            return "chatMessageUser"
        if author == "Tool":
            return "chatMessageTool"
        if author == "System":
            return "chatMessageSystem"
        return "chatMessageAssistant"

    def _shows_author(self, author: str, blocks: list[dict[str, Any]]) -> bool:
        return author not in {"You", "Xenix"}

    def _apply_message_palette(self, author: str, card: QFrame, browser: QTextBrowser) -> None:
        if author != "You":
            card.setAutoFillBackground(False)
            return

        card_palette = QPalette(card.palette())
        card_palette.setColor(QPalette.ColorRole.Window, USER_MESSAGE_BACKGROUND)
        card_palette.setColor(QPalette.ColorRole.WindowText, USER_MESSAGE_FOREGROUND)
        card.setPalette(card_palette)
        card.setAutoFillBackground(True)

        text_palette = QPalette(browser.palette())
        for role in (
            QPalette.ColorRole.Text,
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.BrightText,
            QPalette.ColorRole.ButtonText,
        ):
            text_palette.setColor(role, USER_MESSAGE_FOREGROUND)
        text_palette.setColor(QPalette.ColorRole.Link, USER_MESSAGE_FOREGROUND)
        text_palette.setColor(QPalette.ColorRole.LinkVisited, USER_MESSAGE_FOREGROUND)
        browser.setPalette(text_palette)
        browser.viewport().setPalette(text_palette)

    def _render_blocks(self, blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"text", "markdown"}:
                parts.append(str(block.get("text", "")))
            elif block_type == "file":
                file_path = Path(str(block.get("path", "")))
                parts.append(f"`{file_path.name}`")
            elif block_type == "step_confirmation":
                parts.append(str(block.get("text", "")))
            elif block_type == "thinking":
                parts.append(str(block.get("text") or "Thinking..."))
            elif block_type == "tool_call":
                tool_name = str(block.get("tool_name") or "tool")
                parts.append(f"Calling `{tool_name}`...")
            elif block_type == "tool_call_result":
                tool_name = str(block.get("tool_name") or "tool")
                status = str(block.get("status") or "completed")
                parts.append(f"`{tool_name}` {status}.")
        return "\n\n".join(part for part in parts if part)

    def set_available_width(self, width: int) -> None:
        if self._card.objectName() == "chatMessageUser":
            self._card.setMaximumWidth(max(280, int(width * 0.6)))
        elif self._card.objectName() in {"chatMessageTool", "chatMessageSystem"}:
            self._card.setMaximumWidth(max(320, int(width * 0.78)))

    def set_blocks(self, blocks: list[dict[str, Any]]) -> None:
        self._blocks = list(blocks)
        self._browser.setMarkdown(self._render_blocks(self._blocks))

    def append_markdown_delta(self, delta: str) -> None:
        if not self._blocks or self._blocks[-1].get("type") != "markdown":
            self._blocks.append({"type": "markdown", "text": ""})
        self._blocks[-1]["text"] = str(self._blocks[-1].get("text", "")) + delta
        self._browser.setMarkdown(self._render_blocks(self._blocks))

    def _handle_link_activated(self, url) -> None:
        self.link_activated.emit(url.toString())


class TurnDivider(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatTurnDivider")
        self._blocks: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        line = QFrame(self)
        self._card = line
        line.setObjectName("chatMessageDivider")
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)


class AttachmentChip(QFrame):
    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self.setObjectName("attachmentChip")
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(6)
        name_label = QLabel(Path(path).name)
        name_label.setObjectName("attachmentChipLabel")
        layout.addWidget(name_label)


class ThreadDetailView(QWidget):
    message_submitted = Signal(str, list)
    artifact_link_activated = Signal(str)
    stop_requested = Signal()
    step_budget_continue_requested = Signal()
    step_budget_stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("threadDetailView")
        self.setAcceptDrops(True)
        self._attached_files: list[str] = []
        self._running = False
        self._awaiting_step_confirmation = False
        self._streaming_assistant_bubble: ChatMessageBubble | None = None
        self._thinking_bubble: ChatMessageBubble | None = None

        self._message_container = QWidget()
        self._message_container.setObjectName("chatMessageContainer")
        self._message_outer_layout = QHBoxLayout(self._message_container)
        self._message_outer_layout.setObjectName("chatMessageOuterLayout")
        self._message_outer_layout.setContentsMargins(20, 0, 20, 0)
        self._message_outer_layout.setSpacing(0)

        self._message_column = QWidget()
        self._message_column.setObjectName("chatMessageColumn")
        self._message_layout = QVBoxLayout(self._message_column)
        self._message_layout.setObjectName("chatMessageLayout")
        self._message_layout.setContentsMargins(0, 20, 0, 20)
        self._message_layout.setSpacing(12)
        self._message_layout.addStretch(1)

        self._message_outer_layout.addWidget(self._message_column, 1)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._message_container)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._composer = QFrame()
        self._composer.setObjectName("chatComposer")
        self._composer.setFrameShape(QFrame.StyledPanel)
        composer_layout = QVBoxLayout(self._composer)
        composer_layout.setObjectName("chatComposerLayout")
        composer_layout.setContentsMargins(10, 8, 10, 8)
        composer_layout.setSpacing(7)

        self._attachment_bar = QWidget()
        self._attachment_bar.setObjectName("chatAttachmentBar")
        self._attachment_layout = QHBoxLayout(self._attachment_bar)
        self._attachment_layout.setObjectName("chatAttachmentLayout")
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(6)
        self._attachment_layout.addStretch(1)

        self._attach_button = QPushButton("+")
        self._attach_button.setObjectName("attachButton")
        self._attach_button.setFixedSize(34, 34)
        self._attach_button.setToolTip("Attach files")
        self._attach_button.clicked.connect(self._choose_files)

        self._expanded_attach_button = QPushButton("+")
        self._expanded_attach_button.setObjectName("attachButton")
        self._expanded_attach_button.setFixedSize(34, 34)
        self._expanded_attach_button.setToolTip("Attach files")
        self._expanded_attach_button.clicked.connect(self._choose_files)

        self._editor = AutoGrowingTextEdit(max_lines=6)
        self._editor.setObjectName("chatComposerEditor")
        self._editor.setPlaceholderText("Message Xenix")
        self._editor.multiline_changed.connect(self._set_composer_multiline)
        self._editor.submit_requested.connect(self._handle_button_clicked)

        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("sendButton")
        self._send_button.setMinimumWidth(76)
        self._send_button.setFixedHeight(34)
        self._send_button.clicked.connect(self._handle_button_clicked)

        self._expanded_send_button = QPushButton("Send")
        self._expanded_send_button.setObjectName("sendButton")
        self._expanded_send_button.setMinimumWidth(76)
        self._expanded_send_button.setFixedHeight(34)
        self._expanded_send_button.clicked.connect(self._handle_button_clicked)

        self._step_confirmation_bar = QFrame()
        self._step_confirmation_bar.setObjectName("stepConfirmationBar")
        self._step_confirmation_bar.setFrameShape(QFrame.StyledPanel)
        step_confirmation_layout = QHBoxLayout(self._step_confirmation_bar)
        step_confirmation_layout.setContentsMargins(10, 8, 10, 8)
        step_confirmation_layout.setSpacing(8)

        self._step_confirmation_label = QLabel()
        self._step_confirmation_label.setObjectName("stepConfirmationLabel")
        self._step_confirmation_label.setWordWrap(True)

        self._step_continue_button = QPushButton("Continue")
        self._step_continue_button.setObjectName("stepContinueButton")
        self._step_continue_button.clicked.connect(self.step_budget_continue_requested.emit)

        self._step_stop_button = QPushButton("Stop")
        self._step_stop_button.setObjectName("stepStopButton")
        self._step_stop_button.clicked.connect(self.step_budget_stop_requested.emit)

        step_confirmation_layout.addWidget(self._step_confirmation_label, 1)
        step_confirmation_layout.addWidget(self._step_continue_button, 0, Qt.AlignVCenter)
        step_confirmation_layout.addWidget(self._step_stop_button, 0, Qt.AlignVCenter)
        self._step_confirmation_bar.hide()

        self._compact_input_row = QHBoxLayout()
        self._compact_input_row.setObjectName("chatComposerCompactRow")
        self._compact_input_row.setContentsMargins(0, 0, 0, 0)
        self._compact_input_row.setSpacing(8)
        self._compact_input_row.addWidget(self._attach_button)
        self._compact_input_row.addWidget(self._editor, 1, Qt.AlignVCenter)
        self._compact_input_row.addWidget(self._send_button)

        self._expanded_editor_row = QVBoxLayout()
        self._expanded_editor_row.setObjectName("chatComposerExpandedEditorRow")
        self._expanded_editor_row.setContentsMargins(0, 0, 0, 0)
        self._expanded_editor_row.setSpacing(0)

        self._expanded_controls_row = QHBoxLayout()
        self._expanded_controls_row.setObjectName("chatComposerExpandedControlsRow")
        self._expanded_controls_row.setContentsMargins(0, 0, 0, 0)
        self._expanded_controls_row.setSpacing(8)
        self._expanded_controls_row.addWidget(self._expanded_attach_button)
        self._expanded_controls_row.addStretch(1)
        self._expanded_controls_row.addWidget(self._expanded_send_button)

        composer_layout.addWidget(self._step_confirmation_bar)
        composer_layout.addWidget(self._attachment_bar)
        composer_layout.addLayout(self._compact_input_row)
        composer_layout.addLayout(self._expanded_editor_row)
        composer_layout.addLayout(self._expanded_controls_row)

        self._composer_shell = QWidget()
        self._composer_shell.setObjectName("chatComposerShell")
        composer_shell_layout = QHBoxLayout(self._composer_shell)
        composer_shell_layout.setObjectName("chatComposerShellLayout")
        composer_shell_layout.setContentsMargins(0, 0, 0, 0)
        composer_shell_layout.setSpacing(0)
        composer_shell_layout.addWidget(self._composer, 1)

        self._composer_drop_overlay = QFrame(self._composer_shell)
        self._composer_drop_overlay.setObjectName("composerDropOverlay")
        self._composer_drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._composer_drop_overlay.setAutoFillBackground(True)
        self._composer_drop_overlay.setFrameShape(QFrame.StyledPanel)
        self._composer_drop_overlay.setFrameShadow(QFrame.Raised)
        composer_drop_layout = QVBoxLayout(self._composer_drop_overlay)
        composer_drop_layout.setContentsMargins(12, 10, 12, 10)
        composer_drop_layout.setSpacing(3)
        composer_drop_layout.setAlignment(Qt.AlignCenter)

        self._composer_drop_title = QLabel("Drop files to attach")
        self._composer_drop_title.setObjectName("composerDropTitle")
        self._composer_drop_title.setAlignment(Qt.AlignCenter)
        composer_drop_title_font = QFont(self._composer_drop_title.font())
        composer_drop_title_font.setBold(True)
        self._composer_drop_title.setFont(composer_drop_title_font)

        self._composer_drop_hint = QLabel("Release here to add them to the next message")
        self._composer_drop_hint.setObjectName("composerDropHint")
        self._composer_drop_hint.setAlignment(Qt.AlignCenter)

        composer_drop_layout.addWidget(self._composer_drop_title)
        composer_drop_layout.addWidget(self._composer_drop_hint)
        self._composer_drop_overlay.hide()
        self._install_composer_drop_filters()

        root = QVBoxLayout(self)
        root.setObjectName("threadDetailLayout")
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self._scroll, 1)
        root.addWidget(self._composer_shell, 0)

        self._refresh_attachment_chips()
        self._set_composer_multiline(False)
        self._sync_composer_drop_overlay_geometry()

    def render_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self.finish_streaming_assistant_message()
        self.hide_thinking_indicator()
        self.clear_messages()
        has_rendered_user_message = False
        for message in snapshot.messages:
            if message.kind is AgentMessageKind.SYSTEM:
                continue
            if message.kind is AgentMessageKind.USER:
                if has_rendered_user_message:
                    self.add_turn_divider(auto_scroll=False)
                self.add_message(self._author_label(message.ui_author), message.content_blocks, auto_scroll=False)
                has_rendered_user_message = True
                continue
            if message.kind is AgentMessageKind.TOOL_CALL:
                self.add_message(self._author_label(message.ui_author), message.content_blocks, auto_scroll=False)
                continue
            self.add_message(self._author_label(message.ui_author), message.content_blocks, auto_scroll=False)
        self._scroll_to_latest()

    def clear_messages(self) -> None:
        self._thinking_bubble = None
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_message(self, author: str, blocks: list[dict[str, Any]], *, auto_scroll: bool = True) -> None:
        bubble = ChatMessageBubble(author=author, blocks=blocks, parent=self)
        bubble.link_activated.connect(self.artifact_link_activated.emit)
        bubble.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), bubble)
        if auto_scroll:
            self._scroll_to_latest()

    def add_user_message(self, blocks: list[dict[str, Any]], *, auto_scroll: bool = True) -> None:
        if self._has_user_message():
            self.add_turn_divider(auto_scroll=False)
        self.add_message("You", blocks, auto_scroll=auto_scroll)

    def add_turn_divider(self, *, auto_scroll: bool = True) -> None:
        divider = TurnDivider(parent=self)
        self._message_layout.insertWidget(self._message_insert_index(), divider)
        if auto_scroll:
            self._scroll_to_latest()

    def append_assistant_delta(self, delta: str) -> None:
        if not delta:
            return
        self.hide_thinking_indicator()
        if self._streaming_assistant_bubble is None:
            self._streaming_assistant_bubble = ChatMessageBubble(
                author="Xenix",
                blocks=[{"type": "markdown", "text": ""}],
                parent=self,
            )
            self._streaming_assistant_bubble.link_activated.connect(self.artifact_link_activated.emit)
            self._message_layout.insertWidget(self._message_insert_index(), self._streaming_assistant_bubble)
        self._streaming_assistant_bubble.append_markdown_delta(delta)
        self._scroll_to_latest()

    def finish_streaming_assistant_message(self) -> None:
        self._streaming_assistant_bubble = None

    def show_thinking_indicator(self) -> None:
        if self._thinking_bubble is not None:
            self._scroll_to_latest()
            return
        self._thinking_bubble = ChatMessageBubble(
            author="Xenix",
            blocks=[{"type": "thinking", "text": "Thinking..."}],
            parent=self,
        )
        self._thinking_bubble.link_activated.connect(self.artifact_link_activated.emit)
        self._thinking_bubble.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_layout.count() - 1, self._thinking_bubble)
        self._scroll_to_latest()

    def hide_thinking_indicator(self) -> None:
        if self._thinking_bubble is None:
            return
        bubble = self._thinking_bubble
        self._thinking_bubble = None
        self._message_layout.removeWidget(bubble)
        bubble.deleteLater()

    def _message_insert_index(self) -> int:
        if self._thinking_bubble is None:
            return self._message_layout.count() - 1
        for index in range(self._message_layout.count()):
            item = self._message_layout.itemAt(index)
            if item is not None and item.widget() is self._thinking_bubble:
                return index
        self._thinking_bubble = None
        return self._message_layout.count() - 1

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._resize_user_messages()
        self._sync_composer_drop_overlay_geometry()

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self._composer_shell and event.type() == QEvent.Resize:
            self._sync_composer_drop_overlay_geometry()
        if self._is_composer_drop_target(watched):
            if event.type() in {QEvent.DragEnter, QEvent.DragMove}:
                if self._can_accept_file_drop(event):
                    event.acceptProposedAction()
                    self._set_composer_drop_hover(True)
                    return True
                self._set_composer_drop_hover(False)
                event.ignore()
                return True
            if event.type() == QEvent.Drop:
                self._set_composer_drop_hover(False)
                if self._can_accept_file_drop(event):
                    self._add_local_files(self._local_file_paths(event))
                    event.acceptProposedAction()
                    return True
                event.ignore()
                return True
            if event.type() == QEvent.DragLeave and watched is self._composer_shell:
                self._set_composer_drop_hover(False)
        return super().eventFilter(watched, event)

    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._set_composer_drop_hover(False)
            self.clear_step_confirmation()
        send_text = "Stop" if running else "Send"
        self._send_button.setText(send_text)
        self._expanded_send_button.setText(send_text)
        self._sync_composer_controls_enabled()

    def show_step_confirmation(self, message: str) -> None:
        self._awaiting_step_confirmation = True
        self._set_composer_drop_hover(False)
        self._step_confirmation_label.setText(message)
        self._step_confirmation_bar.show()
        self._sync_composer_controls_enabled()

    def clear_step_confirmation(self) -> None:
        self._awaiting_step_confirmation = False
        self._step_confirmation_label.clear()
        self._step_confirmation_bar.hide()
        self._sync_composer_controls_enabled()

    def show_error(self, message: str) -> None:
        self.add_message("System", [{"type": "markdown", "text": f"Error: {message}"}])

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._can_accept_file_drop(event):
            event.acceptProposedAction()
            self._set_composer_drop_hover(self._is_event_over_composer(event))
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._can_accept_file_drop(event):
            event.acceptProposedAction()
            self._set_composer_drop_hover(self._is_event_over_composer(event))
            return
        self._set_composer_drop_hover(False)
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_composer_drop_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        self._set_composer_drop_hover(False)
        if not self._can_accept_file_drop(event) or not self._is_event_over_composer(event):
            event.ignore()
            return
        self._add_local_files(self._local_file_paths(event))
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

    def _install_composer_drop_filters(self) -> None:
        widgets = [
            self._composer_shell,
            self._composer,
            self._attachment_bar,
            self._attach_button,
            self._expanded_attach_button,
            self._editor,
            self._editor.viewport(),
            self._send_button,
            self._expanded_send_button,
        ]
        for widget in widgets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def _is_composer_drop_target(self, watched) -> bool:
        return isinstance(watched, QWidget) and (
            watched is self._composer_shell
            or watched is self._editor.viewport()
            or self._composer_shell.isAncestorOf(watched)
        )

    def _can_accept_file_drop(self, event) -> bool:
        if self._running or self._awaiting_step_confirmation:
            return False
        return bool(self._local_file_paths(event))

    def _local_file_paths(self, event) -> list[str]:
        mime_data = event.mimeData()
        if mime_data is None:
            return []
        return [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]

    def _is_event_over_composer(self, event) -> bool:
        point = self._event_point(event)
        if point is None:
            return True
        return self._composer_shell.geometry().contains(point)

    def _event_point(self, event) -> QPoint | None:
        if hasattr(event, "position"):
            position = event.position()
            if hasattr(position, "toPoint"):
                return position.toPoint()
        if hasattr(event, "pos"):
            return event.pos()
        return None

    def _set_composer_drop_hover(self, visible: bool) -> None:
        if visible:
            self._sync_composer_drop_overlay_geometry()
            self._composer_drop_overlay.show()
            self._composer_drop_overlay.raise_()
            return
        self._composer_drop_overlay.hide()

    def _sync_composer_drop_overlay_geometry(self) -> None:
        self._composer_drop_overlay.setGeometry(self._composer_shell.rect())

    def _handle_button_clicked(self) -> None:
        if self._running:
            self.stop_requested.emit()
            return
        if self._awaiting_step_confirmation:
            return
        text = self._editor.toPlainText().strip()
        files = list(self._attached_files)
        if not text and not files:
            return
        self._editor.clear()
        self._attached_files.clear()
        self._refresh_attachment_chips()
        self.message_submitted.emit(text, files)

    def _set_composer_multiline(self, multiline: bool) -> None:
        self._attach_button.setVisible(not multiline)
        self._send_button.setVisible(not multiline)
        self._expanded_attach_button.setVisible(multiline)
        self._expanded_send_button.setVisible(multiline)
        if multiline:
            if self._expanded_editor_row.indexOf(self._editor) == -1:
                self._expanded_editor_row.addWidget(self._editor)
        elif self._compact_input_row.indexOf(self._editor) == -1:
            self._compact_input_row.insertWidget(1, self._editor, 1, Qt.AlignVCenter)

    def _sync_composer_controls_enabled(self) -> None:
        can_edit = not self._running and not self._awaiting_step_confirmation
        self._editor.setEnabled(can_edit)
        self._attach_button.setEnabled(can_edit)
        self._expanded_attach_button.setEnabled(can_edit)
        self._send_button.setEnabled(not self._awaiting_step_confirmation)
        self._expanded_send_button.setEnabled(not self._awaiting_step_confirmation)
        self._step_continue_button.setEnabled(self._awaiting_step_confirmation)
        self._step_stop_button.setEnabled(self._awaiting_step_confirmation)

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

    def _has_user_message(self) -> bool:
        for index in range(self._message_layout.count()):
            item = self._message_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            card = getattr(widget, "_card", None)
            if card is not None and card.objectName() == "chatMessageUser":
                return True
        return False

    def _resize_user_messages(self) -> None:
        width = self._message_column.width()
        for index in range(self._message_layout.count()):
            item = self._message_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, ChatMessageBubble):
                widget.set_available_width(width)

    def _scroll_to_latest(self, *, settle_ticks: int = 4) -> None:
        self._scroll_to_latest_after_layout(max(0, settle_ticks))

    def _scroll_to_latest_after_layout(self, remaining_ticks: int) -> None:
        if not self._is_scroll_target_alive():
            return
        if remaining_ticks == 0:
            scrollbar = self._scroll.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            return
        QTimer.singleShot(0, lambda: self._scroll_to_latest_after_layout(remaining_ticks - 1))

    def _is_scroll_target_alive(self) -> bool:
        try:
            return isValid(self) and isValid(self._scroll)
        except RuntimeError:
            return False


ChatBox = ThreadDetailView
