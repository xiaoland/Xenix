from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
from ..services.project_service import ProjectService
from ..services.storage.models import MLTaskType
from ..services.work_item_service import WorkItemService
from .widgets.inference_row_editor import InferenceRowEditorWidget
from .widgets.task_log_view import TaskLogView


class InferenceWorkspace(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        ml_service: MLService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service

        self._project_selector = QComboBox()
        self._work_item_selector = QComboBox()
        self._model_selector = QComboBox()
        self._context_label = QLabel("Select a work item with at least one trained model.")
        self._context_label.setWordWrap(True)
        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)

        self._input_tabs = QTabWidget()
        self._row_editor = InferenceRowEditorWidget()
        self._manual_submit_button = QPushButton("Run Manual Inference")
        self._batch_file_list = QListWidget()
        self._choose_batch_button = QPushButton("Choose Files")
        self._batch_submit_button = QPushButton("Run Batch Inference")

        self._task_table = QTableWidget(0, 4)
        self._task_details_label = QLabel("Select an inference task to inspect its details.")
        self._task_details_label.setWordWrap(True)
        self._task_log_view = TaskLogView()
        self._open_result_button = QPushButton("Open Result")
        self._export_result_button = QPushButton("Export Result")
        self._current_result_dataset_id: str | None = None
        self._current_result_path: str | None = None

        self._build_ui()
        self._wire_events()
        self._reload_projects()

    def reload_state(self) -> None:
        self._reload_projects()
        self.refresh_runtime()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)

        header = QGridLayout()
        header.setHorizontalSpacing(12)
        header.setVerticalSpacing(8)
        header.addWidget(QLabel("Project"), 0, 0)
        header.addWidget(self._project_selector, 0, 1)
        header.addWidget(QLabel("Work Item"), 1, 0)
        header.addWidget(self._work_item_selector, 1, 1)
        header.addWidget(QLabel("Model"), 2, 0)
        header.addWidget(self._model_selector, 2, 1)
        root_layout.addLayout(header)
        root_layout.addWidget(self._context_label)

        self._input_tabs.addTab(self._build_manual_tab(), "Manual")
        self._input_tabs.addTab(self._build_batch_tab(), "Batch File")
        root_layout.addWidget(self._input_tabs)

        runtime_splitter = QSplitter(Qt.Horizontal)
        runtime_splitter.addWidget(self._build_task_panel())
        runtime_splitter.addWidget(self._build_detail_panel())
        runtime_splitter.setStretchFactor(0, 3)
        runtime_splitter.setStretchFactor(1, 2)
        root_layout.addWidget(runtime_splitter, 1)
        root_layout.addWidget(self._message_label)

    def _build_manual_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._row_editor, 1)
        layout.addWidget(self._manual_submit_button)
        return widget

    def _build_batch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._batch_file_list, 1)
        actions = QHBoxLayout()
        actions.addWidget(self._choose_batch_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(self._batch_submit_button)
        return widget

    def _build_task_panel(self) -> QWidget:
        widget = QGroupBox("Inference Tasks")
        layout = QVBoxLayout(widget)
        self._task_table.setHorizontalHeaderLabels(["Status", "Model", "Rows", "Failure"])
        self._task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._task_table.verticalHeader().setVisible(False)
        layout.addWidget(self._task_table)
        return widget

    def _build_detail_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        detail_group = QGroupBox("Task Details")
        detail_layout = QVBoxLayout(detail_group)
        detail_layout.addWidget(self._task_details_label)
        detail_layout.addWidget(self._task_log_view, 1)

        actions = QHBoxLayout()
        actions.addWidget(self._open_result_button)
        actions.addWidget(self._export_result_button)
        actions.addStretch(1)
        detail_layout.addLayout(actions)

        layout.addWidget(detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._project_selector.currentIndexChanged.connect(self._on_project_changed)
        self._work_item_selector.currentIndexChanged.connect(self.refresh_runtime)
        self._manual_submit_button.clicked.connect(self._submit_manual_inference)
        self._choose_batch_button.clicked.connect(self._choose_batch_files)
        self._batch_submit_button.clicked.connect(self._submit_batch_inference)
        self._task_table.itemSelectionChanged.connect(self._load_selected_task_details)
        self._open_result_button.clicked.connect(self._open_result)
        self._export_result_button.clicked.connect(self._export_result)

    def _reload_projects(self) -> None:
        current_project_id = self.current_project_id()
        self._project_selector.blockSignals(True)
        self._project_selector.clear()
        for project in self._project_service.list_projects():
            self._project_selector.addItem(project.name, project.id)
        self._project_selector.blockSignals(False)
        if current_project_id is not None:
            index = self._project_selector.findData(current_project_id)
            if index >= 0:
                self._project_selector.setCurrentIndex(index)
        self._on_project_changed()

    def _reload_work_items(self) -> None:
        project_id = self.current_project_id()
        current_work_item_id = self.current_work_item_id()
        self._work_item_selector.blockSignals(True)
        self._work_item_selector.clear()
        if project_id is not None:
            for work_item in self._work_item_service.list_work_items(project_id):
                self._work_item_selector.addItem(work_item.name, work_item.id)
        self._work_item_selector.blockSignals(False)
        if current_work_item_id is not None:
            index = self._work_item_selector.findData(current_work_item_id)
            if index >= 0:
                self._work_item_selector.setCurrentIndex(index)

    def _reload_models(self) -> None:
        work_item_id = self.current_work_item_id()
        current_model_id = self.current_model_id()
        self._model_selector.blockSignals(True)
        self._model_selector.clear()
        if work_item_id is not None:
            work_item = self._work_item_service.get_work_item(work_item_id)
            for model in self._ml_service.list_trained_models(work_item.id):
                prefix = "[Best] " if work_item.best_trained_model_id == model.id else ""
                self._model_selector.addItem(f"{prefix}{model.model_key}", model.id)
        self._model_selector.blockSignals(False)
        if current_model_id is not None:
            index = self._model_selector.findData(current_model_id)
            if index >= 0:
                self._model_selector.setCurrentIndex(index)

    def current_project_id(self) -> str | None:
        value = self._project_selector.currentData()
        return str(value) if value is not None else None

    def current_work_item_id(self) -> str | None:
        value = self._work_item_selector.currentData()
        return str(value) if value is not None else None

    def current_model_id(self) -> str | None:
        value = self._model_selector.currentData()
        return str(value) if value is not None else None

    def _on_project_changed(self, _index: int = -1) -> None:
        self._reload_work_items()
        self.refresh_runtime()

    def refresh_runtime(self) -> None:
        work_item_id = self.current_work_item_id()
        self._reload_models()
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)
        if work_item_id is None:
            self._context_label.setText("Select a project and work item to run inference.")
            self._task_table.setRowCount(0)
            self._task_details_label.setText("Select an inference task to inspect its details.")
            self._task_log_view.clear()
            self._row_editor.clear()
            return

        try:
            work_item = self._work_item_service.get_work_item(work_item_id)
            dataset = self._dataset_service.get_dataset(work_item.dataset_id)
            trained_models = self._ml_service.list_trained_models(work_item.id)
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        if not trained_models:
            self._context_label.setText("This work item does not have a trained model yet.")
        else:
            self._context_label.setText(
                f"Managed dataset: {Path(dataset.source_path).name}. Features: {', '.join(work_item.feature_columns)}."
            )
        self._row_editor.set_columns(work_item.feature_columns)
        self._refresh_task_table(work_item.id)

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
                task.status.value,
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

    def _submit_manual_inference(self) -> None:
        work_item_id = self.current_work_item_id()
        model_id = self.current_model_id()
        if work_item_id is None or model_id is None:
            self._set_message("Select a work item and trained model before submitting inference.", is_error=True)
            return
        try:
            work_item = self._work_item_service.get_work_item(work_item_id)
            csv_path = self._dataset_service.materialize_manual_inference_csv(
                MaterializeManualInferenceCsvInput(
                    feature_columns=work_item.feature_columns,
                    rows=self._row_editor.rows(),
                )
            )
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=work_item_id,
                    trained_model_id=model_id,
                    input_files=[str(csv_path)],
                )
            )
        except Exception as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(f"Inference task '{task.id}' queued.")
        QMessageBox.information(self, "Queued", "Manual inference queued successfully.")
        self.refresh_runtime()

    def _choose_batch_files(self) -> None:
        file_paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Choose Inference Files",
            "",
            "Supported Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)",
        )
        if not file_paths:
            return
        self._batch_file_list.clear()
        for file_path in file_paths:
            self._batch_file_list.addItem(QListWidgetItem(file_path))

    def _submit_batch_inference(self) -> None:
        work_item_id = self.current_work_item_id()
        model_id = self.current_model_id()
        if work_item_id is None or model_id is None:
            self._set_message("Select a work item and trained model before submitting inference.", is_error=True)
            return
        input_files = [self._batch_file_list.item(index).text() for index in range(self._batch_file_list.count())]
        try:
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=work_item_id,
                    trained_model_id=model_id,
                    input_files=input_files,
                )
            )
        except Exception as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(f"Inference task '{task.id}' queued.")
        QMessageBox.information(self, "Queued", "Batch inference queued successfully.")
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
            self._task_details_label.setText("Select an inference task to inspect its details.")
            self._task_log_view.clear()
            return
        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        summary_lines = [
            f"Task: {details.task.id}",
            f"Status: {details.task.status.value}",
            f"Model: {(details.task.result_payload or {}).get('model_key', '')}",
            f"Rows: {(details.task.result_payload or {}).get('row_count', '')}",
        ]
        if details.task.result_payload:
            result_dataset_id = details.task.result_payload.get("result_dataset_id")
            canonical_output_path = details.task.result_payload.get("canonical_output_path")
            if isinstance(result_dataset_id, str) and isinstance(canonical_output_path, str):
                self._current_result_dataset_id = result_dataset_id
                self._current_result_path = canonical_output_path
                self._open_result_button.setEnabled(True)
                self._export_result_button.setEnabled(True)
                summary_lines.append(f"Result: {canonical_output_path}")
        self._task_details_label.setText("\n".join(summary_lines))
        self._task_log_view.set_logs(details.logs)

    def _open_result(self) -> None:
        if self._current_result_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_result_path))

    def _export_result(self) -> None:
        if self._current_result_dataset_id is None:
            return
        destination_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Prediction Result",
            "",
            "CSV Files (*.csv)",
        )
        if not destination_path:
            return
        try:
            exported_path = self._dataset_service.export_dataset_copy(
                ExportDatasetCopyInput(
                    dataset_id=self._current_result_dataset_id,
                    destination_path=str(Path(destination_path).resolve()),
                )
            )
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(f"Result exported to '{exported_path}'.")
        QMessageBox.information(self, "Exported", "Prediction result exported successfully.")

    def _set_message(self, message: str, *, is_error: bool = False) -> None:
        self._message_label.setText(message)
        self._message_label.setStyleSheet("color: #b42318;" if is_error else "color: #17643a;")
