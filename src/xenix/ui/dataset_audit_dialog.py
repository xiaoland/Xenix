"""Modeless, session-scoped view over the Datasets a conversation produced."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services.dataset_service import DatasetAuditPresentation

if TYPE_CHECKING:
    from ..services.agent.harness_service import AgentHarnessService


class DatasetAuditDialog(QDialog):
    """Independent, modeless audit of the datasets one conversation produced.

    Storage owns the derivation records; this dialog is a read-only projection
    resolved through the Agent Harness for the active conversation Thread.
    """

    def __init__(
        self,
        *,
        harness: AgentHarnessService,
        thread_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._harness = harness
        self._thread_id = thread_id
        self._audits: list[DatasetAuditPresentation] = []

        self._table = QTableWidget(0, 5, self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.itemSelectionChanged.connect(self._render_detail)

        self._empty_label = QLabel(self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._detail = QTextEdit(self)
        self._detail.setReadOnly(True)

        self._refresh_button = QPushButton(self)
        self._refresh_button.clicked.connect(self.refresh)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._refresh_button)
        actions.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table, 3)
        layout.addWidget(self._empty_label, 1)
        layout.addWidget(self._detail, 2)
        layout.addLayout(actions)
        self.resize(780, 540)
        self.retranslate_ui()
        self.refresh()

    def set_thread_id(self, thread_id: str) -> None:
        self._thread_id = thread_id
        self.refresh()

    def refresh(self) -> None:
        try:
            self._audits = self._harness.resolve_session_dataset_audits(self._thread_id)
        except Exception:
            # Read-only projection: a deleted Thread or a failed read must not
            # take the audit window down; it degrades to an empty list.
            self._audits = []
        self._render_table()
        self._render_detail()

    def _render_table(self) -> None:
        selected = self._selected_dataset_id()
        self._table.setRowCount(len(self._audits))
        selected_row = -1
        for row_index, audit in enumerate(self._audits):
            values = (
                audit.name,
                str(audit.generation),
                audit.operation_name,
                str(len(audit.inputs)),
                audit.created_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, audit)
                self._table.setItem(row_index, column, item)
            if audit.dataset_id == selected:
                selected_row = row_index
        if selected_row >= 0:
            self._table.selectRow(selected_row)
        has_audits = bool(self._audits)
        self._table.setVisible(has_audits)
        self._empty_label.setVisible(not has_audits)
        self._detail.setVisible(has_audits)

    def _selected_dataset_id(self) -> str | None:
        audit = self._selected_audit()
        return audit.dataset_id if audit is not None else None

    def _selected_audit(self) -> DatasetAuditPresentation | None:
        row = self._table.currentRow()
        item = self._table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, DatasetAuditPresentation) else None

    def _render_detail(self) -> None:
        audit = self._selected_audit()
        self._detail.setPlainText(self._audit_text(audit) if audit is not None else "")

    def _audit_text(self, audit: DatasetAuditPresentation) -> str:
        lines = [
            self.tr("Dataset: {name} ({dataset_id})").format(
                name=audit.name, dataset_id=audit.dataset_id
            ),
            self.tr("Generation: {generation}").format(generation=audit.generation),
            self.tr("Recorded operation: {operation}").format(
                operation=audit.operation_name
            ),
            self.tr("Recorded at: {created_at}").format(
                created_at=audit.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            ),
        ]
        if audit.inputs:
            lines.append("")
            lines.append(self.tr("Inputs"))
            for edge in audit.inputs:
                base = self.tr("{position}. {name} ({dataset_id})").format(
                    position=edge.position + 1,
                    name=edge.name,
                    dataset_id=edge.dataset_id,
                )
                if edge.alias:
                    base += " — " + self.tr("alias {alias}").format(alias=edge.alias)
                lines.append(base)
        if audit.parameters_payload:
            lines.append("")
            lines.append(self.tr("Recorded parameters"))
            lines.append(
                json.dumps(audit.parameters_payload, ensure_ascii=False, indent=2, default=str)
            )
        if audit.agent_explanation:
            lines.append("")
            lines.append(self.tr("Agent-authored explanation"))
            lines.append(self.tr("Not system-verified."))
            lines.append(audit.agent_explanation)
        return "\n".join(lines)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Session Datasets"))
        self._table.setHorizontalHeaderLabels(
            [
                self.tr("Dataset"),
                self.tr("Generation"),
                self.tr("Operation"),
                self.tr("Inputs"),
                self.tr("Recorded"),
            ]
        )
        self._empty_label.setText(
            self.tr("No datasets have been produced by this conversation yet.")
        )
        self._refresh_button.setText(self.tr("Refresh"))
        self._close_button.setText(self.tr("Close"))
        self._render_detail()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)


__all__ = ["DatasetAuditDialog"]
