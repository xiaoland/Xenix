from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QT_TRANSLATE_NOOP
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.dataset_inspection import DatasetInspection, InspectDatasetInput
from ..services.dataset_service import DatasetService, RegisterDatasetInput
from ..services.project_service import CreateProjectInput, ProjectService
from ..services.work_item_service import CreateWorkItemInput, WorkItemService
from .native_widgets import mark_status_label
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
        self._message_template: str | None = None
        self._message_kwargs: dict[str, str] = {}
        self._raw_message: str | None = None

        self._project_label = QLabel()
        self._dataset_name_label = QLabel()
        self._work_item_name_label = QLabel()
        self._project_selector = QComboBox()
        self._dataset_name_input = QLineEdit()
        self._work_item_name_input = QLineEdit()
        self._new_project_button = QPushButton()
        self._choose_file_button = QPushButton()
        self._create_button = QPushButton()
        self._drop_zone = FileDropZone()
        self._summary_widget = DatasetSummaryWidget()
        self._column_selection = ColumnSelectionWidget(single_target_selection=False)
        self._message_label = QLabel()
        self._message_label.setWordWrap(True)

        self._build_ui()
        self._wire_events()
        self._reload_projects()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(14)

        header_layout = QGridLayout()
        header_layout.setHorizontalSpacing(12)
        header_layout.setVerticalSpacing(8)

        self._project_selector.setMinimumWidth(220)

        self._new_project_button.clicked.connect(self._create_project)
        self._choose_file_button.clicked.connect(self._choose_file)
        self._create_button.clicked.connect(self._create_work_item)

        header_layout.addWidget(self._project_label, 0, 0)
        header_layout.addWidget(self._project_selector, 0, 1)
        header_layout.addWidget(self._new_project_button, 0, 2)
        header_layout.addWidget(self._dataset_name_label, 1, 0)
        header_layout.addWidget(self._dataset_name_input, 1, 1, 1, 2)
        header_layout.addWidget(self._work_item_name_label, 2, 0)
        header_layout.addWidget(self._work_item_name_input, 2, 1, 1, 2)
        root_layout.addLayout(header_layout)

        import_layout = QHBoxLayout()
        import_layout.setSpacing(12)
        import_layout.addWidget(self._drop_zone, 1)
        import_layout.addWidget(self._choose_file_button, 0)
        root_layout.addLayout(import_layout)

        root_layout.addWidget(self._summary_widget)
        root_layout.addWidget(self._column_selection, 1)
        root_layout.addWidget(self._message_label)
        root_layout.addWidget(self._create_button)

    def _wire_events(self) -> None:
        self._drop_zone.file_dropped.connect(self._inspect_path)

    def retranslate_ui(self) -> None:
        self._project_label.setText(self.tr("Project"))
        self._dataset_name_label.setText(self.tr("Dataset Name"))
        self._work_item_name_label.setText(self.tr("Work Item Name"))
        self._dataset_name_input.setPlaceholderText(self.tr("Dataset name"))
        self._work_item_name_input.setPlaceholderText(self.tr("Work item name"))
        self._new_project_button.setText(self.tr("New Project"))
        self._choose_file_button.setText(self.tr("Choose File"))
        self._create_button.setText(self.tr("Create Work Item"))

        if self._message_template is None:
            if self._raw_message is not None:
                self._message_label.setText(self._raw_message)
            else:
                self._message_label.setText(
                    self.tr("Select a project, inspect a dataset, then create an immutable work item.")
                )
        else:
            self._message_label.setText(self.tr(self._message_template).format(**self._message_kwargs))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

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

    def current_project_id(self) -> str | None:
        value = self._project_selector.currentData()
        return str(value) if value is not None else None

    def _create_project(self) -> None:
        name, accepted = QInputDialog.getText(self, self.tr("New Project"), self.tr("Project name"))
        if not accepted:
            return
        try:
            project = self._project_service.create_project(CreateProjectInput(name=name))
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._reload_projects()
        index = self._project_selector.findData(project.id)
        if index >= 0:
            self._project_selector.setCurrentIndex(index)
        self._set_ui_message(
            QT_TRANSLATE_NOOP("DatasetWorkspace", "Project '{project_name}' created."),
            project_name=project.name,
        )

    def _choose_file(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose Dataset File"),
            "",
            self._dataset_file_filter(),
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
            self._set_raw_message(str(exc), is_error=True)
            return

        self._current_source_path = inspection.source_path
        self._current_inspection = inspection
        self._dataset_name_input.setText(Path(inspection.file_name).stem)
        if not self._work_item_name_input.text().strip():
            self._work_item_name_input.setText(Path(inspection.file_name).stem)
        self._summary_widget.set_inspection(inspection)
        self._column_selection.set_columns(inspection.columns)
        self._set_ui_message(
            QT_TRANSLATE_NOOP("DatasetWorkspace", "Dataset inspected. Select columns, then create a work item.")
        )

    def _create_work_item(self) -> None:
        project_id = self.current_project_id()
        inspection = self._current_inspection
        if project_id is None:
            self._set_ui_message(
                QT_TRANSLATE_NOOP(
                    "DatasetWorkspace",
                    "Select or create a project before creating a work item.",
                ),
                is_error=True,
            )
            return
        if inspection is None or self._current_source_path is None:
            self._set_ui_message(
                QT_TRANSLATE_NOOP("DatasetWorkspace", "Inspect a dataset before creating a work item."),
                is_error=True,
            )
            return

        dataset_name = self._dataset_name_input.text().strip() or Path(inspection.file_name).stem
        work_item_name = self._work_item_name_input.text().strip() or dataset_name
        try:
            dataset = self._dataset_service.register_dataset(
                RegisterDatasetInput(
                    project_id=project_id,
                    source_path=self._current_source_path,
                    name=dataset_name,
                )
            )
            work_item = self._work_item_service.create_work_item(
                CreateWorkItemInput(
                    project_id=project_id,
                    name=work_item_name,
                    source_dataset_id=dataset.id,
                    feature_columns=self._column_selection.selected_feature_columns(),
                    target_columns=self._column_selection.selected_target_columns(),
                )
            )
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP(
                "DatasetWorkspace",
                "Work item '{work_item_name}' created with its managed dataset copy.",
            ),
            work_item_name=work_item.name,
        )
        QMessageBox.information(
            self,
            self.tr("Created"),
            self.tr("Work item created. You can now use it in the training and inference workspaces."),
        )

    def _dataset_file_filter(self) -> str:
        return self.tr(
            "Supported Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)"
        )

    def _set_ui_message(self, template: str, *, is_error: bool = False, **kwargs: str) -> None:
        self._message_template = template
        self._message_kwargs = {key: str(value) for key, value in kwargs.items()}
        self._raw_message = None
        self._message_label.setText(self.tr(template).format(**self._message_kwargs))
        mark_status_label(self._message_label, is_error=is_error)

    def _set_raw_message(self, message: str, *, is_error: bool = False) -> None:
        self._message_template = None
        self._message_kwargs = {}
        self._raw_message = message
        self._message_label.setText(message)
        mark_status_label(self._message_label, is_error=is_error)
