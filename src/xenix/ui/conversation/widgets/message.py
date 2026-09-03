"""Chat message rendering, including the black user-message card path."""

from __future__ import annotations

import secrets

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...markdown_renderer import render_chat_markdown
from ..presentation import ArtifactResolver, ChatbotBlock, render_content_blocks
from .artifacts import _load_artifact_preview_pixmap
from .common import _propagate_geometry_change
from .text import AutoHeightTextBrowser

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
        return _load_artifact_preview_pixmap(
            self._artifact_resolver,
            uri,
            available_width=self.width(),
        )

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


class ChatMessageBubble(QFrame):
    link_activated = Signal(str)
    source_file_activated = Signal(str)

    def __init__(
        self,
        *,
        author: str,
        blocks: list[ChatbotBlock],
        artifact_resolver: ArtifactResolver | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._author = author
        self._author_label: QLabel | None = None
        self._artifact_resolver = artifact_resolver
        self._source_attachment_targets: dict[str, str] = {}
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
            body.link_activated.connect(self._handle_link_activated)
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

    def _card_object_name(self, author: str, blocks: list[ChatbotBlock]) -> str:
        if author == "You":
            return "chatMessageUser"
        if author == "System":
            return "chatMessageSystem"
        return "chatMessageAssistant"

    def _shows_author(self, author: str, blocks: list[ChatbotBlock]) -> bool:
        return author not in {"You", "Xenix"}

    def _display_author(self) -> str:
        if self._author == "You":
            return self.tr("You")
        if self._author == "Tool":
            return self.tr("Tool")
        if self._author == "System":
            return self.tr("System")
        return self._author

    def _render_blocks(self, blocks: list[ChatbotBlock]) -> str:
        self._source_attachment_targets.clear()
        return render_chat_markdown(
            render_content_blocks(
                blocks,
                source_attachment_target_resolver=self._source_attachment_target,
            ),
            inline_artifact_images=True,
        )

    def set_available_width(self, width: int) -> None:
        if self._card.objectName() == "chatMessageUser":
            self._card.setMinimumWidth(max(280, int(width * 0.6)))
            self._card.setMaximumWidth(max(320, int(width * 0.8)))
        elif self._card.objectName() == "chatMessageSystem":
            self._card.setMaximumWidth(max(320, int(width * 0.78)))

    def set_blocks(self, blocks: list[ChatbotBlock]) -> None:
        self._blocks = list(blocks)
        self._browser.setHtml(self._render_blocks(self._blocks))

    def retranslate_ui(self) -> None:
        if self._author_label is not None:
            self._author_label.setText(self._display_author())
        self._browser.setHtml(self._render_blocks(self._blocks))

    def _source_attachment_target(self, block: ChatbotBlock) -> str | None:
        if not block.is_openable:
            return None
        file_path = block.file_path
        if not file_path.strip():
            return None
        token = f"xenix-source://{secrets.token_urlsafe(18)}"
        self._source_attachment_targets[token] = file_path
        return token

    def _handle_link_activated(self, url) -> None:
        target = url.toString() if hasattr(url, "toString") else str(url)
        source_path = self._source_attachment_targets.get(target)
        if source_path is not None:
            self.source_file_activated.emit(source_path)
            return
        self.link_activated.emit(target)
