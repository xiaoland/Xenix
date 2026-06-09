from __future__ import annotations

import json
from enum import StrEnum
from collections.abc import Callable
from typing import Any

from sqlmodel import Field, SQLModel

from ..storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    AgentProviderRequestRow,
    AgentToolCallRow,
    AgentToolCallStatus,
    AgentTurnStatus,
)
from .conversation_store import ThreadSnapshot
from .tool_presentations import ToolPresentation, tool_presentation_for_name


class ChatbotEventKind(StrEnum):
    TEXT = "text"
    TOOL = "tool"
    THINKING = "thinking"
    USAGE = "usage"


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
    usage_payload: dict[str, Any] | None = None
    detail_blocks: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)


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

    turns_by_id = {turn.id: turn for turn in snapshot.turns}
    provider_requests_by_turn: dict[str, list[AgentProviderRequestRow]] = {}
    for provider_request in snapshot.provider_requests:
        provider_requests_by_turn.setdefault(provider_request.turn_id, []).append(provider_request)

    events: list[ChatbotEvent] = []
    for index, message in enumerate(snapshot.messages):
        if message.kind in {AgentMessageKind.USER, AgentMessageKind.ASSISTANT}:
            events.append(project_text_message_event(message))
        elif message.kind is AgentMessageKind.TOOL_CALL:
            tool_call = tool_calls_by_request_id.get(message.id)
            if tool_call is not None:
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
        next_turn_id = snapshot.messages[index + 1].turn_id if index + 1 < len(snapshot.messages) else None
        if message.turn_id is not None and message.turn_id != next_turn_id:
            turn = turns_by_id.get(message.turn_id)
            if turn is not None and turn.status is AgentTurnStatus.ENDED:
                usage_event = project_turn_usage_event(
                    turn_id=message.turn_id,
                    sequence_index=message.sequence_index + 1,
                    provider_requests=provider_requests_by_turn.get(message.turn_id, []),
                )
                if usage_event is not None:
                    events.append(usage_event)
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
    detail_blocks = _tool_detail_blocks(tool_call)
    summary = _tool_summary_from_payload(tool_call, status) or presentation.summary_for(status)
    actions = _tool_actions(tool_call)
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
        actions=actions,
    )


def project_turn_usage_event(
    *,
    turn_id: str,
    sequence_index: int,
    provider_requests: list[AgentProviderRequestRow],
) -> ChatbotEvent | None:
    usage_rows = [
        row
        for row in provider_requests
        if isinstance(row.usage_payload, dict)
    ]
    if not usage_rows:
        return None

    input_tokens = sum(_usage_int(row.usage_payload, "input_tokens") for row in usage_rows)
    cached_input_tokens = sum(_usage_int(row.usage_payload, "cached_input_tokens") for row in usage_rows)
    output_tokens = sum(_usage_int(row.usage_payload, "output_tokens") for row in usage_rows)
    total_tokens = sum(_usage_int(row.usage_payload, "total_tokens") for row in usage_rows)
    if total_tokens <= 0 and input_tokens <= 0 and output_tokens <= 0 and cached_input_tokens <= 0:
        return None

    usage_payload = {
        "request_count": len(usage_rows),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens or input_tokens + output_tokens,
    }
    return ChatbotEvent(
        id=f"{turn_id}:usage",
        kind=ChatbotEventKind.USAGE,
        turn_id=turn_id,
        sequence_index=sequence_index,
        author=ChatbotEventAuthor.ASSISTANT,
        status=ChatbotEventStatus.COMPLETED,
        usage_payload=usage_payload,
        source_message_ids=[],
    )


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


def _usage_int(payload: dict[str, Any] | None, key: str) -> int:
    if not isinstance(payload, dict):
        return 0
    value = payload.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def _tool_summary_from_payload(tool_call: AgentToolCallRow, status: AgentToolCallStatus) -> str | None:
    if status is not AgentToolCallStatus.SUCCEEDED:
        return None
    payload = tool_call.result_payload or {}
    if payload.get("async_state") != "running_background":
        return None
    if tool_call.tool_name == "model.hyper_train":
        return "Model tuning running in background"
    if tool_call.tool_name == "model.train":
        return "Model training running in background"
    if tool_call.tool_name == "model.apply":
        return "Model apply running in background"
    return "ML task running in background"


def _tool_actions(tool_call: AgentToolCallRow) -> list[dict[str, Any]]:
    if tool_call.tool_name == "model.task.query":
        return []
    payload = tool_call.result_payload
    if payload is None:
        return []
    raw_task_ids = payload.get("task_ids")
    if not isinstance(raw_task_ids, list):
        raw_task_ids = [payload.get("ml_task_id")] if isinstance(payload.get("ml_task_id"), str) else []
    task_ids = [str(task_id) for task_id in raw_task_ids if str(task_id).strip()]
    if not task_ids:
        return []

    actions: list[dict[str, Any]] = [
        {
            "type": "open_tool_call_detail",
            "task_ids": task_ids,
        }
    ]
    return actions


def _tool_detail_blocks(
    tool_call: AgentToolCallRow,
) -> list[dict[str, Any]]:
    if tool_call.tool_name == "analysis.lambda":
        return _analysis_lambda_detail_blocks(tool_call)

    lines = [f"### {tool_call.tool_name}"]
    lines.append("")
    lines.append(f"Status: `{tool_call.status.value}`")
    if tool_call.error_summary:
        lines.extend(["", "#### Error", tool_call.error_summary])
    lines.extend(["", "#### Arguments", "```json", _json_dump(tool_call.arguments_payload or {}), "```"])
    if tool_call.result_payload is not None:
        lines.extend(["", "#### Result", "```json", _json_dump(tool_call.result_payload), "```"])
    return [{"type": "markdown", "text": "\n".join(lines)}]


def _analysis_lambda_detail_blocks(tool_call: AgentToolCallRow) -> list[dict[str, Any]]:
    payload = tool_call.result_payload or {}
    result = payload.get("result")
    output = result.get("output") if isinstance(result, dict) else None
    if not isinstance(output, dict):
        return _tool_detail_blocks_for_payload(tool_call)

    lines = ["### analysis.lambda result"]
    lines.extend(["", "Status: `" + tool_call.status.value + "`"])
    if tool_call.error_summary:
        lines.extend(["", "#### Error", tool_call.error_summary])
    lines.extend(["", "#### Arguments", "```json", _json_dump(tool_call.arguments_payload or {}), "```"])
    for key in ("markdown", "report", "message", "summary"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            lines.extend(["", value.strip()])
            break

    lines.extend(["", "#### Output", "```json", _json_dump(output), "```"])

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        lines.extend(["", "#### Artifacts"])
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            title = str(artifact.get("title") or artifact.get("artifact_id") or "Artifact")
            uri = str(artifact.get("uri") or "")
            kind = str(artifact.get("kind") or "artifact")
            if uri:
                lines.append(f"- [{title}]({uri}) ({kind})")
            else:
                lines.append(f"- {title} ({kind})")
    return [{"type": "markdown", "text": "\n".join(lines)}]


def _tool_detail_blocks_for_payload(tool_call: AgentToolCallRow) -> list[dict[str, Any]]:
    lines = [f"### {tool_call.tool_name}", "", f"Status: `{tool_call.status.value}`"]
    if tool_call.error_summary:
        lines.extend(["", "#### Error", tool_call.error_summary])
    lines.extend(["", "#### Arguments", "```json", _json_dump(tool_call.arguments_payload or {}), "```"])
    if tool_call.result_payload is not None:
        lines.extend(["", "#### Result", "```json", _json_dump(tool_call.result_payload), "```"])
    return [{"type": "markdown", "text": "\n".join(lines)}]


def _json_dump(value: Any) -> str:
    dumped = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    max_length = 12000
    if len(dumped) <= max_length:
        return dumped
    return dumped[:max_length] + f"\n... <truncated {len(dumped) - max_length} chars>"
