from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QT_TRANSLATE_NOOP, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.dataset_service import (
    DatasetService,
    ExportDatasetCopyInput,
    MaterializeManualInferenceCsvInput,
)
from ..services.ml_service import InferWithFilesInput, MLService
from ..services.scenario_template_service import ScenarioTemplate
from ..services.scenario_workflow_service import ScenarioWorkItemPreparationResult
from ..services.storage.models import MLTaskStatus, MLTaskType
from ..services.work_item_service import WorkItemService
from .scenario_template_text import localized_template_display_name
from .widgets.inference_row_editor import InferenceRowEditorWidget
from .widgets.task_log_view import TaskLogView


class ScenarioInferenceDialog(QDialog):
    def __init__(
        self,
        template: ScenarioTemplate,
        preparation_result: ScenarioWorkItemPreparationResult,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        ml_service: MLService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._preparation_result = preparation_result
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._best_model_id: str | None = None
        self._current_result_dataset_id: str | None = None
        self._current_result_path: str | None = None
        self._message_template: str | None = None
        self._message_kwargs: dict[str, str] = {}
        self._raw_message: str | None = None

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._context_label = QLabel()
        self._best_model_label = QLabel()
        self._message_label = QLabel()

        self._input_tabs = QTabWidget()
        self._manual_tab = QWidget()
        self._batch_tab = QWidget()
        self._manual_hint_label = QLabel()
        self._row_editor = InferenceRowEditorWidget()
        self._manual_submit_button = QPushButton()
        self._batch_hint_label = QLabel()
        self._batch_file_list = QListWidget()
        self._choose_batch_button = QPushButton()
        self._batch_submit_button = QPushButton()

        self._task_table = QTableWidget(0, 4)
        self._task_details_label = QLabel()
        self._task_log_view = TaskLogView()
        self._open_result_button = QPushButton()
        self._export_result_button = QPushButton()
        self._task_group = QGroupBox()
        self._detail_group = QGroupBox()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh_runtime)

        self.resize(1080, 780)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        self.refresh_runtime()
        self._timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        self._summary_label.setWordWrap(True)
        self._context_label.setWordWrap(True)
        self._best_model_label.setWordWrap(True)
        self._message_label.setWordWrap(True)
        self._task_details_label.setWordWrap(True)
        self._manual_hint_label.setWordWrap(True)
        self._batch_hint_label.setWordWrap(True)

        self._build_manual_tab()
        self._build_batch_tab()
        self._input_tabs.addTab(self._manual_tab, "")
        self._input_tabs.addTab(self._batch_tab, "")

        self._task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._task_table.verticalHeader().setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_task_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._context_label)
        layout.addWidget(self._best_model_label)
        layout.addWidget(self._input_tabs)
        layout.addWidget(splitter, 1)
        layout.addWidget(self._message_label)

    def _build_manual_tab(self) -> None:
        layout = QVBoxLayout(self._manual_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._manual_hint_label)
        layout.addWidget(self._row_editor, 1)
        layout.addWidget(self._manual_submit_button)

    def _build_batch_tab(self) -> None:
        layout = QVBoxLayout(self._batch_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._batch_hint_label)
        layout.addWidget(self._batch_file_list, 1)
        actions = QHBoxLayout()
        actions.addWidget(self._choose_batch_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(self._batch_submit_button)

    def _build_task_panel(self) -> QWidget:
        layout = QVBoxLayout(self._task_group)
        layout.addWidget(self._task_table)
        return self._task_group

    def _build_detail_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        detail_layout = QVBoxLayout(self._detail_group)
        detail_layout.addWidget(self._task_details_label)
        detail_layout.addWidget(self._task_log_view, 1)

        actions = QHBoxLayout()
        actions.addWidget(self._open_result_button)
        actions.addWidget(self._export_result_button)
        actions.addStretch(1)
        detail_layout.addLayout(actions)

        layout.addWidget(self._detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._manual_submit_button.clicked.connect(self._submit_manual_inference)
        self._choose_batch_button.clicked.connect(self._choose_batch_files)
        self._batch_submit_button.clicked.connect(self._submit_batch_inference)
        self._task_table.itemSelectionChanged.connect(self._load_selected_task_details)
        self._open_result_button.clicked.connect(self._open_result)
        self._export_result_button.clicked.connect(self._export_result)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Prediction"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr("Use the best trained model to predict one row or a batch file.")
        )
        self._manual_hint_label.setText(
            self.tr("Enter one or more rows below. The current best model is used automatically.")
        )
        self._batch_hint_label.setText(
            self.tr("Choose one or more files with the required input columns.")
        )
        self._manual_submit_button.setText(self.tr("Start Prediction"))
        self._choose_batch_button.setText(self.tr("Choose Files"))
        self._batch_submit_button.setText(self.tr("Start Batch Prediction"))
        self._open_result_button.setText(self.tr("Open Result"))
        self._export_result_button.setText(self.tr("Export Result"))
        self._input_tabs.setTabText(0, self.tr("Single Prediction"))
        self._input_tabs.setTabText(1, self.tr("Batch File"))
        self._task_group.setTitle(self.tr("Prediction Tasks"))
        self._detail_group.setTitle(self.tr("Task Details"))
        self._task_table.setHorizontalHeaderLabels(
            [
                self.tr("Status"),
                self.tr("Model"),
                self.tr("Rows"),
                self.tr("Failure"),
            ]
        )
        self._reload_message_label()
        self.refresh_runtime()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        super().closeEvent(event)

    def refresh_runtime(self) -> None:
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)

        try:
            work_item = self._work_item_service.get_work_item(self._preparation_result.work_item_id)
            dataset = self._dataset_service.get_dataset(work_item.dataset_id)
            trained_models = self._ml_service.list_trained_models(work_item.id)
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._row_editor.set_columns(work_item.feature_columns)
        self._context_label.setText(
            self.tr("Managed dataset: {dataset_name}. Prediction fields: {features}.").format(
                dataset_name=Path(dataset.source_path).name,
                features=", ".join(work_item.feature_columns),
            )
        )

        self._best_model_id = work_item.best_trained_model_id
        best_model_key = None
        for model in trained_models:
            if model.id == self._best_model_id:
                best_model_key = model.model_key
                break

        has_best_model = self._best_model_id is not None and best_model_key is not None
        if has_best_model:
            self._best_model_label.setText(
                self.tr("Using best model: {model_key}").format(model_key=str(best_model_key))
            )
        else:
            self._best_model_label.setText(self.tr("Best model is not available yet."))
        self._manual_submit_button.setEnabled(has_best_model)
        self._batch_submit_button.setEnabled(has_best_model)

        self._refresh_task_table(work_item.id)
        self._load_selected_task_details()

    def _refresh_task_table(self, work_item_id: str) -> None:
        current_task_id = self._selected_task_id()
        tasks = [
            task
            for task in self._ml_service.list_work_item_tasks(work_item_id)
            if task.task_type is MLTaskType.INFERENCE
        ]
        self._task_table.setRowCount(len(tasks))
        for row_index, task in enumerate(tasks):
            result_payload = task.result_payload or {}
            values = [
                self._translate_task_status(task.status),
                str(result_payload.get("model_key", "")),
                str(result_payload.get("row_count", "")),
                task.error_summary or "",
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.UserRole, task.id)
                self._task_table.setItem(row_index, column_index, item)

        if current_task_id is not None:
            for row in range(self._task_table.rowCount()):
                item = self._task_table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == current_task_id:
                    self._task_table.selectRow(row)
                    break
        elif self._task_table.rowCount() > 0:
            self._task_table.selectRow(0)

    def _submit_manual_inference(self) -> None:
        if self._best_model_id is None:
            self._set_raw_message(self.tr("Training must finish before prediction can start."), is_error=True)
            return

        try:
            csv_path = self._dataset_service.materialize_manual_inference_csv(
                MaterializeManualInferenceCsvInput(
                    feature_columns=self._work_item_service.get_work_item(
                        self._preparation_result.work_item_id
                    ).feature_columns,
                    rows=self._row_editor.rows(),
                )
            )
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=self._preparation_result.work_item_id,
                    input_files=[str(csv_path)],
                )
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP("ScenarioInferenceDialog", "Prediction task '{task_id}' queued."),
            task_id=task.id,
        )
        QMessageBox.information(self, self.tr("Queued"), self.tr("Prediction queued successfully."))
        self.refresh_runtime()

    def _choose_batch_files(self) -> None:
        file_paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Choose Prediction Files"),
            "",
            self.tr("Supported Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)"),
        )
        if not file_paths:
            return
        self._batch_file_list.clear()
        for file_path in file_paths:
            self._batch_file_list.addItem(QListWidgetItem(file_path))

    def _submit_batch_inference(self) -> None:
        if self._best_model_id is None:
            self._set_raw_message(self.tr("Training must finish before prediction can start."), is_error=True)
            return

        input_files = [self._batch_file_list.item(index).text() for index in range(self._batch_file_list.count())]
        try:
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=self._preparation_result.work_item_id,
                    input_files=input_files,
                )
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP("ScenarioInferenceDialog", "Prediction task '{task_id}' queued."),
            task_id=task.id,
        )
        QMessageBox.information(self, self.tr("Queued"), self.tr("Batch prediction queued successfully."))
        self.refresh_runtime()

    def _selected_task_id(self) -> str | None:
        selected_items = self._task_table.selectedItems()
        if not selected_items:
            return None
        return str(selected_items[0].data(Qt.UserRole))

    def _load_selected_task_details(self) -> None:
        task_id = self._selected_task_id()
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)
        if task_id is None:
            self._task_details_label.setText(self.tr("Select a prediction task to inspect its details."))
            self._task_log_view.clear()
            return

        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        summary_lines = [
            self.tr("Task: {task_id}").format(task_id=details.task.id),
            self.tr("Status: {status}").format(status=self._translate_task_status(details.task.status)),
            self.tr("Model: {model_key}").format(model_key=(details.task.result_payload or {}).get("model_key", "")),
            self.tr("Rows: {row_count}").format(row_count=(details.task.result_payload or {}).get("row_count", "")),
        ]
        if details.task.result_payload:
            result_dataset_id = details.task.result_payload.get("result_dataset_id")
            canonical_output_path = details.task.result_payload.get("canonical_output_path")
            if isinstance(result_dataset_id, str) and isinstance(canonical_output_path, str):
                self._current_result_dataset_id = result_dataset_id
                self._current_result_path = canonical_output_path
                self._open_result_button.setEnabled(True)
                self._export_result_button.setEnabled(True)
                summary_lines.append(self.tr("Result: {path}").format(path=canonical_output_path))
        self._task_details_label.setText("\n".join(summary_lines))
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
        destination = self._normalize_export_destination(destination, selected_filter)
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
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP("ScenarioInferenceDialog", "Prediction result exported to '{path}'."),
            path=str(exported_path),
        )
        QMessageBox.information(self, self.tr("Exported"), self.tr("Prediction result exported successfully."))

    def _normalize_export_destination(self, destination_path: Path, selected_filter: str) -> Path:
        if destination_path.suffix.lower() in {".csv", ".xlsx"}:
            return destination_path
        if "*.xlsx" in selected_filter:
            return destination_path.with_suffix(".xlsx")
        return destination_path.with_suffix(".csv")

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

    def _translate_task_status(self, status: MLTaskStatus) -> str:
        labels = {
            MLTaskStatus.PENDING: self.tr("Pending"),
            MLTaskStatus.RUNNING: self.tr("Running"),
            MLTaskStatus.SUCCEEDED: self.tr("Succeeded"),
            MLTaskStatus.FAILED: self.tr("Failed"),
            MLTaskStatus.CANCELLED: self.tr("Cancelled"),
        }
        return labels.get(status, str(status))

    def _set_ui_message(self, template: str, *, is_error: bool = False, **kwargs: str) -> None:
        self._message_template = template
        self._message_kwargs = {key: str(value) for key, value in kwargs.items()}
        self._raw_message = None
        self._message_label.setText(self.tr(template).format(**self._message_kwargs))
        self._message_label.setStyleSheet("color: #b42318;" if is_error else "color: #17643a;")

    def _set_raw_message(self, message: str, *, is_error: bool = False) -> None:
        self._message_template = None
        self._message_kwargs = {}
        self._raw_message = message
        self._message_label.setText(message)
        self._message_label.setStyleSheet("color: #b42318;" if is_error else "color: #17643a;")

    def _reload_message_label(self) -> None:
        if self._message_template is not None:
            self._message_label.setText(self.tr(self._message_template).format(**self._message_kwargs))
        elif self._raw_message is not None:
            self._message_label.setText(self._raw_message)
