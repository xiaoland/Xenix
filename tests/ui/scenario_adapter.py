"""Shared pytest adapter that gives a scenario's root to qtbot.

The scenario owns stopping its tasks; pytest-qt owns closing and deleting the
root. The before_close_func wires scenario cleanup ahead of qtbot's own close so
the two responsibilities never race.
"""

from __future__ import annotations

from scripts.ui_lab.contracts import ScenarioContext, ScenarioHandle, ScenarioSpec
from scripts.ui_lab.driver import configure_scenario_application
from scripts.ui_lab.registry import get_scenario


def attach_scenario(qapp, qtbot, scenario_id: str) -> tuple[ScenarioSpec, ScenarioHandle]:
    """Build a scenario, hand root deletion to qtbot, and stop tasks first."""
    scenario = get_scenario(scenario_id)
    configure_scenario_application(qapp, scenario)
    handle = scenario.build(ScenarioContext(qapp))
    qtbot.addWidget(handle.root, before_close_func=lambda _root: handle.cleanup())
    return scenario, handle
