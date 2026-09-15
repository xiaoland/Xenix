"""Shared Tool values and serialization; independent of execution and schema projection."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeAlias, TypeVar

from pydantic import BaseModel, Field, field_validator
from sqlmodel import SQLModel

from ...exceptions import ValidationError

MAX_TOOL_CALLS = 16
MAX_TOOL_PAYLOAD_BYTES = 64 * 1024
MAX_EXCHANGE_RESULT_BYTES = 1024 * 1024
MAX_TOOL_FAILURE_MESSAGE_CHARS = 16 * 1024

# Tool results are direct JSON values, including XTT strings; adapters only
# encode them for transport, without changing their meaning.
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
    """Definitions to advertise and Dataset context for one sampling request.

    Tool visibility does not restrict execution of registered Tools.
    """

    tool_names: tuple[str, ...] = ()
    dataset_ids: tuple[int, ...] = ()


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

    thread_id: int
    tool_call_message_id: int | None = None
    dataset_ids: tuple[int, ...] = ()
    cancel_requested: Callable[[], bool] = lambda: False


@dataclass(frozen=True)
class ToolSuccess:
    """A direct, canonical value returned by an Agent Tool implementation."""

    value: ToolResultValue


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
        hints = tuple(hint.strip() for hint in self.repair_hints if isinstance(hint, str) and hint.strip())
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


@dataclass(frozen=True)
class InvalidToolArguments:
    """Received arguments that must produce a ToolFailure without execution."""

    raw_text: str
    failure: ToolFailure


ToolInvocationOutcome: TypeAlias = ToolSuccess | ToolFailure


ToolInputT = TypeVar("ToolInputT")
ModelInputT = TypeVar("ModelInputT", bound=BaseModel)


AgentToolImplementation: TypeAlias = Callable[
    [ToolInputT, ToolExecutionContext],
    ToolInvocationOutcome,
]


@dataclass(frozen=True)
class AgentTool(Generic[ModelInputT]):
    """Executable Tool registration; provider definitions are derived separately."""

    name: str
    provider_name: str
    description: str
    input_model: type[ModelInputT]
    implementation: AgentToolImplementation[ModelInputT]
    provider_field_enums: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("name", "provider_name"):
            value = getattr(self, name).strip()
            if not value:
                raise ValueError("Tool name cannot be empty.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class StagedToolCall:
    """Immutable in-memory call awaiting an LLM-owned invocation."""

    pending_message_id: int
    staged_call_id: int
    provider_call_id: str
    tool_name: str
    provider_name: str
    arguments: dict[str, Any] | InvalidToolArguments
    scope_fingerprint: str

    def __post_init__(self) -> None:
        if self.pending_message_id < 1 or self.staged_call_id < 1:
            raise ValidationError("Staged tool call identity cannot be empty.")
        if not self.provider_call_id.strip() or not self.tool_name.strip():
            raise ValidationError("Staged tool call provider identity cannot be empty.")
        if not self.scope_fingerprint.strip():
            raise ValidationError("Staged tool call scope fingerprint cannot be empty.")
        if not isinstance(self.arguments, InvalidToolArguments):
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


def tool_result_text(value: ToolResultValue) -> str:
    """Return the canonical string form of a Tool result for paging.

    A string result (for example XTT) is paged as-is; any structured value is
    paged as its compact JSON representation with non-ASCII text preserved.
    """

    if isinstance(value, str):
        return value
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
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


def ensure_bounded_tool_result_value(
    value: ToolResultValue,
    *,
    label: str,
    max_bytes: int = MAX_TOOL_PAYLOAD_BYTES,
) -> None:
    """Validate one direct JSON ToolResult value without changing its shape."""

    payload = canonical_json_bytes(value)
    if len(payload) > max_bytes:
        raise ValidationError(
            f"{label} exceeds the {max_bytes}-byte limit.",
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
    legacy_message = legacy_error_summary.strip() if isinstance(legacy_error_summary, str) else ""
    if not legacy_message:
        legacy_message = "Tool execution failed."
    legacy_details = copy.deepcopy(value) if value is not None else None
    try:
        return ToolFailure(
            code="legacy_tool_failure",
            message=legacy_message,
            details=legacy_details,
        ).to_value()
    except ValidationError:
        return ToolFailure(
            code="legacy_tool_failure",
            message=legacy_message,
        ).to_value()


def tool_failure_from_exception(exc: Exception) -> ToolFailure:
    """Project an exception into an agent-visible tool failure.

    The LLM is the primary consumer of Tool failures and must see the concrete
    error to self-correct.  Preserve the full exception text and structured
    repair contract; never collapse a specific failure into a generic sentinel.
    """

    if isinstance(exc, ValidationError):
        code = exc.error_code or "tool_validation_failed"
        message = str(exc).strip() or "Tool input is invalid."
        details = dict(exc.error_details) if exc.error_details else None
        hints = tuple(exc.repair_hints)
        try:
            return ToolFailure(
                code=code,
                message=message,
                details=details,
                repair_hints=hints,
                retryable=exc.retryable,
            )
        except ValidationError:
            return ToolFailure(code=code, message=message)

    message = str(exc).strip() or type(exc).__name__
    return ToolFailure(
        code="tool_execution_failed",
        message=message,
    )
