"""Chat shell: composition and signal forwarding.

``ThreadDetailView`` composes the ``ChatTimeline`` (message/event display and
scroll follow) and the ``ChatComposer`` (input, attachments, submission intent)
and forwards their signals through one stable public surface.  It owns no
timeline or composer private state itself.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .conversation.composer import ChatComposer
from .conversation.presentation import ComposerAttachmentState, ComposerAttachmentStatus
from .conversation.timeline import ChatTimeline
from .conversation.widgets import (
    AttachmentChip,
    AutoGrowingTextEdit,
    ChatMessageBubble,
    ConnectionRetryItem,
    ToolCallItem,
    UsageOverviewItem,
)


class ThreadDetailView(QWidget):
    message_submitted = Signal(str, list, str)
    files_attached = Signal(list)
    attachment_removed = Signal(str)
    service_link_activated = Signal(str)
    source_file_activated = Signal(str)
    tool_action_requested = Signal(object)
    stop_requested = Signal()
    step_budget_continue_requested = Signal()
    step_budget_stop_requested = Signal()
    model_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("threadDetailView")

        self.timeline = ChatTimeline(self)
        self.composer = ChatComposer(self)

        self.composer.message_submitted.connect(self.message_submitted.emit)
        self.composer.files_attached.connect(self.files_attached.emit)
        self.composer.attachment_removed.connect(self.attachment_removed.emit)
        self.composer.stop_requested.connect(self.stop_requested.emit)
        self.composer.step_budget_continue_requested.connect(self.step_budget_continue_requested.emit)
        self.composer.step_budget_stop_requested.connect(self.step_budget_stop_requested.emit)
        self.composer.model_selected.connect(self.model_selected.emit)
        self.timeline.service_link_activated.connect(self.service_link_activated.emit)
        self.timeline.source_file_activated.connect(self.source_file_activated.emit)
        self.timeline.tool_action_requested.connect(self.tool_action_requested.emit)

        root = QVBoxLayout(self)
        root.setObjectName("threadDetailLayout")
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self.timeline, 1)
        root.addWidget(self.composer, 0)

    def retranslate_ui(self) -> None:
        self.timeline.retranslate_ui()
        self.composer.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    # Timeline forwarding -----------------------------------------------------

    def set_artifact_resolver(self, resolver: Any) -> None:
        self.timeline.set_artifact_resolver(resolver)

    def render_events(self, events: list[Any]) -> None:
        self.timeline.render_events(events)

    def clear_messages(self) -> None:
        self.timeline.clear_messages()

    def apply_chatbot_event(self, event: Any, *, auto_scroll: bool = True) -> None:
        self.timeline.apply_chatbot_event(event, auto_scroll=auto_scroll)

    def hide_thinking_indicator(self) -> None:
        self.timeline.hide_thinking_indicator()

    def show_error(self, message: str) -> None:
        self.timeline.show_error(message)

    # Composer forwarding -----------------------------------------------------

    def set_running(self, running: bool) -> None:
        self.composer.set_running(running)

    def begin_composer_submission(self, attachment_paths: list[str]) -> None:
        self.composer.begin_composer_submission(attachment_paths)

    def acknowledge_composer_submission(self) -> None:
        self.composer.acknowledge_composer_submission()

    def abort_composer_submission(self) -> None:
        self.composer.abort_composer_submission()

    def set_model_options(
        self,
        options: list[tuple[str, str]],
        *,
        selected_fq_model_key: str | None = None,
    ) -> None:
        self.composer.set_model_options(
            options,
            selected_fq_model_key=selected_fq_model_key,
        )

    def set_selected_fq_model_key(self, fq_model_key: str | None) -> None:
        self.composer.set_selected_fq_model_key(fq_model_key)

    def selected_fq_model_key(self) -> str:
        return self.composer.selected_fq_model_key()

    def restore_composer(self, text: str, file_paths: list[str]) -> None:
        self.composer.restore_composer(text, file_paths)

    def set_attachment_status(
        self,
        path: str,
        status: ComposerAttachmentStatus,
        *,
        error: str | None = None,
    ) -> None:
        self.composer.set_attachment_status(path, status, error=error)

    def show_step_confirmation(self, message: str) -> None:
        self.composer.show_step_confirmation(message)

    def clear_step_confirmation(self) -> None:
        self.composer.clear_step_confirmation()


__all__ = [
    "ThreadDetailView",
    "ComposerAttachmentStatus",
    "ComposerAttachmentState",
    "ChatMessageBubble",
    "ToolCallItem",
    "ConnectionRetryItem",
    "UsageOverviewItem",
    "AttachmentChip",
    "AutoGrowingTextEdit",
]
