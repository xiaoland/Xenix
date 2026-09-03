from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from xenix.ui.settings_dialog import SettingsTab
from xenix.ui.windows.auxiliary import AuxiliaryWindowCoordinator


class _SettingsWindow(QWidget):
    agent_settings_saved = Signal()
    software_update_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.tabs: list[SettingsTab] = []
        self.shutdown_calls = 0
        self.update_active: list[bool] = []
        self.retranslate_calls = 0
        self.language_change_calls = 0

    def show_tab(self, tab: SettingsTab) -> None:
        self.tabs.append(tab)

    def set_update_operation_active(self, active: bool) -> None:
        self.update_active.append(active)

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def retranslate_ui(self) -> None:
        self.retranslate_calls += 1

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.language_change_calls += 1
        super().changeEvent(event)


class _KnowledgeWindow(QWidget):
    def __init__(self, parent: QWidget, open_settings: Callable[[], None]) -> None:
        super().__init__(parent)
        self.open_settings = open_settings
        self.shutdown_calls = 0
        self.retranslate_calls = 0
        self.language_change_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def retranslate_ui(self) -> None:
        self.retranslate_calls += 1

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.language_change_calls += 1
        super().changeEvent(event)


class _DetailWindow(QWidget):
    pass


class _UpdateController(QWidget):
    operation_active_changed = Signal(bool)

    def __init__(self, *, can_auto_check: bool = False) -> None:
        super().__init__()
        self.can_auto_check = can_auto_check
        self.active = False
        self.request_calls = 0
        self.auto_check_calls = 0
        self.retranslate_calls = 0
        self.shutdown_calls = 0

    def request_update(self) -> None:
        self.request_calls += 1

    def start_background_check(self) -> None:
        self.auto_check_calls += 1

    def retranslate_ui(self) -> None:
        self.retranslate_calls += 1

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def test_lazily_creates_windows_wires_updates_and_preserves_parent(qtbot: QtBot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    settings: list[_SettingsWindow] = []
    knowledge: list[_KnowledgeWindow] = []
    details: list[_DetailWindow] = []
    update = _UpdateController()
    coordinator = AuxiliaryWindowCoordinator(
        owner,
        settings_factory=lambda parent: settings.append(_SettingsWindow(parent)) or settings[-1],
        knowledge_factory=lambda parent, open_settings: knowledge.append(
            _KnowledgeWindow(parent, open_settings)
        ) or knowledge[-1],
        detail_factory=lambda parent, _ids: details.append(_DetailWindow(parent)) or details[-1],
        update_controller=update,  # type: ignore[arg-type]
    )
    saved: list[None] = []
    coordinator.settings_saved.connect(lambda: saved.append(None))

    coordinator.show_settings()
    coordinator.show_settings(tab=SettingsTab.KNOWLEDGE_BASE)
    coordinator.show_knowledge()
    coordinator.show_tool_call_detail(task_ids=["task-1"])

    assert len(settings) == 1
    assert settings[0].parent() is owner
    assert settings[0].tabs == [SettingsTab.AI, SettingsTab.KNOWLEDGE_BASE]
    assert settings[0].update_active == [False]
    assert len(knowledge) == 1
    assert knowledge[0].parent() is owner
    assert len(details) == 1
    settings[0].agent_settings_saved.emit()
    settings[0].software_update_requested.emit()
    assert saved == [None]
    assert update.request_calls == 1

    knowledge[0].open_settings()
    assert settings[0].tabs[-1] is SettingsTab.KNOWLEDGE_BASE


def test_retranslate_shutdown_and_post_shutdown_requests_are_safe(qtbot: QtBot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    settings: list[_SettingsWindow] = []
    knowledge: list[_KnowledgeWindow] = []
    details: list[_DetailWindow] = []
    update = _UpdateController()
    coordinator = AuxiliaryWindowCoordinator(
        owner,
        settings_factory=lambda parent: settings.append(_SettingsWindow(parent)) or settings[-1],
        knowledge_factory=lambda parent, callback: knowledge.append(
            _KnowledgeWindow(parent, callback)
        ) or knowledge[-1],
        detail_factory=lambda parent, _ids: details.append(_DetailWindow(parent)) or details[-1],
        update_controller=update,  # type: ignore[arg-type]
    )
    coordinator.show_settings()
    coordinator.show_knowledge()
    coordinator.show_tool_call_detail(task_ids=["task-1"])
    coordinator.retranslate_ui()
    coordinator.shutdown()
    coordinator.shutdown()
    coordinator.show_settings()
    coordinator.show_knowledge()
    coordinator.show_tool_call_detail(task_ids=["task-2"])

    assert settings[0].retranslate_calls == 1
    assert knowledge[0].retranslate_calls == 1
    assert update.retranslate_calls == 1
    assert settings[0].shutdown_calls == 1
    assert knowledge[0].shutdown_calls == 1
    assert update.shutdown_calls == 1
    update.operation_active_changed.emit(True)
    assert settings[0].update_active == [False]
    assert len(settings) == len(knowledge) == len(details) == 1


def test_language_change_reaches_visible_parented_windows(qtbot: QtBot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    settings: list[_SettingsWindow] = []
    knowledge: list[_KnowledgeWindow] = []
    coordinator = AuxiliaryWindowCoordinator(
        owner,
        settings_factory=lambda parent: settings.append(_SettingsWindow(parent)) or settings[-1],
        knowledge_factory=lambda parent, callback: knowledge.append(
            _KnowledgeWindow(parent, callback)
        ) or knowledge[-1],
        detail_factory=lambda parent, _ids: _DetailWindow(parent),
    )
    owner.show()
    coordinator.show_settings()
    coordinator.show_knowledge()

    QCoreApplication.sendEvent(owner, QEvent(QEvent.LanguageChange))

    assert settings[0].language_change_calls == 1
    assert knowledge[0].language_change_calls == 1


def test_auto_check_is_coordinator_owned_and_stops_on_shutdown(qtbot: QtBot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    update = _UpdateController(can_auto_check=True)
    coordinator = AuxiliaryWindowCoordinator(
        owner,
        settings_factory=lambda parent: _SettingsWindow(parent),
        knowledge_factory=None,
        detail_factory=lambda parent, _ids: _DetailWindow(parent),
        update_controller=update,  # type: ignore[arg-type]
    )

    qtbot.waitUntil(lambda: update.auto_check_calls == 1, timeout=2_000)
    coordinator.shutdown()
    assert update.auto_check_calls == 1
