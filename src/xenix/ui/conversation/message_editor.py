from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ...services.agent.harness_service import MessageDraft
from ..semantic_identity import identify


class UserMessageEditor(QDialog):
    def __init__(self, draft: MessageDraft, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit message"))
        self.resize(540, 360)
        self.editor = QPlainTextEdit(draft.text)
        self.attachment_list = QListWidget()
        self.attachment_list.setMaximumHeight(110)
        for attachment in draft.attachments:
            self._add_attachment(attachment.name, attachment.dataset_ids, tooltip=attachment.path or "")
        add = QPushButton(self.tr("Attach files"))
        remove = QPushButton(self.tr("Remove attachment"))
        add.clicked.connect(self._choose_files)
        remove.clicked.connect(self._remove_selected)
        remove.setEnabled(False)
        self.attachment_list.currentRowChanged.connect(lambda row: remove.setEnabled(row >= 0))
        actions = QHBoxLayout()
        actions.addWidget(QLabel(self.tr("Attachments")), 1)
        actions.addWidget(add)
        actions.addWidget(remove)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = buttons.addButton(self.tr("Save and send"), QDialogButtonBox.ButtonRole.AcceptRole)
        save.setDefault(False)
        save.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.editor.textChanged.connect(lambda: self._update_save(save))
        self.attachment_list.model().rowsInserted.connect(lambda *_: self._update_save(save))
        self.attachment_list.model().rowsRemoved.connect(lambda *_: self._update_save(save))
        identify(self.editor, "chat.message-editor.text")
        identify(self.attachment_list, "chat.message-editor.attachments")
        identify(save, "chat.message-editor.save")
        layout = QVBoxLayout(self)
        layout.addWidget(self.editor, 1)
        layout.addLayout(actions)
        layout.addWidget(self.attachment_list)
        layout.addWidget(buttons)
        self._update_save(save)
        self.editor.setFocus()

    def attachments(self) -> tuple[tuple[int, ...], tuple[str, ...]]:
        dataset_ids = []
        paths = []
        for index in range(self.attachment_list.count()):
            value = self.attachment_list.item(index).data(Qt.ItemDataRole.UserRole)
            if isinstance(value, str):
                paths.append(value)
            else:
                dataset_ids.extend(value)
        return tuple(dataset_ids), tuple(paths)

    def _add_attachment(self, name: str, value: tuple[int, ...] | str, *, tooltip: str) -> None:
        item = QListWidgetItem(name, self.attachment_list)
        item.setData(Qt.ItemDataRole.UserRole, value)
        item.setToolTip(tooltip)

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Attach files"), "", self.tr("Data files (*.csv *.xlsx *.xls)"),
        )
        existing = {self.attachment_list.item(index).toolTip() for index in range(self.attachment_list.count())}
        for raw_path in paths:
            path = Path(raw_path).resolve()
            if str(path) not in existing:
                self._add_attachment(path.name, str(path), tooltip=str(path))
                existing.add(str(path))

    def _remove_selected(self) -> None:
        row = self.attachment_list.currentRow()
        if row >= 0:
            self.attachment_list.takeItem(row)

    def _update_save(self, save: QPushButton) -> None:
        save.setEnabled(bool(self.editor.toPlainText().strip()) or self.attachment_list.count() > 0)
