from __future__ import annotations

from enum import StrEnum
from collections.abc import Callable
from typing import Any

from sqlmodel import Field, SQLModel

from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    AgentToolCallRow,
    AgentToolCallStatus,
)
from .conversation_store import ThreadSnapshot
from .tools import ToolPresentation, tool_presentation_for_name


class ChatbotEventKind(StrEnum):
    TEXT = "text"
    TOOL = "tool"
    THINKING = "thinking"


class ChatbotEventStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatbotEventAuthor(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatbotEvent(SQLModel):
    id: str
    kind: ChatbotEventKind
    turn_id: str | None = None
    sequence_index: int = 0
    author: ChatbotEventAuthor
    status: ChatbotEventStatus = ChatbotEventStatus.COMPLETED
    content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    source_message_ids: list[str] = Field(default_factory=list)
    tool_call_id: str | None = None
    tool_name: str | None = None
    icon_key: str | None = None
    summary: str | None = None
    detail_blocks: list[dict[str, Any]] = Field(default_factory=list)


ToolPresentationLookup = Callable[[str], ToolPresentation]


def thinking_chatbot_event_id(run_id: str) -> str:
    return f"{run_id}:thinking"


def build_thinking_chatbot_event(
    *,
    run_id: str,
    turn_id: str | None,
    status: ChatbotEventStatus,
) -> ChatbotEvent:
    return ChatbotEvent(
        id=thinking_chatbot_event_id(run_id),
        kind=ChatbotEventKind.THINKING,
        turn_id=turn_id,
        author=ChatbotEventAuthor.ASSISTANT,
        status=status,
        content_blocks=[{"type": "thinking", "text": "Thinking..."}]
        if status is ChatbotEventStatus.IN_PROGRESS
        else [],
        summary="Thinking..." if status is ChatbotEventStatus.IN_PROGRESS else None,
    )


def project_chatbot_events(
    snapshot: ThreadSnapshot,
    *,
    tool_presentation_lookup: ToolPresentationLookup | None = None,
) -> list[ChatbotEvent]:
    messages_by_id = {message.id: message for message in snapshot.messages}
    tool_calls_by_request_id = {tool_call.request_message_id: tool_call for tool_call in snapshot.tool_calls}
    paired_result_message_ids = {
        tool_call.result_message_id for tool_call in snapshot.tool_calls if tool_call.result_message_id is not None
    }

    events: list[ChatbotEvent] = []
    for message in snapshot.messages:
        if message.kind in {AgentMessageKind.USER, AgentMessageKind.ASSISTANT}:
            events.append(project_text_message_event(message))
            continue
        if message.kind is AgentMessageKind.TOOL_CALL:
            tool_call = tool_calls_by_request_id.get(message.id)
            if tool_call is None:
                continue
            result_message = (
                messages_by_id.get(tool_call.result_message_id)
                if tool_call.result_message_id is not None
                else None
            )
            events.append(
                project_tool_chatbot_event(
                    tool_call,
                    request_message=message,
                    result_message=result_message,
                    tool_presentation_lookup=tool_presentation_lookup,
                )
            )
            continue
        if message.kind is AgentMessageKind.TOOL_CALL_RESULT and message.id in paired_result_message_ids:
            continue
    return events


def project_text_message_event(message: AgentMessageRow) -> ChatbotEvent:
    return ChatbotEvent(
        id=message.id,
        kind=ChatbotEventKind.TEXT,
        turn_id=message.turn_id,
        sequence_index=message.sequence_index,
        author=_chatbot_author_for_message(message.ui_author),
        status=_chatbot_status_for_message(message.status),
        content_blocks=list(message.content_blocks),
        source_message_ids=[message.id],
    )


def project_tool_chatbot_event(
    tool_call: AgentToolCallRow,
    *,
    request_message: AgentMessageRow,
    result_message: AgentMessageRow | None = None,
    tool_presentation_lookup: ToolPresentationLookup | None = None,
) -> ChatbotEvent:
    status = tool_call.status
    if result_message is None or tool_call.result_message_id is None:
        status = AgentToolCallStatus.REQUESTED
    presentation = tool_presentation(tool_call.tool_name, tool_presentation_lookup=tool_presentation_lookup)
    detail_blocks = _tool_detail_blocks(result_message, error_summary=tool_call.error_summary)
    summary = _tool_summary_from_blocks(result_message) or presentation.summary_for(status)
    source_message_ids = [request_message.id]
    if result_message is not None:
        source_message_ids.append(result_message.id)

    return ChatbotEvent(
        id=tool_call.id,
        kind=ChatbotEventKind.TOOL,
        turn_id=tool_call.turn_id,
        sequence_index=request_message.sequence_index,
        author=ChatbotEventAuthor.TOOL,
        status=_chatbot_status_for_tool(status),
        source_message_ids=source_message_ids,
        tool_call_id=tool_call.id,
        tool_name=tool_call.tool_name,
        icon_key=presentation.icon_key,
        summary=summary,
        detail_blocks=detail_blocks,
    )


def build_tool_result_content_blocks(
    *,
    tool_name: str,
    status: AgentToolCallStatus,
    detail_blocks: list[dict[str, Any]],
    error_summary: str | None = None,
    tool_presentation_lookup: ToolPresentationLookup | None = None,
) -> list[dict[str, Any]]:
    summary = tool_presentation(tool_name, tool_presentation_lookup=tool_presentation_lookup).summary_for(status)
    blocks: list[dict[str, Any]] = [
        {
            "type": "tool_event_summary",
            "tool_name": tool_name,
            "status": status.value,
            "text": summary,
        }
    ]
    blocks.extend(detail_blocks)
    if error_summary and not _has_human_detail(detail_blocks):
        blocks.append({"type": "markdown", "text": error_summary})
    return blocks


def tool_presentation(
    tool_name: str,
    *,
    tool_presentation_lookup: ToolPresentationLookup | None = None,
) -> ToolPresentation:
    if tool_presentation_lookup is None:
        return tool_presentation_for_name(tool_name)
    return tool_presentation_lookup(tool_name)


def _chatbot_author_for_message(author: AgentMessageAuthor) -> ChatbotEventAuthor:
    if author is AgentMessageAuthor.USER:
        return ChatbotEventAuthor.USER
    if author is AgentMessageAuthor.TOOL:
        return ChatbotEventAuthor.TOOL
    return ChatbotEventAuthor.ASSISTANT


def _chatbot_status_for_message(status: AgentMessageStatus) -> ChatbotEventStatus:
    if status is AgentMessageStatus.IN_PROGRESS:
        return ChatbotEventStatus.IN_PROGRESS
    if status is AgentMessageStatus.FAILED:
        return ChatbotEventStatus.FAILED
    if status is AgentMessageStatus.CANCELLED:
        return ChatbotEventStatus.CANCELLED
    return ChatbotEventStatus.COMPLETED


def _chatbot_status_for_tool(status: AgentToolCallStatus) -> ChatbotEventStatus:
    if status is AgentToolCallStatus.FAILED:
        return ChatbotEventStatus.FAILED
    if status is AgentToolCallStatus.CANCELLED:
        return ChatbotEventStatus.CANCELLED
    if status in {AgentToolCallStatus.REQUESTED, AgentToolCallStatus.RUNNING}:
        return ChatbotEventStatus.PENDING
    return ChatbotEventStatus.COMPLETED


def _tool_summary_from_blocks(message: AgentMessageRow | None) -> str | None:
    if message is None:
        return None
    for block in message.content_blocks:
        if block.get("type") == "tool_event_summary":
            text = str(block.get("text") or "").strip()
            if text:
                return text
    return None


def _tool_detail_blocks(
    message: AgentMessageRow | None,
    *,
    error_summary: str | None,
) -> list[dict[str, Any]]:
    if message is None:
        return []
    detail_blocks = [
        dict(block)
        for block in message.content_blocks
        if block.get("type") not in {"tool_event_summary", "tool_result_payload"}
    ]
    if detail_blocks:
        return detail_blocks
    if error_summary:
        return [{"type": "markdown", "text": error_summary}]
    return []


def _has_human_detail(blocks: list[dict[str, Any]]) -> bool:
    return any(block.get("type") in {"text", "markdown", "tool_call_result"} for block in blocks)
