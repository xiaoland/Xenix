from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts, capture_ui_snapshot
from xenix.ui.semantic_identity import identify


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
