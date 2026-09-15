"""The sole Tool registry and executor; implementations are injected by composition."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from ...exceptions import ValidationError
from .tool_protocol import (
    MAX_TOOL_PAYLOAD_BYTES,
    AgentTool,
    AgentToolSpec,
    InvalidToolArguments,
    ToolExecutionContext,
    ToolFailure,
    ToolInvocationOutcome,
    ToolResultValue,
    ToolScope,
    ToolSuccess,
    canonical_json_bytes,
    ensure_bounded_json,
    tool_result_text,
)
from .tool_result_page_store import ToolResultPageStore
from .tool_schema import project_tool_spec

TOOL_RESULT_PAGE_SIZE_CHARS = 1024
TOOL_RESULT_PAGE_LIMIT_CHARS = 4096
ModelInputT = TypeVar("ModelInputT", bound=BaseModel)


class ResultPageInput(BaseModel):
    """Input for the generic paged-result reader."""

    model_config = ConfigDict(extra="forbid")

    result_id: int = Field(ge=1)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=TOOL_RESULT_PAGE_SIZE_CHARS, ge=1, le=TOOL_RESULT_PAGE_LIMIT_CHARS)


class AgentToolRegistry:
    """Register typed handlers once; definition visibility never restricts invocation."""

    def __init__(
        self,
        tools: Iterable[AgentTool[Any]] = (),
        *,
        paged_results_dir: Path | None = None,
    ) -> None:
        self._tools: dict[str, AgentTool[Any]] = {}
        self._provider_names: dict[str, str] = {}
        self._specs: dict[str, AgentToolSpec] = {}
        self._page_store = ToolResultPageStore(paged_results_dir) if paged_results_dir is not None else None
        for tool in tools:
            self.register(tool)
        if self._page_store is not None:
            self.register(
                AgentTool(
                    name="result.page",
                    provider_name="result_page",
                    description=(
                        "Read one page of a large paged tool result by character range. "
                        "Use it when a tool returns a paged result with result_id, total_chars, "
                        "and has_more=true; pass result_id plus offset to read subsequent pages."
                    ),
                    input_model=ResultPageInput,
                    implementation=self._page_result,
                )
            )

    def register(self, tool: AgentTool[ModelInputT]) -> None:
        if tool.name in self._tools:
            raise ValidationError(f"Tool '{tool.name}' is already registered.")
        owner = self._provider_names.get(tool.provider_name)
        if owner is not None:
            raise ValidationError(f"Provider tool name '{tool.provider_name}' is already registered by '{owner}'.")
        self._tools[tool.name] = tool
        self._provider_names[tool.provider_name] = tool.name

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

    def delete_thread_results(self, thread_id: int) -> int:
        if self._page_store is None:
            return 0
        return self._page_store.delete_for_thread(thread_id)

    def collect_garbage(self, *, max_age_seconds: int) -> int:
        if self._page_store is None:
            return 0
        return self._page_store.collect_garbage(max_age_seconds=max_age_seconds)

    def list_specs(self, scope: ToolScope | None = None) -> list[AgentToolSpec]:
        names = set(scope.tool_names) if scope is not None and scope.tool_names else None
        specs = []
        for name, tool in self._tools.items():
            if names is not None and name not in names and name != "result.page":
                continue
            if name not in self._specs:
                self._specs[name] = project_tool_spec(tool)
            specs.append(self._specs[name].model_copy(deep=True))
        return specs

    def resolve_name(self, name: str) -> str:
        """Resolve a wire alias, retaining unknown names for failed ToolResults."""
        return self._provider_names.get(name, name)

    def get(self, name: str) -> AgentTool[Any]:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValidationError(
                f"Tool '{name}' is not registered.",
                error_code="llm_tool_not_registered",
            ) from exc

    def invoke(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | InvalidToolArguments,
        context: ToolExecutionContext,
    ) -> ToolInvocationOutcome:
        if isinstance(arguments, InvalidToolArguments):
            return arguments.failure
        tool = self.get(tool_name)
        ensure_bounded_json(arguments, label=f"Tool call '{tool_name}' arguments")
        try:
            validated_arguments = tool.input_model.model_validate(arguments)
        except PydanticValidationError as exc:
            raise ValidationError(
                "Tool arguments do not match the registered input model.",
                error_code="llm_tool_arguments_invalid",
                error_details={
                    "schema_keyword": _pydantic_error_schema_keyword(exc),
                    "validation_errors": [
                        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                        for error in exc.errors(include_input=False, include_context=False, include_url=False)
                    ],
                },
                retryable=False,
            ) from None
        outcome = tool.implementation(validated_arguments, context)
        if isinstance(outcome, ToolFailure):
            return outcome
        if tool_name == "result.page":
            # Paging the page envelope again would replace the original cursor.
            return outcome
        return self._bound_success(outcome.value, context)

    def _bound_success(
        self,
        value: ToolResultValue,
        context: ToolExecutionContext,
    ) -> ToolSuccess:
        # Use the canonical message budget; a second, much smaller character
        # limit fragments ordinary instructions and metadata across LLM rounds.
        if len(canonical_json_bytes(value)) <= MAX_TOOL_PAYLOAD_BYTES:
            return ToolSuccess(value=value)
        text = tool_result_text(value)
        if self._page_store is None:
            raise ValidationError("Tool result exceeds the inline payload bound and paged results are unavailable.")
        if context.tool_call_message_id is None:
            raise ValidationError("Paged results require a reserved ToolCall identity.")
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
    first_error: dict[str, Any] = dict(next(iter(exc.errors(include_url=False)), {}))
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
