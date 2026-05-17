from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.dataset_inspection import DatasetInspection, InspectDatasetInput
from ..services.dataset_service import DatasetService
from ..services.scenario_template_service import ScenarioTemplate
from ..services.scenario_workflow_service import (
    PrepareScenarioWorkItemInput,
    ScenarioWorkItemPreparationResult,
    ScenarioWorkflowService,
)
from .scenario_template_text import localized_template_display_name
from .native_widgets import emphasize_label, mark_status_label
from .widgets.column_selection import ColumnSelectionWidget
from .widgets.dataset_summary import DatasetSummaryWidget
from .widgets.file_drop_zone import FileDropZone


class _DataPreparationSignals(QObject):
    inspection_succeeded = Signal(int, object)
    inspection_failed = Signal(int, str)
    preparation_succeeded = Signal(int, object)
    preparation_failed = Signal(int, str)


class ScenarioDataPreparationDialog(QDialog):
    def __init__(
        self,
        template: ScenarioTemplate,
        dataset_service: DatasetService,
        workflow_service: ScenarioWorkflowService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._dataset_service = dataset_service
        self._workflow_service = workflow_service
        self._current_inspection: DatasetInspection | None = None
        self._current_source_path: str | None = None
        self._preparation_result: ScenarioWorkItemPreparationResult | None = None
        self._next_operation_id = 0
        self._active_operation_id: int | None = None
        self._active_operation_kind: str | None = None

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._drop_zone = FileDropZone()
        self._choose_file_button = QPushButton()
        self._summary_widget = DatasetSummaryWidget()
        self._column_selection = ColumnSelectionWidget(
            single_target_selection=self._template.required_target_count == 1,
            required_target_count=self._template.required_target_count,
        )
        self._busy_label = QLabel()
        self._busy_indicator = QProgressBar()
        self._message_label = QLabel()
        self._continue_button = QPushButton()
        self._signals = _DataPreparationSignals(self)

        self.resize(860, 700)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        self._refresh_interaction_state()

    def preparation_result(self) -> ScenarioWorkItemPreparationResult | None:
        return self._preparation_result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._summary_label.setWordWrap(True)
        self._busy_label.setWordWrap(True)
        self._message_label.setWordWrap(True)
        emphasize_label(self._title_label, point_delta=2)
        self._busy_indicator.setRange(0, 0)
        self._busy_indicator.setTextVisible(False)
        self._busy_indicator.hide()
        self._busy_label.hide()

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self._drop_zone, 1)
        actions.addWidget(self._choose_file_button, 0)

        busy_row = QHBoxLayout()
        busy_row.setSpacing(10)
        busy_row.addWidget(self._busy_indicator, 0)
        busy_row.addWidget(self._busy_label, 1)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addLayout(actions)
        layout.addWidget(self._summary_widget)
        layout.addWidget(self._column_selection, 1)
        layout.addLayout(busy_row)
        layout.addWidget(self._message_label)
        layout.addWidget(self._continue_button)

    def _wire_events(self) -> None:
        self._drop_zone.file_dropped.connect(self._inspect_path)
        self._choose_file_button.clicked.connect(self._choose_file)
        self._continue_button.clicked.connect(self._prepare_work_item)
        self._column_selection.selection_changed.connect(self._refresh_interaction_state)
        self._signals.inspection_succeeded.connect(self._on_inspection_succeeded)
        self._signals.inspection_failed.connect(self._on_inspection_failed)
        self._signals.preparation_succeeded.connect(self._on_preparation_succeeded)
        self._signals.preparation_failed.connect(self._on_preparation_failed)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Prepare Scenario Data"))
        self._title_label.setText(localized_template_display_name(self._template))
        if self._template.required_target_count == 0:
            self._summary_label.setText(
                self.tr("Upload one dataset, choose one or more input columns, then continue to training.")
            )
        else:
            self._summary_label.setText(
                self.tr("Upload one dataset, choose the prediction target and input columns, then continue to training.")
            )
        self._choose_file_button.setText(self.tr("Choose File"))
        self._continue_button.setText(self.tr("Continue to Training"))
        self._reload_busy_text()
        if not self._message_label.text():
            self._set_message(self.tr("Choose a dataset file to begin."), is_error=False)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _choose_file(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose Dataset File"),
            "",
            self.tr("Supported Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)"),
        )
        if file_path:
            self._inspect_path(file_path)

    def _inspect_path(self, file_path: str) -> None:
        operation_id = self._start_busy_operation("inspection")
        self._preparation_result = None
        self._current_inspection = None
        self._current_source_path = None
        self._summary_widget.clear()
        self._column_selection.clear()
        thread = threading.Thread(
            target=self._run_inspection,
            args=(operation_id, file_path),
            daemon=True,
        )
        thread.start()

    def _prepare_work_item(self) -> None:
        if self._current_inspection is None or self._current_source_path is None:
            self._set_message(self.tr("Choose and inspect a dataset before continuing."), is_error=True)
            return
        if not self._has_valid_column_selection():
            self._set_message(self._invalid_selection_message(), is_error=True)
            return

        operation_id = self._start_busy_operation("preparation")
        request = PrepareScenarioWorkItemInput(
            template_key=self._template.key,
            source_path=self._current_source_path,
            feature_columns=self._column_selection.selected_feature_columns(),
            target_columns=self._column_selection.selected_target_columns(),
        )
        thread = threading.Thread(
            target=self._run_prepare_work_item,
            args=(operation_id, request),
            daemon=True,
        )
        thread.start()

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._message_label.setText(message)
        mark_status_label(self._message_label, is_error=is_error)

    def _run_inspection(self, operation_id: int, file_path: str) -> None:
        try:
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(Path(file_path).resolve()))
            )
        except XenixError as exc:
            self._signals.inspection_failed.emit(operation_id, str(exc))
            return
        self._signals.inspection_succeeded.emit(operation_id, inspection)

    def _run_prepare_work_item(self, operation_id: int, request: PrepareScenarioWorkItemInput) -> None:
        try:
            prepared = self._workflow_service.prepare_work_item(request)
        except XenixError as exc:
            self._signals.preparation_failed.emit(operation_id, str(exc))
            return
        self._signals.preparation_succeeded.emit(operation_id, prepared)

    def _on_inspection_succeeded(self, operation_id: int, inspection: DatasetInspection) -> None:
        if not self._complete_busy_operation(operation_id, "inspection"):
            return
        self._current_source_path = inspection.source_path
        self._current_inspection = inspection
        self._summary_widget.set_inspection(inspection)
        self._column_selection.set_columns(inspection.columns)
        self._set_message(self.tr("Dataset inspected. Choose columns, then continue."), is_error=False)
        self._refresh_interaction_state()

    def _on_inspection_failed(self, operation_id: int, message: str) -> None:
        if not self._complete_busy_operation(operation_id, "inspection"):
            return
        self._current_inspection = None
        self._current_source_path = None
        self._summary_widget.clear()
        self._column_selection.clear()
        self._set_message(message, is_error=True)
        self._refresh_interaction_state()

    def _on_preparation_succeeded(self, operation_id: int, prepared: ScenarioWorkItemPreparationResult) -> None:
        if not self._complete_busy_operation(operation_id, "preparation"):
            return
        self._preparation_result = prepared
        self._set_message(self.tr("Data preparation finished. Training can start next."), is_error=False)
        QMessageBox.information(
            self,
            self.tr("Prepared"),
            self.tr("The scenario work item is ready for training."),
        )
        self.accept()

    def _on_preparation_failed(self, operation_id: int, message: str) -> None:
        if not self._complete_busy_operation(operation_id, "preparation"):
            return
        self._set_message(message, is_error=True)

    def _start_busy_operation(self, operation_kind: str) -> int:
        self._next_operation_id += 1
        self._active_operation_id = self._next_operation_id
        self._active_operation_kind = operation_kind
        self._reload_busy_text()
        self._busy_indicator.show()
        self._busy_label.show()
        self._refresh_interaction_state()
        return self._active_operation_id

    def _complete_busy_operation(self, operation_id: int, operation_kind: str) -> bool:
        if self._active_operation_id != operation_id or self._active_operation_kind != operation_kind:
            return False
        self._active_operation_id = None
        self._active_operation_kind = None
        self._busy_indicator.hide()
        self._busy_label.hide()
        self._refresh_interaction_state()
        return True

    def _reload_busy_text(self) -> None:
        if self._active_operation_kind == "inspection":
            self._busy_label.setText(self.tr("Inspecting dataset..."))
        elif self._active_operation_kind == "preparation":
            self._busy_label.setText(self.tr("Preparing scenario work item..."))
        else:
            self._busy_label.clear()

    def _refresh_interaction_state(self) -> None:
        is_busy = self._active_operation_kind is not None
        has_inspection = self._current_inspection is not None
        has_valid_column_selection = has_inspection and self._has_valid_column_selection()
        self._drop_zone.setEnabled(not is_busy)
        self._choose_file_button.setEnabled(not is_busy)
        self._summary_widget.setEnabled(not is_busy)
        self._column_selection.setEnabled(not is_busy and has_inspection)
        self._continue_button.setEnabled(not is_busy and has_valid_column_selection)

    def _has_valid_column_selection(self) -> bool:
        feature_columns = self._column_selection.selected_feature_columns()
        target_columns = self._column_selection.selected_target_columns()
        if len(feature_columns) < self._template.min_feature_columns:
            return False
        if len(target_columns) != self._template.required_target_count:
            return False
        if set(feature_columns) & set(target_columns):
            return False
        return True

    def _invalid_selection_message(self) -> str:
        if self._template.required_target_count == 0:
            return self.tr("Choose valid input columns before continuing.")
        return self.tr("Choose valid input columns and a prediction target before continuing.")
