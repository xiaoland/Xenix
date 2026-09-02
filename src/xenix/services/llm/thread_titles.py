"""Thread-title derivation helpers for the Conversation authority.

Pure derivation and prompt-construction logic. The Live Conversation service
owns the orchestration (session/gate/admission); these functions only decide
*what* a title should be, never when it is written or whether the model may run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..storage.models import ConversationMessageKind, ConversationMessageRow
from .messages import (
    AssistantOutputItem,
    DatasetBlock,
    MarkdownBlock,
    SourceAttachmentBlock,
    TextBlock,
    blocks_from_payload,
    blocks_to_markdown,
)
from .providers import ProviderResponse

if TYPE_CHECKING:
    from .conversation import ConversationSnapshot


THREAD_TITLE_MAX_LENGTH = 80
THREAD_TITLE_SYSTEM_PROMPT = (
    "You generate concise conversation titles for Xenix threads. "
    "Return exactly one title only. Use the user's language when it is clear. "
    "Do not include quotes, markdown, labels, or trailing punctuation."
)


def assistant_response_text(response: ProviderResponse) -> str:
    return "\n".join(
        item.text.strip()
        for item in response.output_items
        if isinstance(item, AssistantOutputItem) and item.text and item.text.strip()
    )


def thread_title_message_text(message: ConversationMessageRow) -> str:
    if message.kind in {ConversationMessageKind.USER, ConversationMessageKind.CLIENT_CONTROL}:
        return blocks_to_markdown(blocks_from_payload(message.content_payload))
    if message.kind is ConversationMessageKind.ASSISTANT:
        return "\n".join(value for value in (message.text, message.refusal) if value)
    if message.kind is ConversationMessageKind.TOOL_CALL:
        return f"Tool call: {message.tool_id or ''}".strip()
    if message.kind is ConversationMessageKind.TOOL_RESULT:
        return message.error_summary or "Tool result"
    return ""


def file_stem(file_name: str | None) -> str:
    return Path(file_name).stem if file_name else ""


def is_blank_thread_title(value: str | None) -> bool:
    return not value or not value.strip()


def sanitize_thread_title(raw: str) -> str | None:
    title = re.sub(r"\s+", " ", raw).strip().lstrip("#-*• ").strip()
    for prefix in ("Title:", "title:", "标题：", "标题:"):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    title = title.strip("\"'`“”‘’").rstrip(".。!！?？").strip()
    return (title[:THREAD_TITLE_MAX_LENGTH].rstrip() or None) if title else None


def _final_messages(snapshot: ConversationSnapshot) -> list[ConversationMessageRow]:
    return [
        message
        for message in snapshot.messages
        if message.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
    ]


def is_initial_title_eligible(snapshot: ConversationSnapshot) -> bool:
    """Whether an append may establish this Thread's initial title."""

    return is_blank_thread_title(snapshot.thread.title) and not _final_messages(snapshot)


def is_initial_title_target(snapshot: ConversationSnapshot, first_user_message_id: str) -> bool:
    final_messages = _final_messages(snapshot)
    return (
        is_blank_thread_title(snapshot.thread.title)
        and len(final_messages) == 1
        and final_messages[0].id == first_user_message_id
        and final_messages[0].kind is ConversationMessageKind.USER
    )


def initial_thread_title_prompt(snapshot: ConversationSnapshot) -> str:
    first_message = next(
        (
            message
            for message in snapshot.messages
            if message.kind is ConversationMessageKind.USER
        ),
        None,
    )
    content = (
        blocks_to_markdown(blocks_from_payload(first_message.content_payload))
        if first_message is not None
        else ""
    )
    return "Create a short title for this first user message.\n\nMessage:\n" + content


def thread_title_snapshot_prompt(snapshot: ConversationSnapshot) -> str:
    messages = [
        {
            "kind": message.kind.value,
            "text": thread_title_message_text(message),
        }
        for message in snapshot.messages
        if message.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
    ]
    payload = {
        "thread_id": snapshot.thread.id,
        "current_title": snapshot.thread.title,
        "messages": messages,
    }
    return (
        "Create a short title for this full conversation thread. "
        "Use all persisted messages in the JSON payload.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def fallback_initial_thread_title(snapshot: ConversationSnapshot) -> str:
    first_message = next(
        (
            message
            for message in snapshot.messages
            if message.kind is ConversationMessageKind.USER
        ),
        None,
    )
    if first_message is None:
        return "New analysis"
    for block in blocks_from_payload(first_message.content_payload):
        if isinstance(block, (TextBlock, MarkdownBlock)):
            title = sanitize_thread_title(block.text)
        elif isinstance(block, DatasetBlock):
            title = sanitize_thread_title(block.name)
        elif isinstance(block, SourceAttachmentBlock):
            title = sanitize_thread_title(file_stem(block.file_name))
        else:
            title = None
        if title is not None:
            return title
    return "New analysis"


__all__ = [
    "THREAD_TITLE_MAX_LENGTH",
    "THREAD_TITLE_SYSTEM_PROMPT",
    "assistant_response_text",
    "fallback_initial_thread_title",
    "initial_thread_title_prompt",
    "is_blank_thread_title",
    "is_initial_title_eligible",
    "is_initial_title_target",
    "sanitize_thread_title",
    "thread_title_snapshot_prompt",
]