from __future__ import annotations

import json
from pathlib import Path


def _probe_conftest() -> str:
    repository_root = Path(__file__).resolve().parents[2]
    return f"""
import os
import sys
sys.path.insert(0, {str(repository_root)!r})
sys.path.insert(0, {str(repository_root / "src")!r})
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest_plugins = ["tests.ui.pytest_plugin"]
from tests.ui.conftest import ui_render_environment
"""


def _artifact_manifests(output: Path) -> list[Path]:
    return list(output.glob("*/*/manifest.json"))


def test_assertion_failure_publishes_registered_root(pytester, monkeypatch) -> None:
    output = pytester.path / "artifacts"
    monkeypatch.setenv("XENIX_UI_ARTIFACT_DIR", str(output))
    pytester.makeconftest(_probe_conftest())
    pytester.makepyfile(
        """
from PySide6.QtWidgets import QLabel

def test_failure(qtbot, ui_artifacts):
    root = QLabel("synthetic failure")
    root.resize(240, 60)
    qtbot.addWidget(root)
    ui_artifacts.register(root, name="probe")
    assert False, "intentional probe"
"""
    )

    result = pytester.runpytest_subprocess("-q")

    result.assert_outcomes(failed=1)
    manifest_path = _artifact_manifests(output)[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["reason"] == "pytest-call-failure"
    assert manifest["capture_phase"] == "call"
    assert (manifest_path.parent / "actual.png").stat().st_size > 0


def test_qt_log_failure_is_visible_to_capture_wrapper(pytester, monkeypatch) -> None:
    output = pytester.path / "artifacts"
    monkeypatch.setenv("XENIX_UI_ARTIFACT_DIR", str(output))
    pytester.makeconftest(_probe_conftest())
    pytester.makepyfile(
        """
import pytest
from PySide6.QtCore import qCritical
from PySide6.QtWidgets import QLabel

@pytest.mark.qt_log_level_fail("CRITICAL")
def test_qt_log_failure(qtbot, ui_artifacts):
    root = QLabel("synthetic qt log failure")
    qtbot.addWidget(root)
    ui_artifacts.register(root, name="probe")
    qCritical("synthetic critical message")
"""
    )

    result = pytester.runpytest_subprocess("-q")

    result.assert_outcomes(failed=1)
    manifest_path = _artifact_manifests(output)[0]
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["reason"] == "pytest-call-failure"
    assert "synthetic critical message" in (manifest_path.parent / "qt.log").read_text(encoding="utf-8")


def test_teardown_failure_promotes_pre_cleanup_snapshot(pytester, monkeypatch) -> None:
    output = pytester.path / "artifacts"
    monkeypatch.setenv("XENIX_UI_ARTIFACT_DIR", str(output))
    pytester.makeconftest(_probe_conftest())
    pytester.makepyfile(
        """
import pytest
from PySide6.QtWidgets import QLabel

@pytest.fixture()
def fail_after_test():
    yield
    raise RuntimeError("intentional teardown probe")

def test_teardown_failure(qtbot, ui_artifacts, fail_after_test):
    root = QLabel("present before cleanup")
    root.resize(240, 60)
    qtbot.addWidget(root)
    ui_artifacts.register(root, name="probe")
"""
    )

    result = pytester.runpytest_subprocess("-q")

    result.assert_outcomes(passed=1, errors=1)
    manifest_path = _artifact_manifests(output)[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["reason"] == "pytest-teardown-failure"
    assert manifest["capture_phase"] == "pre-teardown"
    assert (manifest_path.parent / "tree.json").stat().st_size > 0
