from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ..semantic_identity import identify


@dataclass(frozen=True)
class QueuedMessage:
    submission_id: str
    text: str
    attachment_count: int
    steering: bool
    editing: bool = False
    failure: str = ""


class MessageQueuePanel(QWidget):
    remove_requested = Signal(str)
    restore_requested = Signal(str)
    resume_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._title = QLabel()
        self._items = QListWidget()
        self._items.setMaximumHeight(104)
        self._items.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._remove = QPushButton()
        self._restore = QPushButton()
        self._resume = QPushButton()
        self._restore.setEnabled(False)
        self._remove.setEnabled(False)
        self._remove.clicked.connect(lambda: self._emit_selected(self.remove_requested.emit))
        self._restore.clicked.connect(lambda: self._emit_selected(self.restore_requested.emit))
        self._resume.clicked.connect(self.resume_requested.emit)
        self._items.currentItemChanged.connect(self._sync_buttons)
        header = QHBoxLayout()
        header.addWidget(self._title, 1)
        header.addWidget(self._resume)
        header.addWidget(self._restore)
        header.addWidget(self._remove)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._items)
        identify(self._items, "chat.queue.messages")
        identify(self._remove, "chat.queue.remove")
        identify(self._restore, "chat.queue.restore")
        identify(self._resume, "chat.queue.resume")
        self._rows: tuple[QueuedMessage, ...] = ()
        self._paused = False
        self.retranslate_ui()

    def set_messages(self, messages: tuple[QueuedMessage, ...], *, paused: bool) -> None:
        self._rows = messages
        self._paused = paused
        selected = self._selected_id()
        self._items.clear()
        for message in messages:
            if message.failure:
                label = self.tr("Failed")
            elif message.editing:
                label = self.tr("Edit message")
            elif message.steering:
                label = self.tr("Steer")
            else:
                label = self.tr("Queued")
            preview = " ".join(message.text.split())[:160]
            if message.attachment_count:
                attachments = self.tr("%n attachment(s)", "", message.attachment_count)
                preview = f"{preview} · {attachments}" if preview else attachments
            item = QListWidgetItem(f"{label} · {preview}", self._items)
            item.setData(Qt.ItemDataRole.UserRole, message.submission_id)
            item.setToolTip(message.failure)
            if message.submission_id == selected:
                self._items.setCurrentItem(item)
        self._resume.setVisible(paused and any(not message.failure for message in messages))
        self._sync_buttons()
        self.setVisible(bool(messages))

    def retranslate_ui(self) -> None:
        self._title.setText(self.tr("Message queue"))
        self._items.setAccessibleName(self.tr("Message queue"))
        self._remove.setText(self.tr("Remove from queue"))
        self._restore.setText(self.tr("Restore draft"))
        self._resume.setText(self.tr("Resume queue"))
        self.set_messages(self._rows, paused=self._paused)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _selected_id(self) -> str | None:
        item = self._items.currentItem()
        return cast(str, item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _sync_buttons(self) -> None:
        selected = self._selected_id()
        self._remove.setEnabled(selected is not None)
        self._restore.setEnabled(any(row.submission_id == selected and not row.editing for row in self._rows))

    def _emit_selected(self, callback: Callable[[str], None]) -> None:
        if (selected := self._selected_id()) is not None:
            callback(selected)
