from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid


@dataclass(frozen=True)
class ScenarioContext:
    application: QApplication


@dataclass
class ScenarioHandle:
    root: QWidget
    readiness: Callable[[], bool]
    cleanup: Callable[[], None]

    def close(self) -> None:
        self.cleanup()
        if isValid(self.root):
            self.root.close()
            self.root.deleteLater()


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
            },
        }


def ready_immediately() -> bool:
    return True


def no_cleanup() -> None:
    return None
