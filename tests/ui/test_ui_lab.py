from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from scripts.ui_lab.driver import configure_scenario_application
from scripts.ui_lab.registry import get_scenario, list_scenarios
from tests.ui.pytest_plugin import UiArtifactRegistry
from tests.ui.scenario_adapter import attach_scenario
from xenix.ui.chatbot import ThreadDetailView
from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts
from xenix.ui.semantic_identity import item_reference


EXPECTED_SCENARIO_IDS = (
    "chat.empty",
    "chat.mixed-timeline",
    "chat.running-with-attachments",
    "main.history-populated",
    "settings.provider-and-ocr",
)


def _build_scenario(qapp: QApplication, qtbot: QtBot, scenario_id: str):
    scenario, handle = attach_scenario(qapp, qtbot, scenario_id)
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


def test_missing_scenario_font_fails_instead_of_silently_capturing_icon_glyphs(qapp) -> None:
    scenario = get_scenario("chat.empty")
    try:
        with pytest.raises(RuntimeError, match="capture requires the declared text font"):
            configure_scenario_application(qapp, replace(scenario, font_family="Xenix Missing Test Font"))
    finally:
        configure_scenario_application(qapp, scenario)


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
        assert isinstance(handle.root, QWidget)
        handle.cleanup()

    assert not runtime_home.exists()


def test_feature_scenarios_use_production_semantic_contracts(qapp, qtbot, ui_artifacts) -> None:
    _scenario, history = _build_scenario(qapp, qtbot, "main.history-populated")
    ui_artifacts.register(history.root, name="history-panel")
    assert {item_reference(widget) for widget in _widgets_with_role(
        history.root, "main.history.thread-item"
    )} == {"thread:synthetic:001", "thread:synthetic:002", "thread:synthetic:003"}
    history.cleanup()

    _scenario, settings = _build_scenario(qapp, qtbot, "settings.provider-and-ocr")
    ui_artifacts.register(settings.root, name="provider-and-ocr")
    assert len(_widgets_with_role(settings.root, "settings.llm.provider.selector")) == 1
    assert len(_widgets_with_role(settings.root, "settings.knowledge.ocr.setup")) == 1
    settings.cleanup()


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
    handle.cleanup()


def test_running_scenario_exposes_stop_contract(qapp: QApplication, qtbot: QtBot) -> None:
    _scenario, handle = _build_scenario(qapp, qtbot, "chat.running-with-attachments")
    view = handle.root
    assert isinstance(view, ThreadDetailView)

    # Flush deleteLater from the scenario's attachment chip refreshes so the
    # remove controls below reflect the settled widget tree.
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert view.composer.send_button.accessibleIdentifier() == "chat.composer.send-or-stop"
    assert view.composer.send_button.accessibleName() == view.tr("Stop")
    assert view.composer.send_button.isEnabled()
    assert not view.composer.editor.isEnabled()

    remove_buttons = _widgets_with_role(view, "chat.composer.attachment.remove")
    assert {item_reference(button) for button in remove_buttons} == {
        str(Path("C:/xenix-synthetic/quarterly-sales.csv").resolve()),
        str(Path("C:/xenix-synthetic/regional-targets.xlsx").resolve()),
    }
    assert all(not button.isEnabled() for button in remove_buttons)
    handle.cleanup()


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
    assert manifest["render_environment"]["font"]["resolved_family"] == scenario.font_family
    assert manifest["root_geometry"]["width"] == scenario.viewport_width
    assert {artifact["name"] for artifact in manifest["files"]} == {
        "actual.png",
        "tree.json",
    }
    assert (destination / "manifest.json").is_file()
    assert (destination / "actual.png").stat().st_size > 0
    handle.cleanup()


def test_batch_capture_cli_reconciles_registry_scenarios(tmp_path) -> None:
    output = tmp_path / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.ui_lab.capture_all",
            "--output",
            str(output),
            "--scenario",
            "chat.empty",
            "--scenario",
            "chat.mixed-timeline",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["reconciled"] is True
    assert set(payload["captured_scenarios"]) == {"chat.empty", "chat.mixed-timeline"}
    run_dir = output / payload["run_id"]
    assert (run_dir / "chat.empty" / "manifest.json").is_file()
    assert (run_dir / "chat.mixed-timeline" / "actual.png").is_file()
    assert (run_dir / "batch.json").is_file()


def test_batch_capture_aggregates_build_failure_with_stage_manifest(qapp, tmp_path, monkeypatch) -> None:
    from scripts.ui_lab import capture_all as capture_all_module

    def broken(_context):
        raise RuntimeError("synthetic build failure")

    broken_spec = replace(list_scenarios()[0], build=broken)
    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (broken_spec,))

    batch = capture_all_module.capture_all_scenarios(tmp_path / "artifacts", [broken_spec.id])

    assert batch["reconciled"] is False
    assert batch["failures"] == [
        {
            "scenario_id": broken_spec.id,
            "stage": "build",
            "error": "RuntimeError: synthetic build failure",
        }
    ]
    run_dir = tmp_path / "artifacts" / batch["run_id"]
    manifest = json.loads((run_dir / broken_spec.id / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "scenario-capture-failure"
    assert manifest["stage"] == "build"


def test_batch_capture_aggregates_configure_failure_with_stage_manifest(qapp, tmp_path, monkeypatch) -> None:
    """Configure failure is recorded as stage 'configure', not 'build'."""
    from scripts.ui_lab import capture_all as capture_all_module

    def broken_configure(_app, _scenario):
        raise RuntimeError("synthetic configure failure")

    monkeypatch.setattr(capture_all_module, "configure_scenario_application", broken_configure)
    spec = list_scenarios()[0]
    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (spec,))

    batch = capture_all_module.capture_all_scenarios(tmp_path / "artifacts", [spec.id])

    assert batch["reconciled"] is False
    assert batch["failures"] == [
        {
            "scenario_id": spec.id,
            "stage": "configure",
            "error": "RuntimeError: synthetic configure failure",
        }
    ]
    run_dir = tmp_path / "artifacts" / batch["run_id"]
    manifest = json.loads((run_dir / spec.id / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "scenario-capture-failure"
    assert manifest["stage"] == "configure"


def test_batch_capture_prune_runs_removes_prior_runs(qapp, tmp_path, monkeypatch) -> None:
    from scripts.ui_lab import capture_all as capture_all_module

    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (get_scenario("chat.empty"),))
    output = tmp_path / "artifacts"

    first = capture_all_module.capture_all_scenarios(output, ["chat.empty"])
    assert (output / first["run_id"] / "batch.json").is_file()

    second = capture_all_module.capture_all_scenarios(output, ["chat.empty"], prune_runs=True)

    assert not (output / first["run_id"]).exists()
    assert (output / second["run_id"] / "batch.json").is_file()


def test_prune_runs_only_removes_xenix_run_dirs(qapp, tmp_path, monkeypatch) -> None:
    from scripts.ui_lab import capture_all as capture_all_module

    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (get_scenario("chat.empty"),))
    output = tmp_path / "artifacts"

    batch = capture_all_module.capture_all_scenarios(output, ["chat.empty"])
    genuine = output / batch["run_id"]

    matching_name = output / "20200101T000000000000Z"
    matching_name.mkdir(parents=True)
    (matching_name / "batch.json").write_text(
        json.dumps({"run_id": "20200101T000000000000Z"}), encoding="utf-8"
    )

    mismatched_run_id = output / "20200102T000000000000Z"
    mismatched_run_id.mkdir(parents=True)
    (mismatched_run_id / "batch.json").write_text(
        json.dumps({"run_id": "20200103T000000000000Z"}), encoding="utf-8"
    )

    no_batch_json = output / "20200104T000000000000Z"
    no_batch_json.mkdir()

    not_a_run_id = output / "keep-me"
    not_a_run_id.mkdir()

    pruned = capture_all_module.prune_run_directories(output)

    assert pruned == 2
    assert not genuine.exists()
    assert not matching_name.exists()
    assert mismatched_run_id.exists()
    assert no_batch_json.exists()
    assert not_a_run_id.exists()


def test_prune_runs_refuses_dangerous_roots() -> None:
    from scripts.ui_lab import capture_all as capture_all_module

    with pytest.raises(ValueError, match="Refusing to prune"):
        capture_all_module.prune_run_directories(Path.home())


def test_capture_verifier_reports_missing_artifacts(qapp, tmp_path, monkeypatch) -> None:
    from scripts.ui_lab import capture_all as capture_all_module

    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (get_scenario("chat.empty"),))
    output = tmp_path / "artifacts"
    batch = capture_all_module.capture_all_scenarios(output, ["chat.empty"])
    run_dir = output / batch["run_id"]

    report = capture_all_module.verify_captured_artifacts(run_dir)
    assert report["complete"] is True
    assert report["reconciled"] is True
    assert report["failures"] == []
    assert report["scenarios"]["chat.empty"]["complete"] is True

    (run_dir / "chat.empty" / "actual.png").unlink()
    report = capture_all_module.verify_captured_artifacts(run_dir)
    assert report["complete"] is False
    assert report["scenarios"]["chat.empty"]["missing"] == ["actual.png"]


def test_capture_verifier_rejects_unreconciled_batch(qapp, tmp_path, monkeypatch) -> None:
    """Verifier must report incomplete when expected != captured or failures exist."""
    from scripts.ui_lab import capture_all as capture_all_module

    def broken(_context):
        raise RuntimeError("synthetic build failure")

    broken_spec = replace(list_scenarios()[0], build=broken)
    monkeypatch.setattr(capture_all_module, "list_scenarios", lambda: (broken_spec,))

    output = tmp_path / "artifacts"
    batch = capture_all_module.capture_all_scenarios(output, [broken_spec.id])
    run_dir = output / batch["run_id"]

    report = capture_all_module.verify_captured_artifacts(run_dir)
    assert report["complete"] is False
    assert report["reconciled"] is False
    assert len(report["failures"]) == 1
    assert report["failures"][0]["scenario_id"] == broken_spec.id
