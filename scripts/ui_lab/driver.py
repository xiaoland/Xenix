from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEventLoop, QLocale, QTimer
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from .contracts import ScenarioSpec


def configure_scenario_application(app: QApplication, scenario: ScenarioSpec) -> None:
    """Apply the render identity declared by a scenario before construction."""
    app.setStyle(scenario.style_name)
    QLocale.setDefault(QLocale(scenario.locale_name))


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

    def inspect() -> None:
        if not isValid(root) or (root.isVisible() and readiness()):
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
    if timed_out:
        raise TimeoutError("UI scenario did not become ready before timeout")
