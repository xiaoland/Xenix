from __future__ import annotations

import json
import platform
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import PySide6
from PySide6.QtCore import QLocale, qVersion
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from .schema import (
    ArtifactFile,
    RectSnapshot,
    RenderEnvironment,
    UI_ARTIFACT_SCHEMA_VERSION,
    UiArtifactManifest,
)
from .snapshot import capture_ui_snapshot


class CapturePolicy(StrEnum):
    RUNTIME_REDACTED = "runtime-redacted"
    SYNTHETIC = "synthetic"


QT_LOG_MAX_BYTES = 32_768
QT_LOG_MAX_RECORDS = 200
QT_LOG_MAX_LINE_CHARS = 2_000
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/][^\s\"']+")


def capture_ui_artifacts(
    root: QWidget,
    output_dir: Path,
    *,
    reason: str,
    policy: CapturePolicy,
    scenario_id: str | None = None,
    qt_messages: tuple[str, ...] = (),
) -> UiArtifactManifest:
    if not isValid(root):
        raise ValueError("Cannot capture a deleted widget")
    output_dir.mkdir(parents=True, exist_ok=True)

    files: list[ArtifactFile] = []
    tree_path = output_dir / "tree.json"
    _write_json(tree_path, capture_ui_snapshot(root))
    files.append(_artifact_file(tree_path))

    if qt_messages:
        log_path = output_dir / "qt.log"
        log_path.write_text(_bounded_qt_log(qt_messages), encoding="utf-8")
        files.append(_artifact_file(log_path))

    if policy is CapturePolicy.SYNTHETIC:
        screenshot_path = output_dir / "actual.png"
        screenshot = root.grab()
        if not screenshot.save(str(screenshot_path), "PNG"):
            raise RuntimeError("Qt could not save the UI screenshot")
        screenshot_file = _artifact_file(screenshot_path)
        screenshot_file["pixel_width"] = screenshot.width()
        screenshot_file["pixel_height"] = screenshot.height()
        files.append(screenshot_file)

    manifest: UiArtifactManifest = {
        "schema_version": UI_ARTIFACT_SCHEMA_VERSION,
        "reason": reason,
        "scenario_id": scenario_id,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "policy": policy.value,
        "redaction": {
            "widget_text": "omitted",
            "paths": "redacted",
            "qt_log_max_bytes": QT_LOG_MAX_BYTES,
            "qt_log_max_records": QT_LOG_MAX_RECORDS,
        },
        "render_environment": _render_environment(root),
        "root_geometry": _root_geometry(root),
        "files": files,
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _render_environment(root: QWidget) -> RenderEnvironment:
    app = QApplication.instance()
    screen = root.screen()
    return {
        "python": platform.python_version(),
        "pyside": PySide6.__version__,
        "qt": qVersion(),
        "os": platform.platform(),
        "qpa": QApplication.platformName() if app is not None else "",
        "style": app.style().objectName() if isinstance(app, QApplication) else "",
        "locale": QLocale().name(),
        "logical_dpi": screen.logicalDotsPerInch() if screen is not None else None,
        "device_pixel_ratio": root.devicePixelRatioF(),
    }


def _root_geometry(root: QWidget) -> RectSnapshot:
    geometry = root.geometry()
    return {
        "x": geometry.x(),
        "y": geometry.y(),
        "width": geometry.width(),
        "height": geometry.height(),
    }


def _artifact_file(path: Path) -> ArtifactFile:
    return {"name": path.name, "bytes": path.stat().st_size}


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _redact_log_line(value: str) -> str:
    redacted = value.replace(str(Path.home()), "<home>")
    redacted = _WINDOWS_PATH.sub("<path>", redacted)
    for prefix in ("api_key=", "api-key=", "authorization=", "bearer "):
        index = redacted.casefold().find(prefix)
        if index >= 0:
            redacted = redacted[: index + len(prefix)] + "<redacted>"
    return redacted


def _bounded_qt_log(messages: tuple[str, ...]) -> str:
    chunks: list[str] = []
    used_bytes = 0
    for message in messages[:QT_LOG_MAX_RECORDS]:
        line = _redact_log_line(message)[:QT_LOG_MAX_LINE_CHARS] + "\n"
        encoded = line.encode("utf-8")
        remaining = QT_LOG_MAX_BYTES - used_bytes
        if remaining <= 0:
            break
        if len(encoded) > remaining:
            encoded = encoded[:remaining]
            line = encoded.decode("utf-8", errors="ignore")
        chunks.append(line)
        used_bytes += len(line.encode("utf-8"))
    return "".join(chunks)
