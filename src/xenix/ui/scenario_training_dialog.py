from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.ml_service import MLService
from ..services.scenario_template_service import ScenarioTemplate
from ..services.scenario_template_service import ScenarioTrainingPlanStep
from ..services.scenario_workflow_service import (
    ScenarioTrainingRun,
    ScenarioTrainingRunSnapshot,
    ScenarioTrainingStepSnapshot,
    ScenarioTrainingStepStatus,
    ScenarioWorkflowService,
    ScenarioWorkItemPreparationResult,
    StartScenarioTrainingRunInput,
)
from ..services.storage.models import MLTaskType
from .scenario_template_text import localized_template_display_name
from .widgets.task_log_view import TaskLogView


class ScenarioTrainingDialog(QDialog):
    continue_to_prediction_requested = Signal(object)

    def __init__(
        self,
        template: ScenarioTemplate,
        preparation_result: ScenarioWorkItemPreparationResult,
        workflow_service: ScenarioWorkflowService,
        ml_service: MLService,
        training_steps: list[ScenarioTrainingPlanStep] | None = None,
        *,
        start_immediately: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._preparation_result = preparation_result
        self._workflow_service = workflow_service
        self._ml_service = ml_service
        self._training_steps = list(training_steps or [])
        self._current_run: ScenarioTrainingRun | None = None
        self._current_snapshot: ScenarioTrainingRunSnapshot | None = None

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._status_summary_label = QLabel()
        self._best_model_label = QLabel()
        self._run_again_button = QPushButton()
        self._continue_button = QPushButton()

        self._step_table = QTableWidget(0, 5)
        self._task_details_label = QLabel()
        self._task_details_label.setWordWrap(True)
        self._task_log_view = TaskLogView()
        self._step_group = QGroupBox()
        self._detail_group = QGroupBox()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh_runtime)

        self.resize(980, 760)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        if start_immediately:
            self._start_training_run()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        self._summary_label.setWordWrap(True)
        self._status_summary_label.setWordWrap(True)
        self._best_model_label.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self._run_again_button)
        actions.addWidget(self._continue_button)
        actions.addStretch(1)

        self._step_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._step_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._step_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._step_table.verticalHeader().setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_step_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._status_summary_label)
        layout.addWidget(self._best_model_label)
        layout.addLayout(actions)
        layout.addWidget(splitter, 1)

    def _build_step_panel(self) -> QWidget:
        layout = QVBoxLayout(self._step_group)
        layout.addWidget(self._step_table)
        return self._step_group

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
        self._run_again_button.clicked.connect(self._start_training_run)
        self._continue_button.clicked.connect(self._continue_to_prediction)
        self._step_table.itemSelectionChanged.connect(self._load_selected_step_details)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Training Dashboard"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr("The selected model plan is running in the background. Review the result and continue when a best model is ready.")
        )
        self._run_again_button.setText(self.tr("Run Selected Plan Again"))
        self._continue_button.setText(self.tr("Continue to Prediction"))
        self._step_group.setTitle(self.tr("Training Steps"))
        self._detail_group.setTitle(self.tr("Task Details"))
        self._step_table.setHorizontalHeaderLabels(
            [
                self.tr("Step"),
                self.tr("Model"),
                self.tr("Training"),
                self.tr("Evaluate"),
                self.tr("Status"),
            ]
        )
        if self._current_snapshot is None:
            self._status_summary_label.setText(self.tr("Preparing the training plan..."))
            self._best_model_label.setText(self.tr("Best model: waiting for evaluation."))
            self._task_details_label.setText(self.tr("Select a plan step to inspect task details."))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh_runtime()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        super().closeEvent(event)

    def _start_training_run(self) -> None:
        self._current_run = self._workflow_service.start_training_run(
            StartScenarioTrainingRunInput(
                template_key=self._template.key,
                work_item_id=self._preparation_result.work_item_id,
                selected_steps=self._training_steps,
            )
        )
        self.refresh_runtime()
        self._timer.start()

    def refresh_runtime(self) -> None:
        if self._current_run is None:
            return
        self._current_snapshot = self._workflow_service.get_training_run_snapshot(self._current_run)
        self._refresh_summary(self._current_snapshot)
        self._refresh_step_table(self._current_snapshot)
        self._continue_button.setEnabled(self._current_snapshot.can_proceed_to_inference)
        if self._current_snapshot.is_terminal:
            self._timer.stop()

    def _refresh_summary(self, snapshot: ScenarioTrainingRunSnapshot) -> None:
        succeeded_count = sum(1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED)
        failed_count = sum(1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.FAILED)
        if snapshot.can_proceed_to_inference:
            self._status_summary_label.setText(
                self.tr("Training finished. {succeeded_count} plan step(s) succeeded and the best model is ready.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        elif failed_count > 0 and snapshot.is_terminal:
            self._status_summary_label.setText(
                self.tr(
                    "Training finished with partial failure. {succeeded_count} step(s) succeeded and {failed_count} step(s) failed."
                ).format(
                    succeeded_count=str(succeeded_count),
                    failed_count=str(failed_count),
                )
            )
        else:
            self._status_summary_label.setText(
                self.tr("Training is running. {succeeded_count} completed step(s) so far.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        self._best_model_label.setText(self._build_best_model_text(snapshot))

    def _build_best_model_text(self, snapshot: ScenarioTrainingRunSnapshot) -> str:
        if snapshot.best_trained_model_id is None:
            return self.tr("Best model: waiting for evaluation.")

        trained_models = self._ml_service.list_trained_models(snapshot.work_item_id)
        best_model_key = snapshot.best_trained_model_id
        for model in trained_models:
            if model.id == snapshot.best_trained_model_id:
                best_model_key = model.model_key
                break

        tasks = self._ml_service.list_work_item_tasks(snapshot.work_item_id)
        for task in tasks:
            if task.task_type is not MLTaskType.EVALUATE or not task.result_payload:
                continue
            evaluate_model = (task.request_payload or {}).get("evaluate_model", {})
            if evaluate_model.get("trained_model_id") != snapshot.best_trained_model_id:
                continue
            evaluation = task.result_payload.get("evaluation", {})
            metric_name = evaluation.get("primary_metric_name")
            metric_value = evaluation.get("primary_metric_value")
            if isinstance(metric_name, str) and metric_value is not None:
                return self.tr("Best model: {model_key} ({metric_name}={metric_value})").format(
                    model_key=str(best_model_key),
                    metric_name=metric_name,
                    metric_value=str(metric_value),
                )
        return self.tr("Best model: {model_key}").format(model_key=str(best_model_key))

    def _refresh_step_table(self, snapshot: ScenarioTrainingRunSnapshot) -> None:
        selected_step_key = self._selected_step_key()
        self._step_table.setRowCount(len(snapshot.step_snapshots))
        for row_index, step in enumerate(snapshot.step_snapshots):
            values = [
                self.tr("Step {number}").format(number=str(row_index + 1)),
                step.model_key,
                self._translate_task_status(step.root_status),
                self._translate_task_status(step.evaluate_status) if step.evaluate_status is not None else self.tr("Waiting"),
                self._translate_step_status(step.status),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.UserRole, step.step_key)
                self._step_table.setItem(row_index, column_index, item)

        if selected_step_key is not None:
            for row in range(self._step_table.rowCount()):
                item = self._step_table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == selected_step_key:
                    self._step_table.selectRow(row)
                    break
        elif self._step_table.rowCount() > 0:
            self._step_table.selectRow(0)

    def _selected_step_key(self) -> str | None:
        selected_items = self._step_table.selectedItems()
        if not selected_items:
            return None
        return str(selected_items[0].data(Qt.UserRole))

    def _load_selected_step_details(self) -> None:
        snapshot = self._current_snapshot
        if snapshot is None:
            return
        step_key = self._selected_step_key()
        if step_key is None:
            self._task_details_label.setText(self.tr("Select a plan step to inspect task details."))
            self._task_log_view.clear()
            return

        selected_snapshot = next((step for step in snapshot.step_snapshots if step.step_key == step_key), None)
        if selected_snapshot is None:
            return

        task_id = selected_snapshot.evaluate_task_id or selected_snapshot.root_task_id
        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError:
            self._task_details_label.setText(
                self.tr("Task details are temporarily unavailable for the selected step.")
            )
            self._task_log_view.clear()
            return
        lines = [
            self.tr("Task: {task_id}").format(task_id=details.task.id),
            self.tr("Model: {model_key}").format(model_key=selected_snapshot.model_key),
            self.tr("Status: {status}").format(status=self._translate_step_status(selected_snapshot.status)),
        ]
        if details.task.result_payload:
            lines.append(self.tr("Result: {summary}").format(summary=self._summarize_result(details.task.result_payload)))
        if selected_snapshot.failure_summary:
            lines.append(self.tr("Failure: {summary}").format(summary=selected_snapshot.failure_summary))
        self._task_details_label.setText("\n".join(lines))
        self._task_log_view.set_logs(details.logs)

    def _translate_task_status(self, status: Any) -> str:
        labels = {
            "pending": self.tr("Pending"),
            "running": self.tr("Running"),
            "succeeded": self.tr("Succeeded"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
        }
        key = getattr(status, "value", status)
        return labels.get(key, str(key))

    def _translate_step_status(self, status: ScenarioTrainingStepStatus) -> str:
        labels = {
            ScenarioTrainingStepStatus.RUNNING: self.tr("Running"),
            ScenarioTrainingStepStatus.SUCCEEDED: self.tr("Succeeded"),
            ScenarioTrainingStepStatus.FAILED: self.tr("Failed"),
        }
        return labels[status]

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

    def _continue_to_prediction(self) -> None:
        if self._current_snapshot is None or not self._current_snapshot.can_proceed_to_inference:
            return
        self.continue_to_prediction_requested.emit(self._preparation_result)
        self.close()
