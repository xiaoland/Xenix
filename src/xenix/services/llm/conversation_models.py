"""Conversation data models shared by the LLM conversation boundary.

These typed values cross the Conversation boundary: inputs, snapshots,
submission claims, live events, and the process-local control/exchange types.
They are independent of the service so ``LLMConversationService`` can stay a
narrow canonical writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError
from ...observability import LLMUsageAggregate
from ..storage.models import ConversationMessageRow, ConversationThreadRow
from .messages import (
    CanonicalMessageBlock,
    ProviderOutputItem,
    normalize_message_blocks,
)
from .providers import LLMRetryEvent
from .tooling import StagedToolCall, TerminalToolResult, ToolScope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateConversationThreadInput(SQLModel):
    title: str | None = None
    system_prompt: str | None = None
    interface_locale: str | None = None
    selected_fq_model_key: str | None = None


class AppendUserMessageInput(SQLModel):
    thread_id: str
    client_submission_id: str
    content_blocks: list[CanonicalMessageBlock] = Field(default_factory=list)

    @field_validator("content_blocks", mode="before")
    @classmethod
    def _parse_content_blocks(cls, value: Any) -> list[CanonicalMessageBlock]:
        return list(normalize_message_blocks(value))


class ConversationSnapshot(SQLModel):
    thread: ConversationThreadRow
    messages: list[ConversationMessageRow] = Field(default_factory=list)


@dataclass(frozen=True)
class ConversationUsageOverview:
    """A read-only usage projection for one completed User interaction."""

    root_user_message_id: str
    terminal_llm_message_id: str
    terminal_sequence_index: int
    usage: LLMUsageAggregate


@dataclass(frozen=True)
class SubmissionClaim:
    thread_id: str
    expected_frontier_id: str | None
    client_submission_id: str
    initial_title_eligible: bool = False
    existing_message_id: str | None = None


@dataclass(frozen=True)
class PendingSampling:
    pending_message_id: str
    thread_id: str
    staged_calls: tuple[StagedToolCall, ...] = ()
    has_assistant_output: bool = False


@dataclass(frozen=True)
class ConversationLiveEvent:
    kind: str
    pending_message_id: str
    retry: LLMRetryEvent | None = None
    staged_call_id: str | None = None


class ThreadPausedError(ValidationError):
    """A runtime-only Thread pause prevented a new LLM provider request."""

    def __init__(self, thread_id: str) -> None:
        super().__init__(
            f"LLM sampling is paused for Thread '{thread_id}'.",
            error_code="llm_thread_paused",
        )


@dataclass
class _ThreadControl:
    """Process-local pause state; never persisted as Conversation state."""

    paused: bool = False


@dataclass
class _PendingExchange:
    pending_message_id: str
    thread_id: str
    sequence_index: int
    frontier_message_id: str
    root_user_message_id: str | None
    scope: ToolScope
    scope_fingerprint: str
    output_items: tuple[ProviderOutputItem, ...] = ()
    calls: dict[str, StagedToolCall] = field(default_factory=dict)
    results: dict[str, TerminalToolResult] = field(default_factory=dict)
    tool_execution_started: bool = False
    cancelled: bool = False


__all__ = [
    "AppendUserMessageInput",
    "ConversationLiveEvent",
    "ConversationSnapshot",
    "ConversationUsageOverview",
    "CreateConversationThreadInput",
    "PendingSampling",
    "SubmissionClaim",
    "ThreadPausedError",
    "_PendingExchange",
    "_ThreadControl",
    "_utc_now",
]
