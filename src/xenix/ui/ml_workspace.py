from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QT_TRANSLATE_NOOP, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
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
from ..services.ml_service import (
    BulkTuneWithEvaluateInput,
    BulkTuningSelection,
    FitWithEvaluateInput,
    MLService,
)
from ..services.project_service import ProjectService
from ..services.storage.models import MLTaskArtifactKind, MLTaskStatus, MLTaskType
from ..services.trained_model_metadata import parse_trained_model_metadata
from ..services.work_item_service import WorkItemService
from .widgets.json_schema_form import JsonSchemaFormWidget
from .widgets.task_log_view import TaskLogView


class MLWorkspace(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        ml_service: MLService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._ml_service = ml_service
        self._catalog = {entry.model_key: entry for entry in self._ml_service.list_models()}
        self._message_template: str | None = None
        self._message_kwargs: dict[str, str] = {}
        self._raw_message: str | None = None

        self._project_label = QLabel()
        self._work_item_label = QLabel()
        self._manual_model_label = QLabel()
        self._project_selector = QComboBox()
        self._work_item_selector = QComboBox()
        self._refresh_button = QPushButton()
        self._context_label = QLabel()
        self._context_label.setWordWrap(True)
        self._message_label = QLabel()
        self._message_label.setWordWrap(True)

        self._manual_model_selector = QComboBox()
        self._manual_form = JsonSchemaFormWidget()
        self._manual_submit_button = QPushButton()

        self._tuning_model_list = QListWidget()
        self._tuning_forms_container = QWidget()
        self._tuning_forms_layout = QVBoxLayout(self._tuning_forms_container)
        self._tuning_forms_layout.setContentsMargins(0, 0, 0, 0)
        self._tuning_forms_layout.setSpacing(10)
        self._tuning_submit_button = QPushButton()
        self._tuning_forms: dict[str, JsonSchemaFormWidget] = {}

        self._task_table = QTableWidget(0, 5)
        self._task_details_label = QLabel()
        self._task_details_label.setWordWrap(True)
        self._task_log_view = TaskLogView()
        self._trained_model_list = QListWidget()

        self._manual_tab = QWidget()
        self._tuning_tab = QWidget()
        self._operation_tabs = QTabWidget()
        self._task_group = QGroupBox()
        self._trained_models_group = QGroupBox()
        self._task_detail_group = QGroupBox()

        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self.refresh_runtime)

        self._build_ui()
        self._wire_events()
        self._reload_projects()
        self.retranslate_ui()
        self._timer.start()

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
        header.addWidget(self._project_label, 0, 0)
        header.addWidget(self._project_selector, 0, 1)
        header.addWidget(self._work_item_label, 1, 0)
        header.addWidget(self._work_item_selector, 1, 1)
        header.addWidget(self._refresh_button, 0, 2, 2, 1)
        root_layout.addLayout(header)
        root_layout.addWidget(self._context_label)

        self._build_manual_tab()
        self._build_tuning_tab()
        self._operation_tabs.addTab(self._manual_tab, "")
        self._operation_tabs.addTab(self._tuning_tab, "")
        root_layout.addWidget(self._operation_tabs)

        runtime_splitter = QSplitter(Qt.Horizontal)
        runtime_splitter.addWidget(self._build_task_panel())
        runtime_splitter.addWidget(self._build_details_panel())
        runtime_splitter.setStretchFactor(0, 3)
        runtime_splitter.setStretchFactor(1, 2)
        root_layout.addWidget(runtime_splitter, 1)
        root_layout.addWidget(self._message_label)

    def _build_manual_tab(self) -> None:
        layout = QVBoxLayout(self._manual_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(self._manual_model_label)
        row.addWidget(self._manual_model_selector, 1)
        layout.addLayout(row)
        layout.addWidget(self._manual_form)
        layout.addWidget(self._manual_submit_button)

    def _build_tuning_tab(self) -> None:
        layout = QVBoxLayout(self._tuning_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        split = QSplitter(Qt.Horizontal)
        self._tuning_model_list.setSelectionMode(QAbstractItemView.MultiSelection)
        split.addWidget(self._tuning_model_list)

        forms_frame = QFrame()
        forms_layout = QVBoxLayout(forms_frame)
        forms_layout.setContentsMargins(0, 0, 0, 0)
        forms_layout.addWidget(self._tuning_forms_container)
        split.addWidget(forms_frame)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)

        layout.addWidget(split)
        layout.addWidget(self._tuning_submit_button)

    def _build_task_panel(self) -> QWidget:
        layout = QVBoxLayout(self._task_group)
        self._task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._task_table.verticalHeader().setVisible(False)
        layout.addWidget(self._task_table)
        return self._task_group

    def _build_details_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        trained_models_layout = QVBoxLayout(self._trained_models_group)
        trained_models_layout.addWidget(self._trained_model_list)

        detail_layout = QVBoxLayout(self._task_detail_group)
        detail_layout.addWidget(self._task_details_label)
        detail_layout.addWidget(self._task_log_view, 1)

        layout.addWidget(self._trained_models_group)
        layout.addWidget(self._task_detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._refresh_button.clicked.connect(self.refresh_runtime)
        self._project_selector.currentIndexChanged.connect(self._on_project_changed)
        self._work_item_selector.currentIndexChanged.connect(self.refresh_runtime)
        self._manual_model_selector.currentIndexChanged.connect(self._on_manual_model_changed)
        self._manual_submit_button.clicked.connect(self._submit_manual_fit)
        self._tuning_model_list.itemSelectionChanged.connect(self._rebuild_tuning_forms)
        self._tuning_submit_button.clicked.connect(self._submit_tuning)
        self._task_table.itemSelectionChanged.connect(self._load_selected_task_details)

    def retranslate_ui(self) -> None:
        self._project_label.setText(self.tr("Project"))
        self._work_item_label.setText(self.tr("Work Item"))
        self._manual_model_label.setText(self.tr("Model"))
        self._refresh_button.setText(self.tr("Refresh"))
        self._manual_submit_button.setText(self.tr("Run Fit"))
        self._tuning_submit_button.setText(self.tr("Run Tuning"))
        self._operation_tabs.setTabText(0, self.tr("Manual Fit"))
        self._operation_tabs.setTabText(1, self.tr("Tuning"))
        self._task_group.setTitle(self.tr("Tasks"))
        self._trained_models_group.setTitle(self.tr("Trained Models"))
        self._task_detail_group.setTitle(self.tr("Task Details"))
        self._task_table.setHorizontalHeaderLabels(
            [
                self.tr("Status"),
                self.tr("Type"),
                self.tr("Model"),
                self.tr("Finished"),
                self.tr("Failure"),
            ]
        )
        self._rebuild_tuning_forms()
        self._reload_message_label()
        self.refresh_runtime()
        self._load_selected_task_details()

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

    def _populate_models(self) -> None:
        self._manual_model_selector.blockSignals(True)
        self._manual_model_selector.clear()
        self._tuning_model_list.clear()
        for entry in self._catalog.values():
            self._manual_model_selector.addItem(entry.display_name, entry.model_key)
            item = QListWidgetItem(entry.display_name)
            item.setData(Qt.UserRole, entry.model_key)
            self._tuning_model_list.addItem(item)
        self._manual_model_selector.blockSignals(False)
        self._on_manual_model_changed()

    def current_project_id(self) -> str | None:
        data = self._project_selector.currentData()
        return str(data) if data is not None else None

    def current_work_item_id(self) -> str | None:
        data = self._work_item_selector.currentData()
        return str(data) if data is not None else None

    def _on_project_changed(self, _index: int = -1) -> None:
        self._reload_work_items()
        self._populate_models()
        self.refresh_runtime()

    def _on_manual_model_changed(self, _index: int = -1) -> None:
        model_key = self._manual_model_selector.currentData()
        if model_key is None:
            self._manual_form.set_schema({})
            return
        entry = self._catalog[str(model_key)]
        self._manual_form.set_schema(entry.param_schema)

    def _rebuild_tuning_forms(self) -> None:
        current_values = {model_key: form.values() for model_key, form in self._tuning_forms.items()}
        while self._tuning_forms_layout.count():
            item = self._tuning_forms_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._tuning_forms.clear()

        selected_items = self._tuning_model_list.selectedItems()
        if not selected_items:
            placeholder = QLabel(self.tr("Select one or more models to configure their tuning grids."))
            placeholder.setWordWrap(True)
            self._tuning_forms_layout.addWidget(placeholder)
            return

        for item in selected_items:
            model_key = str(item.data(Qt.UserRole))
            entry = self._catalog[model_key]
            group = QGroupBox(entry.display_name)
            group_layout = QVBoxLayout(group)
            form = JsonSchemaFormWidget()
            form.set_schema(entry.param_grid_schema or {}, initial_values=current_values.get(model_key))
            group_layout.addWidget(form)
            self._tuning_forms_layout.addWidget(group)
            self._tuning_forms[model_key] = form
        self._tuning_forms_layout.addStretch(1)

    def refresh_runtime(self) -> None:
        work_item_id = self.current_work_item_id()
        if work_item_id is None:
            self._context_label.setText(self.tr("Select a project and work item to inspect the training workflow."))
            self._task_table.setRowCount(0)
            self._trained_model_list.clear()
            self._task_details_label.setText(self.tr("Select a task to inspect its details."))
            self._task_log_view.clear()
            return

        try:
            work_item = self._work_item_service.get_work_item(work_item_id)
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        if work_item.dataset_id is None or not work_item.feature_columns:
            self._context_label.setText(
                self.tr(
                    "This work item is not ready for training yet. Link a dataset and store feature/target columns in the dataset workspace first."
                )
            )
        else:
            target_text = ", ".join(work_item.target_columns) if work_item.target_columns else self.tr("(none)")
            self._context_label.setText(
                self.tr("Dataset linked. Features: {features}. Targets: {targets}.").format(
                    features=", ".join(work_item.feature_columns),
                    targets=target_text,
                )
            )

        self._refresh_task_table(work_item_id)
        self._refresh_trained_models(work_item)

    def _refresh_task_table(self, work_item_id: str) -> None:
        tasks = self._ml_service.list_work_item_tasks(work_item_id)
        current_task_id = self._selected_task_id()
        self._task_table.setRowCount(len(tasks))
        for row_index, task in enumerate(tasks):
            task_type = self._translate_task_type(task.task_type)
            model_key = ""
            if task.request_payload:
                if isinstance(task.request_payload.get("manual_training"), dict):
                    model_key = str(task.request_payload["manual_training"].get("model_key", ""))
                elif isinstance(task.request_payload.get("hyperparameter_tuning"), dict):
                    model_key = str(task.request_payload["hyperparameter_tuning"].get("model_key", ""))
                elif isinstance(task.request_payload.get("evaluate_model"), dict):
                    model_key = str(task.request_payload["evaluate_model"].get("model_key", ""))
            values = [
                self._translate_task_status(task.status),
                task_type,
                model_key,
                task.finished_at.isoformat() if task.finished_at else "",
                task.error_summary or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, task.id)
                self._task_table.setItem(row_index, column, item)

        if current_task_id is not None:
            for row in range(self._task_table.rowCount()):
                item = self._task_table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == current_task_id:
                    self._task_table.selectRow(row)
                    break

    def _refresh_trained_models(self, work_item: Any) -> None:
        trained_models = self._ml_service.list_trained_models(work_item.id)
        self._trained_model_list.clear()
        for model in trained_models:
            prefix = f"{self.tr('[Best]')} " if work_item.best_trained_model_id == model.id else ""
            metadata = parse_trained_model_metadata(model.metadata_payload)
            label = metadata.saved_name if metadata is not None and metadata.saved_name else model.model_key
            if metadata is not None and metadata.evaluation_primary_metric_name and metadata.evaluation_primary_metric_value is not None:
                label = (
                    f"{label} | "
                    f"{metadata.evaluation_primary_metric_name}={metadata.evaluation_primary_metric_value:.4f}"
                )
            self._trained_model_list.addItem(f"{prefix}{label}")

    def _load_selected_task_details(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            self._task_details_label.setText(self.tr("Select a task to inspect its details."))
            self._task_log_view.clear()
            return
        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        summary_lines = [
            self.tr("Task: {task_id}").format(task_id=details.task.id),
            self.tr("Type: {task_type}").format(task_type=self._translate_task_type(details.task.task_type)),
            self.tr("Status: {status}").format(status=self._translate_task_status(details.task.status)),
        ]
        if details.task.result_payload:
            summary_lines.append(
                self.tr("Result: {summary}").format(summary=self._summarize_result(details.task.result_payload))
            )
        if details.artifacts:
            summary_lines.append(self.tr("Artifacts:"))
            summary_lines.extend(
                self.tr("- {artifact_kind}: {path}").format(
                    artifact_kind=self._translate_artifact_kind(artifact.artifact_kind),
                    path=artifact.absolute_path,
                )
                for artifact in details.artifacts
            )
        self._task_details_label.setText("\n".join(summary_lines))
        self._task_log_view.set_logs(details.logs)

    def _submit_manual_fit(self) -> None:
        work_item_id = self.current_work_item_id()
        model_key = self._manual_model_selector.currentData()
        if work_item_id is None or model_key is None:
            self._set_ui_message(
                QT_TRANSLATE_NOOP("MLWorkspace", "Select a work item and model before submitting training."),
                is_error=True,
            )
            return
        try:
            task = self._ml_service.fit_with_evaluate(
                FitWithEvaluateInput(
                    work_item_id=work_item_id,
                    model_key=str(model_key),
                    params=self._manual_form.values(),
                )
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP("MLWorkspace", "Training task '{task_id}' queued."),
            task_id=task.id,
        )
        QMessageBox.information(
            self,
            self.tr("Queued"),
            self.tr("Fit task queued. Evaluation will follow automatically."),
        )
        self.refresh_runtime()

    def _submit_tuning(self) -> None:
        work_item_id = self.current_work_item_id()
        if work_item_id is None:
            self._set_ui_message(
                QT_TRANSLATE_NOOP("MLWorkspace", "Select a work item before submitting tuning."),
                is_error=True,
            )
            return
        selections: list[BulkTuningSelection] = []
        try:
            for model_key, form in self._tuning_forms.items():
                selections.append(BulkTuningSelection(model_key=model_key, param_grid=form.values()))
            if not selections:
                self._set_ui_message(
                    QT_TRANSLATE_NOOP("MLWorkspace", "Select one or more models before submitting tuning."),
                    is_error=True,
                )
                return
            tasks = self._ml_service.bulk_tune_with_evaluate(
                BulkTuneWithEvaluateInput(work_item_id=work_item_id, selections=selections)
            )
        except Exception as exc:
            self._set_raw_message(str(exc), is_error=True)
            return

        self._set_ui_message(
            QT_TRANSLATE_NOOP("MLWorkspace", "{count} tuning task(s) queued."),
            count=str(len(tasks)),
        )
        QMessageBox.information(
            self,
            self.tr("Queued"),
            self.tr("Tuning tasks queued. Evaluation will follow automatically."),
        )
        self.refresh_runtime()

    def _selected_task_id(self) -> str | None:
        selected_items = self._task_table.selectedItems()
        if not selected_items:
            return None
        return str(selected_items[0].data(Qt.UserRole))

    def _summarize_result(self, result_payload: dict[str, Any]) -> str:
        if isinstance(result_payload.get("evaluation"), dict):
            evaluation = result_payload["evaluation"]
            metric_name = evaluation.get("primary_metric_name", self.tr("metric"))
            metric_value = evaluation.get("primary_metric_value", "")
            return f"{metric_name}={metric_value}"
        if "best_params" in result_payload:
            return self.tr("Best params: {params}").format(params=result_payload["best_params"])
        if "params" in result_payload:
            return self.tr("Params: {params}").format(params=result_payload["params"])
        return str(result_payload)

    def _translate_task_status(self, status: MLTaskStatus) -> str:
        labels = {
            MLTaskStatus.PENDING: self.tr("Pending"),
            MLTaskStatus.RUNNING: self.tr("Running"),
            MLTaskStatus.SUCCEEDED: self.tr("Succeeded"),
            MLTaskStatus.FAILED: self.tr("Failed"),
            MLTaskStatus.CANCELLED: self.tr("Cancelled"),
        }
        return labels.get(status, str(status))

    def _translate_task_type(self, task_type: MLTaskType) -> str:
        labels = {
            MLTaskType.INSPECT_DATASET: self.tr("Inspect Dataset"),
            MLTaskType.FIT: self.tr("Fit"),
            MLTaskType.HYPERPARAMETER_TUNING: self.tr("Hyperparameter Tuning"),
            MLTaskType.EVALUATE: self.tr("Evaluate"),
            MLTaskType.INFERENCE: self.tr("Inference"),
        }
        return labels.get(task_type, str(task_type))

    def _translate_artifact_kind(self, artifact_kind: MLTaskArtifactKind) -> str:
        labels = {
            MLTaskArtifactKind.MODEL: self.tr("Model"),
            MLTaskArtifactKind.HOLDOUT_DATA: self.tr("Holdout Data"),
            MLTaskArtifactKind.TRAINING_REPORT: self.tr("Training Report"),
            MLTaskArtifactKind.EVALUATION_REPORT: self.tr("Evaluation Report"),
            MLTaskArtifactKind.INFERENCE_RESULT: self.tr("Inference Result"),
            MLTaskArtifactKind.EXPORT_FILE: self.tr("Export File"),
            MLTaskArtifactKind.OTHER: self.tr("Other"),
        }
        return labels.get(artifact_kind, str(artifact_kind))

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
