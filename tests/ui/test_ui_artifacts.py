from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from scripts.ui_lab import artifact_index as artifact_index_module
from scripts.ui_lab.artifact_index import build_artifact_index
from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts, capture_ui_snapshot
from xenix.ui.diagnostics import snapshot as snapshot_module
from xenix.ui.semantic_identity import identify, identify_repeated_item


def _artifact_widget(qtbot: QtBot) -> QWidget:
    root = QWidget()
    root.setObjectName("artifactRoot")
    root.resize(360, 180)
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    nested = QHBoxLayout()
    first = identify(QPushButton("private visible text"), "test.action.duplicate")
    second = identify(QPushButton("other private text"), "test.action.duplicate")
    secret = QLineEdit("super-secret-value")
    choices = QComboBox()
    choices.addItems(["private-model-a", "private-model-b"])
    choices.setCurrentIndex(1)
    nested.addWidget(first)
    nested.addSpacing(12)
    nested.addWidget(second)
    layout.addLayout(nested)
    layout.addWidget(secret)
    layout.addWidget(choices)
    return root


def _ownership_nodes(node):
    yield node
    for child in node["children"]:
        yield from _ownership_nodes(child)


def _layout_kinds(node):
    for item in node["items"]:
        yield item["kind"]
        child = item.get("child_layout")
        if child is not None:
            yield from _layout_kinds(child)


def test_snapshot_keeps_ownership_and_layout_relations_without_widget_text(qtbot: QtBot) -> None:
    root = _artifact_widget(qtbot)

    snapshot = capture_ui_snapshot(root)
    serialized = json.dumps(snapshot, sort_keys=True)
    nodes = list(_ownership_nodes(snapshot["ownership"]))

    assert "super-secret-value" not in serialized
    assert "private-model" not in serialized
    assert "private visible text" not in serialized
    assert sum(node["semantic_id"] == "test.action.duplicate" for node in nodes) == 2
    assert snapshot["layout"] is not None
    assert {"layout", "widget", "spacer"} <= set(_layout_kinds(snapshot["layout"]))


def test_snapshot_outputs_item_reference_for_repeated_controls(qtbot: QtBot) -> None:
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    chip = identify_repeated_item(
        QPushButton("remove"),
        role="chat.composer.attachment",
        item_reference="attachment:01J8A",
    )
    layout.addWidget(chip)

    snapshot = capture_ui_snapshot(root)
    nodes = list(_ownership_nodes(snapshot["ownership"]))

    repeated = [node for node in nodes if node.get("item_reference") == "attachment:01J8A"]
    assert len(repeated) == 1
    assert repeated[0]["semantic_id"] == "chat.composer.attachment"


def test_capture_policy_controls_pixels_and_bounds_redacted_logs(qtbot: QtBot, tmp_path) -> None:
    root = _artifact_widget(qtbot)
    root.show()
    qtbot.waitUntil(root.isVisible)
    messages = (
        r"failed C:\Users\person\private\report.csv api_key=secret-value",
        "x" * 40_000,
    )

    runtime_dir = tmp_path / "runtime"
    runtime_manifest = capture_ui_artifacts(
        root,
        runtime_dir,
        reason="runtime-probe",
        policy=CapturePolicy.RUNTIME_REDACTED,
        qt_messages=messages,
    )
    synthetic_dir = tmp_path / "synthetic"
    synthetic_manifest = capture_ui_artifacts(
        root,
        synthetic_dir,
        reason="synthetic-probe",
        scenario_id="test.artifact.widget",
        policy=CapturePolicy.SYNTHETIC,
    )

    assert not (runtime_dir / "actual.png").exists()
    assert (synthetic_dir / "actual.png").stat().st_size > 0
    assert (runtime_dir / "qt.log").stat().st_size <= 32_768
    log = (runtime_dir / "qt.log").read_text(encoding="utf-8")
    assert "person" not in log
    assert "secret-value" not in log
    assert runtime_manifest["redaction"]["widget_text"] == "omitted"
    assert synthetic_manifest["render_environment"]["font"]["family"]
    screenshot = next(file for file in synthetic_manifest["files"] if file["name"] == "actual.png")
    assert screenshot["pixel_width"] > 0
    assert screenshot["pixel_height"] > 0


def test_deleted_widget_is_rejected_without_touching_cpp_state(qapp, qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(widget, QEvent.DeferredDelete)

    with pytest.raises(ValueError, match="deleted"):
        capture_ui_snapshot(widget)


def test_artifact_index_projects_only_bounded_manifest_metadata(qtbot: QtBot, tmp_path) -> None:
    root = _artifact_widget(qtbot)
    root.show()
    qtbot.waitUntil(root.isVisible)
    artifact_root = tmp_path / "ui-artifacts"
    capture_ui_artifacts(
        root,
        artifact_root / "scenario" / "sample",
        reason="capture-only",
        scenario_id="sample.visual",
        policy=CapturePolicy.SYNTHETIC,
    )

    index = build_artifact_index(artifact_root)

    assert index["artifact_count"] == 1
    assert index["artifacts"][0]["path"] == "scenario/sample"
    assert index["artifacts"][0]["scenario_id"] == "sample.visual"
    assert "super-secret-value" not in json.dumps(index)


def test_capture_removes_stale_artifacts_from_reused_directory(qtbot: QtBot, tmp_path) -> None:
    root = _artifact_widget(qtbot)
    root.show()
    qtbot.waitUntil(root.isVisible)
    destination = tmp_path / "reused"

    capture_ui_artifacts(
        root, destination, reason="synthetic", scenario_id="test.reuse", policy=CapturePolicy.SYNTHETIC
    )
    assert (destination / "actual.png").exists()

    capture_ui_artifacts(
        root,
        destination,
        reason="runtime",
        policy=CapturePolicy.RUNTIME_REDACTED,
        qt_messages=("api_key=secret",),
    )
    assert not (destination / "actual.png").exists()
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert {file["name"] for file in manifest["files"]} == {"tree.json", "qt.log"}


def test_snapshot_counts_layout_items_toward_node_budget(qtbot: QtBot, monkeypatch) -> None:
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    for _ in range(20):
        layout.addSpacing(4)

    monkeypatch.setattr(snapshot_module, "MAX_UI_SNAPSHOT_NODES", 5)
    snapshot = capture_ui_snapshot(root)

    assert snapshot["layout"] is not None
    assert snapshot["layout"]["truncated"] is True
    assert len(snapshot["layout"]["items"]) < 20


def test_artifact_index_is_bounded_by_count(qtbot: QtBot, tmp_path, monkeypatch) -> None:
    root = _artifact_widget(qtbot)
    root.show()
    qtbot.waitUntil(root.isVisible)
    artifact_root = tmp_path / "ui-artifacts"
    for index in (1, 2):
        capture_ui_artifacts(
            root,
            artifact_root / f"case{index}",
            reason="capture-only",
            scenario_id=f"sample.{index}",
            policy=CapturePolicy.SYNTHETIC,
        )

    monkeypatch.setattr(artifact_index_module, "MAX_INDEX_ARTIFACTS", 1)
    index = build_artifact_index(artifact_root)

    assert index["artifact_count"] == 1
    assert index["truncated"] is True
