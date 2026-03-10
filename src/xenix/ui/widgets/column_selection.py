from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ...services.dataset_inspection import DatasetColumnMetadata


class ColumnSelectionWidget(QFrame):
    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        hint = QLabel("Select feature columns and target columns for the current work item.")
        hint.setWordWrap(True)
        root_layout.addWidget(hint)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        self._feature_list = QListWidget()
        self._feature_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._target_list = QListWidget()
        self._target_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        columns_layout.addLayout(self._build_column_group("Feature Columns", self._feature_list))
        columns_layout.addLayout(self._build_column_group("Target Columns", self._target_list))
        root_layout.addLayout(columns_layout)

    def _build_column_group(self, title: str, widget: QListWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        label = QLabel(title)
        label.setAlignment(Qt.AlignLeft)
        label.setStyleSheet("font-weight: 600;")
        layout.addWidget(label)
        layout.addWidget(widget)
        return layout

    def clear(self) -> None:
        self._feature_list.clear()
        self._target_list.clear()

    def set_columns(
        self,
        columns: list[DatasetColumnMetadata],
        feature_columns: list[str] | None = None,
        target_columns: list[str] | None = None,
    ) -> None:
        feature_names = set(feature_columns or [])
        target_names = set(target_columns or [])

        self.clear()
        for column in columns:
            label = f"{column.name} ({column.kind.value})"

            feature_item = QListWidgetItem(label)
            feature_item.setData(Qt.UserRole, column.name)
            self._feature_list.addItem(feature_item)
            if column.name in feature_names:
                feature_item.setSelected(True)

            target_item = QListWidgetItem(label)
            target_item.setData(Qt.UserRole, column.name)
            self._target_list.addItem(target_item)
            if column.name in target_names:
                target_item.setSelected(True)

    def selected_feature_columns(self) -> list[str]:
        return [item.data(Qt.UserRole) for item in self._feature_list.selectedItems()]

    def selected_target_columns(self) -> list[str]:
        return [item.data(Qt.UserRole) for item in self._target_list.selectedItems()]
