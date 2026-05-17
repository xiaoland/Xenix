from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QDateTime, QEvent, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from ..datetime_utils import format_datetime_for_display
from ..exceptions import XenixError
from ..services.dataset_service import DatasetService, ExportDatasetCopyInput
from ..services.inference_history_service import (
    InferenceHistoryFilter,
    InferenceHistoryRow,
    InferenceHistoryService,
    InferenceHistorySortDirection,
)
from ..services.ml_service import MLService
from ..services.storage.models import MLTaskStatus
from .native_widgets import mark_status_label
from .widgets.task_log_view import TaskLogView


class InferenceHistoryDialog(QDialog):
    def __init__(
        self,
        history_service: InferenceHistoryService,
        dataset_service: DatasetService,
        ml_service: MLService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history_service = history_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._rows: list[InferenceHistoryRow] = []
        self._current_result_dataset_id: str | None = None
        self._current_result_path: str | None = None
        self._message_label = QLabel()

        self._sort_label = QLabel()
        self._sort_selector = QComboBox()
        self._start_checkbox = QCheckBox()
        self._start_edit = QDateTimeEdit()
        self._end_checkbox = QCheckBox()
        self._end_edit = QDateTimeEdit()
        self._refresh_button = QPushButton()

        self._table = QTableWidget(0, 4)
        self._detail_label = QLabel()
        self._task_log_view = TaskLogView()
        self._task_group = QGroupBox()
        self._detail_group = QGroupBox()
        self._open_result_button = QPushButton()
        self._export_result_button = QPushButton()

        self.resize(1100, 760)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        self.refresh_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        controls = QFormLayout()
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(8)

        self._message_label.setWordWrap(True)
        self._detail_label.setWordWrap(True)
        self._start_edit.setCalendarPopup(True)
        self._end_edit.setCalendarPopup(True)
        self._start_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._end_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._start_edit.setDateTime(QDateTime.currentDateTime())
        self._end_edit.setDateTime(QDateTime.currentDateTime())

        controls.addRow(self._sort_label, self._sort_selector)
        controls.addRow(self._start_checkbox, self._start_edit)
        controls.addRow(self._end_checkbox, self._end_edit)

        actions = QHBoxLayout()
        actions.addWidget(self._refresh_button)
        actions.addStretch(1)

        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_task_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addLayout(controls)
        layout.addLayout(actions)
        layout.addWidget(splitter, 1)
        layout.addWidget(self._message_label)

    def _build_task_panel(self) -> QWidget:
        layout = QVBoxLayout(self._task_group)
        layout.addWidget(self._table)
        return self._task_group

    def _build_detail_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        detail_layout = QVBoxLayout(self._detail_group)
        detail_layout.addWidget(self._detail_label)
        detail_layout.addWidget(self._task_log_view, 1)

        actions = QHBoxLayout()
        actions.addWidget(self._open_result_button)
        actions.addWidget(self._export_result_button)
        actions.addStretch(1)
        detail_layout.addLayout(actions)

        layout.addWidget(self._detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._refresh_button.clicked.connect(self.refresh_history)
        self._table.itemSelectionChanged.connect(self._load_selected_row_details)
        self._open_result_button.clicked.connect(self._open_result)
        self._export_result_button.clicked.connect(self._export_result)
        self._start_checkbox.toggled.connect(self._refresh_filter_controls)
        self._end_checkbox.toggled.connect(self._refresh_filter_controls)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("History"))
        self._sort_label.setText(self.tr("Sort"))
        self._start_checkbox.setText(self.tr("Start time"))
        self._end_checkbox.setText(self.tr("End time"))
        self._refresh_button.setText(self.tr("Refresh"))
        self._open_result_button.setText(self.tr("Open Result"))
        self._export_result_button.setText(self.tr("Export Result"))
        self._task_group.setTitle(self.tr("Inference Results"))
        self._detail_group.setTitle(self.tr("Task Details"))
        self._table.setHorizontalHeaderLabels(
            [
                self.tr("Finished"),
                self.tr("Work Item"),
                self.tr("Model"),
                self.tr("Rows"),
            ]
        )
        self._reload_sort_options()
        self._refresh_filter_controls()
        if not self._message_label.text():
            self._set_message(self.tr("Refresh to load prediction history."), is_error=False)
        if not self._detail_label.text():
            self._detail_label.setText(self.tr("Select a history row to inspect its details."))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh_history()
        super().changeEvent(event)

    def refresh_history(self) -> None:
        selected_task_id = self._selected_task_id()
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)

        try:
            self._rows = self._history_service.list_results(self._build_filter())
        except Exception as exc:
            self._rows = []
            self._table.setRowCount(0)
            self._detail_label.setText(self.tr("Select a history row to inspect its details."))
            self._task_log_view.clear()
            self._set_message(str(exc), is_error=True)
            return

        self._table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                self._format_finished_at(row.finished_at),
                row.work_item_name or "",
                row.model_key or "",
                "" if row.row_count is None else str(row.row_count),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.UserRole, row.inference_task_id)
                self._table.setItem(row_index, column_index, item)

        if selected_task_id is not None:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == selected_task_id:
                    self._table.selectRow(row)
                    break
        elif self._table.rowCount() > 0:
            self._table.selectRow(0)
        else:
            self._detail_label.setText(self.tr("Select a history row to inspect its details."))
            self._task_log_view.clear()

        if self._rows:
            self._set_message(
                self.tr("Loaded {count} prediction result(s).").format(count=str(len(self._rows))),
                is_error=False,
            )
        else:
            self._set_message(self.tr("No prediction results match the current filter."), is_error=False)
        self._load_selected_row_details()

    def _reload_sort_options(self) -> None:
        current_value = self._sort_selector.currentData()
        self._sort_selector.blockSignals(True)
        self._sort_selector.clear()
        self._sort_selector.addItem(
            self.tr("Newest first"),
            InferenceHistorySortDirection.DESC.value,
        )
        self._sort_selector.addItem(
            self.tr("Oldest first"),
            InferenceHistorySortDirection.ASC.value,
        )
        index = self._sort_selector.findData(current_value)
        if index < 0:
            index = self._sort_selector.findData(InferenceHistorySortDirection.DESC.value)
        if index >= 0:
            self._sort_selector.setCurrentIndex(index)
        self._sort_selector.blockSignals(False)

    def _refresh_filter_controls(self) -> None:
        self._start_edit.setEnabled(self._start_checkbox.isChecked())
        self._end_edit.setEnabled(self._end_checkbox.isChecked())

    def _build_filter(self) -> InferenceHistoryFilter:
        sort_value = self._sort_selector.currentData()
        sort_direction = InferenceHistorySortDirection.DESC
        if isinstance(sort_value, str):
            sort_direction = InferenceHistorySortDirection(sort_value)
        return InferenceHistoryFilter(
            start_time=self._selected_datetime(self._start_checkbox, self._start_edit),
            end_time=self._selected_datetime(self._end_checkbox, self._end_edit),
            sort_direction=sort_direction,
        )

    def _selected_datetime(self, checkbox: QCheckBox, editor: QDateTimeEdit) -> datetime | None:
        if not checkbox.isChecked():
            return None
        value = editor.dateTime().toUTC().toPython()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _selected_task_id(self) -> str | None:
        selected_items = self._table.selectedItems()
        if not selected_items:
            return None
        return str(selected_items[0].data(Qt.UserRole))

    def _load_selected_row_details(self) -> None:
        task_id = self._selected_task_id()
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)
        if task_id is None:
            self._detail_label.setText(self.tr("Select a history row to inspect its details."))
            self._task_log_view.clear()
            return

        row = next((candidate for candidate in self._rows if candidate.inference_task_id == task_id), None)
        if row is None:
            return

        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError as exc:
            self._detail_label.setText(str(exc))
            self._task_log_view.clear()
            self._set_message(str(exc), is_error=True)
            return

        self._current_result_dataset_id = row.result_dataset_id
        self._current_result_path = row.result_path
        self._open_result_button.setEnabled(True)
        self._export_result_button.setEnabled(True)
        summary_lines = [
            self.tr("Task: {task_id}").format(task_id=row.inference_task_id),
            self.tr("Finished: {finished_at}").format(finished_at=self._format_finished_at(row.finished_at)),
            self.tr("Work item: {work_item_name}").format(work_item_name=row.work_item_name or ""),
            self.tr("Model: {model_key}").format(model_key=row.model_key or ""),
            self.tr("Rows: {row_count}").format(row_count="" if row.row_count is None else str(row.row_count)),
            self.tr("Result: {path}").format(path=row.result_path),
            self.tr("Status: {status}").format(status=self._translate_task_status(details.task.status)),
        ]
        if row.scenario_template_name:
            summary_lines.append(
                self.tr("Scenario: {scenario_name}").format(scenario_name=row.scenario_template_name)
            )
        self._detail_label.setText("\n".join(summary_lines))
        self._task_log_view.set_logs(details.logs)

    def _open_result(self) -> None:
        if self._current_result_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_result_path))

    def _export_result(self) -> None:
        if self._current_result_dataset_id is None:
            return
        destination_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Prediction Result"),
            "",
            self.tr("CSV Files (*.csv);;Excel Files (*.xlsx)"),
        )
        if not destination_path:
            return
        destination = Path(destination_path).resolve()
        if destination.suffix.lower() not in {".csv", ".xlsx"}:
            if "*.xlsx" in selected_filter:
                destination = destination.with_suffix(".xlsx")
            else:
                destination = destination.with_suffix(".csv")
        csv_encoding = "utf-8"
        if destination.suffix.lower() == ".csv":
            selected_encoding = self._choose_csv_encoding()
            if selected_encoding is None:
                return
            csv_encoding = selected_encoding
        try:
            exported_path = self._dataset_service.export_dataset_copy(
                ExportDatasetCopyInput(
                    dataset_id=self._current_result_dataset_id,
                    destination_path=str(destination),
                    csv_encoding=csv_encoding,
                )
            )
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(
            self.tr("Prediction result exported to '{path}'.").format(path=str(exported_path)),
            is_error=False,
        )
        QMessageBox.information(self, self.tr("Exported"), self.tr("Prediction result exported successfully."))

    def _choose_csv_encoding(self) -> str | None:
        labels = [
            self.tr("UTF-8"),
            self.tr("UTF-8 with BOM"),
            self.tr("GBK"),
        ]
        selected_label, accepted = QInputDialog.getItem(
            self,
            self.tr("CSV Encoding"),
            self.tr("Choose CSV encoding"),
            labels,
            0,
            False,
        )
        if not accepted:
            return None
        mapping = {
            labels[0]: "utf-8",
            labels[1]: "utf-8-sig",
            labels[2]: "gbk",
        }
        return mapping[selected_label]

    def _format_finished_at(self, finished_at: datetime) -> str:
        return format_datetime_for_display(finished_at, format_string="%Y-%m-%d %H:%M:%S")

    def _translate_task_status(self, status: MLTaskStatus) -> str:
        labels = {
            MLTaskStatus.PENDING: self.tr("Pending"),
            MLTaskStatus.RUNNING: self.tr("Running"),
            MLTaskStatus.SUCCEEDED: self.tr("Succeeded"),
            MLTaskStatus.FAILED: self.tr("Failed"),
            MLTaskStatus.CANCELLED: self.tr("Cancelled"),
        }
        return labels.get(status, str(status))

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._message_label.setText(message)
        mark_status_label(self._message_label, is_error=is_error)
