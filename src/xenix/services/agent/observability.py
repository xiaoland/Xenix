from __future__ import annotations

import json
from collections import Counter
from typing import Any

from ...observability import stable_hash
from ..storage.models import AgentProviderRequestRow, AgentToolCallRow
from ..llm import AgentToolSpec, ProviderMessage, ProviderResponse, ProviderToolCall

AI_OPERATION_CHAT = "chat"
AI_OPERATION_EXECUTE_TOOL = "execute_tool"
AI_WORKFLOW_NAME = "xenix.agent_harness"


def turn_span_attributes(*, thread_id: str, turn_id: str, run_id: str) -> dict[str, Any]:
    return {
        "openinference.span.kind": "AGENT",
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.workflow.name": AI_WORKFLOW_NAME,
        "xenix.ai.thread.id_hash": stable_hash(thread_id),
        "xenix.ai.turn.id_hash": stable_hash(turn_id),
        "xenix.ai.run.id_hash": stable_hash(run_id),
    }


def provider_request_span_attributes(
    provider_request: AgentProviderRequestRow,
    *,
    provider_messages: list[ProviderMessage],
    tool_specs: list[AgentToolSpec],
    loop_step_index: int,
    stream: bool,
) -> dict[str, Any]:
    attributes = _provider_base_attributes(provider_request)
    attributes.update(_request_shape_attributes(provider_messages))
    attributes.update(_tool_exposure_attributes(tool_specs))
    attributes.update(
        {
            "openinference.span.kind": "LLM",
            "gen_ai.operation.name": AI_OPERATION_CHAT,
            "gen_ai.request.stream": stream,
            "xenix.ai.loop.step_index": loop_step_index,
            "xenix.ai.provider_request.id_hash": stable_hash(provider_request.id),
        }
    )
    return attributes


def provider_response_shape_attributes(provider_response: ProviderResponse) -> dict[str, Any]:
    assistant_text_present = any(
        isinstance(block, dict)
        and isinstance(block.get("text"), str)
        and bool(block["text"].strip())
        for block in provider_response.assistant_content_blocks
    )
    tool_call_count = len(provider_response.tool_calls)
    assistant_block_count = len(provider_response.assistant_content_blocks)
    return {
        "xenix.ai.response.assistant_text_present": assistant_text_present,
        "xenix.ai.response.assistant_block_count": assistant_block_count,
        "xenix.ai.response.tool_call_count": tool_call_count,
        "xenix.ai.response.empty": not assistant_text_present and tool_call_count == 0,
    }


def provider_usage_attributes(provider_request: AgentProviderRequestRow) -> dict[str, Any]:
    return provider_usage_payload_attributes(provider_request, provider_request.usage_payload)


def provider_usage_payload_attributes(
    provider_request: AgentProviderRequestRow,
    usage_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    attributes = _provider_base_attributes(provider_request)
    usage_present = isinstance(usage_payload, dict)
    attributes["xenix.ai.usage.present"] = usage_present
    if not usage_present:
        return attributes

    input_tokens = _usage_int(usage_payload, "input_tokens")
    cached_input_tokens = _usage_int(usage_payload, "cached_input_tokens")
    output_tokens = _usage_int(usage_payload, "output_tokens")
    total_tokens = _usage_int(usage_payload, "total_tokens")
    attributes.update(
        {
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.cache_read.input_tokens": cached_input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "llm.token_count.prompt": input_tokens,
            "llm.token_count.prompt_details.cache_read": cached_input_tokens,
            "llm.token_count.completion": output_tokens,
            "llm.token_count.total": total_tokens or input_tokens + output_tokens,
        }
    )
    return attributes


def provider_metric_attributes(provider_request: AgentProviderRequestRow) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": AI_OPERATION_CHAT,
        "gen_ai.provider.name": provider_request.provider_name or "unknown",
        "llm.provider": provider_request.provider_name or "unknown",
        "agent.provider.name": provider_request.provider_name or "unknown",
        "agent.provider_request.kind": provider_request.request_kind.value,
        "xenix.ai.request.kind": provider_request.request_kind.value,
        "xenix.ai.usage.present": isinstance(provider_request.usage_payload, dict),
    }
    if provider_request.model:
        attributes["agent.model.hash"] = stable_hash(provider_request.model)
        attributes["xenix.ai.model.hash"] = stable_hash(provider_request.model)
    return attributes


def token_metric_measurements(provider_request: AgentProviderRequestRow) -> list[tuple[str, int, dict[str, Any]]]:
    usage_payload = provider_request.usage_payload
    if not isinstance(usage_payload, dict):
        return []

    base = provider_metric_attributes(provider_request)
    measurements: list[tuple[str, int, dict[str, Any]]] = []
    input_tokens = _usage_int(usage_payload, "input_tokens")
    output_tokens = _usage_int(usage_payload, "output_tokens")
    if input_tokens > 0:
        measurements.append(("input", input_tokens, {**base, "gen_ai.token.type": "input"}))
    if output_tokens > 0:
        measurements.append(("output", output_tokens, {**base, "gen_ai.token.type": "output"}))
    return measurements


def tool_call_span_attributes(
    tool_call: AgentToolCallRow,
    *,
    provider_request: AgentProviderRequestRow | None = None,
    loop_step_index: int | None = None,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "openinference.span.kind": "TOOL",
        "gen_ai.operation.name": AI_OPERATION_EXECUTE_TOOL,
        "gen_ai.tool.name": tool_call.tool_name,
        "gen_ai.tool.type": "function",
        "agent.tool.name": tool_call.tool_name,
        "xenix.ai.tool.category": tool_category(tool_call.tool_name),
        "xenix.ai.tool_call.id_hash": stable_hash(tool_call.id),
    }
    if provider_request is not None:
        attributes.update(
            {
                "xenix.ai.provider_request.id_hash": stable_hash(provider_request.id),
                "xenix.ai.turn.id_hash": stable_hash(provider_request.turn_id),
            }
        )
    if loop_step_index is not None:
        attributes["xenix.ai.loop.step_index"] = loop_step_index
    return attributes


def tool_call_metric_attributes(tool_call: AgentToolCallRow) -> dict[str, Any]:
    return {
        "agent.tool.name": tool_call.tool_name,
        "gen_ai.operation.name": AI_OPERATION_EXECUTE_TOOL,
        "gen_ai.tool.name": tool_call.tool_name,
        "gen_ai.tool.type": "function",
        "xenix.ai.tool.category": tool_category(tool_call.tool_name),
    }


def invalid_tool_call_attributes(
    tool_calls: list[ProviderToolCall],
    available_tool_names: set[str],
) -> dict[str, Any]:
    invalid_names = [
        tool_call.tool_name
        for tool_call in tool_calls
        if tool_call.tool_name not in available_tool_names
    ]
    if not invalid_names:
        return {}
    return {
        "xenix.ai.failure.category": "invalid_tool_call",
        "xenix.ai.invalid_tool_call.count": len(invalid_names),
        "xenix.ai.invalid_tool_call.first_name_hash": stable_hash(invalid_names[0]),
    }


def streaming_timing_attributes(
    *,
    first_event_ms: float | None,
    first_text_ms: float | None,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    if first_event_ms is not None:
        seconds = max(0.0, first_event_ms / 1000)
        attributes["gen_ai.response.time_to_first_chunk"] = seconds
        attributes["xenix.ai.stream.time_to_first_event_ms"] = max(0.0, first_event_ms)
    if first_text_ms is not None:
        attributes["xenix.ai.stream.time_to_first_text_ms"] = max(0.0, first_text_ms)
    return attributes


def _provider_base_attributes(provider_request: AgentProviderRequestRow) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": AI_OPERATION_CHAT,
        "gen_ai.provider.name": provider_request.provider_name or "unknown",
        "llm.provider": provider_request.provider_name or "unknown",
        "agent.provider.name": provider_request.provider_name or "unknown",
        "agent.provider_request.kind": provider_request.request_kind.value,
        "xenix.ai.request.kind": provider_request.request_kind.value,
        "xenix.ai.turn.id_hash": stable_hash(provider_request.turn_id),
    }
    if provider_request.run_id:
        attributes["xenix.ai.run.id_hash"] = stable_hash(provider_request.run_id)
    if provider_request.model:
        attributes["agent.model.hash"] = stable_hash(provider_request.model)
        attributes["xenix.ai.model.hash"] = stable_hash(provider_request.model)
    return attributes


def _request_shape_attributes(provider_messages: list[ProviderMessage]) -> dict[str, Any]:
    role_counts = Counter(message.role for message in provider_messages)
    return {
        "xenix.ai.request.message_count": len(provider_messages),
        "xenix.ai.request.message.system_count": role_counts.get("system", 0),
        "xenix.ai.request.message.user_count": role_counts.get("user", 0),
        "xenix.ai.request.message.assistant_count": role_counts.get("assistant", 0),
        "xenix.ai.request.message.tool_count": role_counts.get("tool", 0),
        "xenix.ai.request.system_present": role_counts.get("system", 0) > 0,
        "xenix.ai.request.tool_result_present": role_counts.get("tool", 0) > 0,
    }


def _tool_exposure_attributes(tool_specs: list[AgentToolSpec]) -> dict[str, Any]:
    category_counts = Counter(tool_category(spec.name) for spec in tool_specs)
    schema_bytes = sum(
        len(json.dumps(spec.parameters_schema, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
        for spec in tool_specs
    )
    return {
        "xenix.ai.tools.exposed.count": len(tool_specs),
        "xenix.ai.tools.exposed.data_count": category_counts.get("data", 0),
        "xenix.ai.tools.exposed.analysis_count": category_counts.get("analysis", 0),
        "xenix.ai.tools.exposed.model_count": category_counts.get("model", 0),
        "xenix.ai.tools.schema_bytes_bucket": _size_bucket(schema_bytes),
    }


def tool_category(tool_name: str) -> str:
    return tool_name.split(".", 1)[0] if "." in tool_name else "custom"


def _size_bucket(size: int) -> str:
    if size <= 0:
        return "0"
    for upper in (512, 2048, 8192, 32768, 131072):
        if size <= upper:
            return f"le_{upper}"
    return "gt_131072"


def _usage_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    return 0
