from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QT_TRANSLATE_NOOP, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from ..exceptions import ValidationError, XenixError
from ..services.dataset_inspection import DatasetInspection, InspectDatasetInput
from ..services.dataset_service import (
    DatasetService,
    ExportDatasetCopyInput,
    MaterializeManualInferenceCsvInput,
)
from ..services.ml_service import InferWithFilesInput, MLService
from ..services.scenario_model_source_service import CompatibleTrainedModelOption
from ..services.scenario_template_service import ScenarioTemplate
from ..services.scenario_workflow_service import ScenarioWorkItemPreparationResult
from ..services.storage.models import MLTaskStatus, MLTaskType, TrainedModelRow, WorkItemRow
from ..services.trained_model_metadata import parse_trained_model_metadata
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
        available_trained_models: list[CompatibleTrainedModelOption] | None = None,
        preferred_trained_model_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._preparation_result = preparation_result
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._available_trained_models = (
            list(available_trained_models)
            if available_trained_models is not None
            else None
        )
        self._preferred_trained_model_id = preferred_trained_model_id
        self._best_model_id: str | None = None
        self._current_result_dataset_id: str | None = None
        self._current_result_path: str | None = None
        self._previewed_result_task_id: str | None = None
        self._previewed_result_path: str | None = None
        self._preferred_task_id: str | None = None
        self._batch_inspections: dict[str, DatasetInspection] = {}
        self._message_template: str | None = None
        self._message_kwargs: dict[str, str] = {}
        self._raw_message: str | None = None

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._context_label = QLabel()
        self._model_label = QLabel()
        self._model_selector = QComboBox()
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
        self._batch_preview_label = QLabel()
        self._batch_preview_summary_label = QLabel()
        self._batch_preview_table = QTableWidget(0, 0)
        self._choose_batch_button = QPushButton()
        self._batch_submit_button = QPushButton()

        self._result_summary_label = QLabel()
        self._result_table = QTableWidget(0, 0)
        self._open_result_button = QPushButton()
        self._export_result_button = QPushButton()
        self._result_group = QGroupBox()

        self._task_table = QTableWidget(0, 4)
        self._task_details_label = QLabel()
        self._task_log_view = TaskLogView()
        self._task_group = QGroupBox()
        self._detail_group = QGroupBox()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh_runtime)

        self.resize(1080, 820)
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
        self._batch_preview_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self._batch_preview_summary_label.setWordWrap(True)
        self._result_summary_label.setWordWrap(True)

        self._configure_preview_table(self._batch_preview_table)
        self._configure_preview_table(self._result_table)

        model_row = QHBoxLayout()
        model_row.setSpacing(12)
        model_row.addWidget(self._model_label)
        model_row.addWidget(self._model_selector, 1)
        model_row.addWidget(self._best_model_label, 2)

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
        layout.addLayout(model_row)
        layout.addWidget(self._input_tabs)
        layout.addWidget(self._build_result_panel())
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
        layout.addWidget(self._batch_preview_label)
        layout.addWidget(self._batch_preview_summary_label)
        layout.addWidget(self._batch_preview_table)
        layout.addWidget(self._batch_submit_button)

    def _build_result_panel(self) -> QWidget:
        layout = QVBoxLayout(self._result_group)
        layout.setSpacing(10)
        layout.addWidget(self._result_summary_label)
        layout.addWidget(self._result_table)
        actions = QHBoxLayout()
        actions.addWidget(self._open_result_button)
        actions.addWidget(self._export_result_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return self._result_group

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

        layout.addWidget(self._detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._model_selector.currentIndexChanged.connect(self._handle_model_selection_changed)
        self._row_editor.rows_changed.connect(self._refresh_action_state)
        self._manual_submit_button.clicked.connect(self._submit_manual_inference)
        self._choose_batch_button.clicked.connect(self._choose_batch_files)
        self._batch_submit_button.clicked.connect(self._submit_batch_inference)
        self._batch_file_list.itemSelectionChanged.connect(self._refresh_batch_preview)
        self._task_table.itemSelectionChanged.connect(self._load_selected_task_details)
        self._open_result_button.clicked.connect(self._open_result)
        self._export_result_button.clicked.connect(self._export_result)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Prediction"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr("Choose a trained model, submit one row or batch files, and review prediction results directly here.")
        )
        self._model_label.setText(self.tr("Prediction Model"))
        self._choose_batch_button.setText(self.tr("Choose Files"))
        self._manual_submit_button.setText(self.tr("Start Prediction"))
        self._batch_submit_button.setText(self.tr("Start Batch Prediction"))
        self._open_result_button.setText(self.tr("Open Result"))
        self._export_result_button.setText(self.tr("Export Result"))
        self._batch_preview_label.setText(self.tr("Batch Preview"))
        self._input_tabs.setTabText(0, self.tr("Single Prediction"))
        self._input_tabs.setTabText(1, self.tr("Batch File"))
        self._result_group.setTitle(self.tr("Prediction Result"))
        self._task_group.setTitle(self.tr("Prediction Activity"))
        self._detail_group.setTitle(self.tr("Advanced Task Details"))
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
        self._reload_model_selector(work_item, trained_models)
        self._refresh_best_model_label(work_item, trained_models)
        self._refresh_action_state()
        self._refresh_batch_preview()
        self._refresh_task_table(work_item.id)
        self._load_selected_task_details()

    def _handle_model_selection_changed(self) -> None:
        try:
            work_item = self._work_item_service.get_work_item(self._preparation_result.work_item_id)
            trained_models = (
                []
                if self._available_trained_models is not None
                else self._ml_service.list_trained_models(work_item.id)
            )
        except XenixError:
            self._refresh_action_state()
            return
        self._refresh_best_model_label(work_item, trained_models)
        self._refresh_action_state()

    def _reload_model_selector(self, work_item: WorkItemRow, trained_models: list[TrainedModelRow]) -> None:
        current_model_id = self._current_model_id()
        self._model_selector.blockSignals(True)
        self._model_selector.clear()
        if self._available_trained_models is not None:
            for option in self._available_trained_models:
                prefix = f"{self.tr('[Best]')} " if option.is_best_for_work_item else ""
                self._model_selector.addItem(
                    f"{prefix}{option.model_display_name}",
                    option.trained_model_id,
                )
            preferred_model_id = current_model_id or self._preferred_trained_model_id
        else:
            for model in trained_models:
                prefix = f"{self.tr('[Best]')} " if work_item.best_trained_model_id == model.id else ""
                self._model_selector.addItem(
                    f"{prefix}{self._trained_model_label(model)}",
                    model.id,
                )
            preferred_model_id = current_model_id or work_item.best_trained_model_id
        if preferred_model_id is not None:
            index = self._model_selector.findData(preferred_model_id)
            if index >= 0:
                self._model_selector.setCurrentIndex(index)
        if self._model_selector.count() > 0 and self._model_selector.currentIndex() < 0:
            self._model_selector.setCurrentIndex(0)
        self._model_selector.blockSignals(False)

    def _refresh_best_model_label(self, work_item: WorkItemRow, trained_models: list[TrainedModelRow]) -> None:
        if self._available_trained_models is not None:
            if not self._available_trained_models:
                self._best_model_label.setText(self.tr("No compatible trained models are available yet."))
                return
            selected_option = self._selected_compatible_model()
            best_option = next(
                (option for option in self._available_trained_models if option.is_best_for_work_item),
                None,
            )
            if selected_option is None:
                self._best_model_label.setText(self.tr("Choose one trained model to start prediction."))
                return
            if best_option is None or selected_option.trained_model_id == best_option.trained_model_id:
                self._best_model_label.setText(
                    self.tr("Compatible model selected: {model_name}.").format(
                        model_name=selected_option.model_display_name
                    )
                )
                return
            self._best_model_label.setText(
                self.tr("Current model: {selected_model}. Source best model: {best_model}.").format(
                    selected_model=selected_option.model_display_name,
                    best_model=best_option.model_display_name,
                )
            )
            return
        if not trained_models:
            self._best_model_label.setText(self.tr("No trained models are available yet."))
            return
        selected_model_id = self._current_model_id()
        best_model = next((model for model in trained_models if model.id == work_item.best_trained_model_id), None)
        selected_model = next((model for model in trained_models if model.id == selected_model_id), None)
        if selected_model is None:
            self._best_model_label.setText(self.tr("Choose one trained model to start prediction."))
            return
        selected_name = self._trained_model_label(selected_model)
        if best_model is None:
            self._best_model_label.setText(
                self.tr("Current model: {model_name}.").format(model_name=selected_name)
            )
            return
        best_name = self._trained_model_label(best_model)
        if selected_model.id == best_model.id:
            self._best_model_label.setText(
                self.tr("Best model selected: {model_name}.").format(model_name=best_name)
            )
            return
        self._best_model_label.setText(
            self.tr("Current model: {selected_model}. Best available model: {best_model}.").format(
                selected_model=selected_name,
                best_model=best_name,
            )
        )

    def _refresh_task_table(self, work_item_id: str) -> None:
        current_task_id = self._preferred_task_id or self._selected_task_id()
        tasks = [
            task
            for task in reversed(self._ml_service.list_work_item_tasks(work_item_id))
            if task.task_type is MLTaskType.INFERENCE
        ]
        self._task_table.setRowCount(len(tasks))
        selected_preferred = False
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
            if current_task_id == task.id:
                self._task_table.selectRow(row_index)
                selected_preferred = True

        if selected_preferred:
            self._preferred_task_id = None
            return
        if self._task_table.rowCount() > 0 and self._task_table.currentRow() < 0:
            self._task_table.selectRow(0)

    def _submit_manual_inference(self) -> None:
        model_id = self._current_model_id()
        if model_id is None:
            self._set_raw_message(self.tr("Choose one trained model before prediction can start."), is_error=True)
            return
        if self._row_editor.has_partial_rows() or not self._row_editor.has_complete_rows():
            self._set_raw_message(
                self.tr("Complete every value in at least one input row before prediction can start."),
                is_error=True,
            )
            return

        try:
            work_item = self._work_item_service.get_work_item(self._preparation_result.work_item_id)
            csv_path = self._dataset_service.materialize_manual_inference_csv(
                MaterializeManualInferenceCsvInput(
                    feature_columns=work_item.feature_columns,
                    rows=self._row_editor.complete_rows(),
                )
            )
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=self._preparation_result.work_item_id,
                    trained_model_id=model_id,
                    input_files=[str(csv_path)],
                )
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._preferred_task_id = task.id
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
        self._load_batch_files(file_paths)

    def _load_batch_files(self, file_paths: list[str]) -> None:
        self._batch_file_list.clear()
        self._batch_inspections.clear()
        skipped: list[str] = []
        feature_columns = list(self._preparation_result.feature_columns)

        for raw_path in file_paths:
            absolute_path = str(Path(raw_path).resolve())
            try:
                inspection = self._dataset_service.inspect_source_file(
                    InspectDatasetInput(source_path=absolute_path)
                )
            except Exception as exc:
                skipped.append(f"{Path(raw_path).name}: {exc}")
                continue
            available_columns = {column.name for column in inspection.columns}
            missing_columns = [column for column in feature_columns if column not in available_columns]
            if missing_columns:
                skipped.append(
                    self.tr("{file_name}: missing columns {columns}").format(
                        file_name=inspection.file_name,
                        columns=", ".join(missing_columns),
                    )
                )
                continue
            item = QListWidgetItem(
                self.tr("{file_name} · {row_count} rows").format(
                    file_name=inspection.file_name,
                    row_count=str(inspection.row_count),
                )
            )
            item.setData(Qt.UserRole, inspection.source_path)
            self._batch_file_list.addItem(item)
            self._batch_inspections[inspection.source_path] = inspection

        if self._batch_file_list.count() > 0:
            self._batch_file_list.setCurrentRow(0)
        self._refresh_batch_preview()
        self._refresh_action_state()

        if skipped and self._batch_file_list.count() == 0:
            self._set_raw_message("\n".join(skipped), is_error=True)
        elif skipped:
            self._set_raw_message("\n".join(skipped), is_error=True)

    def _submit_batch_inference(self) -> None:
        model_id = self._current_model_id()
        if model_id is None:
            self._set_raw_message(self.tr("Choose one trained model before prediction can start."), is_error=True)
            return

        input_files = [self._batch_file_path_at(index) for index in range(self._batch_file_list.count())]
        if not input_files:
            self._set_raw_message(self.tr("Load at least one compatible batch file before prediction starts."), is_error=True)
            return
        try:
            task = self._ml_service.infer(
                InferWithFilesInput(
                    work_item_id=self._preparation_result.work_item_id,
                    trained_model_id=model_id,
                    input_files=input_files,
                )
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._preferred_task_id = task.id
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

    def _current_model_id(self) -> str | None:
        value = self._model_selector.currentData()
        return str(value) if value is not None else None

    def _load_selected_task_details(self) -> None:
        task_id = self._selected_task_id()
        self._current_result_dataset_id = None
        self._current_result_path = None
        self._open_result_button.setEnabled(False)
        self._export_result_button.setEnabled(False)
        if task_id is None:
            self._task_details_label.setText(self.tr("Select one prediction activity item to inspect its task details."))
            self._task_log_view.clear()
            self._clear_result_preview(self.tr("Run prediction to preview the result here."))
            return

        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        payload = details.task.result_payload or {}
        summary_lines = [
            self.tr("Task: {task_id}").format(task_id=details.task.id),
            self.tr("Status: {status}").format(status=self._translate_task_status(details.task.status)),
            self.tr("Model: {model_key}").format(model_key=payload.get("model_key", "")),
            self.tr("Rows: {row_count}").format(row_count=payload.get("row_count", "")),
        ]
        if details.task.error_summary:
            summary_lines.append(self.tr("Failure: {summary}").format(summary=details.task.error_summary))

        result_dataset_id = payload.get("result_dataset_id")
        canonical_output_path = payload.get("canonical_output_path")
        if isinstance(result_dataset_id, str) and isinstance(canonical_output_path, str):
            self._current_result_dataset_id = result_dataset_id
            self._current_result_path = canonical_output_path
            self._open_result_button.setEnabled(True)
            self._export_result_button.setEnabled(True)
            summary_lines.append(self.tr("Result: {path}").format(path=canonical_output_path))
            self._show_result_preview(task_id, canonical_output_path, payload)
        elif details.task.status is MLTaskStatus.RUNNING:
            self._clear_result_preview(self.tr("Prediction is running. Result preview appears automatically when it finishes."))
        elif details.task.status is MLTaskStatus.FAILED:
            self._clear_result_preview(self.tr("Prediction failed. Open the advanced task details to inspect the failure summary and logs."))
        else:
            self._clear_result_preview(self.tr("Result preview is not available for the selected prediction activity yet."))

        self._task_details_label.setText("\n".join(summary_lines))
        self._task_log_view.set_logs(details.logs)

    def _show_result_preview(self, task_id: str, result_path: str, payload: dict[str, object]) -> None:
        if self._previewed_result_task_id != task_id or self._previewed_result_path != result_path:
            try:
                inspection = self._dataset_service.inspect_source_file(
                    InspectDatasetInput(source_path=str(Path(result_path).resolve()))
                )
            except Exception as exc:
                self._clear_result_preview(str(exc))
                return
            self._populate_preview_table(self._result_table, inspection)
            self._previewed_result_task_id = task_id
            self._previewed_result_path = result_path

        model_key = payload.get("model_key")
        prediction_column_name = payload.get("prediction_column_name")
        row_count = payload.get("row_count")
        self._result_summary_label.setText(
            self.tr("Previewing {row_count} result row(s). Output column: {prediction_column}. Model: {model_key}.").format(
                row_count=str(row_count or ""),
                prediction_column=str(prediction_column_name or ""),
                model_key=str(model_key or ""),
            )
        )

    def _refresh_batch_preview(self) -> None:
        selected_item = self._batch_file_list.currentItem()
        if selected_item is None and self._batch_file_list.count() > 0:
            self._batch_file_list.setCurrentRow(0)
            selected_item = self._batch_file_list.currentItem()
        if selected_item is None:
            self._batch_preview_summary_label.setText(
                self.tr("Load one or more compatible batch files to preview the first 5 rows.")
            )
            self._clear_preview_table(self._batch_preview_table)
            return
        source_path = selected_item.data(Qt.UserRole)
        inspection = self._batch_inspections.get(str(source_path))
        if inspection is None:
            self._batch_preview_summary_label.setText(self.tr("Preview data is temporarily unavailable for the selected batch file."))
            self._clear_preview_table(self._batch_preview_table)
            return
        self._batch_preview_summary_label.setText(
            self.tr("Previewing {file_name} · {row_count} rows.").format(
                file_name=inspection.file_name,
                row_count=str(inspection.row_count),
            )
        )
        self._populate_preview_table(self._batch_preview_table, inspection)

    def _refresh_action_state(self) -> None:
        has_model = self._current_model_id() is not None
        has_complete_rows = self._row_editor.has_complete_rows()
        has_partial_rows = self._row_editor.has_partial_rows()
        has_batch_files = self._batch_file_list.count() > 0
        self._manual_submit_button.setEnabled(has_model and has_complete_rows and not has_partial_rows)
        self._batch_submit_button.setEnabled(has_model and has_batch_files)

        if not has_model:
            self._manual_hint_label.setText(self.tr("Choose one trained model to enable manual prediction."))
            self._batch_hint_label.setText(self.tr("Choose one trained model, then load compatible batch files."))
            return
        if has_partial_rows:
            self._manual_hint_label.setText(
                self.tr("Complete every value in the current row set before manual prediction can start.")
            )
        elif has_complete_rows:
            self._manual_hint_label.setText(
                self.tr("Manual prediction is ready. Every populated row has complete input values.")
            )
        else:
            self._manual_hint_label.setText(
                self.tr("Enter one or more complete rows below to enable manual prediction.")
            )

        if has_batch_files:
            self._batch_hint_label.setText(
                self.tr("Batch prediction is ready. The preview below shows the selected file.")
            )
        else:
            self._batch_hint_label.setText(
                self.tr("Choose one or more files with the required input columns.")
            )

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

    def _model_display_name(self, model_key: str) -> str:
        try:
            return self._ml_service.get_model(model_key).display_name
        except Exception:
            return model_key

    def _trained_model_label(self, model: TrainedModelRow) -> str:
        metadata = parse_trained_model_metadata(model.metadata_payload)
        if metadata is not None and metadata.saved_name:
            return metadata.saved_name
        return self._model_display_name(model.model_key)

    def _selected_compatible_model(self) -> CompatibleTrainedModelOption | None:
        if self._available_trained_models is None:
            return None
        selected_model_id = self._current_model_id()
        if selected_model_id is None:
            return None
        return next(
            (
                option
                for option in self._available_trained_models
                if option.trained_model_id == selected_model_id
            ),
            None,
        )

    def _batch_file_path_at(self, index: int) -> str:
        item = self._batch_file_list.item(index)
        if item is None:
            raise ValidationError("Selected batch file is unavailable.")
        source_path = item.data(Qt.UserRole)
        if not isinstance(source_path, str) or not source_path:
            raise ValidationError("Selected batch file is unavailable.")
        return source_path

    def _configure_preview_table(self, table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(140)

    def _populate_preview_table(self, table: QTableWidget, inspection: DatasetInspection) -> None:
        table.clear()
        table.setColumnCount(len(inspection.preview_columns))
        table.setHorizontalHeaderLabels(inspection.preview_columns)
        table.setRowCount(len(inspection.preview_rows))
        for row_index, row in enumerate(inspection.preview_rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))
        table.resizeColumnsToContents()

    def _clear_preview_table(self, table: QTableWidget) -> None:
        table.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

    def _clear_result_preview(self, summary_text: str) -> None:
        self._result_summary_label.setText(summary_text)
        self._clear_preview_table(self._result_table)
        self._previewed_result_task_id = None
        self._previewed_result_path = None
