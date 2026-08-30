from __future__ import annotations

from xenix.services.agent.chatbot_events import (
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
)
from xenix.ui.chatbot import ComposerAttachmentStatus, ThreadDetailView

from .contracts import ScenarioContext, ScenarioHandle, no_cleanup, ready_immediately


def build_chat_empty(_context: ScenarioContext) -> ScenarioHandle:
    view = _base_chat_view()
    return ScenarioHandle(view, ready_immediately, no_cleanup)


def build_chat_mixed_timeline(_context: ScenarioContext) -> ScenarioHandle:
    view = _base_chat_view()
    view.render_events(
        [
            ChatbotEvent(
                id="message:user:001",
                kind=ChatbotEventKind.TEXT,
                sequence_index=0,
                author=ChatbotEventAuthor.USER,
                content_blocks=[{"type": "text", "text": "Compare quarterly sales by region."}],
                source_message_ids=["message:user:001"],
            ),
            ChatbotEvent(
                id="message:assistant:001",
                kind=ChatbotEventKind.TEXT,
                sequence_index=1,
                author=ChatbotEventAuthor.ASSISTANT,
                text="I profiled the synthetic dataset and checked regional totals.",
                content_blocks=[
                    {
                        "type": "text",
                        "text": "I profiled the synthetic dataset and checked regional totals.",
                    }
                ],
                source_message_ids=["message:assistant:001"],
            ),
            _tool_event("tool:profile:001", 2, "Profile complete", "12 columns, 240 rows"),
            _tool_event("tool:query:001", 3, "Query complete", "North leads the synthetic total"),
            ChatbotEvent(
                id="connection:001",
                kind=ChatbotEventKind.CONNECTION,
                sequence_index=4,
                author=ChatbotEventAuthor.ASSISTANT,
                status=ChatbotEventStatus.IN_PROGRESS,
                icon_key="connection",
                summary="llm_connection_retry",
                detail_blocks=[
                    {
                        "type": "llm_connection_retry",
                        "retry_events": [
                            {
                                "attempt_number": 1,
                                "max_attempts": 3,
                                "error_code": "synthetic_timeout",
                            }
                        ],
                    }
                ],
            ),
        ]
    )
    return ScenarioHandle(view, ready_immediately, no_cleanup)


def build_chat_running_with_attachments(_context: ScenarioContext) -> ScenarioHandle:
    view = _base_chat_view()
    paths = [
        "C:/xenix-synthetic/quarterly-sales.csv",
        "C:/xenix-synthetic/regional-targets.xlsx",
    ]
    view.restore_composer("Summarize the attached synthetic files.", paths)
    view.set_attachment_status(paths[0], ComposerAttachmentStatus.READY)
    view.set_attachment_status(
        paths[1],
        ComposerAttachmentStatus.FAILED,
        error="Synthetic import failed",
    )
    view.set_running(True)
    return ScenarioHandle(view, ready_immediately, no_cleanup)


def _base_chat_view() -> ThreadDetailView:
    view = ThreadDetailView()
    view.set_model_options(
        [
            ("synthetic/fast", "Synthetic Fast"),
            ("synthetic/reasoning", "Synthetic Reasoning"),
        ],
        selected_fq_model_key="synthetic/fast",
    )
    return view


def _tool_event(
    event_id: str,
    sequence_index: int,
    summary: str,
    detail: str,
) -> ChatbotEvent:
    return ChatbotEvent(
        id=event_id,
        kind=ChatbotEventKind.TOOL,
        sequence_index=sequence_index,
        author=ChatbotEventAuthor.TOOL,
        status=ChatbotEventStatus.COMPLETED,
        tool_call_id=event_id,
        tool_name="analysis.profile",
        icon_key="analysis",
        summary=summary,
        detail_blocks=[{"type": "text", "text": detail}],
    )
