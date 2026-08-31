"""Timeline event item widgets: tool calls, connection retries, usage."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....services.agent import ChatbotEvent
from ...icons import chevron_icon, tool_icon
from ...markdown_renderer import render_chat_markdown
from ...semantic_identity import identify_repeated_item
from ..presentation import (
    ArtifactResolver,
    connection_attempt_counts,
    connection_retry_events,
    payload_int,
    render_content_blocks,
    translate_tool_summary,
    usage_overview_text,
)
from .common import UNBOUNDED_WIDGET_WIDTH, _propagate_geometry_change
from .text import AutoHeightTextBrowser


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
        identify_repeated_item(
            self,
            role="chat.timeline.tool-call",
            item_reference=event.id,
        )
        identify_repeated_item(
            self._chevron_button,
            role="chat.tool-call.toggle-details",
            item_reference=event.id,
        )
        identify_repeated_item(
            self._details_button,
            role="chat.tool-call.open-details",
            item_reference=event.id,
        )
        self._icon_label.setPixmap(tool_icon(event.icon_key).pixmap(QSize(16, 16)))
        self._summary_label.setText(self._summary_text(event))
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
        toggle_label = self.tr("Hide result") if self._expanded else self.tr("Show result")
        self._chevron_button.setToolTip(toggle_label)
        self._chevron_button.setAccessibleName(toggle_label)
        self._detail_browser.setHtml(
            render_chat_markdown(self._detail_markdown(event), inline_artifact_images=False)
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

    def _summary_text(self, event: ChatbotEvent) -> str:
        return translate_tool_summary(event.summary or "")

    def _detail_markdown(self, event: ChatbotEvent) -> str:
        return render_content_blocks(event.detail_blocks)


class ConnectionRetryItem(QFrame):
    def __init__(
        self,
        event: ChatbotEvent,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("chatConnectionRetryItem")
        self._card = self
        self._event = event
        self._expanded = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setObjectName("chatConnectionRetryItemLayout")
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setObjectName("chatConnectionRetryHeaderLayout")
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setObjectName("chatConnectionRetryIcon")
        self._icon_label.setFixedWidth(22)
        self._icon_label.setAlignment(Qt.AlignCenter)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("chatConnectionRetrySummary")
        self._summary_label.setWordWrap(True)

        self._chevron_button = QToolButton()
        self._chevron_button.setObjectName("chatConnectionRetryChevron")
        self._chevron_button.setFixedSize(28, 24)
        self._chevron_button.setAutoRaise(True)
        self._chevron_button.setArrowType(Qt.NoArrow)
        self._chevron_button.setIconSize(QSize(16, 16))
        self._chevron_button.clicked.connect(self._toggle_detail)

        header_layout.addWidget(self._icon_label, 0, Qt.AlignVCenter)
        header_layout.addWidget(self._summary_label, 1, Qt.AlignVCenter)
        header_layout.addWidget(self._chevron_button, 0, Qt.AlignVCenter)
        layout.addWidget(header)

        self._detail_browser = AutoHeightTextBrowser()
        self._detail_browser.setObjectName("chatConnectionRetryDetail")
        self._detail_browser.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self._detail_browser)

        self.set_event(event)

    def set_event(self, event: ChatbotEvent) -> None:
        self._event = event
        identify_repeated_item(
            self,
            role="chat.timeline.connection-retry",
            item_reference=event.id,
        )
        identify_repeated_item(
            self._chevron_button,
            role="chat.connection-retry.toggle-details",
            item_reference=event.id,
        )
        self._icon_label.setPixmap(tool_icon(event.icon_key).pixmap(QSize(16, 16)))
        attempt_number, max_attempts = connection_attempt_counts(event.detail_blocks)
        self._summary_label.setText(
            self.tr("Connecting ({attempt}/{max})").format(
                attempt=attempt_number,
                max=max_attempts,
            )
        )
        has_detail = bool(event.detail_blocks)
        self._chevron_button.setVisible(has_detail)
        self._chevron_button.setEnabled(has_detail)
        if not has_detail:
            self._expanded = False
        self._chevron_button.setIcon(chevron_icon(expanded=self._expanded))
        toggle_label = self.tr("Hide details") if self._expanded else self.tr("Show details")
        self._chevron_button.setToolTip(toggle_label)
        self._chevron_button.setAccessibleName(toggle_label)
        self._detail_browser.setHtml(
            render_chat_markdown(
                self._connection_detail_markdown(event.detail_blocks),
                inline_artifact_images=False,
            )
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

    def _connection_detail_markdown(self, detail_blocks: list[dict[str, Any]]) -> str:
        retry_events = connection_retry_events(detail_blocks)
        if not retry_events:
            return ""
        lines = ["### " + self.tr("LLM connection retry"), ""]
        for retry_event in retry_events:
            attempt_number = payload_int(retry_event, "attempt_number")
            max_attempts = payload_int(retry_event, "max_attempts")
            if attempt_number and max_attempts:
                lines.append(
                    "#### "
                    + self.tr("Attempt {attempt}/{max}").format(
                        attempt=attempt_number,
                        max=max_attempts,
                    )
                )
            else:
                lines.append("#### " + self.tr("Attempt"))
            error_code = str(retry_event.get("error_code") or "").strip()
            if error_code:
                lines.append(
                    self.tr("Error code: `{code}`").format(code=error_code)
                )
            error_summary = str(retry_event.get("error_summary") or "").strip()
            if error_summary:
                lines.append(error_summary)
            lines.append("")
        return "\n".join(lines).strip()


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
        self._label.setText(usage_overview_text(event.usage_payload))
        _propagate_geometry_change(self)

    def retranslate_ui(self) -> None:
        self.set_event(self._event)

    def set_available_width(self, width: int) -> None:
        self.setMaximumWidth(UNBOUNDED_WIDGET_WIDTH)
        self._label.setMaximumWidth(max(280, width))
