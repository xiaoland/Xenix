from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFormLayout, QKeySequenceEdit, QLabel, QWidget

from ..conversation.shortcuts import ConversationShortcuts, PORTABLE
from ..semantic_identity import identify


class ShortcutSettingsEditor(QWidget):
    def __init__(self, shortcuts: ConversationShortcuts) -> None:
        super().__init__()
        self._send_label = QLabel()
        self._steer_label = QLabel()
        self.send_editor = QKeySequenceEdit(QKeySequence.fromString(shortcuts.send, PORTABLE))
        self.steer_editor = QKeySequenceEdit(QKeySequence.fromString(shortcuts.steer, PORTABLE))
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for label, editor, identifier in (
            (self._send_label, self.send_editor, "settings.shortcuts.send"),
            (self._steer_label, self.steer_editor, "settings.shortcuts.steer"),
        ):
            editor.setMaximumSequenceLength(1)
            label.setBuddy(editor)
            identify(editor, identifier)
            layout.addRow(label, editor)
        self.retranslate_ui()

    def current_settings(self) -> ConversationShortcuts:
        return ConversationShortcuts(
            send=self.send_editor.keySequence().toString(PORTABLE),
            steer=self.steer_editor.keySequence().toString(PORTABLE),
        )

    def retranslate_ui(self) -> None:
        self._send_label.setText(self.tr("Send or queue a message"))
        self._steer_label.setText(self.tr("Steer the conversation"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
