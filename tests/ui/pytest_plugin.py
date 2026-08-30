from __future__ import annotations

import json
import os
import re
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts


_SAFE_NAME = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")
_REGISTRY_KEY: pytest.StashKey[UiArtifactRegistry] = pytest.StashKey()


@dataclass(frozen=True)
class _RegisteredRoot:
    name: str
    root: QWidget


class UiArtifactRegistry:
    def __init__(self, request: pytest.FixtureRequest, qtlog) -> None:
        self._item = request.node
        self._config = request.config
        self._qtlog = qtlog
        self._roots: list[_RegisteredRoot] = []
        self._staging_dir: Path | None = None

    def register(self, root: QWidget, *, name: str) -> None:
        if _SAFE_NAME.fullmatch(name) is None:
            raise ValueError("UI artifact root name must be a stable lowercase role")
        if any(registered.name == name for registered in self._roots):
            raise ValueError(f"UI artifact root name is already registered: {name}")
        if not isValid(root):
            raise ValueError("Cannot register a deleted widget")
        # Keep the explicitly registered root alive until pytest-qt cleanup.
        # qtbot itself intentionally stores only weak references.
        self._roots.append(_RegisteredRoot(name, root))

    @property
    def has_roots(self) -> bool:
        return bool(self._roots)

    def publish_call_failure(self) -> None:
        self._capture(self._published_dir(), reason="pytest-call-failure")

    def stage_before_teardown(self) -> None:
        self._staging_dir = self._basetemp() / "ui-artifact-staging" / _safe_test_id(self._item.nodeid)
        self._capture(self._staging_dir, reason="pytest-pre-teardown")

    def publish_teardown_failure(self) -> None:
        if self._staging_dir is None or not self._staging_dir.exists():
            return
        destination = self._published_dir()
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self._staging_dir, destination, dirs_exist_ok=True)
        index_path = destination / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["reason"] = "pytest-teardown-failure"
        _write_json(index_path, index)
        for manifest_path in destination.glob("*/manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reason"] = "pytest-teardown-failure"
            _write_json(manifest_path, manifest)
        self._roots.clear()

    def discard_staging(self) -> None:
        if self._staging_dir is not None and self._staging_dir.exists():
            shutil.rmtree(self._staging_dir)
        self._roots.clear()

    def _capture(self, destination: Path, *, reason: str) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        captured_names: list[str] = []
        messages = tuple(record.message for record in self._qtlog.records)
        for registered in self._roots:
            root = registered.root
            if not isValid(root):
                continue
            capture_ui_artifacts(
                root,
                destination / registered.name,
                reason=reason,
                scenario_id=None,
                policy=CapturePolicy.SYNTHETIC,
                qt_messages=messages,
            )
            captured_names.append(registered.name)
        _write_json(
            destination / "index.json",
            {
                "schema_version": 1,
                "test_id": self._item.nodeid,
                "reason": reason,
                "roots": captured_names,
            },
        )

    def _published_dir(self) -> Path:
        configured = os.environ.get("XENIX_UI_ARTIFACT_DIR", "ui-artifacts")
        return Path(configured).resolve() / _safe_test_id(self._item.nodeid)

    def _basetemp(self) -> Path:
        configured = self._config.getoption("basetemp")
        return Path(configured).resolve() if configured else Path.cwd().resolve() / ".pytest-ui-staging"


@pytest.fixture()
def ui_artifacts(request: pytest.FixtureRequest, qtlog) -> UiArtifactRegistry:
    registry = UiArtifactRegistry(request, qtlog)
    request.node.stash[_REGISTRY_KEY] = registry
    return registry


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    report = yield
    registry = item.stash.get(_REGISTRY_KEY, None)
    if registry is None or not registry.has_roots:
        return report
    try:
        if report.when == "call":
            if report.failed:
                registry.publish_call_failure()
            else:
                registry.stage_before_teardown()
        elif report.when == "teardown":
            if report.failed:
                registry.publish_teardown_failure()
            else:
                registry.discard_staging()
    except Exception as exc:
        warnings.warn(
            pytest.PytestWarning(f"UI failure artifact capture failed: {exc}"),
            stacklevel=2,
        )
    return report


def _safe_test_id(nodeid: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", nodeid).strip("-.")
    return safe[:180] or "ui-test"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
