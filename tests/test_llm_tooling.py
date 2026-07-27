import pytest
from pydantic import BaseModel, ConfigDict, model_validator

from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AgentToolRegistry,
    ToolExecutionContext,
    ToolSuccess,
)
from xenix.services.llm.tooling import AgentTool


class _TypedOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    limit: int


class _TypedInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    mode: str
    options: _TypedOptions | None = None

    @model_validator(mode="after")
    def _options_required_for_careful_mode(self) -> "_TypedInput":
        if self.mode == "careful" and self.options is None:
            raise ValueError("careful mode requires options")
        return self


def test_typed_registry_validates_model_rules_before_passing_model_to_handler() -> None:
    calls: list[_TypedInput] = []

    def implementation(
        input_data: _TypedInput,
        _context: ToolExecutionContext,
    ) -> ToolSuccess:
        calls.append(input_data)
        return ToolSuccess({"ok": True})

    registry = AgentToolRegistry()
    registry.register(
        AgentTool(
            name="test.typed",
            provider_name="test_typed",
            description="Validate one typed call.",
            input_model=_TypedInput,
            implementation=implementation,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        registry.validate_call(
            tool_name="test.typed",
            provider_name="test_typed",
            arguments={"mode": "careful"},
        )

    assert exc_info.value.error_code == "llm_tool_arguments_invalid"
    assert calls == []

    outcome = registry.invoke(
        tool_name="test.typed",
        provider_name="test_typed",
        arguments={"mode": "careful", "options": {"limit": 3}},
        context=ToolExecutionContext(thread_id="thread-1"),
    )

    assert isinstance(outcome, ToolSuccess)
    assert isinstance(calls[0], _TypedInput)
    assert calls[0].options == _TypedOptions(limit=3)
