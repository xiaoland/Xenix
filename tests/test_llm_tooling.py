import pytest

from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    ToolExecutionContext,
    ToolSuccess,
)


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["fast", "careful"]},
            "options": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 5}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
        "required": ["mode", "options"],
        "additionalProperties": False,
    }


def _registry(schema: dict, calls: list[dict]) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="test.schema",
            provider_name="test_schema",
            description="Validate one schema-bound call.",
            parameters_schema=schema,
        ),
        lambda arguments, _context: calls.append(arguments) or ToolSuccess({"ok": True}),
    )
    return registry


@pytest.mark.parametrize(
    ("arguments", "keyword"),
    [
        ({"mode": "fast"}, "required"),
        ({"mode": "fast", "options": {"limit": "1"}}, "type"),
        ({"mode": "unknown", "options": {"limit": 1}}, "enum"),
        ({"mode": "fast", "options": {"limit": 0}}, "minimum"),
        ({"mode": "fast", "options": {"limit": 6}}, "maximum"),
        ({"mode": "fast", "options": {"limit": 1, "private": True}}, "additionalProperties"),
        ({"mode": "fast", "options": {"limit": 1}, "private": True}, "additionalProperties"),
    ],
)
def test_registry_rejects_schema_invalid_arguments_before_invocation(
    arguments: dict,
    keyword: str,
) -> None:
    calls: list[dict] = []
    registry = _registry(_schema(), calls)

    with pytest.raises(ValidationError, match="registered schema") as exc_info:
        registry.invoke(
            tool_name="test.schema",
            provider_name="test_schema",
            arguments=arguments,
            context=ToolExecutionContext(thread_id="thread-1"),
        )

    assert exc_info.value.error_code == "llm_tool_arguments_invalid"
    assert exc_info.value.error_details == {"schema_keyword": keyword}
    assert calls == []
    exposed = str(exc_info.value) + str(exc_info.value.error_details)
    assert "unknown" not in exposed
    assert "private" not in exposed


def test_registry_executes_valid_schema_bound_arguments() -> None:
    calls: list[dict] = []
    registry = _registry(_schema(), calls)
    arguments = {"mode": "careful", "options": {"limit": 3}}

    outcome = registry.invoke(
        tool_name="test.schema",
        provider_name="test_schema",
        arguments=arguments,
        context=ToolExecutionContext(thread_id="thread-1"),
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.value == {"ok": True}
    assert calls == [arguments]


def test_registry_freezes_schema_and_returns_isolated_spec_copies() -> None:
    calls: list[dict] = []
    schema = _schema()
    spec = AgentToolSpec(
        name="test.schema",
        provider_name="test_schema",
        description="Validate one schema-bound call.",
        parameters_schema=schema,
    )
    registry = AgentToolRegistry()
    registry.register(
        spec,
        lambda arguments, _context: calls.append(arguments) or ToolSuccess({"ok": True}),
    )

    spec.parameters_schema["required"] = []
    registry.list_specs()[0].parameters_schema["required"] = []
    registry.get("test.schema").spec.parameters_schema["required"] = []

    with pytest.raises(ValidationError) as exc_info:
        registry.invoke(
            tool_name="test.schema",
            provider_name="test_schema",
            arguments={},
            context=ToolExecutionContext(thread_id="thread-1"),
        )

    assert exc_info.value.error_code == "llm_tool_arguments_invalid"
    assert calls == []
    assert registry.list_specs()[0].parameters_schema["required"] == ["mode", "options"]


def test_registry_rejects_draft_2020_12_invalid_schema_at_registration() -> None:
    registry = AgentToolRegistry()

    with pytest.raises(ValidationError, match="parameter schema is invalid") as exc_info:
        registry.register(
            AgentToolSpec(
                name="test.invalid-schema",
                provider_name="test_invalid_schema",
                description="Invalid schema.",
                parameters_schema={"type": "not-a-json-schema-type"},
            ),
            lambda _arguments, _context: ToolSuccess({"ok": True}),
        )

    assert exc_info.value.error_code == "llm_tool_schema_invalid"
    assert "not-a-json-schema-type" not in str(exc_info.value)
