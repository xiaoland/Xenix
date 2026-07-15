"""LLM-owned tool protocol and bounded registry primitives."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Protocol

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from ...exceptions import ValidationError


MAX_TOOL_CALLS = 16
MAX_TOOL_PAYLOAD_BYTES = 64 * 1024
MAX_EXCHANGE_RESULT_BYTES = 1024 * 1024
MAX_TOOL_ERROR_SUMMARY_CHARS = 256


class AgentToolSpec(SQLModel):
    """Provider-neutral definition advertised to an LLM."""

    name: str
    provider_name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "provider_name")
    @classmethod
    def _required_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Tool name cannot be empty.")
        return normalized


@dataclass(frozen=True)
class ToolScope:
    """Provider-neutral scope selected for one sampling request."""

    tool_names: tuple[str, ...] = ()
    dataset_ids: tuple[str, ...] = ()


def scope_fingerprint(scope: ToolScope, specs: list[AgentToolSpec]) -> str:
    """Return a stable digest for the frozen advertised scope."""

    payload = {
        "tool_names": list(scope.tool_names),
        "dataset_ids": list(scope.dataset_ids),
        "definitions": [
            {
                "name": spec.name,
                "provider_name": spec.provider_name,
                "description": spec.description,
                "parameters_schema": spec.parameters_schema,
            }
            for spec in specs
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class ToolExecutionContext:
    """Bounded live context supplied to an injected implementation."""

    thread_id: str
    dataset_ids: tuple[str, ...] = ()
    cancel_requested: Callable[[], bool] = lambda: False


class AgentToolImplementation(Protocol):
    def __call__(self, arguments: dict[str, Any], context: ToolExecutionContext) -> Any:
        """Execute one already validated call and return a bounded candidate."""


@dataclass(frozen=True)
class RegisteredTool:
    spec: AgentToolSpec
    implementation: AgentToolImplementation


@dataclass(frozen=True)
class StagedToolCall:
    """Immutable in-memory call awaiting an LLM-owned invocation."""

    pending_message_id: str
    staged_call_id: str
    provider_call_id: str
    tool_name: str
    provider_name: str
    arguments: dict[str, Any]
    scope_fingerprint: str

    def __post_init__(self) -> None:
        if not self.pending_message_id.strip() or not self.staged_call_id.strip():
            raise ValidationError("Staged tool call identity cannot be empty.")
        if not self.provider_call_id.strip() or not self.tool_name.strip():
            raise ValidationError("Staged tool call provider identity cannot be empty.")
        if not self.scope_fingerprint.strip():
            raise ValidationError("Staged tool call scope fingerprint cannot be empty.")
        ensure_bounded_json(self.arguments, label=f"Tool call '{self.tool_name}' arguments")


@dataclass(frozen=True)
class TerminalToolResult:
    """Bounded terminal candidate held until the exchange commits atomically."""

    status: str
    payload: dict[str, Any] = dataclass_field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None

    def __post_init__(self) -> None:
        ensure_bounded_json(self.payload, label="Terminal tool result payload")
        if self.error_summary is not None:
            if not isinstance(self.error_summary, str) or len(self.error_summary) > MAX_TOOL_ERROR_SUMMARY_CHARS:
                raise ValidationError(
                    f"Terminal tool result error summary exceeds the {MAX_TOOL_ERROR_SUMMARY_CHARS}-character limit."
                )


class AgentToolRegistry:
    """LLM-owned registry with duplicate and payload-bound checks.

    The concrete implementation is injected by the composition root.  This
    class does not import Agent Harness or a domain service.
    """

    def __init__(
        self,
        tools: Mapping[str, RegisteredTool] | Iterable[RegisteredTool] | None = None,
    ) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._provider_names: dict[str, str] = {}
        values = (tools or {}).values() if isinstance(tools, Mapping) else (tools or ())
        for tool in values:
            self.register(tool.spec, tool.implementation)

    def register(self, spec: AgentToolSpec, implementation: AgentToolImplementation) -> None:
        if spec.name in self._tools:
            raise ValidationError(f"Tool '{spec.name}' is already registered.")
        owner = self._provider_names.get(spec.provider_name)
        if owner is not None:
            raise ValidationError(
                f"Provider tool name '{spec.provider_name}' is already registered by '{owner}'."
            )
        self._tools[spec.name] = RegisteredTool(spec=spec, implementation=implementation)
        self._provider_names[spec.provider_name] = spec.name

    register_tool = register

    def list_specs(self, scope: ToolScope | None = None) -> list[AgentToolSpec]:
        names = set(scope.tool_names) if scope is not None and scope.tool_names else None
        return [
            tool.spec
            for tool in self._tools.values()
            if names is None or tool.spec.name in names
        ]

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValidationError(f"Tool '{name}' is not registered.") from exc

    def validate_call(
        self,
        *,
        tool_name: str,
        provider_name: str,
        arguments: dict[str, Any],
        scope: ToolScope | None = None,
    ) -> None:
        tool = self.get(tool_name)
        if tool.spec.provider_name != provider_name:
            raise ValidationError(
                f"Provider tool name '{provider_name}' does not match '{tool_name}'."
            )
        if scope is not None and scope.tool_names and tool_name not in scope.tool_names:
            raise ValidationError(f"Tool '{tool_name}' is outside the advertised scope.")
        ensure_bounded_json(arguments, label=f"Tool call '{tool_name}' arguments")

    def invoke(
        self,
        *,
        tool_name: str,
        provider_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
        scope: ToolScope | None = None,
    ) -> Any:
        self.validate_call(
            tool_name=tool_name,
            provider_name=provider_name,
            arguments=arguments,
            scope=scope,
        )
        tool = self.get(tool_name)
        return tool.implementation(copy.deepcopy(arguments), context)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError("Tool payload is not JSON serializable.") from exc


def ensure_bounded_json(value: Any, *, label: str) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object.")
    payload = canonical_json_bytes(value)
    if len(payload) > MAX_TOOL_PAYLOAD_BYTES:
        raise ValidationError(
            f"{label} exceeds the {MAX_TOOL_PAYLOAD_BYTES}-byte limit.",
            error_code="llm_tool_payload_too_large",
        )


def bounded_result_payload(value: Any) -> tuple[dict[str, Any], bool]:
    """Return a copied result envelope and whether it fit the result bound."""

    if isinstance(value, Mapping):
        payload = copy.deepcopy(dict(value))
    else:
        payload = {"value": copy.deepcopy(value)}
    try:
        size = len(canonical_json_bytes(payload))
    except ValidationError:
        return {"status": "error", "error_code": "tool_result_invalid_json"}, False
    if size > MAX_TOOL_PAYLOAD_BYTES:
        return {"status": "error", "error_code": "tool_result_too_large"}, False
    return payload, True
