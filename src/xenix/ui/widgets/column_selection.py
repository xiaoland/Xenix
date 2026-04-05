from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ...services.dataset_inspection import DatasetColumnMetadata


class ColumnSelectionWidget(QFrame):
    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._columns: list[DatasetColumnMetadata] = []

        self._hint_label = QLabel()
        self._feature_title_label = QLabel()
        self._target_title_label = QLabel()
        self._feature_picker = QComboBox()
        self._add_feature_button = QPushButton()
        self._selected_feature_list = QListWidget()
        self._remove_feature_button = QPushButton()
        self._target_selector = QComboBox()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self._hint_label.setWordWrap(True)
        root_layout.addWidget(self._hint_label)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        self._selected_feature_list.setSelectionMode(QListWidget.SingleSelection)

        columns_layout.addLayout(self._build_feature_group())
        columns_layout.addLayout(self._build_target_group())
        root_layout.addLayout(columns_layout)

        self._wire_events()
        self.retranslate_ui()
        self._refresh_action_state()

    def _build_feature_group(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        self._feature_title_label.setAlignment(Qt.AlignLeft)
        self._feature_title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self._feature_title_label)

        picker_row = QHBoxLayout()
        picker_row.setSpacing(8)
        picker_row.addWidget(self._feature_picker, 1)
        picker_row.addWidget(self._add_feature_button, 0)
        layout.addLayout(picker_row)
        layout.addWidget(self._selected_feature_list, 1)
        layout.addWidget(self._remove_feature_button, 0, alignment=Qt.AlignLeft)
        return layout

    def _build_target_group(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        self._target_title_label.setAlignment(Qt.AlignLeft)
        self._target_title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self._target_title_label)
        layout.addWidget(self._target_selector)
        layout.addStretch(1)
        return layout

    def _wire_events(self) -> None:
        self._add_feature_button.clicked.connect(self._add_selected_feature)
        self._remove_feature_button.clicked.connect(self._remove_selected_feature)
        self._feature_picker.currentIndexChanged.connect(self._refresh_action_state)
        self._selected_feature_list.itemSelectionChanged.connect(self._refresh_action_state)
        self._target_selector.currentIndexChanged.connect(self._on_target_changed)

    def retranslate_ui(self) -> None:
        self._hint_label.setText(self.tr("Choose one prediction target, then add one or more input columns."))
        self._feature_title_label.setText(self.tr("Input Columns"))
        self._target_title_label.setText(self.tr("Prediction Target"))
        self._add_feature_button.setText(self.tr("Add"))
        self._remove_feature_button.setText(self.tr("Remove"))
        self._reload_target_selector()
        self._reload_feature_picker()
        self._refresh_selected_feature_list()
        self._refresh_action_state()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def clear(self) -> None:
        self._columns = []
        self._selected_feature_list.clear()
        self._feature_picker.clear()
        self._target_selector.clear()
        self._refresh_action_state()

    def set_columns(
        self,
        columns: list[DatasetColumnMetadata],
        feature_columns: list[str] | None = None,
        target_columns: list[str] | None = None,
    ) -> None:
        self.clear()
        self._columns = list(columns)
        selected_target = next(iter(target_columns or []), None)
        selected_features = [name for name in (feature_columns or []) if name != selected_target]
        self._reload_target_selector(selected_target=selected_target)
        self._refresh_selected_feature_list(selected_features=selected_features)
        self._reload_feature_picker()
        self._refresh_action_state()

    def selected_feature_columns(self) -> list[str]:
        return [str(self._selected_feature_list.item(index).data(Qt.UserRole)) for index in range(self._selected_feature_list.count())]

    def selected_target_columns(self) -> list[str]:
        target = self._selected_target_name()
        return [target] if target is not None else []

    def _reload_target_selector(self, *, selected_target: str | None = None) -> None:
        if selected_target is None:
            selected_target = self._selected_target_name()
        self._target_selector.blockSignals(True)
        self._target_selector.clear()
        self._target_selector.addItem(self.tr("Choose target column"), None)
        for column in self._columns:
            self._target_selector.addItem(self._column_label(column), column.name)
        index = self._target_selector.findData(selected_target)
        self._target_selector.setCurrentIndex(index if index >= 0 else 0)
        self._target_selector.blockSignals(False)

    def _reload_feature_picker(self) -> None:
        selected_features = set(self.selected_feature_columns())
        selected_target = self._selected_target_name()
        current_value = self._feature_picker.currentData()
        self._feature_picker.blockSignals(True)
        self._feature_picker.clear()
        self._feature_picker.addItem(self.tr("Choose input column"), None)
        for column in self._columns:
            if column.name == selected_target or column.name in selected_features:
                continue
            self._feature_picker.addItem(self._column_label(column), column.name)
        index = self._feature_picker.findData(current_value)
        self._feature_picker.setCurrentIndex(index if index >= 0 else 0)
        self._feature_picker.blockSignals(False)

    def _refresh_selected_feature_list(self, *, selected_features: list[str] | None = None) -> None:
        if selected_features is None:
            selected_features = self.selected_feature_columns()
        selected_target = self._selected_target_name()
        feature_names = [name for name in selected_features if name != selected_target]
        self._selected_feature_list.clear()
        for feature_name in feature_names:
            column = next((item for item in self._columns if item.name == feature_name), None)
            if column is None:
                continue
            feature_item = QListWidgetItem(self._column_label(column))
            feature_item.setData(Qt.UserRole, column.name)
            self._selected_feature_list.addItem(feature_item)

    def _add_selected_feature(self) -> None:
        feature_name = self._feature_picker.currentData()
        if feature_name is None:
            return
        selected_features = self.selected_feature_columns()
        selected_features.append(str(feature_name))
        self._refresh_selected_feature_list(selected_features=selected_features)
        self._reload_feature_picker()
        self._refresh_action_state()

    def _remove_selected_feature(self) -> None:
        selected_item = self._selected_feature_list.currentItem()
        if selected_item is None:
            return
        feature_name = str(selected_item.data(Qt.UserRole))
        selected_features = [name for name in self.selected_feature_columns() if name != feature_name]
        self._refresh_selected_feature_list(selected_features=selected_features)
        self._reload_feature_picker()
        self._refresh_action_state()

    def _on_target_changed(self) -> None:
        self._refresh_selected_feature_list()
        self._reload_feature_picker()
        self._refresh_action_state()

    def _selected_target_name(self) -> str | None:
        current_value = self._target_selector.currentData()
        return str(current_value) if current_value is not None else None

    def _refresh_action_state(self) -> None:
        self._add_feature_button.setEnabled(self._feature_picker.currentData() is not None)
        self._remove_feature_button.setEnabled(self._selected_feature_list.currentItem() is not None)

    def _column_label(self, column: DatasetColumnMetadata) -> str:
        return f"{column.name} ({column.kind.value})"
