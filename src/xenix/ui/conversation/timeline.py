"""Chat timeline: message/event entry maintenance, scrolling, and display.

``ChatTimeline`` owns the message column, the scroll area, the scroll-to-bottom
button, and the per-event widget registry.  It renders canonical Chatbot events
and re-emits link/tool actions; it never reaches into the composer.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QEvent, QSize, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ...services.agent import (
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
    project_chatbot_events,
)
from ..icons import scroll_to_bottom_icon
from ..semantic_identity import identify
from .presentation import ArtifactResolver, event_display_blocks
from .widgets import ChatMessageBubble, ConnectionRetryItem, ToolCallItem, UsageOverviewItem

_SCROLL_FOLLOW_THRESHOLD = 24


class ChatTimeline(QWidget):
    service_link_activated = Signal(str)
    source_file_activated = Signal(str)
    tool_action_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thinking_bubble: ChatMessageBubble | None = None
        self._event_widgets_by_id: dict[str, QWidget] = {}
        self._message_bubbles_by_id: dict[str, ChatMessageBubble] = {}
        self._artifact_resolver: ArtifactResolver | None = None
        self._auto_follow_latest = True
        self._scroll_to_latest_token = 0
        self._scrollbar_adjusting = False

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
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.valueChanged.connect(self._handle_scroll_value_changed)
        scrollbar.rangeChanged.connect(self._handle_scroll_range_changed)

        self._scroll_to_bottom_button = QToolButton(self)
        self._scroll_to_bottom_button.setObjectName("scrollToBottomButton")
        self._scroll_to_bottom_button.setFixedSize(36, 36)
        self._scroll_to_bottom_button.setIcon(scroll_to_bottom_icon())
        self._scroll_to_bottom_button.setIconSize(QSize(18, 18))
        self._scroll_to_bottom_button.setAutoRaise(True)
        self._scroll_to_bottom_button.clicked.connect(self._handle_scroll_to_bottom_clicked)
        self._scroll_to_bottom_button.hide()
        identify(self._scroll_to_bottom_button, "chat.timeline.scroll-to-bottom")

        root = QVBoxLayout(self)
        root.setObjectName("chatTimelineRootLayout")
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._scroll, 1)

        self.retranslate_ui()
        self._sync_scroll_to_bottom_button_geometry()
        self._sync_scroll_to_bottom_button_visibility()

    def retranslate_ui(self) -> None:
        self._scroll_to_bottom_button.setToolTip(self.tr("Scroll to bottom"))
        self._scroll_to_bottom_button.setAccessibleName(self.tr("Scroll to bottom"))
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

    def set_artifact_resolver(self, resolver: ArtifactResolver | None) -> None:
        self._artifact_resolver = resolver

    @property
    def scroll_to_bottom_button(self) -> QToolButton:
        return self._scroll_to_bottom_button

    @property
    def message_bubbles_by_id(self) -> dict[str, ChatMessageBubble]:
        return self._message_bubbles_by_id

    def render_events(self, events: list[ChatbotEvent]) -> None:
        self.hide_thinking_indicator()
        self.clear_messages()
        for event in events:
            self.add_event(event, auto_scroll=False)
        self._auto_follow_latest = True
        self._scroll_to_latest(force=True)

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
        bubble.link_activated.connect(self.service_link_activated.emit)
        bubble.source_file_activated.connect(self.source_file_activated.emit)
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

    def show_error(self, message: str) -> None:
        self.add_message("System", [{"type": "ui_error", "message": message}])

    def add_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> QWidget | None:
        if event.kind is ChatbotEventKind.ACTIVITY:
            return self.add_activity_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.THINKING:
            return self.add_thinking_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.TOOL:
            return self.add_tool_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.CONNECTION:
            return self.add_connection_event(event, auto_scroll=auto_scroll)
        if event.kind is ChatbotEventKind.USAGE:
            return self.add_usage_event(event, auto_scroll=auto_scroll)
        blocks = event_display_blocks(event)
        if event.kind is ChatbotEventKind.TEXT and not blocks:
            # A reasoning-only Assistant Message and a user event containing
            # only UI-hidden attachment blocks remain in the Event stream but
            # must not allocate an empty visual card.
            return None
        return self.add_message(
            self._event_author_label(event.author),
            blocks,
            message_id=event.source_message_ids[0] if event.source_message_ids else None,
            event_id=event.id,
            auto_scroll=auto_scroll,
        )

    def add_tool_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ToolCallItem:
        item = ToolCallItem(event, artifact_resolver=self._artifact_resolver, parent=self)
        item.link_activated.connect(self.service_link_activated.emit)
        item.action_requested.connect(self.tool_action_requested.emit)
        item.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), item)
        self._event_widgets_by_id[event.id] = item
        if auto_scroll:
            self._scroll_to_latest()
        return item

    def add_connection_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ConnectionRetryItem:
        item = ConnectionRetryItem(event, parent=self)
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
        return self._add_activity_indicator(event, auto_scroll=auto_scroll)

    def add_activity_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ChatMessageBubble:
        return self._add_activity_indicator(event, auto_scroll=auto_scroll)

    def _activity_blocks(self, event: ChatbotEvent) -> list[dict[str, Any]]:
        if event.content_blocks:
            return list(event.content_blocks)
        return [{"type": "thinking", "text": "Thinking..."}]

    def _add_activity_indicator(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> ChatMessageBubble:
        bubble = ChatMessageBubble(
            author=self._event_author_label(event.author),
            blocks=self._activity_blocks(event),
            artifact_resolver=self._artifact_resolver,
            parent=self,
        )
        bubble.link_activated.connect(self.service_link_activated.emit)
        bubble.source_file_activated.connect(self.source_file_activated.emit)
        bubble.set_available_width(self._message_column.width())
        self._message_layout.insertWidget(self._message_insert_index(), bubble)
        self._event_widgets_by_id[event.id] = bubble
        self._thinking_bubble = bubble
        if auto_scroll:
            self._scroll_to_latest()
        return bubble

    def apply_message_event(self, message, *, auto_scroll: bool = True) -> None:
        """Compatibility entry point that still follows the Event projection."""

        for event in project_chatbot_events(SimpleNamespace(messages=[message])):
            self.apply_chatbot_event(event, auto_scroll=auto_scroll)

    def apply_chatbot_event(self, event: ChatbotEvent, *, auto_scroll: bool = True) -> None:
        if event.kind is ChatbotEventKind.ACTIVITY:
            if event.status is ChatbotEventStatus.IN_PROGRESS:
                if self._thinking_bubble is not None:
                    for event_id, widget in list(self._event_widgets_by_id.items()):
                        if widget is self._thinking_bubble:
                            self._event_widgets_by_id.pop(event_id, None)
                    self._thinking_bubble.set_blocks(self._activity_blocks(event))
                    self._event_widgets_by_id[event.id] = self._thinking_bubble
                    if auto_scroll:
                        self._scroll_to_latest()
                    return
                self.add_activity_event(event, auto_scroll=auto_scroll)
                return
            self._remove_event_widget(event.id)
            return
        if event.kind is ChatbotEventKind.THINKING:
            if event.status is ChatbotEventStatus.IN_PROGRESS:
                existing = self._event_widgets_by_id.get(event.id)
                if isinstance(existing, ChatMessageBubble):
                    existing.set_blocks(self._activity_blocks(event))
                    self._thinking_bubble = existing
                    if auto_scroll:
                        self._scroll_to_latest()
                    return
                self.add_thinking_event(event, auto_scroll=auto_scroll)
                return
            self._remove_event_widget(event.id)
            return
        if event.kind is ChatbotEventKind.CONNECTION and event.status is ChatbotEventStatus.COMPLETED:
            self._remove_event_widget(event.id)
            return
        self.hide_thinking_indicator()
        display_blocks = event_display_blocks(event)
        if event.kind is ChatbotEventKind.TEXT and not display_blocks:
            self._remove_event_widget(event.id)
            for source_id in event.source_message_ids:
                if source_id != event.id:
                    self._remove_event_widget(source_id)
            return
        existing = self._event_widgets_by_id.get(event.id)
        if existing is not None:
            if isinstance(existing, ToolCallItem):
                existing.set_event(event)
            elif isinstance(existing, ConnectionRetryItem):
                existing.set_event(event)
            elif isinstance(existing, UsageOverviewItem):
                existing.set_event(event)
            elif isinstance(existing, ChatMessageBubble):
                existing.set_blocks(display_blocks)
            if auto_scroll:
                self._scroll_to_latest()
            return
        self.add_event(event, auto_scroll=auto_scroll)

    def _remove_event_widget(self, event_id: str) -> None:
        widget = self._event_widgets_by_id.pop(event_id, None)
        if widget is None:
            widget = self._message_bubbles_by_id.get(event_id)
        if widget is None:
            return
        for mapped_id, mapped_widget in list(self._event_widgets_by_id.items()):
            if mapped_widget is widget:
                self._event_widgets_by_id.pop(mapped_id, None)
        for mapped_id, mapped_widget in list(self._message_bubbles_by_id.items()):
            if mapped_widget is widget:
                self._message_bubbles_by_id.pop(mapped_id, None)
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
        self._sync_scroll_to_bottom_button_geometry()

    def _author_label(self, author) -> str:
        author_value = getattr(author, "value", author)
        if author_value == "user":
            return "You"
        if author_value == "tool":
            return "Tool"
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
            if isinstance(widget, (ChatMessageBubble, ToolCallItem, ConnectionRetryItem, UsageOverviewItem)):
                widget.set_available_width(width)

    def _scroll_to_latest(self, *, settle_ticks: int = 4, force: bool = False) -> None:
        if not force and not self._auto_follow_latest:
            self._sync_scroll_to_bottom_button_visibility()
            return
        self._auto_follow_latest = True
        self._scroll_to_latest_token += 1
        self._scroll_to_latest_after_layout(max(0, settle_ticks), self._scroll_to_latest_token)

    def _scroll_to_latest_after_layout(self, remaining_ticks: int, token: int) -> None:
        if not self._is_scroll_target_alive():
            return
        if token != self._scroll_to_latest_token:
            return
        if remaining_ticks == 0:
            scrollbar = self._scroll.verticalScrollBar()
            self._scrollbar_adjusting = True
            try:
                scrollbar.setValue(scrollbar.maximum())
            finally:
                self._scrollbar_adjusting = False
            self._auto_follow_latest = True
            self._sync_scroll_to_bottom_button_visibility()
            return
        QTimer.singleShot(0, lambda: self._scroll_to_latest_after_layout(remaining_ticks - 1, token))

    def _handle_scroll_value_changed(self, _value: int) -> None:
        if self._scrollbar_adjusting:
            self._sync_scroll_to_bottom_button_visibility()
            return
        self._auto_follow_latest = self._is_scroll_at_bottom()
        if not self._auto_follow_latest:
            self._cancel_pending_scroll_to_latest()
        self._sync_scroll_to_bottom_button_visibility()

    def _handle_scroll_range_changed(self, _minimum: int, _maximum: int) -> None:
        if self._auto_follow_latest:
            self._scroll_to_latest(settle_ticks=0, force=True)
            return
        self._sync_scroll_to_bottom_button_visibility()

    def _handle_scroll_to_bottom_clicked(self) -> None:
        self._scroll_to_latest(force=True)

    def _cancel_pending_scroll_to_latest(self) -> None:
        self._scroll_to_latest_token += 1

    def _is_scroll_at_bottom(self) -> bool:
        scrollbar = self._scroll.verticalScrollBar()
        return scrollbar.value() >= scrollbar.maximum() - _SCROLL_FOLLOW_THRESHOLD

    def _sync_scroll_to_bottom_button_visibility(self) -> None:
        if not self._is_scroll_target_alive():
            return
        scrollbar = self._scroll.verticalScrollBar()
        visible = scrollbar.maximum() > 0 and not self._is_scroll_at_bottom()
        self._scroll_to_bottom_button.setVisible(visible)
        if visible:
            self._sync_scroll_to_bottom_button_geometry()
            self._scroll_to_bottom_button.raise_()

    def _sync_scroll_to_bottom_button_geometry(self) -> None:
        if not self._is_scroll_target_alive():
            return
        button = self._scroll_to_bottom_button
        scroll_geometry = self._scroll.geometry()
        x = scroll_geometry.x() + max(0, (scroll_geometry.width() - button.width()) // 2)
        y = scroll_geometry.y() + max(0, scroll_geometry.height() - button.height() - 14)
        button.move(x, y)

    def _is_scroll_target_alive(self) -> bool:
        try:
            return isValid(self) and isValid(self._scroll) and isValid(self._scroll_to_bottom_button)
        except RuntimeError:
            return False


__all__ = ["ChatTimeline"]
