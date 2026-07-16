"""Black-box coverage for Agent Skill activation and resource boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from xenix.app import (
    _agent_skill_context_messages,
    _agent_skill_activated_skill_names,
    _agent_skill_tool_scope_names,
    _register_agent_skill_tools,
)
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import AgentHarnessService, AgentSkill, AgentSkillCatalog, SubmitUserTurnInput
from xenix.services.llm import (
    AgentToolRegistry,
    LLMConversationService,
    ProviderMessage,
    ProviderResponse,
    ProviderToolCall,
)
from xenix.services.llm.tooling import ToolScope
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ConversationToolResultStatus


class _SkillProvider:
    def __init__(self) -> None:
        self.calls: list[list[ProviderMessage]] = []

    def complete(self, messages: list[ProviderMessage], _tools: list[Any]) -> ProviderResponse:
        self.calls.append(list(messages))
        call_number = len(self.calls)
        if call_number == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="read-before-activate",
                        tool_name="agent.skill.read_reference",
                        provider_name="agent_skill_read_reference",
                        arguments={
                            "skill_name": "demo-skill",
                            "path": "references/guide.md",
                        },
                    )
                ]
            )
        if call_number == 2:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="activate-demo",
                        tool_name="agent.skill.activate",
                        provider_name="agent_skill_activate",
                        arguments={"name": "demo-skill"},
                    )
                ]
            )
        if call_number == 3:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="read-after-activate",
                        tool_name="agent.skill.read_reference",
                        provider_name="agent_skill_read_reference",
                        arguments={
                            "skill_name": "demo-skill",
                            "path": "references/guide.md",
                        },
                    )
                ]
            )
        if call_number == 4:
            return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "完成。"}])
        raise AssertionError(f"unexpected provider call {call_number}")


def _catalog() -> AgentSkillCatalog:
    return AgentSkillCatalog(
        [
            AgentSkill(
                name="demo-skill",
                description="A skill used for boundary tests.",
                body="Follow the demo instructions.",
                resources={"references": {"references/guide.md": "bounded guide"}, "assets": {}},
            )
        ]
    )


def _active_flag(messages: list[ProviderMessage]) -> bool:
    context = next(message.content for message in messages if "available_agent_skills" in message.content)
    payload = context.split("<available_agent_skills>", 1)[1].split("</available_agent_skills>", 1)[0]
    return bool(json.loads(payload)[0]["active"])


def test_skill_context_uses_successful_result_payload() -> None:
    catalog = _catalog()
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="activate-call",
                tool_id="agent.skill.activate",
                value_payload={"skill_name": "wrong-from-tool-call"},
            ),
            SimpleNamespace(
                id="activate-result",
                tool_call_message_id="activate-call",
                result_status=ConversationToolResultStatus.SUCCEEDED,
                value_payload={"skill_name": "demo-skill"},
            ),
        ]
    )
    assert _agent_skill_activated_skill_names(snapshot) == {"demo-skill"}
    assert _active_flag(_agent_skill_context_messages(catalog, snapshot)) is True


def test_modeling_skill_scope_keeps_its_result_explanation_tool() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(id="activate-modeling", tool_id="agent.skill.activate"),
            SimpleNamespace(
                tool_call_message_id="activate-modeling",
                result_status=ConversationToolResultStatus.SUCCEEDED,
                value_payload={"skill_name": "xenix-data-modeling"},
            ),
        ]
    )

    scope = _agent_skill_tool_scope_names(snapshot)

    assert scope is not None
    assert "model.train" in scope
    assert "analysis.graph" in scope


def test_skill_resource_reads_require_activation_in_the_same_thread(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "runtime"))
    storage = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    catalog = _catalog()
    registry = AgentToolRegistry()
    active_names = set[str]()
    _register_agent_skill_tools(
        registry,
        catalog,
        activated_skill_names_provider=lambda _thread_id: active_names,
    )
    spec = next(spec for spec in registry.list_specs() if spec.name == "agent.skill.read_reference")

    with pytest.raises(ValidationError, match="must be activated"):
        registry.invoke(
            tool_name=spec.name,
            provider_name=spec.provider_name,
            arguments={"skill_name": "demo-skill", "path": "references/guide.md"},
            context=ToolExecutionContext(thread_id="thread-before-activation"),
        )

    active_names.add("demo-skill")
    result = registry.invoke(
        tool_name=spec.name,
        provider_name=spec.provider_name,
        arguments={"skill_name": "demo-skill", "path": "references/guide.md"},
        context=ToolExecutionContext(thread_id="thread-after-activation"),
    )
    assert result["path"] == "references/guide.md"
    assert result["size_bytes"] == len("bounded guide".encode("utf-8"))


def test_skill_harness_replays_failed_then_successful_resource_read(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "runtime"))
    storage = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    catalog = _catalog()
    registry = AgentToolRegistry()
    provider: _SkillProvider
    conversation: LLMConversationService

    def active_names(thread_id: str) -> set[str]:
        return _agent_skill_activated_skill_names(conversation.get_thread_snapshot(thread_id))

    conversation = LLMConversationService(
        session_factory=storage.session_factory,
        tool_registry=registry,
        context_messages_provider=lambda snapshot: _agent_skill_context_messages(catalog, snapshot),
    )
    _register_agent_skill_tools(registry, catalog, activated_skill_names_provider=active_names)
    provider = _SkillProvider()
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(text="Use the demo skill.", client_submission_id="skill-boundary")
    )

    calls = [message for message in snapshot.messages if message.kind.value == "tool_call"]
    results = [message for message in snapshot.messages if message.kind.value == "tool_result"]
    assert [message.tool_id for message in calls] == [
        "agent.skill.read_reference",
        "agent.skill.activate",
        "agent.skill.read_reference",
    ]
    assert [result.result_status.value for result in results] == ["failed", "succeeded", "succeeded"]
    assert results[0].value_payload == {}
    assert results[2].value_payload["path"] == "references/guide.md"
    assert _active_flag(provider.calls[0]) is False
    assert _active_flag(provider.calls[1]) is False
    assert _active_flag(provider.calls[2]) is True
