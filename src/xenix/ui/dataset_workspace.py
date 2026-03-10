from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.dataset_inspection import DatasetInspection, InspectDatasetInput
from ..services.dataset_service import DatasetService, RegisterDatasetInput
from ..services.project_service import CreateProjectInput, ProjectService
from ..services.work_item_service import (
    AttachDatasetSelectionInput,
    CreateWorkItemInput,
    WorkItemService,
)
from .widgets.column_selection import ColumnSelectionWidget
from .widgets.dataset_summary import DatasetSummaryWidget
from .widgets.file_drop_zone import FileDropZone


class DatasetWorkspace(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service

        self._current_inspection: DatasetInspection | None = None
        self._current_source_path: str | None = None

        self._project_selector = QComboBox()
        self._work_item_selector = QComboBox()
        self._dataset_name_input = QLineEdit()
        self._drop_zone = FileDropZone()
        self._summary_widget = DatasetSummaryWidget()
        self._column_selection = ColumnSelectionWidget()
        self._message_label = QLabel("Select a project and work item, then import a dataset.")
        self._message_label.setWordWrap(True)

        self._build_ui()
        self._wire_events()
        self._reload_projects()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(14)

        header_layout = QGridLayout()
        header_layout.setHorizontalSpacing(12)
        header_layout.setVerticalSpacing(8)

        self._project_selector.setMinimumWidth(220)
        self._work_item_selector.setMinimumWidth(220)
        self._dataset_name_input.setPlaceholderText("Dataset name")

        new_project_button = QPushButton("New Project")
        new_project_button.clicked.connect(self._create_project)
        self._new_project_button = new_project_button

        new_work_item_button = QPushButton("New Work Item")
        new_work_item_button.clicked.connect(self._create_work_item)
        self._new_work_item_button = new_work_item_button

        choose_file_button = QPushButton("Choose File")
        choose_file_button.clicked.connect(self._choose_file)
        self._choose_file_button = choose_file_button

        save_button = QPushButton("Save Dataset Setup")
        save_button.clicked.connect(self._save_selection)
        self._save_button = save_button

        header_layout.addWidget(QLabel("Project"), 0, 0)
        header_layout.addWidget(self._project_selector, 0, 1)
        header_layout.addWidget(new_project_button, 0, 2)
        header_layout.addWidget(QLabel("Work Item"), 1, 0)
        header_layout.addWidget(self._work_item_selector, 1, 1)
        header_layout.addWidget(new_work_item_button, 1, 2)
        header_layout.addWidget(QLabel("Dataset Name"), 2, 0)
        header_layout.addWidget(self._dataset_name_input, 2, 1, 1, 2)
        root_layout.addLayout(header_layout)

        import_layout = QHBoxLayout()
        import_layout.setSpacing(12)
        import_layout.addWidget(self._drop_zone, 1)
        import_layout.addWidget(choose_file_button, 0)
        root_layout.addLayout(import_layout)

        root_layout.addWidget(self._summary_widget)
        root_layout.addWidget(self._column_selection, 1)
        root_layout.addWidget(self._message_label)
        root_layout.addWidget(save_button)

    def _wire_events(self) -> None:
        self._drop_zone.file_dropped.connect(self._inspect_path)
        self._project_selector.currentIndexChanged.connect(self._on_project_changed)
        self._work_item_selector.currentIndexChanged.connect(self._load_work_item_state)

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
        current_work_item_id = self.current_work_item_id()
        self._work_item_selector.blockSignals(True)
        self._work_item_selector.clear()

        project_id = self.current_project_id()
        if project_id is not None:
            for work_item in self._work_item_service.list_work_items(project_id):
                self._work_item_selector.addItem(work_item.name, work_item.id)

        self._work_item_selector.blockSignals(False)

        if current_work_item_id is not None:
            index = self._work_item_selector.findData(current_work_item_id)
            if index >= 0:
                self._work_item_selector.setCurrentIndex(index)
        self._load_work_item_state()

    def current_project_id(self) -> str | None:
        value = self._project_selector.currentData()
        return str(value) if value is not None else None

    def current_work_item_id(self) -> str | None:
        value = self._work_item_selector.currentData()
        return str(value) if value is not None else None

    def _on_project_changed(self, _index: int = -1) -> None:
        self._reload_work_items()

    def _create_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Project", "Project name")
        if not accepted:
            return
        try:
            project = self._project_service.create_project(CreateProjectInput(name=name))
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._reload_projects()
        index = self._project_selector.findData(project.id)
        if index >= 0:
            self._project_selector.setCurrentIndex(index)
        self._set_message(f"Project '{project.name}' created.")

    def _create_work_item(self) -> None:
        project_id = self.current_project_id()
        if project_id is None:
            self._set_message("Create or select a project first.", is_error=True)
            return

        name, accepted = QInputDialog.getText(self, "New Work Item", "Work item name")
        if not accepted:
            return
        try:
            work_item = self._work_item_service.create_work_item(
                CreateWorkItemInput(project_id=project_id, name=name)
            )
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._reload_work_items()
        index = self._work_item_selector.findData(work_item.id)
        if index >= 0:
            self._work_item_selector.setCurrentIndex(index)
        self._set_message(f"Work item '{work_item.name}' created.")

    def _choose_file(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose Dataset File",
            "",
            "Supported Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)",
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
        self._dataset_name_input.setText(Path(inspection.file_name).stem)
        self._summary_widget.set_inspection(inspection)
        self._column_selection.set_columns(inspection.columns)
        self._set_message("Dataset inspected. Review the summary and select columns before saving.")

    def _load_work_item_state(self, _index: int = -1) -> None:
        work_item_id = self.current_work_item_id()
        if work_item_id is None:
            self._current_source_path = None
            self._current_inspection = None
            self._summary_widget.clear()
            self._column_selection.clear()
            return

        try:
            work_item = self._work_item_service.get_work_item(work_item_id)
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        if work_item.dataset_id is None:
            return

        try:
            dataset = self._dataset_service.get_dataset(work_item.dataset_id)
            inspection = self._dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=dataset.source_path)
            )
        except XenixError:
            return

        self._current_source_path = inspection.source_path
        self._current_inspection = inspection
        self._dataset_name_input.setText(dataset.name)
        self._summary_widget.set_inspection(inspection)
        self._column_selection.set_columns(
            inspection.columns,
            feature_columns=work_item.feature_columns,
            target_columns=work_item.target_columns,
        )

    def _save_selection(self) -> None:
        project_id = self.current_project_id()
        work_item_id = self.current_work_item_id()
        inspection = self._current_inspection
        if project_id is None:
            self._set_message("Select or create a project before saving.", is_error=True)
            return
        if work_item_id is None:
            self._set_message("Select or create a work item before saving.", is_error=True)
            return
        if inspection is None or self._current_source_path is None:
            self._set_message("Import and inspect a dataset before saving.", is_error=True)
            return

        dataset_name = self._dataset_name_input.text().strip() or Path(inspection.file_name).stem
        try:
            dataset = self._dataset_service.register_dataset(
                RegisterDatasetInput(
                    project_id=project_id,
                    source_path=self._current_source_path,
                    name=dataset_name,
                )
            )
            self._work_item_service.attach_dataset_selection(
                AttachDatasetSelectionInput(
                    work_item_id=work_item_id,
                    dataset_id=dataset.id,
                    feature_columns=self._column_selection.selected_feature_columns(),
                    target_columns=self._column_selection.selected_target_columns(),
                )
            )
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return

        self._set_message(f"Dataset '{dataset.name}' saved to the current work item.")
        QMessageBox.information(self, "Saved", "Dataset setup saved to the selected work item.")
        self._load_work_item_state()

    def _set_message(self, message: str, *, is_error: bool = False) -> None:
        self._message_label.setText(message)
        self._message_label.setStyleSheet(
            "color: #b42318;" if is_error else "color: #17643a;"
        )
