from __future__ import annotations

from types import SimpleNamespace

from xenix.services.agent.composition import agent_skill_tool_scope_names


def test_inactive_agent_skill_scope_discloses_only_activation_and_knowledge() -> None:
    snapshot = SimpleNamespace(messages=[])

    assert agent_skill_tool_scope_names(snapshot) == (
        "agent.skill.activate",
        "knowledge.lookup",
    )


def test_activated_modeling_skill_discloses_only_its_tools_and_common_building_blocks() -> None:
    snapshot = _snapshot_with_activated_skill("xenix-data-modeling")

    scope = agent_skill_tool_scope_names(snapshot)

    assert scope is not None
    assert "model.metadata" in scope
    assert "model.train" in scope
    assert "model.apply" in scope
    assert "analysis.profile" in scope
    assert "data.clean" not in scope


def test_unknown_activated_skill_fails_closed_to_initial_scope() -> None:
    snapshot = _snapshot_with_activated_skill("unknown-skill")

    assert agent_skill_tool_scope_names(snapshot) == (
        "agent.skill.activate",
        "knowledge.lookup",
    )


def _snapshot_with_activated_skill(skill_name: str) -> SimpleNamespace:
    activation = SimpleNamespace(id="activation-1", tool_id="agent.skill.activate")
    result = SimpleNamespace(
        id="result-1",
        tool_call_message_id="activation-1",
        result_status="succeeded",
        value_payload={"skill_name": skill_name},
    )
    return SimpleNamespace(messages=[activation, result])
