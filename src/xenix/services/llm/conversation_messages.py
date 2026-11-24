"""Message row construction, provider history projection, and frontier validation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ...exceptions import ValidationError
from ..storage.models import (
    ConversationMessageKind,
    ConversationMessageRow,
    ConversationToolResultStatus,
)
from .conversation_models import ConversationSnapshot, _PendingExchange, _utc_now
from .messages import AssistantOutputItem, blocks_from_payload
from .providers import ProviderMessage
from .tool_protocol import (
    MAX_EXCHANGE_RESULT_BYTES,
    InvalidToolArguments,
    canonical_json_bytes,
    canonical_tool_result_value,
)
from .tool_registry import AgentToolRegistry


def build_final_message_rows(
    exchange: _PendingExchange,
    sequence: int,
) -> list[ConversationMessageRow]:
    rows: list[ConversationMessageRow] = []
    for item in exchange.output_items:
        if isinstance(item, AssistantOutputItem):
            rows.append(
                ConversationMessageRow(
                    thread_id=exchange.thread_id,
                    sequence_index=sequence,
                    kind=ConversationMessageKind.ASSISTANT,
                    text=item.text,
                    reasoning=item.reasoning,
                    refusal=item.refusal,
                    created_at=_utc_now(),
                )
            )
            sequence += 1
    for call in exchange.calls.values():
        # Preserve undecodable arguments verbatim for history and replay;
        # they must never appear to be a successfully decoded empty object.
        content_payload = {"tool_name": call.tool_name, "provider_name": call.provider_name}
        if isinstance(call.arguments, InvalidToolArguments):
            content_payload["raw_arguments"] = call.arguments.raw_text
            arguments_payload = None
        else:
            arguments_payload = dict(call.arguments)
        rows.append(
            ConversationMessageRow(
                id=call.staged_call_id,
                thread_id=exchange.thread_id,
                sequence_index=sequence,
                kind=ConversationMessageKind.TOOL_CALL,
                # ``tool_name`` is canonical registry identity; the
                # provider-facing name is adapter pairing data needed for
                # faithful replay and belongs in this immutable payload.
                content_payload=content_payload,
                provider_call_id=call.provider_call_id,
                tool_id=call.tool_name,
                contract_version="v1",
                arguments_payload=arguments_payload,
                scope_fingerprint=call.scope_fingerprint,
                created_at=_utc_now(),
            )
        )
        sequence += 1
    for call in exchange.calls.values():
        result = exchange.results[call.staged_call_id]
        rows.append(
            ConversationMessageRow(
                thread_id=exchange.thread_id,
                sequence_index=sequence,
                kind=ConversationMessageKind.TOOL_RESULT,
                content_payload={"tool_name": call.tool_name},
                tool_call_message_id=call.staged_call_id,
                result_status=ConversationToolResultStatus(result.status),
                value_payload=result.value,
                # New failures are their own typed canonical value.  Keep
                # this legacy column empty rather than duplicating a
                # competing failure summary.
                error_summary=None,
                created_at=_utc_now(),
            )
        )
        sequence += 1
    if not rows:
        raise ValidationError("LLM output produced no final Message.")
    return rows


def build_provider_messages(
    snapshot: ConversationSnapshot,
    *,
    tool_registry: AgentToolRegistry,
    context_messages_provider: Callable[[ConversationSnapshot], list[ProviderMessage]] | None = None,
) -> list[ProviderMessage]:
    rows: list[ProviderMessage] = [ProviderMessage(role="system", content=snapshot.thread.system_prompt)]
    if context_messages_provider is not None:
        # Composition injects provider-neutral contextual instructions.
        # They are derived from finalized Messages only and never mutate
        # the canonical conversation or introduce a Harness dependency.
        rows.extend(context_messages_provider(snapshot))
    messages = [row for row in snapshot.messages if row.kind is not ConversationMessageKind.PENDING_LLM_SAMPLING]
    index = 0
    while index < len(messages):
        row = messages[index]
        if row.kind is ConversationMessageKind.USER:
            blocks = blocks_from_payload(row.content_payload)
            rows.append(
                ProviderMessage(
                    role="user",
                    content="",
                    content_blocks=list(blocks),
                    source_message_id=row.id,
                )
            )
        elif row.kind is ConversationMessageKind.CLIENT_CONTROL:
            blocks = blocks_from_payload(row.content_payload)
            rows.append(
                ProviderMessage(
                    role="user",
                    content="",
                    content_blocks=list(blocks),
                    source_message_id=row.id,
                )
            )
        elif row.kind is ConversationMessageKind.ASSISTANT:
            calls: list[ConversationMessageRow] = []
            index += 1
            while index < len(messages) and messages[index].kind is ConversationMessageKind.TOOL_CALL:
                calls.append(messages[index])
                index += 1
            payload: dict[str, Any] = {}
            if row.reasoning:
                payload["reasoning_content"] = row.reasoning
            if row.refusal:
                payload["refusal"] = row.refusal
            if calls:
                payload["tool_calls"] = [provider_call_payload(call, tool_registry) for call in calls]
            blocks = blocks_from_payload(row.content_payload)
            rows.append(
                ProviderMessage(
                    role="assistant",
                    content=row.text or "",
                    content_blocks=list(blocks),
                    provider_payload=payload,
                    source_message_id=row.id,
                )
            )
            continue
        elif row.kind is ConversationMessageKind.TOOL_CALL:
            calls = []
            while index < len(messages) and messages[index].kind is ConversationMessageKind.TOOL_CALL:
                calls.append(messages[index])
                index += 1
            rows.append(
                ProviderMessage(
                    role="assistant",
                    content="",
                    provider_payload={"tool_calls": [provider_call_payload(call, tool_registry) for call in calls]},
                    source_message_id=calls[0].id,
                )
            )
            continue
        elif row.kind is ConversationMessageKind.TOOL_RESULT:
            call = next((candidate for candidate in messages if candidate.id == row.tool_call_message_id), None)
            if call is not None:
                rows.append(
                    ProviderMessage(
                        role="tool",
                        tool_result_value=row_canonical_tool_result_value(row),
                        provider_payload={"tool_call_id": call.provider_call_id or ""},
                        source_message_id=row.id,
                    )
                )
        index += 1
    return rows


def provider_call_payload(call: ConversationMessageRow, tool_registry: AgentToolRegistry) -> dict[str, Any]:
    payload = call.content_payload if isinstance(call.content_payload, dict) else {}
    raw_provider_name = payload.get("provider_name")
    if isinstance(raw_provider_name, str) and raw_provider_name.strip():
        provider_name = raw_provider_name.strip()
    else:
        # v14-to-v15 rows written before the provider-name preservation
        # repair contain only the canonical registry name.  The LLM-owned
        # registry is the only compatible fallback authority; new rows
        # always persist the provider-facing name above.
        tool_name = (call.tool_id or "").strip()
        try:
            provider_name = tool_registry.get(tool_name).provider_name
        except ValidationError:
            provider_name = tool_name
    return {
        "id": call.provider_call_id or "",
        "type": "function",
        "function": {
            "name": provider_name,
            "arguments": (
                payload["raw_arguments"]
                if "raw_arguments" in payload
                else json.dumps(call.arguments_payload or {}, ensure_ascii=False, separators=(",", ":"))
            ),
        },
    }


def row_canonical_tool_result_value(result: ConversationMessageRow) -> Any:
    status = getattr(result, "result_status", None)
    failed = status is ConversationToolResultStatus.FAILED or getattr(status, "value", status) == "failed"
    return canonical_tool_result_value(
        value=result.value_payload,
        failed=failed,
        legacy_error_summary=result.error_summary,
    )


def validate_exchange_result_budget(exchange: _PendingExchange) -> None:
    total = 0
    for result in exchange.results.values():
        envelope = {
            "status": result.status,
            "value": result.value,
        }
        total += len(canonical_json_bytes(envelope))
    if total > MAX_EXCHANGE_RESULT_BYTES:
        raise ValidationError("The staged Tool Result exchange exceeds its byte limit.")


def validate_user_append_messages(
    messages: list[ConversationMessageRow],
    expected_frontier_id: int | None,
    *,
    allow_paused_frontier: bool = False,
) -> None:
    if any(row.kind is ConversationMessageKind.PENDING_LLM_SAMPLING for row in messages):
        raise ValidationError("Cannot append a User Message while LLM sampling is pending.")
    if not messages:
        if expected_frontier_id is not None:
            raise ValidationError("The requested User frontier is stale.")
        return
    tail = messages[-1]
    if expected_frontier_id is not None and tail.id != expected_frontier_id:
        raise ValidationError("The requested User frontier is stale.")
    # A paused Thread (the user pressed Stop) abandons its current frontier,
    # so a new User Message may re-enter whether the stop landed during
    # initial sampling (USER/CLIENT_CONTROL frontier) or tool-result
    # sampling (TOOL_RESULT frontier).
    if allow_paused_frontier:
        return
    if tail.kind in {
        ConversationMessageKind.USER,
        ConversationMessageKind.CLIENT_CONTROL,
        ConversationMessageKind.TOOL_RESULT,
    }:
        raise ValidationError("The existing Client frontier must be sampled before another User Message.")
