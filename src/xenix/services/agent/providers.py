from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib import request

from sqlmodel import Field, SQLModel

from ...exceptions import ValidationError
from ..storage.models import AgentMessageKind, AgentMessageRow


class AgentToolSpec(SQLModel):
    name: str
    provider_name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ProviderToolCall(SQLModel):
    provider_call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(SQLModel):
    assistant_content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ProviderToolCall] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AgentProvider(Protocol):
    def complete(
        self,
        messages: list[AgentMessageRow],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        ...


class ScriptedAgentProvider:
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = list(responses)

    def complete(
        self,
        messages: list[AgentMessageRow],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        if not self._responses:
            raise ValidationError("Scripted provider has no responses left.")
        return self._responses.pop(0)


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self._base_url = (base_url or os.getenv("XENIX_LLM_BASE_URL") or "https://api.openai.com").rstrip("/")
        self._api_key = api_key or os.getenv("XENIX_LLM_API_KEY")
        self._model = model or os.getenv("XENIX_LLM_MODEL") or "gpt-4o-mini"
        self._timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: list[AgentMessageRow],
        tools: list[AgentToolSpec],
    ) -> ProviderResponse:
        if not self._api_key:
            raise ValidationError("XENIX_LLM_API_KEY is required for the OpenAI-compatible provider.")

        tool_by_provider_name = {tool.provider_name: tool for tool in tools}
        payload = {
            "model": self._model,
            "messages": self._build_messages(messages),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.provider_name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema,
                    },
                }
                for tool in tools
            ],
            "tool_choice": "auto",
        }
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
        with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))

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
                    arguments=arguments,
                )
            )
        return ProviderResponse(
            assistant_content_blocks=content_blocks,
            tool_calls=tool_calls,
            raw_payload=raw,
        )

    def _build_messages(self, rows: list[AgentMessageRow]) -> list[dict[str, Any]]:
        provider_messages: list[dict[str, Any]] = []
        for row in rows:
            text = self._content_blocks_to_text(row.content_blocks)
            if row.kind is AgentMessageKind.SYSTEM:
                provider_messages.append({"role": "system", "content": text})
            elif row.kind is AgentMessageKind.USER:
                provider_messages.append({"role": "user", "content": text})
            elif row.kind is AgentMessageKind.ASSISTANT:
                provider_messages.append({"role": "assistant", "content": text})
            elif row.kind is AgentMessageKind.TOOL_CALL_RESULT:
                provider_messages.append({"role": "tool", "content": text, "tool_call_id": row.provider_payload.get("tool_call_id", "")})
        return provider_messages

    def _content_blocks_to_text(self, blocks: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"text", "markdown"}:
                lines.append(str(block.get("text", "")))
            elif block_type == "file":
                lines.append(f"Attached file: {block.get('path')}")
            else:
                lines.append(json.dumps(block, ensure_ascii=False))
        return "\n".join(line for line in lines if line)

