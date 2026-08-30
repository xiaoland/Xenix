from __future__ import annotations

from .contracts import ScenarioSpec
from .scenarios import (
    build_chat_empty,
    build_chat_mixed_timeline,
    build_chat_running_with_attachments,
)


_SCENARIOS = (
    ScenarioSpec(
        id="chat.empty",
        title="Empty chat",
        description="Fresh timeline and composer with deterministic model options.",
        viewport_width=900,
        viewport_height=680,
        build=build_chat_empty,
    ),
    ScenarioSpec(
        id="chat.mixed-timeline",
        title="Mixed chat timeline",
        description="User, assistant, repeated tool, and connection retry events.",
        viewport_width=900,
        viewport_height=720,
        build=build_chat_mixed_timeline,
    ),
    ScenarioSpec(
        id="chat.running-with-attachments",
        title="Running chat with attachments",
        description="Locked composer with ready and failed synthetic attachments.",
        viewport_width=900,
        viewport_height=680,
        build=build_chat_running_with_attachments,
    ),
)

_BY_ID = {scenario.id: scenario for scenario in _SCENARIOS}
if len(_BY_ID) != len(_SCENARIOS):
    raise RuntimeError("Widget Lab scenario IDs must be unique")


def list_scenarios() -> tuple[ScenarioSpec, ...]:
    return tuple(sorted(_SCENARIOS, key=lambda scenario: scenario.id))


def get_scenario(scenario_id: str) -> ScenarioSpec:
    try:
        return _BY_ID[scenario_id]
    except KeyError as exc:
        available = ", ".join(scenario.id for scenario in list_scenarios())
        raise ValueError(f"Unknown UI scenario '{scenario_id}'. Available: {available}") from exc
