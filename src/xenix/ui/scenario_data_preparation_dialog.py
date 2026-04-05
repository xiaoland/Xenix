from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QFileDialog, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

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
from .widgets.column_selection import ColumnSelectionWidget
from .widgets.dataset_summary import DatasetSummaryWidget
from .widgets.file_drop_zone import FileDropZone


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

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._drop_zone = FileDropZone()
        self._choose_file_button = QPushButton()
        self._summary_widget = DatasetSummaryWidget()
        self._column_selection = ColumnSelectionWidget()
        self._message_label = QLabel()
        self._continue_button = QPushButton()

        self.resize(860, 700)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()

    def preparation_result(self) -> ScenarioWorkItemPreparationResult | None:
        return self._preparation_result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._summary_label.setWordWrap(True)
        self._message_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 20px; font-weight: 600;")

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self._drop_zone, 1)
        actions.addWidget(self._choose_file_button, 0)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addLayout(actions)
        layout.addWidget(self._summary_widget)
        layout.addWidget(self._column_selection, 1)
        layout.addWidget(self._message_label)
        layout.addWidget(self._continue_button)

    def _wire_events(self) -> None:
        self._drop_zone.file_dropped.connect(self._inspect_path)
        self._choose_file_button.clicked.connect(self._choose_file)
        self._continue_button.clicked.connect(self._prepare_work_item)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Prepare Scenario Data"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr("Upload one dataset, choose the prediction target and input columns, then continue to training.")
        )
        self._choose_file_button.setText(self.tr("Choose File"))
        self._continue_button.setText(self.tr("Continue to Training"))
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
        try:
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(Path(file_path).resolve()))
            )
        except XenixError as exc:
            self._current_inspection = None
            self._current_source_path = None
            self._summary_widget.clear()
            self._column_selection.clear()
            self._set_message(str(exc), is_error=True)
            return

        self._current_source_path = inspection.source_path
        self._current_inspection = inspection
        self._summary_widget.set_inspection(inspection)
        self._column_selection.set_columns(inspection.columns)
        self._set_message(self.tr("Dataset inspected. Choose columns, then continue."), is_error=False)

    def _prepare_work_item(self) -> None:
        if self._current_inspection is None or self._current_source_path is None:
            self._set_message(self.tr("Choose and inspect a dataset before continuing."), is_error=True)
            return

        try:
            self._preparation_result = self._workflow_service.prepare_work_item(
                PrepareScenarioWorkItemInput(
                    template_key=self._template.key,
                    source_path=self._current_source_path,
                    feature_columns=self._column_selection.selected_feature_columns(),
                    target_columns=self._column_selection.selected_target_columns(),
                )
            )
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(self.tr("Data preparation finished. Training can start next."), is_error=False)
        QMessageBox.information(
            self,
            self.tr("Prepared"),
            self.tr("The scenario work item is ready for training."),
        )
        self.accept()

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._message_label.setText(message)
        self._message_label.setStyleSheet("color: #b42318;" if is_error else "color: #17643a;")
