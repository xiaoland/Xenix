"""Usage attribution and completed-interaction projection for canonical conversations."""

from __future__ import annotations

import logging

from ...exceptions import report_exception
from ...observability import LLMUsageObservability
from ..storage.models import ConversationMessageKind, ConversationMessageRow
from .conversation_models import ConversationSnapshot, ConversationUsageOverview

LOGGER = logging.getLogger(__name__)


def primary_usage_root(messages: list[ConversationMessageRow]) -> int | None:
    if not messages:
        return None
    frontier = messages[-1]
    if frontier.kind is ConversationMessageKind.USER:
        return frontier.id
    if frontier.kind is not ConversationMessageKind.TOOL_RESULT:
        return None
    for row in reversed(messages[:-1]):
        if row.kind is ConversationMessageKind.USER:
            return row.id
    return None


def completed_user_interactions(
    messages: list[ConversationMessageRow],
) -> list[tuple[ConversationMessageRow, ConversationMessageRow]]:
    """Find terminal LLM emissions without inventing a durable Turn."""

    rows = sorted(
        (
            row
            for row in messages
            if row.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING
        ),
        key=lambda row: row.sequence_index,
    )
    completed: list[tuple[ConversationMessageRow, ConversationMessageRow]] = []
    active_user: ConversationMessageRow | None = None
    index = 0
    llm_kinds = {ConversationMessageKind.ASSISTANT, ConversationMessageKind.TOOL_CALL}
    while index < len(rows):
        row = rows[index]
        if row.kind is ConversationMessageKind.USER:
            active_user = row
            index += 1
            continue
        if row.kind not in llm_kinds:
            index += 1
            continue
        emission: list[ConversationMessageRow] = []
        while index < len(rows) and rows[index].kind in llm_kinds:
            emission.append(rows[index])
            index += 1
        has_tool_calls = any(item.kind is ConversationMessageKind.TOOL_CALL for item in emission)
        terminal = next(
            (item for item in reversed(emission) if item.kind is ConversationMessageKind.ASSISTANT),
            None,
        )
        if active_user is not None and not has_tool_calls and terminal is not None:
            completed.append((active_user, terminal))
            active_user = None
    return completed


def query_usage_overviews(
    snapshot: ConversationSnapshot,
    usage_observability: LLMUsageObservability,
) -> tuple[ConversationUsageOverview, ...]:
    """Read safe token totals for completed User-to-LLM interactions.

    Canonical Messages determine which interactions are complete.  The
    injected observability reader contributes only independently-recorded
    token facts; missing or failing telemetry never changes the snapshot
    or any Conversation command.
    """

    completed = completed_user_interactions(snapshot.messages)
    if not completed:
        return ()
    try:
        aggregates = usage_observability.query_primary_usage(
            thread_id=snapshot.thread.id,
            root_user_message_ids=[root.id for root, _terminal in completed],
        )
    except Exception as exc:
        report_exception(exc)
        LOGGER.warning("LLM usage observability query failed: %s", exc.__class__.__name__)
        return ()
    return tuple(
        ConversationUsageOverview(
            root_user_message_id=root.id,
            terminal_llm_message_id=terminal.id,
            terminal_sequence_index=terminal.sequence_index,
            usage=aggregate,
        )
        for root, terminal in completed
        if (aggregate := aggregates.get(root.id)) is not None and aggregate.request_count > 0
    )
