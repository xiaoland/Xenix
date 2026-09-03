"""Pure chatbot presentation and composer-state boundaries.

These functions project canonical Chatbot events into display data (HTML-ready
text, visible blocks, translated labels) without constructing or touching Qt
widgets.  Display blocks are typed pydantic models instead of raw ``dict`` so the
presentation boundary has explicit field access; upstream JSON is coerced here
once, then the rest of the Chatbot UI works with ``ChatbotBlock`` values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field
from PySide6.QtCore import QCoreApplication

from ...services.agent import ChatbotEvent, ChatbotEventAuthor, ChatbotEventKind

ArtifactResolver = Callable[[str], Any]
SourceAttachmentTargetResolver = Callable[["ChatbotBlock"], str | None]

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


class UsagePayload(BaseModel):
    """Typed token-usage payload rendered by ``UsageOverviewItem``.

    The upstream event may carry additional fields; ``extra="allow"`` keeps them
    while giving the three values Xenix renders a typed, defaulted shape.
    """

    model_config = ConfigDict(extra="allow")

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


class RetryEvent(BaseModel):
    """One LLM connection retry event carried in a connection detail block."""

    model_config = ConfigDict(extra="allow")

    attempt_number: int | None = None
    max_attempts: int | None = None
    error_code: str = ""
    error_summary: str = ""


class ChatbotBlock(BaseModel):
    """A typed display block consumed by the Chatbot timeline/composer.

    ``extra="allow"`` tolerates the historical, heterogeneous block payload
    while giving the fields Xenix renders an explicit, typed shape.  It is a
    presentation value only; local paths are allowed here because they never
    cross the provider boundary.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    text: str = ""
    message: str = ""
    path: str = ""
    file_name: str = ""
    file_path: str = ""
    artifact_id: str = ""
    dataset_id: str = ""
    is_openable: bool = False
    chatbot_source_projection: bool = False
    chatbot_visible: bool | None = None
    visible: bool | None = None
    tool_name: str = ""
    status: str = ""
    error_summary: str = ""
    source_group_id: str = ""
    retry_events: list[RetryEvent] = Field(default_factory=list)


def coerce_blocks(values: Iterable[Any]) -> list[ChatbotBlock]:
    """Convert upstream JSON/dict blocks into typed ``ChatbotBlock`` values."""

    return [
        block if isinstance(block, ChatbotBlock) else ChatbotBlock.model_validate(block)
        for block in values
        if isinstance(block, (Mapping, ChatbotBlock))
    ]


def render_content_blocks(
    blocks: list[ChatbotBlock],
    *,
    source_attachment_target_resolver: SourceAttachmentTargetResolver | None = None,
) -> str:
    parts: list[str] = []
    for block in blocks:
        block_type = block.type
        if block_type in {"text", "markdown"}:
            parts.append(block.text)
        elif block_type == "ui_error":
            message = block.message
            parts.append(
                QCoreApplication.translate("ThreadDetailView", "Error: {message}").format(
                    message=message
                )
            )
        elif block_type == "file":
            file_path = Path(block.path)
            parts.append(f"`{file_path.name}`")
        elif block_type == "source_attachment":
            if not chatbot_block_is_visible(block):
                continue
            file_name = block.file_name.strip()
            if block.chatbot_source_projection:
                if not file_name:
                    continue
                target = None
                if block.is_openable and source_attachment_target_resolver is not None:
                    try:
                        target = source_attachment_target_resolver(block)
                    except Exception:
                        target = None
                target = safe_ui_open_target(target)
                if target:
                    parts.append(f"[{escape_markdown_link_label(file_name)}]({target})")
                else:
                    parts.append(f"`{file_name}`")
                continue
            artifact_id = block.artifact_id.strip()
            if artifact_id and file_name:
                parts.append(f"[{escape_markdown_link_label(file_name)}](artifact://{artifact_id})")
            elif file_name:
                parts.append(f"`{file_name}`")
        elif block_type == "dataset":
            # Canonical DatasetBlocks are provider/context facts, not raw
            # Chatbot attachments.  Harness enrichment supplies a separate
            # UI-only source_attachment block when one can be resolved.
            continue
        elif block_type == "step_confirmation":
            parts.append(block.text)
        elif block_type == "thinking":
            text = block.text
            if text and text != "Thinking...":
                parts.append(text)
            else:
                parts.append(QCoreApplication.translate("ThreadDetailView", "Thinking..."))
        elif block_type == "tool_event_summary":
            parts.append(translate_tool_summary(block.text))
        elif block_type == "tool_call":
            tool_name = block.tool_name or QCoreApplication.translate("ThreadDetailView", "tool")
            parts.append(
                QCoreApplication.translate("ThreadDetailView", "Calling `{tool_name}`...").format(
                    tool_name=tool_name
                )
            )
        elif block_type == "tool_call_result":
            tool_name = block.tool_name or QCoreApplication.translate("ThreadDetailView", "tool")
            status = block.status or "completed"
            error_summary = block.error_summary.strip()
            text = QCoreApplication.translate(
                "ThreadDetailView", "`{tool_name}` {status}."
            ).format(tool_name=tool_name, status=translate_tool_status(status))
            if error_summary:
                text = f"{text} {error_summary}"
            parts.append(text)
    return "\n\n".join(part for part in parts if part)


def chatbot_block_is_visible(block: ChatbotBlock) -> bool:
    """Apply the Harness/UI-only presentation hint with legacy compatibility."""

    if block.chatbot_visible is not None:
        return block.chatbot_visible
    if block.visible is not None:
        return block.visible
    return True


def assistant_display_blocks(
    blocks: list[ChatbotBlock],
    *,
    text: str | None = None,
    refusal: str | None = None,
) -> list[ChatbotBlock]:
    """Choose the Assistant content that the current product renders.

    The event projection deliberately carries reasoning and refusal fields
    unchanged.  Only this UI projection drops reasoning; a refusal is shown as
    ordinary assistant text until a dedicated refusal treatment exists.
    """

    display_blocks: list[ChatbotBlock] = []
    seen_text: set[str] = set()
    for block in blocks:
        block_type = block.type.strip().lower()
        block_text = block.text.strip()
        if block_type in {"text", "markdown"} and block_text:
            display_blocks.append(block)
            seen_text.add(block_text)
        elif block_type == "refusal" and block_text:
            display_blocks.append(ChatbotBlock(type="text", text=block_text))
            seen_text.add(block_text)

    for value in (text, refusal):
        normalized = str(value or "").strip()
        if normalized and normalized not in seen_text:
            display_blocks.append(ChatbotBlock(type="text", text=normalized))
            seen_text.add(normalized)
    return display_blocks


def event_display_blocks(event: ChatbotEvent) -> list[ChatbotBlock]:
    """Return blocks for one event without changing the event projection."""

    author = getattr(getattr(event, "author", None), "value", getattr(event, "author", None))
    kind = getattr(getattr(event, "kind", None), "value", getattr(event, "kind", None))
    blocks = [
        block
        for block in coerce_blocks(event.content_blocks)
        if block.type.strip().lower() != "dataset"
        and (block.type.strip().lower() != "source_attachment" or chatbot_block_is_visible(block))
    ]
    if str(kind) == ChatbotEventKind.TEXT.value and str(author) == ChatbotEventAuthor.ASSISTANT.value:
        return assistant_display_blocks(blocks, text=event.text, refusal=event.refusal)
    return blocks


def escape_markdown_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def safe_ui_open_target(value: Any) -> str | None:
    """Accept only opaque URI capabilities, never a local path in Markdown."""

    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(char in value for char in "\r\n"):
        return None
    lowered = value.lower()
    if lowered.startswith("file:") or value.startswith(("/", "\\")):
        return None
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return None
    return value


def translate_tool_status(status: str) -> str:
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


def translate_tool_summary(summary: str) -> str:
    if summary == "Running tool...":
        return QCoreApplication.translate("ToolCallItem", "Running tool...")
    if summary == "Ran tool":
        return QCoreApplication.translate("ToolCallItem", "Ran tool")
    if summary == "Cancelled tool run":
        return QCoreApplication.translate("ToolCallItem", "Cancelled tool run")
    if summary == "Searching knowledge...":
        return QCoreApplication.translate("ToolCallItem", "Searching knowledge...")
    if summary == "Searched knowledge":
        return QCoreApplication.translate("ToolCallItem", "Searched knowledge")
    if summary == "Failed to search knowledge":
        return QCoreApplication.translate("ToolCallItem", "Failed to search knowledge")
    if summary == "Cancelled knowledge search":
        return QCoreApplication.translate("ToolCallItem", "Cancelled knowledge search")
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


def format_token_count(value: int) -> str:
    if value <= 999:
        return str(max(0, value))
    rounded_tenths = (value + 50) // 100
    return f"{rounded_tenths / 10:.1f}k"


def usage_overview_text(payload: UsagePayload | None) -> str:
    payload = payload or UsagePayload()
    input_text = format_token_count(payload.input_tokens)
    if payload.cached_input_tokens > 0:
        input_text += QCoreApplication.translate(
            "UsageOverviewItem",
            " ({cached} cached)",
        ).format(cached=format_token_count(payload.cached_input_tokens))
    text = QCoreApplication.translate(
        "UsageOverviewItem",
        "↑ {input} · ↓ {output}",
    ).format(
        input=input_text,
        output=format_token_count(payload.output_tokens),
    )
    return text


def connection_retry_events(detail_blocks: list[ChatbotBlock]) -> list[RetryEvent]:
    for block in detail_blocks:
        if block.type != "llm_connection_retry":
            continue
        return block.retry_events
    return []


def connection_attempt_counts(detail_blocks: list[ChatbotBlock]) -> tuple[int, int]:
    retry_events = connection_retry_events(detail_blocks)
    last_event = retry_events[-1] if retry_events else RetryEvent()
    attempt_number = last_event.attempt_number or 1
    max_attempts = last_event.max_attempts or attempt_number
    return attempt_number, max_attempts


__all__ = [
    "ArtifactResolver",
    "SourceAttachmentTargetResolver",
    "SUPPORTED_DATASET_SUFFIXES",
    "ComposerAttachmentStatus",
    "ComposerAttachmentState",
    "UsagePayload",
    "RetryEvent",
    "ChatbotBlock",
    "coerce_blocks",
    "render_content_blocks",
    "chatbot_block_is_visible",
    "assistant_display_blocks",
    "event_display_blocks",
    "escape_markdown_link_label",
    "safe_ui_open_target",
    "translate_tool_status",
    "translate_tool_summary",
    "format_token_count",
    "usage_overview_text",
    "connection_retry_events",
    "connection_attempt_counts",
]
