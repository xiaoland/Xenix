from __future__ import annotations

from .contracts import ScenarioSpec
from .feature_scenarios import build_history_populated, build_settings_provider_and_ocr
from .scenarios import (
    build_chat_empty,
    build_chat_mixed_timeline,
    build_chat_running_with_attachments,
)


_SCENARIOS = (
    ScenarioSpec(
        id="main.history-populated",
        title="Populated history panel",
        description="Production history panel with synthetic summaries; not a full app shell.",
        viewport_width=248,
        viewport_height=680,
        build=build_history_populated,
    ),
    ScenarioSpec(
        id="settings.provider-and-ocr",
        title="Provider editor and OCR status",
        description="Production settings components with synthetic provider draft and ready OCR port.",
        viewport_width=1050,
        viewport_height=760,
        build=build_settings_provider_and_ocr,
    ),
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
