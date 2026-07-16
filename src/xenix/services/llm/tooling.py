"""LLM-owned tool protocol and bounded registry primitives."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from .xenix_table_text import render_xenix_table_tool_result


MAX_TOOL_CALLS = 16
MAX_TOOL_PAYLOAD_BYTES = 64 * 1024
MAX_EXCHANGE_RESULT_BYTES = 1024 * 1024
MAX_TOOL_FAILURE_MESSAGE_CHARS = 16 * 1024

# A Tool Result is a JSON value, rather than a JSON-object-only payload.  In
# particular, tabular tools return Xenix Table Text directly as a string.  The
# provider adapter is responsible only for carrying this value on its wire;
# it must not manufacture a different semantic result.
ToolResultValue: TypeAlias = Any


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


@dataclass(frozen=True)
class ToolSuccess:
    """A direct, canonical value returned by an Agent Tool implementation."""

    value: ToolResultValue

    def __post_init__(self) -> None:
        ensure_bounded_tool_result_value(self.value, label="Tool success value")


@dataclass(frozen=True)
class ToolFailure:
    """A bounded, typed failure value returned or normalized by the LLM tool boundary."""

    code: str
    message: str
    details: ToolResultValue | None = None
    repair_hints: tuple[str, ...] = ()
    retryable: bool | None = None

    def __post_init__(self) -> None:
        code = self.code.strip() if isinstance(self.code, str) else ""
        if not code:
            raise ValidationError("Tool failure code cannot be empty.")
        message = self.message.strip() if isinstance(self.message, str) else ""
        if not message:
            message = "Tool execution failed."
        if len(message) > MAX_TOOL_FAILURE_MESSAGE_CHARS:
            message = message[:MAX_TOOL_FAILURE_MESSAGE_CHARS]
        hints = tuple(
            hint.strip()
            for hint in self.repair_hints
            if isinstance(hint, str) and hint.strip()
        )
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "repair_hints", hints)
        object.__setattr__(self, "retryable", self.retryable if isinstance(self.retryable, bool) else None)
        ensure_bounded_tool_result_value(self.to_value(), label="Tool failure value")

    def to_value(self) -> dict[str, ToolResultValue]:
        value: dict[str, ToolResultValue] = {
            "type": "tool_failure",
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            value["details"] = self.details
        if self.repair_hints:
            value["repair_hints"] = list(self.repair_hints)
        if self.retryable is not None:
            value["retryable"] = self.retryable
        return value


ToolInvocationOutcome: TypeAlias = ToolSuccess | ToolFailure


class AgentToolImplementation(Protocol):
    def __call__(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolInvocationOutcome:
        """Execute one validated call and return the direct canonical outcome."""


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
    value: ToolResultValue = None

    def __post_init__(self) -> None:
        if self.status not in {"succeeded", "failed"}:
            raise ValidationError("Terminal tool result status is invalid.")
        ensure_bounded_tool_result_value(self.value, label="Terminal tool result value")


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
    ) -> ToolInvocationOutcome:
        self.validate_call(
            tool_name=tool_name,
            provider_name=provider_name,
            arguments=arguments,
            scope=scope,
        )
        tool = self.get(tool_name)
        outcome = tool.implementation(copy.deepcopy(arguments), context)
        if isinstance(outcome, (ToolSuccess, ToolFailure)):
            return outcome
        # Existing injected integrations may still return a direct JSON value.
        # It is normalized once at the LLM-owned Tool interface, never wrapped
        # into a second raw-payload representation.
        return ToolSuccess(value=outcome)


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


def ensure_bounded_tool_result_value(value: ToolResultValue, *, label: str) -> None:
    """Validate one direct JSON ToolResult value without changing its shape."""

    payload = canonical_json_bytes(value)
    if len(payload) > MAX_TOOL_PAYLOAD_BYTES:
        raise ValidationError(
            f"{label} exceeds the {MAX_TOOL_PAYLOAD_BYTES}-byte limit.",
            error_code="llm_tool_payload_too_large",
        )


def terminal_tool_result(outcome: ToolInvocationOutcome) -> TerminalToolResult:
    """Normalize a direct Tool outcome into the staged atomic-exchange value."""

    if isinstance(outcome, ToolSuccess):
        return TerminalToolResult(status="succeeded", value=copy.deepcopy(outcome.value))
    if isinstance(outcome, ToolFailure):
        return TerminalToolResult(status="failed", value=copy.deepcopy(outcome.to_value()))
    raise ValidationError("Agent Tool returned an unsupported outcome.")


def canonical_tool_result_value(
    *,
    value: ToolResultValue,
    failed: bool,
    legacy_error_summary: str | None = None,
) -> ToolResultValue:
    """Read a persisted Tool Result as the one value consumers may use.

    New failed rows already carry a typed ``ToolFailure`` object in
    ``value_payload``.  Old immutable rows used ``error_summary`` instead;
    synthesize the equivalent value only at read time so history remains
    intelligible without mutating it or inventing a second durable field.
    """

    if not failed:
        return copy.deepcopy(value)
    if isinstance(value, dict) and value.get("type") == "tool_failure":
        return copy.deepcopy(value)
    # Some old failed rows retained a bounded diagnostic payload alongside the
    # generic summary. Preserve it as structured legacy detail when it still
    # fits the current canonical value bound; this is a read compatibility
    # conversion, not a second durable result field.
    try:
        return ToolFailure(
            code="legacy_tool_failure",
            message=(legacy_error_summary or "Tool execution failed."),
            details=copy.deepcopy(value) if value is not None else None,
        ).to_value()
    except ValidationError:
        return ToolFailure(
            code="legacy_tool_failure",
            message=(legacy_error_summary or "Tool execution failed."),
        ).to_value()


def tool_failure_from_exception(exc: Exception) -> ToolFailure:
    """Preserve useful diagnostics from a Tool exception in one typed value."""

    code = getattr(exc, "error_code", None)
    details = getattr(exc, "error_details", None)
    hints = getattr(exc, "repair_hints", None)
    retryable = getattr(exc, "retryable", None)
    message = str(exc).strip() or exc.__class__.__name__
    if not isinstance(code, str) or not code.strip():
        code = "tool_execution_failed"
    if isinstance(details, (dict, list)) and not details:
        details = None
    if not isinstance(details, (dict, list, str, int, float, bool)) and details is not None:
        details = None
    if details is None:
        details = {"exception_type": exc.__class__.__name__}
    try:
        return ToolFailure(
            code=code,
            message=message,
            details=details,
            repair_hints=tuple(hints) if isinstance(hints, list | tuple) else (),
            retryable=retryable,
        )
    except ValidationError:
        # A malformed domain-provided detail must not replace the original
        # diagnostic with an opaque generic error.
        return ToolFailure(
            code="tool_execution_failed",
            message=message,
            details={"exception_type": exc.__class__.__name__},
        )
