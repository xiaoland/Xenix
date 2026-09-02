"""LLM-owned tool protocol and bounded registry primitives."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeAlias, TypeVar, cast, overload

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
)
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from .tool_result_page_store import ToolResultPageStore


MAX_TOOL_CALLS = 16
MAX_TOOL_PAYLOAD_BYTES = 64 * 1024
MAX_EXCHANGE_RESULT_BYTES = 1024 * 1024
MAX_TOOL_FAILURE_MESSAGE_CHARS = 16 * 1024
TOOL_RESULT_PAGE_SIZE_CHARS = 1024
TOOL_RESULT_PAGE_LIMIT_CHARS = 4096
TOOL_RESULT_INLINE_CHARS = 2048

_PUBLIC_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_SENSITIVE_DIAGNOSTIC_MARKERS = (
    "api key",
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "token",
)
_SENSITIVE_DIAGNOSTIC_KEYS = (
    "credential",
    "endpoint",
    "password",
    "path",
    "secret",
    "token",
    "url",
    "uri",
)
_PUBLIC_VALIDATION_DETAIL_KEYS = frozenset(
    {
        "actual_count",
        "actual_dimensions",
        "available_modes",
        "category_count",
        "color_field",
        "color_mode",
        "count_field",
        "dimensions",
        "distance_metric",
        "engine",
        "expected_count",
        "expected_dimensions",
        "field",
        "field_role",
        "maximum_dimensions",
        "maximum_length",
        "minimum",
        "mode",
        "operation",
        "palette_size",
        "requested_field",
        "requested_mode",
        "schema_keyword",
        "sql",
        "status_code",
        "text_index",
        "total_terms",
        "visible_terms",
        "word_field",
    }
)

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
    tool_call_message_id: str | None = None
    dataset_ids: tuple[str, ...] = ()
    cancel_requested: Callable[[], bool] = lambda: False


@dataclass(frozen=True)
class ToolSuccess:
    """A direct, canonical value returned by an Agent Tool implementation."""

    value: ToolResultValue

    def __post_init__(self) -> None:
        # A concrete Tool may return up to the exchange-level bound. The invoke
        # boundary re-pages anything above the inline Tool payload bound, so a
        # large raw value never crosses the LLM boundary un-paged.
        ensure_bounded_tool_result_value(
            self.value,
            label="Tool success value",
            max_bytes=MAX_EXCHANGE_RESULT_BYTES,
        )


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


class ResultPageInput(BaseModel):
    """Input for the generic paged-result reader."""

    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(min_length=1, max_length=64)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=TOOL_RESULT_PAGE_SIZE_CHARS, ge=1, le=TOOL_RESULT_PAGE_LIMIT_CHARS)


ToolInvocationOutcome: TypeAlias = ToolSuccess | ToolFailure


ToolInputT = TypeVar("ToolInputT")
ModelInputT = TypeVar("ModelInputT", bound=BaseModel)


AgentToolImplementation: TypeAlias = Callable[
    [ToolInputT, ToolExecutionContext],
    ToolInvocationOutcome,
]


@dataclass(frozen=True)
class AgentTool(Generic[ModelInputT]):
    """Typed Tool registration whose provider schema is a derived projection."""

    name: str
    provider_name: str
    description: str
    input_model: type[ModelInputT]
    implementation: AgentToolImplementation[ModelInputT]
    provider_field_enums: tuple[tuple[str, tuple[str, ...]], ...] = field(
        default_factory=tuple
    )

    @property
    def spec(self) -> AgentToolSpec:
        return AgentToolSpec(
            name=self.name,
            provider_name=self.provider_name,
            description=self.description,
            parameters_schema=project_provider_tool_schema(
                self.input_model,
                field_enums=dict(self.provider_field_enums),
            ),
        )


@dataclass(frozen=True)
class RegisteredTool:
    spec: AgentToolSpec
    implementation: AgentToolImplementation[Any]
    input_model: type[BaseModel] | None = None


_FORBIDDEN_PROVIDER_SCHEMA_KEYWORDS = frozenset(
    {
        "allOf",
        "anyOf",
        "dependentRequired",
        "dependentSchemas",
        "else",
        "if",
        "not",
        "oneOf",
        "then",
    }
)
_SIMPLE_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)


def project_provider_tool_schema(
    input_model: type[BaseModel],
    *,
    field_enums: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Project a Pydantic input authority into the portable provider subset."""

    raw_schema = input_model.model_json_schema(mode="validation")
    raw_defs = raw_schema.get("$defs", {})
    if not isinstance(raw_defs, dict):
        raise ValidationError(
            "Tool parameter schema is invalid.",
            error_code="llm_tool_schema_invalid",
        )
    projected = cast(
        dict[str, Any],
        _project_provider_schema_node(
            raw_schema,
            definitions=raw_defs,
            resolving=(),
        ),
    )
    projected.pop("$defs", None)
    if projected.get("type") != "object" or projected.get("additionalProperties") is not False:
        raise ValidationError(
            "Tool input models must project to a closed top-level object.",
            error_code="llm_tool_schema_invalid",
        )

    properties = projected.get("properties")
    if not isinstance(properties, dict):
        raise ValidationError(
            "Tool parameter schema is invalid.",
            error_code="llm_tool_schema_invalid",
        )
    for field_name, raw_values in (field_enums or {}).items():
        field_schema = properties.get(field_name)
        values = tuple(dict.fromkeys(raw_values))
        enum_schema = field_schema
        if (
            isinstance(field_schema, dict)
            and field_schema.get("type") == "array"
            and isinstance(field_schema.get("items"), dict)
        ):
            enum_schema = field_schema["items"]
        if (
            not values
            or not isinstance(enum_schema, dict)
            or enum_schema.get("type") != "string"
        ):
            raise ValidationError(
                "Tool provider enum projection is invalid.",
                error_code="llm_tool_schema_invalid",
            )
        enum_schema["enum"] = list(values)

    _reject_nonportable_provider_schema(projected)
    return projected


def _project_provider_schema_node(
    raw_node: Any,
    *,
    definitions: dict[str, Any],
    resolving: tuple[str, ...],
) -> Any:
    if isinstance(raw_node, list):
        return [
            _project_provider_schema_node(
                item,
                definitions=definitions,
                resolving=resolving,
            )
            for item in raw_node
        ]
    if not isinstance(raw_node, dict):
        return copy.deepcopy(raw_node)

    node = copy.deepcopy(raw_node)
    reference = node.pop("$ref", None)
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise ValidationError(
                "Tool parameter schema contains an unsupported reference.",
                error_code="llm_tool_schema_invalid",
            )
        definition_name = reference.removeprefix("#/$defs/")
        if definition_name in resolving or definition_name not in definitions:
            raise ValidationError(
                "Tool parameter schema contains an invalid reference.",
                error_code="llm_tool_schema_invalid",
            )
        target = _project_provider_schema_node(
            definitions[definition_name],
            definitions=definitions,
            resolving=(*resolving, definition_name),
        )
        if not isinstance(target, dict):
            raise ValidationError(
                "Tool parameter schema contains an invalid reference.",
                error_code="llm_tool_schema_invalid",
            )
        target.update(node)
        node = target

    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator not in node:
            continue
        raw_variants = node.pop(combinator)
        if not isinstance(raw_variants, list) or not raw_variants:
            raise ValidationError(
                "Tool parameter schema contains an unsupported combinator.",
                error_code="llm_tool_schema_invalid",
            )
        variants = [
            _project_provider_schema_node(
                variant,
                definitions=definitions,
                resolving=resolving,
            )
            for variant in raw_variants
        ]
        collapsed = _collapse_provider_schema_union(variants, combinator=combinator)
        collapsed.update(node)
        if collapsed.get("default") is None:
            collapsed.pop("default", None)
        node = collapsed

    projected: dict[str, Any] = {}
    for key, value in node.items():
        if key == "$defs":
            continue
        if key == "title" and isinstance(value, str):
            continue
        if key == "const":
            projected["enum"] = [copy.deepcopy(value)]
            continue
        if key == "properties":
            if not isinstance(value, dict):
                raise ValidationError(
                    "Tool parameter schema properties are invalid.",
                    error_code="llm_tool_schema_invalid",
                )
            projected[key] = {
                property_name: _project_provider_schema_node(
                    property_schema,
                    definitions=definitions,
                    resolving=resolving,
                )
                for property_name, property_schema in value.items()
            }
            continue
        projected[key] = _project_provider_schema_node(
            value,
            definitions=definitions,
            resolving=resolving,
        )
    return projected


def _collapse_provider_schema_union(
    variants: list[Any],
    *,
    combinator: str,
) -> dict[str, Any]:
    if combinator == "allOf" and len(variants) == 1 and isinstance(variants[0], dict):
        return variants[0]
    if combinator == "allOf":
        raise ValidationError(
            "Tool parameter schema contains an unsupported combinator.",
            error_code="llm_tool_schema_invalid",
        )
    if not all(isinstance(variant, dict) for variant in variants):
        raise ValidationError(
            "Tool parameter schema contains an unsupported union.",
            error_code="llm_tool_schema_invalid",
        )

    typed_variants = [
        variant
        for variant in variants
        if isinstance(variant.get("type"), str)
        and variant["type"] in _SIMPLE_JSON_TYPES
    ]
    if len(typed_variants) != len(variants):
        raise ValidationError(
            "Tool parameter schema contains an unsupported union.",
            error_code="llm_tool_schema_invalid",
        )

    non_null = [variant for variant in typed_variants if variant["type"] != "null"]
    if len(non_null) == 1 and len(non_null) != len(typed_variants):
        return cast(dict[str, Any], non_null[0])
    if all(set(variant) <= {"type"} for variant in typed_variants):
        types = list(dict.fromkeys(variant["type"] for variant in typed_variants))
        if "number" in types and "integer" in types:
            types.remove("integer")
        return {"type": types[0] if len(types) == 1 else types}
    raise ValidationError(
        "Tool parameter schema contains an unsupported union.",
        error_code="llm_tool_schema_invalid",
    )


def _reject_nonportable_provider_schema(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _reject_nonportable_provider_schema(item)
        return
    if not isinstance(value, dict):
        return
    forbidden = _FORBIDDEN_PROVIDER_SCHEMA_KEYWORDS & set(value)
    if forbidden or "$ref" in value or "$defs" in value:
        raise ValidationError(
            "Tool parameter schema contains unsupported provider keywords.",
            error_code="llm_tool_schema_invalid",
        )
    for item in value.values():
        _reject_nonportable_provider_schema(item)


def _freeze_tool_spec(spec: AgentToolSpec) -> tuple[AgentToolSpec, Draft202012Validator]:
    """Snapshot and compile one advertised schema before it becomes executable."""

    frozen_spec = spec.model_copy(deep=True)
    try:
        ensure_bounded_json(
            frozen_spec.parameters_schema,
            label=f"Tool '{frozen_spec.name}' parameter schema",
        )
        Draft202012Validator.check_schema(frozen_spec.parameters_schema)
    except (SchemaError, ValidationError):
        raise ValidationError(
            "Tool parameter schema is invalid.",
            error_code="llm_tool_schema_invalid",
        ) from None
    return frozen_spec, Draft202012Validator(frozen_spec.parameters_schema)


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
        *,
        paged_results_dir: Path | None = None,
    ) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._provider_names: dict[str, str] = {}
        self._validators: dict[str, Draft202012Validator] = {}
        self._page_store = (
            ToolResultPageStore(paged_results_dir) if paged_results_dir is not None else None
        )
        values = (tools or {}).values() if isinstance(tools, Mapping) else (tools or ())
        for tool in values:
            self._register(
                tool.spec,
                tool.implementation,
                input_model=tool.input_model,
            )
        if self._page_store is not None:
            self._register_builtin_result_page_tool()

    @overload
    def register(self, tool: AgentTool[ModelInputT], implementation: None = None) -> None: ...

    @overload
    def register(
        self,
        tool: AgentToolSpec,
        implementation: AgentToolImplementation[dict[str, Any]],
    ) -> None: ...

    def register(
        self,
        tool: AgentTool[Any] | AgentToolSpec,
        implementation: AgentToolImplementation[Any] | None = None,
    ) -> None:
        if isinstance(tool, AgentTool):
            if implementation is not None:
                raise TypeError("Typed AgentTool registration already owns its implementation.")
            self._register(
                tool.spec,
                tool.implementation,
                input_model=tool.input_model,
            )
            return
        if implementation is None:
            raise TypeError("Legacy AgentToolSpec registration requires an implementation.")
        self._register(tool, implementation, input_model=None)

    def _register(
        self,
        spec: AgentToolSpec,
        implementation: AgentToolImplementation[Any],
        *,
        input_model: type[BaseModel] | None,
    ) -> None:
        if spec.name in self._tools:
            raise ValidationError(f"Tool '{spec.name}' is already registered.")
        owner = self._provider_names.get(spec.provider_name)
        if owner is not None:
            raise ValidationError(
                f"Provider tool name '{spec.provider_name}' is already registered by '{owner}'."
            )
        registered_spec, validator = _freeze_tool_spec(spec)
        self._tools[registered_spec.name] = RegisteredTool(
            spec=registered_spec,
            implementation=implementation,
            input_model=input_model,
        )
        self._provider_names[registered_spec.provider_name] = registered_spec.name
        self._validators[registered_spec.name] = validator

    def _register_builtin_result_page_tool(self) -> None:
        spec = AgentToolSpec(
            name="result.page",
            provider_name="result_page",
            description=(
                "Read one page of a large paged tool result by character range. "
                "Use it when a tool returns a paged result with result_id, total_chars, "
                "and has_more=true; pass result_id plus offset to read subsequent pages."
            ),
            parameters_schema=project_provider_tool_schema(ResultPageInput),
        )
        self._register(spec, self._page_result, input_model=ResultPageInput)

    def _page_result(
        self,
        input_data: ResultPageInput,
        _context: ToolExecutionContext,
    ) -> ToolSuccess:
        if self._page_store is None:
            raise ValidationError("Paged results are unavailable.")
        page = self._page_store.read_page(
            input_data.result_id,
            offset=input_data.offset,
            limit=input_data.limit,
        )
        return ToolSuccess(
            value={
                "result_id": input_data.result_id,
                "offset": input_data.offset,
                "limit": input_data.limit,
                "total_chars": page.total_chars,
                "text": page.text,
                "has_more": page.has_more,
            }
        )

    def delete_thread_results(self, thread_id: str) -> int:
        if self._page_store is None:
            return 0
        return self._page_store.delete_for_thread(thread_id)

    def collect_garbage(self, *, max_age_seconds: int) -> int:
        if self._page_store is None:
            return 0
        return self._page_store.collect_garbage(max_age_seconds=max_age_seconds)

    def list_specs(self, scope: ToolScope | None = None) -> list[AgentToolSpec]:
        names = set(scope.tool_names) if scope is not None and scope.tool_names else None
        return [
            tool.spec.model_copy(deep=True)
            for tool in self._tools.values()
            if names is None or tool.spec.name in names
        ]

    def get(self, name: str) -> RegisteredTool:
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise ValidationError(f"Tool '{name}' is not registered.") from exc
        return RegisteredTool(
            spec=tool.spec.model_copy(deep=True),
            implementation=tool.implementation,
            input_model=tool.input_model,
        )

    def validate_call(
        self,
        *,
        tool_name: str,
        provider_name: str,
        arguments: dict[str, Any],
        scope: ToolScope | None = None,
    ) -> None:
        self._admit_call(
            tool_name=tool_name,
            provider_name=provider_name,
            arguments=arguments,
            scope=scope,
        )

    def _admit_call(
        self,
        *,
        tool_name: str,
        provider_name: str,
        arguments: dict[str, Any],
        scope: ToolScope | None,
    ) -> BaseModel | dict[str, Any]:
        tool = self.get(tool_name)
        if tool.spec.provider_name != provider_name:
            raise ValidationError(
                f"Provider tool name '{provider_name}' does not match '{tool_name}'."
            )
        if scope is not None and scope.tool_names and tool_name not in scope.tool_names:
            raise ValidationError(f"Tool '{tool_name}' is outside the advertised scope.")
        ensure_bounded_json(arguments, label=f"Tool call '{tool_name}' arguments")
        if tool.input_model is not None:
            try:
                return tool.input_model.model_validate(arguments)
            except PydanticValidationError as exc:
                raise ValidationError(
                    "Tool arguments do not match the registered input model.",
                    error_code="llm_tool_arguments_invalid",
                    error_details={
                        "schema_keyword": _pydantic_error_schema_keyword(exc)
                    },
                    retryable=False,
                ) from None

        validator = self._validators[tool_name]
        validation_error = next(validator.iter_errors(arguments), None)
        if validation_error is not None:
            keyword = validation_error.validator
            if not isinstance(keyword, str) or keyword not in validator.VALIDATORS:
                keyword = "schema"
            raise ValidationError(
                "Tool arguments do not match the registered schema.",
                error_code="llm_tool_arguments_invalid",
                error_details={"schema_keyword": keyword},
                retryable=False,
            )
        return copy.deepcopy(arguments)

    def invoke(
        self,
        *,
        tool_name: str,
        provider_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
        scope: ToolScope | None = None,
    ) -> ToolInvocationOutcome:
        validated_arguments = self._admit_call(
            tool_name=tool_name,
            provider_name=provider_name,
            arguments=arguments,
            scope=scope,
        )
        tool = self.get(tool_name)
        outcome = tool.implementation(validated_arguments, context)
        if isinstance(outcome, ToolFailure):
            return outcome
        value = outcome.value if isinstance(outcome, ToolSuccess) else outcome
        return self._bound_success(value, context)

    def _bound_success(
        self,
        value: ToolResultValue,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        text = tool_result_text(value)
        if len(text) <= TOOL_RESULT_INLINE_CHARS:
            return ToolSuccess(value=value)
        if len(text.encode("utf-8")) > MAX_EXCHANGE_RESULT_BYTES:
            raise ValidationError("Tool result exceeds the paged result size limit.")
        if self._page_store is None:
            raise ValidationError(
                "Tool result exceeds the inline payload bound and paged results are unavailable."
            )
        result_id = self._page_store.save(
            thread_id=context.thread_id,
            tool_call_message_id=context.tool_call_message_id,
            text=text,
        )
        total_chars = len(text)
        has_more = total_chars > TOOL_RESULT_PAGE_SIZE_CHARS
        return ToolSuccess(
            value={
                "result_id": result_id,
                "total_chars": total_chars,
                "page_size": TOOL_RESULT_PAGE_SIZE_CHARS,
                "offset": 0,
                "text": text[:TOOL_RESULT_PAGE_SIZE_CHARS],
                "has_more": has_more,
            }
        )


def _pydantic_error_schema_keyword(exc: PydanticValidationError) -> str:
    first_error: dict[str, Any] = dict(
        next(iter(exc.errors(include_url=False)), {})
    )
    error_type = first_error.get("type")
    if error_type == "missing":
        return "required"
    if error_type == "extra_forbidden":
        return "additionalProperties"
    if error_type == "literal_error":
        return "enum"
    if isinstance(error_type, str):
        if error_type.endswith("_type"):
            return "type"
        if error_type in {"greater_than", "greater_than_equal"}:
            return "minimum"
        if error_type in {"less_than", "less_than_equal"}:
            return "maximum"
    return "schema"


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
    fallback_message = "Tool execution failed."
    legacy_message = legacy_error_summary.strip() if isinstance(legacy_error_summary, str) else ""
    if not legacy_message or not _diagnostic_value_is_public(legacy_message):
        legacy_message = fallback_message
    legacy_details = (
        copy.deepcopy(value)
        if value is not None and _diagnostic_value_is_public(value)
        else None
    )
    # Some old failed rows retained a bounded diagnostic payload alongside the
    # generic summary. Preserve only public structured detail that still fits
    # the current canonical value bound; this is a read compatibility
    # conversion, not a mutation or second durable result field.
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
    """Project an exception into a provider-safe failure without exposing diagnostics."""

    if not isinstance(exc, ValidationError):
        return _unexpected_tool_failure()

    code = exc.error_code or "tool_validation_failed"
    message = str(exc).strip() or "Tool input is invalid."
    details = dict(exc.error_details) if exc.error_details else None
    hints = tuple(exc.repair_hints)
    if not _validation_diagnostic_is_public(
        code=code,
        message=message,
        details=details,
        hints=hints,
    ):
        return _invalid_tool_input_failure()
    try:
        return ToolFailure(
            code=code,
            message=message,
            details=details,
            repair_hints=hints,
            retryable=exc.retryable,
        )
    except ValidationError:
        return _invalid_tool_input_failure()


def _unexpected_tool_failure() -> ToolFailure:
    return ToolFailure(
        code="tool_execution_failed",
        message="Tool execution failed.",
    )


def _invalid_tool_input_failure() -> ToolFailure:
    return ToolFailure(
        code="tool_validation_failed",
        message="Tool input is invalid.",
        retryable=False,
    )


def _validation_diagnostic_is_public(
    *,
    code: str,
    message: str,
    details: ToolResultValue | None,
    hints: tuple[str, ...],
) -> bool:
    if not _PUBLIC_ERROR_CODE_PATTERN.fullmatch(code):
        return False
    return all(
        _diagnostic_value_is_public(value)
        for value in (message, details, list(hints))
        if value is not None
    )


def _diagnostic_value_is_public(value: ToolResultValue, *, key: str | None = None) -> bool:
    if key is not None:
        normalized_key = key.casefold().replace("-", "_")
        if (
            normalized_key not in _PUBLIC_VALIDATION_DETAIL_KEYS
            or any(marker in normalized_key for marker in _SENSITIVE_DIAGNOSTIC_KEYS)
        ):
            return False
    if value is None or isinstance(value, bool | int | float):
        return True
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if any(marker in normalized for marker in _SENSITIVE_DIAGNOSTIC_MARKERS):
            return False
        return not (
            "://" in normalized
            or "/" in value
            or "\\" in value
            or value.startswith(("~", "."))
            or (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
        )
    if isinstance(value, list | tuple):
        return all(_diagnostic_value_is_public(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(item_key, str)
            and _diagnostic_value_is_public(item_value, key=item_key)
            for item_key, item_value in value.items()
        )
    return False
