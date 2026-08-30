from __future__ import annotations

import os


os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout
from pytestqt.qtbot import QtBot

from scripts.ui_lab.contracts import ScenarioContext
from scripts.ui_lab.driver import configure_scenario_application
from scripts.ui_lab.registry import get_scenario
from tests.ui.pytest_plugin import UiArtifactRegistry
from xenix.ui.chatbot import ChatMessageBubble, ThreadDetailView


def test_native_chat_window_expose_focus_dialog_and_user_bubble(
    qapp: QApplication,
    qtbot: QtBot,
    ui_artifacts: UiArtifactRegistry,
) -> None:
    assert QApplication.platformName() == "windows"
    scenario = get_scenario("chat.mixed-timeline")
    configure_scenario_application(qapp, scenario)
    handle = scenario.build(ScenarioContext(qapp))
    view = handle.root
    assert isinstance(view, ThreadDetailView)
    qtbot.addWidget(view)
    ui_artifacts.register(view, name="chat-native-window")
    view.resize(scenario.viewport_width, scenario.viewport_height)

    with qtbot.waitExposed(view, timeout=5_000):
        view.show()
    with qtbot.waitActive(view, timeout=5_000):
        view.raise_()
        view.activateWindow()
    view._editor.setFocus(Qt.FocusReason.OtherFocusReason)
    qtbot.waitUntil(lambda: qapp.focusWidget() is view._editor, timeout=5_000)

    user_bubble = next(
        bubble
        for bubble in view.findChildren(ChatMessageBubble)
        if bubble._author == "You"
    )
    for width in (760, 980):
        previous_card_width = user_bubble._card.width()
        view.resize(width, scenario.viewport_height)
        qtbot.waitUntil(
            lambda target_width=width, prior_width=previous_card_width: (
                view.width() == target_width and user_bubble._card.width() != prior_width
            ),
            timeout=5_000,
        )
        user_bubble._card.repaint()
        image = user_bubble._card.grab().toImage()
        assert image.width() > 0 and image.height() > 0
        assert _is_black(image.pixelColor(2, 2))

    dialog = QDialog(view)
    dialog.setWindowTitle("Synthetic native dialog")
    dialog_editor = QLineEdit(dialog)
    QVBoxLayout(dialog).addWidget(dialog_editor)
    qtbot.addWidget(dialog)
    with qtbot.waitExposed(dialog, timeout=5_000):
        dialog.show()
    with qtbot.waitActive(dialog, timeout=5_000):
        dialog.raise_()
        dialog.activateWindow()
    dialog_editor.setFocus(Qt.FocusReason.OtherFocusReason)
    qtbot.waitUntil(lambda: qapp.focusWidget() is dialog_editor, timeout=5_000)
    dialog.accept()
    handle.close()


def _is_black(color: QColor) -> bool:
    return color.red() <= 8 and color.green() <= 8 and color.blue() <= 8
