from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ..services.agent import (
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
    ThreadSnapshot,
    project_chatbot_events,
)
from ..services.storage.models import AgentMessageAuthor, AgentMessageKind
from .icons import attach_file_icon, chevron_icon, remove_icon, tool_icon
from .markdown_renderer import render_chat_markdown

USER_MESSAGE_BACKGROUND = QColor("#000000")
USER_MESSAGE_FOREGROUND = QColor("#ffffff")
USER_MESSAGE_DOCUMENT_STYLE_SHEET = """
body, p, li, pre, code, table, thead, tbody, tr, td, th {
    color: #ffffff;
}
a {
    color: #ffffff;
}
""".strip()
UNBOUNDED_WIDGET_WIDTH = 16777215
ArtifactResolver = Callable[[str], Any]
SUPPORTED_DATASET_SUFFIXES = {".csv", ".xlsx", ".xls"}


class ComposerAttachmentStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


@dataclass
class ComposerAttachmentState:
    path: str
    status: ComposerAttachmentStatus = ComposerAttachmentStatus.PENDING
    error: str | None = None


def _render_content_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "markdown"}:
            parts.append(str(block.get("text", "")))
        elif block_type == "ui_error":
            message = str(block.get("message", ""))
            parts.append(
                QCoreApplication.translate("ThreadDetailView", "Error: {message}").format(
                    message=message
                )
            )
        elif block_type == "file":
            file_path = Path(str(block.get("path", "")))
            parts.append(f"`{file_path.name}`")
        elif block_type == "dataset":
            name = str(block.get("name") or block.get("file_name") or "")
            dataset_id = str(block.get("dataset_id") or "")
            if dataset_id:
                parts.append(f"`{name}` (`{dataset_id}`)")
            elif name:
                parts.append(f"`{name}`")
        elif block_type == "step_confirmation":
            parts.append(str(block.get("text", "")))
        elif block_type == "thinking":
            text = str(block.get("text") or "")
            if text and text != "Thinking...":
                parts.append(text)
            else:
                parts.append(QCoreApplication.translate("ThreadDetailView", "Thinking..."))
        elif block_type == "tool_event_summary":
            parts.append(_translate_tool_summary(str(block.get("text", ""))))
        elif block_type == "tool_call":
            tool_name = str(
                block.get("tool_name")
                or QCoreApplication.translate("ThreadDetailView", "tool")
            )
            parts.append(
                QCoreApplication.translate("ThreadDetailView", "Calling `{tool_name}`...").format(
                    tool_name=tool_name
                )
            )
        elif block_type == "tool_call_result":
            tool_name = str(
                block.get("tool_name")
                or QCoreApplication.translate("ThreadDetailView", "tool")
            )
            status = str(block.get("status") or "completed")
            error_summary = str(block.get("error_summary") or "").strip()
            text = QCoreApplication.translate(
                "ThreadDetailView", "`{tool_name}` {status}."
            ).format(tool_name=tool_name, status=_translate_tool_status(status))
            if error_summary:
                text = f"{text} {error_summary}"
            parts.append(text)
    return "\n\n".join(part for part in parts if part)


def _translate_tool_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized == "completed":
        return QCoreApplication.translate("ThreadDetailView", "completed")
    if normalized == "failed":
        return QCoreApplication.translate("ThreadDetailView", "failed")
    if normalized == "cancelled":
        return QCoreApplication.translate("ThreadDetailView", "cancelled")
    if normalized == "running":
        return QCoreApplication.translate("ThreadDetailView", "running")
    if normalized == "requested":
        return QCoreApplication.translate("ThreadDetailView", "requested")
    return status


def _translate_tool_summary(summary: str) -> str:
    if summary == "Running tool...":
        return QCoreApplication.translate("ToolCallItem", "Running tool...")
    if summary == "Ran tool":
        return QCoreApplication.translate("ToolCallItem", "Ran tool")
    if summary == "Cancelled tool run":
        return QCoreApplication.translate("ToolCallItem", "Cancelled tool run")
    if summary == "Inspecting dataset...":
        return QCoreApplication.translate("ToolCallItem", "Inspecting dataset...")
    if summary == "Inspected dataset":
        return QCoreApplication.translate("ToolCallItem", "Inspected dataset")
    if summary == "Cancelled dataset inspection":
        return QCoreApplication.translate("ToolCallItem", "Cancelled dataset inspection")
    if summary == "Integrating data...":
        return QCoreApplication.translate("ToolCallItem", "Integrating data...")
    if summary == "Integrated data":
        return QCoreApplication.translate("ToolCallItem", "Integrated data")
    if summary == "Cancelled data integration":
        return QCoreApplication.translate("ToolCallItem", "Cancelled data integration")
    if summary == "Profiling dataset...":
        return QCoreApplication.translate("ToolCallItem", "Profiling dataset...")
    if summary == "Profiled dataset":
        return QCoreApplication.translate("ToolCallItem", "Profiled dataset")
    if summary == "Cancelled dataset profile":
        return QCoreApplication.translate("ToolCallItem", "Cancelled dataset profile")
    if summary == "Drawing graph...":
        return QCoreApplication.translate("ToolCallItem", "Drawing graph...")
    if summary == "Drew graph":
        return QCoreApplication.translate("ToolCallItem", "Drew graph")
    if summary == "Cancelled graph drawing":
        return QCoreApplication.translate("ToolCallItem", "Cancelled graph drawing")
    if summary == "Cleaning dataset...":
        return QCoreApplication.translate("ToolCallItem", "Cleaning dataset...")
    if summary == "Cleaned dataset":
        return QCoreApplication.translate("ToolCallItem", "Cleaned dataset")
    if summary == "Cancelled dataset cleaning":
        return QCoreApplication.translate("ToolCallItem", "Cancelled dataset cleaning")
    if summary == "Querying dataset...":
        return QCoreApplication.translate("ToolCallItem", "Querying dataset...")
    if summary == "Queried dataset":
        return QCoreApplication.translate("ToolCallItem", "Queried dataset")
    if summary == "Cancelled dataset query":
        return QCoreApplication.translate("ToolCallItem", "Cancelled dataset query")
    if summary == "Transforming dataset...":
        return QCoreApplication.translate("ToolCallItem", "Transforming dataset...")
    if summary == "Transformed dataset":
        return QCoreApplication.translate("ToolCallItem", "Transformed dataset")
    if summary == "Cancelled dataset transformation":
        return QCoreApplication.translate("ToolCallItem", "Cancelled dataset transformation")
    if summary == "Selecting features...":
        return QCoreApplication.translate("ToolCallItem", "Selecting features...")
    if summary == "Selected features":
        return QCoreApplication.translate("ToolCallItem", "Selected features")
    if summary == "Cancelled feature selection":
        return QCoreApplication.translate("ToolCallItem", "Cancelled feature selection")
    if summary == "Loading model metadata...":
        return QCoreApplication.translate("ToolCallItem", "Loading model metadata...")
    if summary == "Loaded model metadata":
        return QCoreApplication.translate("ToolCallItem", "Loaded model metadata")
    if summary == "Cancelled model metadata lookup":
        return QCoreApplication.translate("ToolCallItem", "Cancelled model metadata lookup")
    if summary == "Training model...":
        return QCoreApplication.translate("ToolCallItem", "Training model...")
    if summary == "Trained model":
        return QCoreApplication.translate("ToolCallItem", "Trained model")
    if summary == "Cancelled model training":
        return QCoreApplication.translate("ToolCallItem", "Cancelled model training")
    if summary == "Tuning model...":
        return QCoreApplication.translate("ToolCallItem", "Tuning model...")
    if summary == "Tuned model":
        return QCoreApplication.translate("ToolCallItem", "Tuned model")
    if summary == "Model tuning running in background":
        return QCoreApplication.translate("ToolCallItem", "Model tuning running in background")
    if summary == "Cancelled model tuning":
        return QCoreApplication.translate("ToolCallItem", "Cancelled model tuning")
    if summary == "Applying model...":
        return QCoreApplication.translate("ToolCallItem", "Applying model...")
    if summary == "Applied model":
        return QCoreApplication.translate("ToolCallItem", "Applied model")
    if summary == "Model training running in background":
        return QCoreApplication.translate("ToolCallItem", "Model training running in background")
    if summary == "Model apply running in background":
        return QCoreApplication.translate("ToolCallItem", "Model apply running in background")
    if summary == "Checking model task...":
        return QCoreApplication.translate("ToolCallItem", "Checking model task...")
    if summary == "Checked model task":
        return QCoreApplication.translate("ToolCallItem", "Checked model task")
    if summary == "Cancelled model task check":
        return QCoreApplication.translate("ToolCallItem", "Cancelled model task check")
    if summary == "Cancelled model apply":
        return QCoreApplication.translate("ToolCallItem", "Cancelled model apply")
    return summary


def _format_token_count(value: int) -> str:
    if value <= 999:
        return str(max(0, value))
    rounded_tenths = (value + 50) // 100
    return f"{rounded_tenths / 10:.1f}k"


def _usage_overview_text(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    input_tokens = _payload_int(payload, "input_tokens")
    cached_input_tokens = _payload_int(payload, "cached_input_tokens")
    output_tokens = _payload_int(payload, "output_tokens")
    input_text = _format_token_count(input_tokens)
    if cached_input_tokens > 0:
        input_text += QCoreApplication.translate(
            "UsageOverviewItem",
            " ({cached} cached)",
        ).format(cached=_format_token_count(cached_input_tokens))
    text = QCoreApplication.translate(
        "UsageOverviewItem",
        "↑ {input} · ↓ {output}",
    ).format(
        input=input_text,
        output=_format_token_count(output_tokens),
    )
    return text


def _payload_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


class AutoHeightTextBrowser(QTextBrowser):
    def __init__(
        self,
        *,
        artifact_resolver: ArtifactResolver | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._artifact_resolver = artifact_resolver
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        self.viewport().setAutoFillBackground(False)
        palette = QPalette(self.palette())
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        self.setPalette(palette)
        self.viewport().setPalette(palette)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        text_option = self.document().defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)
        self.document().contentsChanged.connect(self._sync_height)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())
        self._sync_height()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()

    def set_artifact_resolver(self, resolver: ArtifactResolver | None) -> None:
        self._artifact_resolver = resolver

    def loadResource(self, resource_type: int, name):  # type: ignore[override]
        if resource_type == QTextDocument.ImageResource and name.scheme() == "artifact":
            pixmap = self._load_artifact_pixmap(name.toString())
            if not pixmap.isNull():
                return pixmap
        return super().loadResource(resource_type, name)

    def _sync_height(self) -> None:
        self.document().setTextWidth(self.viewport().width())
        document_height = self.document().size().height()
        margins = self.contentsMargins()
        height = int(document_height + margins.top() + margins.bottom() + self.frameWidth() * 2 + 2)
        self.setFixedHeight(max(1, height))
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)
        _propagate_geometry_change(self)

    def _load_artifact_pixmap(self, uri: str) -> QPixmap:
        if self._artifact_resolver is None:
            return QPixmap()
        try:
            artifact = self._artifact_resolver(uri)
        except Exception:
            return QPixmap()

        mime_type = str(getattr(artifact, "mime_type", "") or "")
        if mime_type and not mime_type.startswith("image/"):
            return QPixmap()
        if not bool(getattr(artifact, "ready_to_open", False)):
            return QPixmap()
        if not bool(getattr(artifact, "exists", False)):
            return QPixmap()

        pixmap = QPixmap(str(getattr(artifact, "absolute_path", "")))
        if pixmap.isNull():
            return pixmap
        max_width = max(160, min(720, self.viewport().width() - 24))
        max_height = 360
        if pixmap.width() <= max_width and pixmap.height() <= max_height:
            return pixmap
        return pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class UserMessageCard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatMessageUser")
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), USER_MESSAGE_BACKGROUND)
        super().paintEvent(event)


class UserMessageDocument(QTextDocument):
    def __init__(self, owner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._owner = owner

    def loadResource(self, resource_type: int, name):  # type: ignore[override]
        if resource_type == QTextDocument.ImageResource and name.scheme() == "artifact":
            pixmap = self._owner.load_artifact_pixmap(name.toString())
            if not pixmap.isNull():
                return pixmap
        return super().loadResource(resource_type, name)


class UserMessageBody(QWidget):
    link_activated = Signal(str)

    def __init__(
        self,
        *,
        artifact_resolver: ArtifactResolver | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._artifact_resolver = artifact_resolver
        self._document = UserMessageDocument(self, self)
        self._document.setDefaultStyleSheet(USER_MESSAGE_DOCUMENT_STYLE_SHEET)
        self._document.setDocumentMargin(0)
        self._document.setDefaultFont(self.font())
        text_option = self._document.defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._document.setDefaultTextOption(text_option)
        self._document.contentsChanged.connect(self._sync_height)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def document(self) -> QTextDocument:
        return self._document

    def set_artifact_resolver(self, resolver: ArtifactResolver | None) -> None:
        self._artifact_resolver = resolver

    def load_artifact_pixmap(self, uri: str) -> QPixmap:
        if self._artifact_resolver is None:
            return QPixmap()
        try:
            artifact = self._artifact_resolver(uri)
        except Exception:
            return QPixmap()

        mime_type = str(getattr(artifact, "mime_type", "") or "")
        if mime_type and not mime_type.startswith("image/"):
            return QPixmap()
        if not bool(getattr(artifact, "ready_to_open", False)):
            return QPixmap()
        if not bool(getattr(artifact, "exists", False)):
            return QPixmap()

        pixmap = QPixmap(str(getattr(artifact, "absolute_path", "")))
        if pixmap.isNull():
            return pixmap
        max_width = max(160, min(720, self.width() - 24))
        max_height = 360
        if pixmap.width() <= max_width and pixmap.height() <= max_height:
            return pixmap
        return pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def setHtml(self, html: str) -> None:
        self._document.setHtml(html)
        self._sync_height()
        self.update()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        width = max(1, int(self._document.idealWidth()))
        height = max(1, int(self._document.size().height()))
        return QSize(width, height)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_height()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        self._document.drawContents(painter)
        super().paintEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._anchor_at_event(event):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            anchor = self._anchor_at_event(event)
            if anchor:
                self.link_activated.emit(anchor)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _sync_height(self) -> None:
        self._document.setTextWidth(max(1, self.width()))
        height = max(1, int(self._document.size().height()) + 2)
        if self.height() != height:
            self.setFixedHeight(height)
        _propagate_geometry_change(self)

    def _anchor_at_event(self, event) -> str:
        position = event.position() if hasattr(event, "position") else event.pos()
        return self._document.documentLayout().anchorAt(position)


class AutoGrowingTextEdit(QPlainTextEdit):
    multiline_changed = Signal(bool)
    submit_requested = Signal()

    def __init__(
        self,
        *,
        max_lines: int = 6,
        min_height: int = 34,
        horizontal_padding: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_lines = max(1, max_lines)
        self._min_height = min_height
        self._horizontal_padding = max(0, horizontal_padding)
        self._multiline = False
        self._viewport_insets = (0, 0)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        self.viewport().setAutoFillBackground(False)
        palette = QPalette(self.palette())
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        self.setPalette(palette)
        self.viewport().setPalette(palette)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(self._horizontal_padding, 0, self._horizontal_padding, 0)
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
            top = max(0, (editor_height - line_height) // 2 - 1)
            bottom = 0
        else:
            top = 6
            bottom = 6 if not should_scroll else 0
        insets = (top, bottom)
        if insets != self._viewport_insets:
            self._viewport_insets = insets
            self.setViewportMargins(self._horizontal_padding, top, self._horizontal_padding, bottom)


def _propagate_geometry_change(widget: QWidget) -> None:
    current: QWidget | None = widget
    while current is not None:
        current.updateGeometry()
        current = current.parentWidget()


class ChatMessageBubble(QFrame):
    link_activated = Signal(str)

    def __init__(
        self,
        *,
        author: str,
        blocks: list[dict[str, Any]],
        artifact_resolver: ArtifactResolver | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._author = author
        self._author_label: QLabel | None = None
        self._artifact_resolver = artifact_resolver
        self.setObjectName("chatMessageRow")

        if author == "You":
            card = UserMessageCard(self)
        else:
            card = QFrame(self)
            card.setObjectName(self._card_object_name(author, blocks))
            card.setFrameShape(QFrame.StyledPanel)
            card.setAutoFillBackground(False)
        self._card = card

        card_layout = QVBoxLayout(card)
        card_layout.setObjectName("chatMessageCardLayout")
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(7)

        if self._shows_author(author, blocks):
            author_label = QLabel(self._display_author())
            self._author_label = author_label
            author_label.setObjectName("chatMessageAuthor")
            author_font = QFont(author_label.font())
            author_font.setBold(True)
            author_label.setFont(author_font)
            card_layout.addWidget(author_label)

        self._blocks = list(blocks)
        if author == "You":
            body = UserMessageBody(artifact_resolver=artifact_resolver, parent=card)
            self._browser = body
            body.setObjectName("chatMessageBody")
            body.link_activated.connect(self.link_activated.emit)
            body.setHtml(self._render_blocks(blocks))
            card_layout.addWidget(body)
        else:
            browser = AutoHeightTextBrowser(artifact_resolver=artifact_resolver)
            self._browser = browser
            browser.setObjectName("chatMessageBody")
            browser.setOpenLinks(False)
            browser.setOpenExternalLinks(False)
            browser.setFrameShape(QFrame.NoFrame)
            browser.anchorClicked.connect(self._handle_link_activated)
            browser.setHtml(self._render_blocks(blocks))
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
        if author == "System":
            return "chatMessageSystem"
        return "chatMessageAssistant"

    def _shows_author(self, author: str, blocks: list[dict[str, Any]]) -> bool:
        return author not in {"You", "Xenix"}

    def _display_author(self) -> str:
        if self._author == "You":
            return self.tr("You")
        if self._author == "Tool":
            return self.tr("Tool")
        if self._author == "System":
            return self.tr("System")
        return self._author

    def _render_blocks(self, blocks: list[dict[str, Any]]) -> str:
        return render_chat_markdown(_render_content_blocks(blocks), inline_artifact_images=True)

    def set_available_width(self, width: int) -> None:
        if self._card.objectName() == "chatMessageUser":
            self._card.setMinimumWidth(max(280, int(width * 0.6)))
            self._card.setMaximumWidth(max(320, int(width * 0.8)))
        elif self._card.objectName() == "chatMessageSystem":
            self._card.setMaximumWidth(max(320, int(width * 0.78)))

    def set_blocks(self, blocks: list[dict[str, Any]]) -> None:
        self._blocks = list(blocks)
        self._browser.setHtml(self._render_blocks(self._blocks))

    def retranslate_ui(self) -> None:
        if self._author_label is not None:
            self._author_label.setText(self._display_author())
        self._browser.setHtml(self._render_blocks(self._blocks))

    def _handle_link_activated(self, url) -> None:
        self.link_activated.emit(url.toString())


class ToolCallItem(QFrame):
    link_activated = Signal(str)
    action_requested = Signal(object)

    def __init__(
        self,
        event: ChatbotEvent,
        *,
        artifact_resolver: ArtifactResolver | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("chatToolCallItem")
        self._card = self
        self._event = event
        self._artifact_resolver = artifact_resolver
        self._expanded = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setObjectName("chatToolCallItemLayout")
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setObjectName("chatToolCallHeaderLayout")
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setObjectName("chatToolCallIcon")
        self._icon_label.setFixedWidth(22)
        self._icon_label.setAlignment(Qt.AlignCenter)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("chatToolCallSummary")
        self._summary_label.setWordWrap(True)

        self._chevron_button = QToolButton()
        self._chevron_button.setObjectName("chatToolCallChevron")
        self._chevron_button.setFixedSize(28, 24)
        self._chevron_button.setAutoRaise(True)
        self._chevron_button.setArrowType(Qt.NoArrow)
        self._chevron_button.setIconSize(QSize(16, 16))
        self._chevron_button.clicked.connect(self._toggle_detail)

        self._details_button = QPushButton()
        self._details_button.setObjectName("chatToolCallActionButton")
        self._details_button.setFixedHeight(24)
        self._details_button.clicked.connect(self._request_details)

        header_layout.addWidget(self._icon_label, 0, Qt.AlignVCenter)
        header_layout.addWidget(self._summary_label, 1, Qt.AlignVCenter)
        header_layout.addWidget(self._details_button, 0, Qt.AlignVCenter)
        header_layout.addWidget(self._chevron_button, 0, Qt.AlignVCenter)
        layout.addWidget(header)

        self._detail_browser = AutoHeightTextBrowser(artifact_resolver=artifact_resolver)
        self._detail_browser.setObjectName("chatToolCallDetail")
        self._detail_browser.setOpenLinks(False)
        self._detail_browser.setOpenExternalLinks(False)
        self._detail_browser.setFrameShape(QFrame.NoFrame)
        self._detail_browser.anchorClicked.connect(self._handle_link_activated)
        layout.addWidget(self._detail_browser)

        self.set_event(event)

    def set_event(self, event: ChatbotEvent) -> None:
        self._event = event
        self._icon_label.setPixmap(tool_icon(event.icon_key).pixmap(QSize(16, 16)))
        self._summary_label.setText(_translate_tool_summary(event.summary or ""))
        details_action = self._action_by_type("open_tool_call_detail")
        self._details_button.setVisible(details_action is not None)
        self._details_button.setEnabled(details_action is not None)
        self._details_button.setText(self.tr("Details"))
        self._details_button.setToolTip(self.tr("Open tool call details"))
        has_detail = bool(event.detail_blocks)
        self._chevron_button.setVisible(has_detail)
        self._chevron_button.setEnabled(has_detail)
        if not has_detail:
            self._expanded = False
        self._chevron_button.setIcon(chevron_icon(expanded=self._expanded))
        self._chevron_button.setToolTip(
            self.tr("Hide result") if self._expanded else self.tr("Show result")
        )
        self._detail_browser.setHtml(
            render_chat_markdown(_render_content_blocks(event.detail_blocks), inline_artifact_images=False)
        )
        self._detail_browser.setVisible(has_detail and self._expanded)
        _propagate_geometry_change(self)

    def retranslate_ui(self) -> None:
        self.set_event(self._event)

    def set_available_width(self, width: int) -> None:
        self.setMaximumWidth(UNBOUNDED_WIDGET_WIDTH)

    def _toggle_detail(self) -> None:
        if not self._event.detail_blocks:
            return
        self._expanded = not self._expanded
        self.set_event(self._event)

    def _handle_link_activated(self, url) -> None:
        self.link_activated.emit(url.toString())

    def _action_by_type(self, action_type: str) -> dict[str, Any] | None:
        for action in self._event.actions:
            if action.get("type") == action_type:
                return dict(action)
        return None

    def _request_details(self) -> None:
        action = self._action_by_type("open_tool_call_detail")
        if action is not None:
            self.action_requested.emit(action)


class UsageOverviewItem(QFrame):
    def __init__(self, event: ChatbotEvent, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatUsageOverviewItem")
        self._event = event
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setObjectName("chatUsageOverviewLayout")
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)

        label = QLabel(self)
        self._label = label
        label.setObjectName("chatUsageOverviewLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        label_font = QFont(label.font())
        if label_font.pointSize() > 0:
            label_font.setPointSize(max(1, label_font.pointSize() - 1))
        elif label_font.pixelSize() > 0:
            label_font.setPixelSize(max(1, label_font.pixelSize() - 2))
        label.setFont(label_font)
        label_palette = QPalette(label.palette())
        label_palette.setColor(
            QPalette.ColorRole.WindowText,
            label_palette.color(QPalette.ColorRole.PlaceholderText),
        )
        label.setPalette(label_palette)

        layout.addWidget(label, 1)
        self.set_event(event)

    def set_event(self, event: ChatbotEvent) -> None:
        self._event = event
        self._label.setText(_usage_overview_text(event.usage_payload))
        _propagate_geometry_change(self)

    def retranslate_ui(self) -> None:
        self.set_event(self._event)

    def set_available_width(self, width: int) -> None:
        self.setMaximumWidth(UNBOUNDED_WIDGET_WIDTH)
        self._label.setMaximumWidth(max(280, width))


class AttachmentChip(QFrame):
    remove_requested = Signal(str)

    def __init__(self, state: ComposerAttachmentState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = state.path
        self.setObjectName("attachmentChip")
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(6)
        name_label = QLabel(Path(state.path).name)
        name_label.setObjectName("attachmentChipLabel")
        status_label = QLabel()
        status_label.setObjectName("attachmentChipStatus")
        status_label.setFixedWidth(16)
        remove_button = QToolButton()
        remove_button.setObjectName("attachmentChipRemoveButton")
        remove_button.setFixedSize(18, 18)
        remove_button.setIcon(remove_icon())
        remove_button.setIconSize(QSize(12, 12))
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self.path))
        self._status_label = status_label
        self._remove_button = remove_button
        layout.addWidget(name_label)
        layout.addWidget(status_label)
        layout.addWidget(remove_button)
        self.set_state(state)

    def set_state(self, state: ComposerAttachmentState) -> None:
        self.path = state.path
        if state.status is ComposerAttachmentStatus.PENDING:
            self._status_label.setText("...")
        elif state.status is ComposerAttachmentStatus.FAILED:
            self._status_label.setText("!")
        else:
            self._status_label.clear()
        self._status_label.setProperty("attachmentStatus", state.status.value)
        self.setProperty("attachmentStatus", state.status.value)
        self._status_label.setToolTip(state.error or "")


class ThreadDetailView(QWidget):
    message_submitted = Signal(str, list, str)
    files_attached = Signal(list)
    attachment_removed = Signal(str)
    artifact_link_activated = Signal(str)
    tool_action_requested = Signal(object)
    stop_requested = Signal()
    step_budget_continue_requested = Signal()
    step_budget_stop_requested = Signal()
    model_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("threadDetailView")
        self.setAcceptDrops(True)
        self._attached_files: list[str] = []
        self._attachment_states: dict[str, ComposerAttachmentState] = {}
        self._running = False
        self._awaiting_step_confirmation = False
        self._thinking_bubble: ChatMessageBubble | None = None
        self._event_widgets_by_id: dict[str, QWidget] = {}
        self._message_bubbles_by_id: dict[str, ChatMessageBubble] = {}
        self._model_options: list[tuple[str, str]] = []
        self._artifact_resolver: ArtifactResolver | None = None

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

        self._attach_button = QPushButton()
        self._configure_attach_button(self._attach_button)
        self._attach_button.clicked.connect(self._choose_files)

        self._editor = AutoGrowingTextEdit(max_lines=6)
        self._editor.setObjectName("chatComposerEditor")
        self._editor.submit_requested.connect(self._handle_button_clicked)

        self._model_picker = QComboBox()
        self._model_picker.setObjectName("modelPicker")
        self._model_picker.setMinimumWidth(180)
        self._model_picker.setFixedHeight(34)
        self._model_picker.currentIndexChanged.connect(self._handle_model_picker_changed)

        self._send_button = QPushButton()
        self._send_button.setObjectName("sendButton")
        self._send_button.setMinimumWidth(76)
        self._send_button.setFixedHeight(34)
        self._send_button.clicked.connect(self._handle_button_clicked)

        self._step_confirmation_bar = QFrame()
        self._step_confirmation_bar.setObjectName("stepConfirmationBar")
        self._step_confirmation_bar.setFrameShape(QFrame.StyledPanel)
        step_confirmation_layout = QHBoxLayout(self._step_confirmation_bar)
        step_confirmation_layout.setContentsMargins(10, 8, 10, 8)
        step_confirmation_layout.setSpacing(8)

        self._step_confirmation_label = QLabel()
        self._step_confirmation_label.setObjectName("stepConfirmationLabel")
        self._step_confirmation_label.setWordWrap(True)

        self._step_continue_button = QPushButton()
        self._step_continue_button.setObjectName("stepContinueButton")
        self._step_continue_button.clicked.connect(self.step_budget_continue_requested.emit)

        self._step_stop_button = QPushButton()
        self._step_stop_button.setObjectName("stepStopButton")
        self._step_stop_button.clicked.connect(self.step_budget_stop_requested.emit)

        step_confirmation_layout.addWidget(self._step_confirmation_label, 1)
        step_confirmation_layout.addWidget(self._step_continue_button, 0, Qt.AlignVCenter)
        step_confirmation_layout.addWidget(self._step_stop_button, 0, Qt.AlignVCenter)
        self._step_confirmation_bar.hide()

        self._composer_controls_row = QHBoxLayout()
        self._composer_controls_row.setObjectName("chatComposerControlsRow")
        self._composer_controls_row.setContentsMargins(0, 0, 0, 0)
        self._composer_controls_row.setSpacing(8)
        self._composer_controls_row.addWidget(self._attach_button)
        self._composer_controls_row.addStretch(1)
        self._composer_controls_row.addWidget(self._model_picker)
        self._composer_controls_row.addWidget(self._send_button)

        composer_layout.addWidget(self._step_confirmation_bar)
        composer_layout.addWidget(self._attachment_bar)
        composer_layout.addWidget(self._editor)
        composer_layout.addLayout(self._composer_controls_row)

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

        self._composer_drop_title = QLabel()
        self._composer_drop_title.setObjectName("composerDropTitle")
        self._composer_drop_title.setAlignment(Qt.AlignCenter)
        composer_drop_title_font = QFont(self._composer_drop_title.font())
        composer_drop_title_font.setBold(True)
        self._composer_drop_title.setFont(composer_drop_title_font)

        self._composer_drop_hint = QLabel()
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

        self.retranslate_ui()
        self._refresh_attachment_chips()
        self._sync_composer_drop_overlay_geometry()

    def retranslate_ui(self) -> None:
        self._editor.setPlaceholderText(self.tr("Message Xenix"))
        self._attach_button.setToolTip(self.tr("Attach files"))
        self._model_picker.setToolTip(self.tr("Model for the next turn"))
        self._step_continue_button.setText(self.tr("Continue"))
        self._step_stop_button.setText(self.tr("Stop"))
        self._composer_drop_title.setText(self.tr("Drop files to attach"))
        self._composer_drop_hint.setText(self.tr("Release here to add them to the next message"))
        self._sync_send_button_text()
        for index in range(self._message_layout.count()):
            item = self._message_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            retranslate = getattr(widget, "retranslate_ui", None)
            if callable(retranslate):
                retranslate()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def render_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self.render_events(project_chatbot_events(snapshot))

    def set_artifact_resolver(self, resolver: ArtifactResolver | None) -> None:
        self._artifact_resolver = resolver

    def render_events(self, events: list[ChatbotEvent]) -> None:
        self.hide_thinking_indicator()
        self.clear_messages()
        for event in events:
            self.add_event(event, auto_scroll=False)
        self._scroll_to_latest()

    def clear_messages(self) -> None:
        self._thinking_bubble = None
        self._event_widgets_by_id.clear()
        self._message_bubbles_by_id.clear()
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_message(
        self,
        author: str,
        blocks: list[dict[str, Any]],
        *,
        message_id: str | None = None,
        event_id: str | None = None,
        auto_scroll: bool = True,
    ) -> ChatMessageBubble:
        bubble = ChatMessageBubble(
            author=author,
            blocks=blocks,
            artifact_resolver=self._artifact_resolver,
            parent=self,
        )
        bubble.link_activated.connect(self.artifact_link_activated.emit)
        bubble.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), bubble)
        widget_id = event_id or message_id
        if widget_id is not None:
            self._event_widgets_by_id[widget_id] = bubble
        if message_id is not None:
            self._message_bubbles_by_id[message_id] = bubble
        if auto_scroll:
            self._scroll_to_latest()
        return bubble

    def add_user_message(self, blocks: list[dict[str, Any]], *, auto_scroll: bool = True) -> None:
        self.add_message("You", blocks, auto_scroll=auto_scroll)

    def add_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> QWidget:
        if event.kind is ChatbotEventKind.THINKING:
            return self.add_thinking_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.TOOL:
            return self.add_tool_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.USAGE:
            return self.add_usage_event(event, auto_scroll=auto_scroll)
        return self.add_message(
            self._event_author_label(event.author),
            event.content_blocks,
            message_id=event.source_message_ids[0] if event.source_message_ids else None,
            event_id=event.id,
            auto_scroll=auto_scroll,
        )

    def add_tool_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ToolCallItem:
        item = ToolCallItem(event, artifact_resolver=self._artifact_resolver, parent=self)
        item.link_activated.connect(self.artifact_link_activated.emit)
        item.action_requested.connect(self.tool_action_requested.emit)
        item.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), item)
        self._event_widgets_by_id[event.id] = item
        if auto_scroll:
            self._scroll_to_latest()
        return item

    def add_usage_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> UsageOverviewItem:
        item = UsageOverviewItem(event, parent=self)
        item.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), item)
        self._event_widgets_by_id[event.id] = item
        if auto_scroll:
            self._scroll_to_latest()
        return item

    def add_thinking_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ChatMessageBubble:
        bubble = ChatMessageBubble(
            author=self._event_author_label(event.author),
            blocks=event.content_blocks,
            artifact_resolver=self._artifact_resolver,
            parent=self,
        )
        bubble.link_activated.connect(self.artifact_link_activated.emit)
        bubble.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), bubble)
        self._event_widgets_by_id[event.id] = bubble
        self._thinking_bubble = bubble
        if auto_scroll:
            self._scroll_to_latest()
        return bubble

    def apply_message_event(self, message, *, auto_scroll: bool = True) -> None:
        if message.kind is AgentMessageKind.SYSTEM:
            return
        if message.kind in {AgentMessageKind.TOOL_CALL, AgentMessageKind.TOOL_CALL_RESULT}:
            return
        existing = self._message_bubbles_by_id.get(message.id)
        if existing is not None:
            existing.set_blocks(message.content_blocks)
            if auto_scroll:
                self._scroll_to_latest()
            return
        self.add_message(
            self._author_label(message.ui_author),
            message.content_blocks,
            message_id=message.id,
            auto_scroll=auto_scroll,
        )

    def apply_chatbot_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> None:
        if event.kind is ChatbotEventKind.THINKING:
            if event.status is ChatbotEventStatus.IN_PROGRESS:
                existing = self._event_widgets_by_id.get(event.id)
                if isinstance(existing, ChatMessageBubble):
                    existing.set_blocks(event.content_blocks)
                    self._thinking_bubble = existing
                    if auto_scroll:
                        self._scroll_to_latest()
                    return
                self.add_thinking_event(event, auto_scroll=auto_scroll)
                return
            self._remove_event_widget(event.id)
            return
        existing = self._event_widgets_by_id.get(event.id)
        if existing is not None:
            if isinstance(existing, ToolCallItem):
                existing.set_event(event)
            elif isinstance(existing, UsageOverviewItem):
                existing.set_event(event)
            elif isinstance(existing, ChatMessageBubble):
                existing.set_blocks(event.content_blocks)
            if auto_scroll:
                self._scroll_to_latest()
            return
        self.add_event(event, auto_scroll=auto_scroll)

    def _remove_event_widget(self, event_id: str) -> None:
        widget = self._event_widgets_by_id.pop(event_id, None)
        if widget is None:
            return
        if widget is self._thinking_bubble:
            self._thinking_bubble = None
        self._message_layout.removeWidget(widget)
        widget.deleteLater()

    def hide_thinking_indicator(self) -> None:
        if self._thinking_bubble is None:
            return
        bubble = self._thinking_bubble
        self._thinking_bubble = None
        for event_id, widget in list(self._event_widgets_by_id.items()):
            if widget is bubble:
                self._event_widgets_by_id.pop(event_id, None)
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
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def set_model_options(
        self,
        options: list[tuple[str, str]],
        *,
        selected_fq_model_key: str | None = None,
    ) -> None:
        self._model_options = list(options)
        current_key = selected_fq_model_key or self.selected_fq_model_key()
        self._model_picker.blockSignals(True)
        self._model_picker.clear()
        for fq_model_key, label in self._model_options:
            self._model_picker.addItem(label, fq_model_key)
        if current_key:
            index = self._model_picker.findData(current_key)
            if index >= 0:
                self._model_picker.setCurrentIndex(index)
        self._model_picker.blockSignals(False)
        self._sync_composer_controls_enabled()

    def set_selected_fq_model_key(self, fq_model_key: str | None) -> None:
        if not fq_model_key:
            return
        index = self._model_picker.findData(fq_model_key)
        if index < 0:
            return
        self._model_picker.blockSignals(True)
        self._model_picker.setCurrentIndex(index)
        self._model_picker.blockSignals(False)

    def selected_fq_model_key(self) -> str:
        value = self._model_picker.currentData()
        return str(value or "")

    def _handle_model_picker_changed(self, _index: int) -> None:
        fq_model_key = self.selected_fq_model_key()
        if fq_model_key:
            self.model_selected.emit(fq_model_key)

    def _sync_send_button_text(self) -> None:
        if self._running:
            send_text = self.tr("Stop")
        elif self._has_pending_attachments():
            send_text = "..."
        else:
            send_text = self.tr("Send")
        self._send_button.setText(send_text)

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
        self.add_message("System", [{"type": "ui_error", "message": message}])

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
            self.tr("Attach files"),
            "",
            self.tr("Data files (*.csv *.xlsx *.xls)"),
        )
        self._add_local_files(paths)

    def _configure_attach_button(self, button: QPushButton) -> None:
        button.setObjectName("attachButton")
        button.setFixedSize(34, 34)
        button.setIcon(attach_file_icon())
        button.setIconSize(QSize(16, 16))
        button.setToolTip(self.tr("Attach files"))

    def _add_local_files(self, paths: list[str], *, notify: bool = True) -> None:
        added_paths: list[str] = []
        for raw_path in paths:
            path = str(Path(raw_path).resolve())
            if Path(path).suffix.lower() not in SUPPORTED_DATASET_SUFFIXES:
                continue
            if path not in self._attached_files:
                self._attached_files.append(path)
                self._attachment_states[path] = ComposerAttachmentState(path=path)
                added_paths.append(path)
        self._refresh_attachment_chips()
        self._sync_composer_controls_enabled()
        if notify and added_paths:
            self.files_attached.emit(added_paths)

    def restore_composer(self, text: str, file_paths: list[str]) -> None:
        self._editor.setPlainText(text)
        self._attached_files.clear()
        self._attachment_states.clear()
        self._add_local_files(file_paths, notify=False)

    def set_attachment_status(
        self,
        path: str,
        status: ComposerAttachmentStatus,
        *,
        error: str | None = None,
    ) -> None:
        resolved_path = str(Path(path).resolve())
        state = self._attachment_states.get(resolved_path)
        if state is None:
            return
        state.status = status
        state.error = error
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def _remove_attached_file(self, path: str, *, notify: bool = True) -> None:
        resolved_path = str(Path(path).resolve())
        if resolved_path not in self._attached_files:
            return
        self._attached_files.remove(resolved_path)
        self._attachment_states.pop(resolved_path, None)
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()
        if notify:
            self.attachment_removed.emit(resolved_path)

    def _install_composer_drop_filters(self) -> None:
        widgets = [
            self._composer_shell,
            self._composer,
            self._attachment_bar,
            self._attach_button,
            self._editor,
            self._editor.viewport(),
            self._model_picker,
            self._send_button,
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
        return [
            url.toLocalFile()
            for url in mime_data.urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in SUPPORTED_DATASET_SUFFIXES
        ]

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
        if self._has_unready_attachments():
            return
        files = self._ready_attachment_paths()
        if not text and not files:
            return
        self._editor.clear()
        self._attached_files.clear()
        self._attachment_states.clear()
        self._refresh_attachment_chips()
        self.message_submitted.emit(text, files, self.selected_fq_model_key())

    def _sync_composer_controls_enabled(self) -> None:
        can_edit = not self._running and not self._awaiting_step_confirmation
        self._editor.setEnabled(can_edit)
        self._attach_button.setEnabled(can_edit)
        self._send_button.setEnabled(not self._awaiting_step_confirmation and not self._has_unready_attachments())
        self._model_picker.setEnabled(bool(self._model_options))
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
            state = self._attachment_states.get(path) or ComposerAttachmentState(
                path=path,
                status=ComposerAttachmentStatus.READY,
            )
            chip = AttachmentChip(state, self)
            chip.remove_requested.connect(self._remove_attached_file)
            self._attachment_layout.insertWidget(self._attachment_layout.count() - 1, chip)

    def _has_unready_attachments(self) -> bool:
        return any(
            state.status is not ComposerAttachmentStatus.READY
            for state in self._attachment_states.values()
        )

    def _has_pending_attachments(self) -> bool:
        return any(
            state.status is ComposerAttachmentStatus.PENDING
            for state in self._attachment_states.values()
        )

    def _ready_attachment_paths(self) -> list[str]:
        ready_paths: list[str] = []
        for path in self._attached_files:
            state = self._attachment_states.get(path)
            if state is not None and state.status is ComposerAttachmentStatus.READY:
                ready_paths.append(path)
        return ready_paths

    def _author_label(self, author: AgentMessageAuthor) -> str:
        if author is AgentMessageAuthor.USER:
            return "You"
        if author is AgentMessageAuthor.TOOL:
            return "Tool"
        if author is AgentMessageAuthor.SYSTEM:
            return "System"
        return "Xenix"

    def _event_author_label(self, author: ChatbotEventAuthor) -> str:
        if author is ChatbotEventAuthor.USER:
            return "You"
        if author is ChatbotEventAuthor.TOOL:
            return "Tool"
        return "Xenix"

    def _resize_user_messages(self) -> None:
        width = self._message_column.width()
        for index in range(self._message_layout.count()):
            item = self._message_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, (ChatMessageBubble, ToolCallItem, UsageOverviewItem)):
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
