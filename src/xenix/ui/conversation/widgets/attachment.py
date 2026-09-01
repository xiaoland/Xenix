"""Composer attachment chip."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ...icons import remove_icon, spinner_icon, status_error_icon
from ...semantic_identity import identify_repeated_item
from ..presentation import ComposerAttachmentState, ComposerAttachmentStatus


class AttachmentChip(QFrame):
    remove_requested = Signal(str)

    def __init__(self, state: ComposerAttachmentState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = state.path
        self.setObjectName("attachmentChip")
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(6)
        name_label = QLabel(Path(state.path).name)
        name_label.setObjectName("attachmentChipLabel")
        status_label = QLabel()
        status_label.setObjectName("attachmentChipStatus")
        status_label.setFixedWidth(16)
        status_label.setAlignment(Qt.AlignCenter)
        remove_button = QToolButton()
        remove_button.setObjectName("attachmentChipRemoveButton")
        remove_button.setFixedSize(18, 18)
        remove_button.setIcon(remove_icon())
        remove_button.setIconSize(QSize(12, 12))
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self.path))
        self._status_label = status_label
        self._remove_button = remove_button
        layout.addWidget(name_label)
        layout.addWidget(status_label)
        layout.addWidget(remove_button)
        identify_repeated_item(
            self,
            role="chat.composer.attachment",
            item_reference=state.path,
        )
        identify_repeated_item(
            remove_button,
            role="chat.composer.attachment.remove",
            item_reference=state.path,
        )
        self.set_state(state)

    def set_state(self, state: ComposerAttachmentState) -> None:
        self.path = state.path
        if state.status is ComposerAttachmentStatus.PENDING:
            self._status_label.clear()
            self._status_label.setPixmap(spinner_icon().pixmap(QSize(12, 12)))
        elif state.status is ComposerAttachmentStatus.FAILED:
            self._status_label.clear()
            self._status_label.setPixmap(status_error_icon().pixmap(QSize(12, 12)))
        else:
            self._status_label.clear()
            self._status_label.setPixmap(QPixmap())
        self._status_label.setProperty("attachmentStatus", state.status.value)
        self.setProperty("attachmentStatus", state.status.value)
        self._status_label.setToolTip(state.error or "")

    def set_removal_enabled(self, enabled: bool) -> None:
        self._remove_button.setEnabled(enabled)
