from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib import error, request

from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError


def _dict_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return default


class AgentToolSpec(SQLModel):
    name: str
    provider_name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ProviderMessage(SQLModel):
    role: str
    content: str
    content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    source_message_id: str | None = None


class ProviderToolCall(SQLModel):
    provider_call_id: str
    tool_name: str
    provider_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(SQLModel):
    assistant_content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ProviderToolCall] = Field(default_factory=list)
    usage_payload: dict[str, Any] | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ProviderStreamEvent:
    delta_text: str = ""
    response: ProviderResponse | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_delta(self) -> bool:
        return bool(self.delta_text)

    @property
    def is_complete(self) -> bool:
        return self.response is not None


class AgentProvider(Protocol):
    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        ...


class ScriptedAgentProvider:
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = list(responses)

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        if not self._responses:
            raise ValidationError("Scripted provider has no responses left.")
        return self._responses.pop(0)


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        provider_key: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 120,
        streaming_enabled: bool = True,
    ) -> None:
        self._provider_key = (provider_key or "openai").strip() or "openai"
        self._base_url = (base_url or "https://api.openai.com").rstrip("/")
        self._api_key = api_key or ""
        self._model = model or "gpt-4o-mini"
        self._timeout_seconds = timeout_seconds
        self._streaming_enabled = streaming_enabled

    @property
    def provider_key(self) -> str:
        return self._provider_key

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        if not self._api_key:
            raise ValidationError("LLM API key is required for the OpenAI-compatible provider.")

        payload = self._build_payload(messages, tools, stream=False)
        raw = self._post_json(payload)
        return self._parse_chat_completion(raw, tools)

    def stream(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
    ):
        if not self._streaming_enabled:
            yield ProviderStreamEvent(response=self.complete(messages, tools))
            return
        if not self._api_key:
            raise ValidationError("LLM API key is required for the OpenAI-compatible provider.")

        payload = self._build_payload(messages, tools, stream=True)
        text_parts: list[str] = []
        raw_chunks: list[dict[str, Any]] = []
        tool_call_accumulator: dict[int, dict[str, Any]] = {}
        usage_payload: dict[str, Any] | None = None
        for chunk in self._post_stream(payload):
            raw_chunks.append(chunk)
            chunk_usage = self._normalize_usage_payload(chunk.get("usage"))
            if chunk_usage is not None:
                usage_payload = chunk_usage
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    text_parts.append(content)
                    yield ProviderStreamEvent(delta_text=content, raw_payload=chunk)
                self._accumulate_tool_call_deltas(tool_call_accumulator, delta.get("tool_calls") or [])

        text = "".join(text_parts)
        tool_calls = self._build_tool_calls(tool_call_accumulator, tools)
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": text}] if text else [],
                tool_calls=tool_calls,
                usage_payload=usage_payload,
                raw_payload={"chunks": raw_chunks},
            )
        )

    def _build_payload(
        self,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        payload = {
            "model": self._model,
            "messages": self._build_messages(messages),
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.provider_name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema,
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        if stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self._base_url}/v1/chat/completions"
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise ValidationError(self._format_http_error(endpoint, exc)) from exc

    def _post_stream(self, payload: dict[str, Any]):
        endpoint = f"{self._base_url}/v1/chat/completions"
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    yield json.loads(data)
        except error.HTTPError as exc:
            raise ValidationError(self._format_http_error(endpoint, exc)) from exc

    def _format_http_error(self, endpoint: str, exc: error.HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="replace")
        provider_message = self._extract_provider_error_message(body)
        detail = f": {provider_message}" if provider_message else ""
        return f"LLM provider request failed with HTTP {exc.code} at {endpoint}{detail}."

    def _extract_provider_error_message(self, body: str) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body.strip()
        provider_error = payload.get("error")
        if isinstance(provider_error, dict):
            message = provider_error.get("message")
            code = provider_error.get("code")
            if message and code:
                return f"{message} ({code})"
            if message:
                return str(message)
        return body.strip()

    def _parse_chat_completion(self, raw: dict[str, Any], tools: list[AgentToolSpec]) -> ProviderResponse:
        tool_by_provider_name = {tool.provider_name: tool for tool in tools}
        choice = raw.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content")
        content_blocks = [{"type": "markdown", "text": content}] if isinstance(content, str) and content else []
        tool_calls: list[ProviderToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            provider_name = function.get("name")
            spec = tool_by_provider_name.get(provider_name)
            if spec is None:
                continue
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Tool call '{spec.name}' arguments are not valid JSON.") from exc
            tool_calls.append(
                ProviderToolCall(
                    provider_call_id=str(call.get("id") or ""),
                    tool_name=spec.name,
                    provider_name=str(provider_name or ""),
                    arguments=arguments,
                )
            )
        return ProviderResponse(
            assistant_content_blocks=content_blocks,
            tool_calls=tool_calls,
            usage_payload=self._normalize_usage_payload(raw.get("usage")),
            raw_payload=raw,
        )

    def _normalize_usage_payload(self, raw_usage: Any) -> dict[str, Any] | None:
        if not isinstance(raw_usage, dict):
            return None

        input_tokens = self._int_or_none(
            raw_usage.get("prompt_tokens", raw_usage.get("input_tokens"))
        )
        output_tokens = self._int_or_none(
            raw_usage.get("completion_tokens", raw_usage.get("output_tokens"))
        )
        total_tokens = self._int_or_none(raw_usage.get("total_tokens"))
        prompt_details = raw_usage.get("prompt_tokens_details")
        input_details = raw_usage.get("input_tokens_details")
        cached_input_tokens = self._int_or_none(
            _dict_get(prompt_details, "cached_tokens", _dict_get(input_details, "cached_tokens"))
        )

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        if all(value is None for value in (input_tokens, output_tokens, total_tokens, cached_input_tokens)):
            return {"provider_usage": dict(raw_usage)}

        return {
            "input_tokens": input_tokens or 0,
            "cached_input_tokens": cached_input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "total_tokens": total_tokens or 0,
            "provider_usage": dict(raw_usage),
        }

    def _int_or_none(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    def _accumulate_tool_call_deltas(
        self,
        accumulator: dict[int, dict[str, Any]],
        tool_call_deltas: list[dict[str, Any]],
    ) -> None:
        for delta in tool_call_deltas:
            index = int(delta.get("index") or 0)
            current = accumulator.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if delta.get("id"):
                current["id"] = str(delta["id"])
            function = delta.get("function") or {}
            if function.get("name"):
                current["name"] += str(function["name"])
            if function.get("arguments"):
                current["arguments"] += str(function["arguments"])

    def _build_tool_calls(
        self,
        accumulator: dict[int, dict[str, Any]],
        tools: list[AgentToolSpec],
    ) -> list[ProviderToolCall]:
        tool_by_provider_name = {tool.provider_name: tool for tool in tools}
        tool_calls: list[ProviderToolCall] = []
        for index in sorted(accumulator):
            current = accumulator[index]
            spec = tool_by_provider_name.get(current["name"])
            if spec is None:
                continue
            try:
                arguments = json.loads(current["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Tool call '{spec.name}' arguments are not valid JSON.") from exc
            tool_calls.append(
                ProviderToolCall(
                    provider_call_id=current["id"],
                    tool_name=spec.name,
                    provider_name=current["name"],
                    arguments=arguments,
                )
            )
        return tool_calls

    def _build_messages(self, rows: list[ProviderMessage]) -> list[dict[str, Any]]:
        provider_messages: list[dict[str, Any]] = []
        for row in rows:
            message = {"role": row.role, "content": row.content}
            if row.role == "assistant":
                tool_calls = row.provider_payload.get("tool_calls")
                if isinstance(tool_calls, list) and tool_calls:
                    message["tool_calls"] = tool_calls
            if row.role == "tool":
                message["tool_call_id"] = row.provider_payload.get("tool_call_id", "")
            provider_messages.append(message)
        return provider_messages
