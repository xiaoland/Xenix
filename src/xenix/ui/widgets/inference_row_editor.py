from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class InferenceRowEditorWidget(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._columns: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        self._add_button = QPushButton("Add Row")
        self._remove_button = QPushButton("Remove Row")
        self._add_button.clicked.connect(self._add_row)
        self._remove_button.clicked.connect(self._remove_selected_rows)
        controls.addWidget(self._add_button)
        controls.addWidget(self._remove_button)
        controls.addStretch(1)

        self._table = QTableWidget(0, 0, self)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)

        layout.addLayout(controls)
        layout.addWidget(self._table)

    def set_columns(self, columns: list[str]) -> None:
        self._columns = list(columns)
        self._table.setColumnCount(len(self._columns))
        self._table.setHorizontalHeaderLabels(self._columns)
        self._table.setRowCount(0)
        if self._columns:
            self._add_row()

    def rows(self) -> list[dict[str, str | None]]:
        rows: list[dict[str, str | None]] = []
        for row_index in range(self._table.rowCount()):
            payload: dict[str, str | None] = {}
            has_value = False
            for column_index, column_name in enumerate(self._columns):
                item = self._table.item(row_index, column_index)
                value = item.text().strip() if item is not None else ""
                if value:
                    has_value = True
                payload[column_name] = value or None
            if has_value:
                rows.append(payload)
        return rows

    def clear(self) -> None:
        self._columns = []
        self._table.setColumnCount(0)
        self._table.setRowCount(0)

    def _add_row(self) -> None:
        if not self._columns:
            return
        row_index = self._table.rowCount()
        self._table.insertRow(row_index)
        for column_index in range(len(self._columns)):
            self._table.setItem(row_index, column_index, QTableWidgetItem(""))

    def _remove_selected_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        for row_index in selected_rows:
            self._table.removeRow(row_index)
        if self._columns and self._table.rowCount() == 0:
            self._add_row()
