from __future__ import annotations

import json
import os
import subprocess
import sys

from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from scripts.ui_lab.contracts import ScenarioContext
from scripts.ui_lab.driver import configure_scenario_application
from scripts.ui_lab.registry import get_scenario, list_scenarios
from tests.ui.pytest_plugin import UiArtifactRegistry
from xenix.ui.chatbot import ThreadDetailView
from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts
from xenix.ui.semantic_identity import item_reference


EXPECTED_SCENARIO_IDS = (
    "chat.empty",
    "chat.mixed-timeline",
    "chat.running-with-attachments",
)


def _build_scenario(qapp: QApplication, qtbot: QtBot, scenario_id: str):
    scenario = get_scenario(scenario_id)
    configure_scenario_application(qapp, scenario)
    handle = scenario.build(ScenarioContext(qapp))
    qtbot.addWidget(handle.root)
    handle.root.resize(scenario.viewport_width, scenario.viewport_height)
    handle.root.show()
    qtbot.waitUntil(lambda: handle.root.isVisible() and handle.readiness())
    return scenario, handle


def _widgets_with_role(root: QWidget, role: str) -> list[QWidget]:
    return [
        widget
        for widget in root.findChildren(QWidget)
        if widget.accessibleIdentifier() == role
    ]


def test_registry_is_stable_sorted_and_machine_discoverable() -> None:
    assert tuple(scenario.id for scenario in list_scenarios()) == EXPECTED_SCENARIO_IDS

    result = subprocess.run(
        [sys.executable, "-m", "scripts.ui_lab", "--list", "--json"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    payload = json.loads(result.stdout)

    assert tuple(item["id"] for item in payload) == EXPECTED_SCENARIO_IDS


def test_all_scenarios_build_without_runtime_services_or_state(
    qapp: QApplication,
    qtbot: QtBot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_home = tmp_path / "must-not-be-created"
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    for scenario_id in EXPECTED_SCENARIO_IDS:
        _scenario, handle = _build_scenario(qapp, qtbot, scenario_id)
        assert isinstance(handle.root, ThreadDetailView)
        handle.close()

    assert not runtime_home.exists()


def test_mixed_timeline_repeated_controls_have_authoritative_item_references(
    qapp: QApplication,
    qtbot: QtBot,
    ui_artifacts: UiArtifactRegistry,
) -> None:
    _scenario, handle = _build_scenario(qapp, qtbot, "chat.mixed-timeline")
    ui_artifacts.register(handle.root, name="chat-mixed-timeline")

    tool_toggles = _widgets_with_role(handle.root, "chat.tool-call.toggle-details")
    retry_toggles = _widgets_with_role(handle.root, "chat.connection-retry.toggle-details")

    assert {item_reference(widget) for widget in tool_toggles} == {
        "tool:profile:001",
        "tool:query:001",
    }
    assert len(retry_toggles) == 1
    assert item_reference(retry_toggles[0]) == "connection:001"
    assert all(widget.accessibleName() for widget in tool_toggles + retry_toggles)
    handle.close()


def test_running_scenario_exposes_stop_contract(qapp: QApplication, qtbot: QtBot) -> None:
    _scenario, handle = _build_scenario(qapp, qtbot, "chat.running-with-attachments")
    view = handle.root
    assert isinstance(view, ThreadDetailView)

    assert view._send_button.accessibleIdentifier() == "chat.composer.send-or-stop"
    assert view._send_button.accessibleName() == view.tr("Stop")
    assert not view._editor.isEnabled()
    handle.close()


def test_synthetic_scenario_capture_emits_structured_artifacts(
    qapp: QApplication,
    qtbot: QtBot,
    tmp_path,
) -> None:
    scenario, handle = _build_scenario(qapp, qtbot, "chat.mixed-timeline")
    destination = tmp_path / scenario.id

    manifest = capture_ui_artifacts(
        handle.root,
        destination,
        reason="scenario-contract-test",
        scenario_id=scenario.id,
        policy=CapturePolicy.SYNTHETIC,
    )

    assert manifest["scenario_id"] == scenario.id
    assert manifest["root_geometry"]["width"] == scenario.viewport_width
    assert {artifact["name"] for artifact in manifest["files"]} == {
        "actual.png",
        "tree.json",
    }
    assert (destination / "manifest.json").is_file()
    assert (destination / "actual.png").stat().st_size > 0
    handle.close()
