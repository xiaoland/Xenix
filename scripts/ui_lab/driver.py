from __future__ import annotations

import os
import sys
import warnings
from collections.abc import Callable
from functools import cache
from pathlib import Path

from PySide6.QtCore import QEventLoop, QLocale, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QRawFont
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from .contracts import ScenarioSpec


def configure_scenario_application(
    app: QApplication, scenario: ScenarioSpec, *, strict_font: bool = True
) -> None:
    """Apply the scenario's render settings before construction."""
    app.setStyle(scenario.style_name)
    try:
        font = _scenario_font(scenario.font_family, scenario.font_point_size)
    except RuntimeError:
        if strict_font:
            raise
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        _warn_scenario_font_fallback()
    app.setFont(font)
    QLocale.setDefault(QLocale(scenario.locale_name))


@cache
def _warn_scenario_font_fallback() -> None:
    warnings.warn(
        "A declared UI scenario font is unavailable. Widget contracts use the platform default font. "
        "Deterministic capture requires the declared font.",
        stacklevel=2,
    )


def _scenario_font(family: str, point_size: int) -> QFont:
    _ensure_scenario_font(family)
    font = QFont(family, point_size)
    resolved = QFontInfo(font)
    raw_font = QRawFont.fromFont(font)
    if resolved.family().casefold() != family.casefold() or not all(
        raw_font.supportsCharacter(ord(character)) for character in "AaZz0123"
    ):
        raise RuntimeError(
            f"Scenario font {family!r} resolved to {resolved.family()!r}; "
            "capture requires the declared text font, not a fallback."
        )
    return font


def _ensure_scenario_font(family: str) -> None:
    # Qt's Windows offscreen backend can start without system font discovery.
    # Register installed files in this process only; never download/install fonts.
    if (
        sys.platform == "win32"
        and family in {"Segoe UI", "Microsoft YaHei"}
        and family not in QFontDatabase.families()
    ):
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in (("msyh.ttc", "msyhbd.ttc", "msyhl.ttc") if family == "Microsoft YaHei" else ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf")):
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
