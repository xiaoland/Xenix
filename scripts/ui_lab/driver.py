from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import sys

from PySide6.QtCore import QEventLoop, QLocale, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QRawFont
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from .contracts import ScenarioSpec


def configure_scenario_application(app: QApplication, scenario: ScenarioSpec) -> None:
    """Apply the render identity declared by a scenario before construction."""
    app.setStyle(scenario.style_name)
    _ensure_scenario_font(scenario.font_family)
    app.setFont(QFont(scenario.font_family, scenario.font_point_size))
    resolved = QFontInfo(app.font())
    raw_font = QRawFont.fromFont(app.font())
    if resolved.family().casefold() != scenario.font_family.casefold() or not all(
        raw_font.supportsCharacter(ord(character)) for character in "AaZz0123"
    ):
        raise RuntimeError(
            f"Scenario font {scenario.font_family!r} resolved to {resolved.family()!r}; "
            "capture requires the declared text font, not a fallback."
        )
    QLocale.setDefault(QLocale(scenario.locale_name))


def _ensure_scenario_font(family: str) -> None:
    # Qt's Windows offscreen backend can start without system font discovery.
    # Register installed files in this process only; never download/install fonts.
    if (
        sys.platform == "win32"
        and family == "Segoe UI"
        and family not in QFontDatabase.families()
    ):
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"):
            if QFontDatabase.addApplicationFont(str(fonts / filename)) < 0:
                raise RuntimeError(f"Cannot load required scenario font face: {filename}")


def settle_scenario(
    root: QWidget,
    readiness: Callable[[], bool],
    *,
    timeout_ms: int = 2_000,
) -> None:
    """Process Qt events until one scenario is visible and ready."""
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    timed_out = False
    root_deleted = False

    def inspect() -> None:
        nonlocal root_deleted
        if not isValid(root):
            root_deleted = True
            loop.quit()
        elif root.isVisible() and readiness():
            loop.quit()

    def timeout() -> None:
        nonlocal timed_out
        timed_out = True
        loop.quit()

    poll.timeout.connect(inspect)
    QTimer.singleShot(timeout_ms, timeout)
    poll.start()
    inspect()
    loop.exec()
    poll.stop()
    if root_deleted:
        raise RuntimeError("UI scenario root was deleted before it became ready")
    if timed_out:
        raise TimeoutError("UI scenario did not become ready before timeout")
