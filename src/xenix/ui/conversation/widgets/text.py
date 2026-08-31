"""Auto-height text widgets used across the chatbot presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette, QPixmap, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QSizePolicy,
    QTextBrowser,
    QWidget,
)

from ..presentation import ArtifactResolver
from .artifacts import _load_artifact_preview_pixmap
from .common import _propagate_geometry_change


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
        return _load_artifact_preview_pixmap(
            self._artifact_resolver,
            uri,
            available_width=self.viewport().width(),
        )


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
