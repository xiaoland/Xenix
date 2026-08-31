from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid


@dataclass(frozen=True)
class ScenarioContext:
    application: QApplication


@dataclass
class ScenarioHandle:
    """A built scenario with an explicit lifecycle ownership contract.

    - stop: the scenario stops its own tasks, timers, and connections.
    - cleanup: the idempotent public wrapper around stop.
    - close: stops tasks and closes the root window.
    - The host owns deleting the root QWidget; close never calls deleteLater,
      so pytest-qt can own deletion without a double free and the gallery can
      delete the root on scenario switch.
    """

    root: QWidget
    readiness: Callable[[], bool]
    stop: Callable[[], None]
    _stopped: bool = field(default=False, init=False, repr=False)

    def cleanup(self) -> None:
        """Idempotently stop the scenario's own tasks/timers/connections."""
        if self._stopped:
            return
        self._stopped = True
        self.stop()

    def close(self) -> None:
        """Stop scenario tasks and close the root window.

        The host owns deleting the root; this never calls deleteLater.
        Repeated calls are safe: cleanup is idempotent and QWidget.close is a
        no-op after the first close.
        """
        self.cleanup()
        if isValid(self.root):
            self.root.close()


ScenarioBuilder = Callable[[ScenarioContext], ScenarioHandle]


@dataclass(frozen=True)
class ScenarioSpec:
    id: str
    title: str
    description: str
    viewport_width: int
    viewport_height: int
    build: ScenarioBuilder
    style_name: str = "Fusion"
    locale_name: str = "en_US"
    font_family: str = "Segoe UI"
    font_point_size: int = 9

    def metadata(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "viewport": {
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            "render": {
                "style": self.style_name,
                "locale": self.locale_name,
                "font_family": self.font_family,
                "font_point_size": self.font_point_size,
            },
        }


def ready_immediately() -> bool:
    return True


def no_cleanup() -> None:
    return None
