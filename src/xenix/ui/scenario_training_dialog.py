from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.ml.contracts import MetricDirection
from ..services.ml.evaluation import get_default_policy
from ..services.ml.registry import get_model_catalog_entry
from ..services.ml_service import MLService
from ..services.scenario_template_service import (
    ScenarioTemplate,
    ScenarioTrainingOperation,
    ScenarioTrainingPlanStep,
)
from ..services.scenario_workflow_service import (
    ScenarioTrainingRun,
    ScenarioTrainingRunSnapshot,
    ScenarioTrainingStepSnapshot,
    ScenarioTrainingStepStatus,
    ScenarioWorkflowService,
    ScenarioWorkItemPreparationResult,
    StartScenarioTrainingRunInput,
)
from ..services.storage.models import MLTaskArtifactKind, MLTaskType
from ..services.trained_model_metadata import parse_trained_model_metadata
from .scenario_template_text import localized_template_display_name
from .widgets.task_log_view import TaskLogView


class _ScenarioTrainingResultCard(QWidget):
    clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step_key: str | None = None
        self._frame = QFrame(self)
        self._title_label = QLabel()
        self._status_label = QLabel()
        self._rank_label = QLabel()
        self._mode_label = QLabel()
        self._metrics_label = QLabel()
        self._params_label = QLabel()
        self._save_state_label = QLabel()
        self._hint_label = QLabel()

        self._build_ui()

    def set_snapshot(
        self,
        snapshot: ScenarioTrainingStepSnapshot,
        *,
        is_selected: bool,
        is_best_model: bool,
        metrics_text: str,
        params_text: str,
        save_state_text: str,
        hint_text: str,
        mode_text: str,
        rank_text: str,
        status_text: str,
    ) -> None:
        self._step_key = snapshot.step_key
        title = snapshot.model_display_name
        if is_best_model:
            title = self.tr("{model_name} · Best Model").format(model_name=title)
        self._title_label.setText(title)
        self._status_label.setText(status_text)
        self._rank_label.setText(rank_text)
        self._rank_label.setVisible(bool(rank_text))
        self._mode_label.setText(mode_text)
        self._metrics_label.setText(metrics_text)
        self._params_label.setText(params_text)
        self._save_state_label.setText(save_state_text)
        self._hint_label.setText(hint_text)
        self._refresh_style(snapshot.status, is_selected, is_best_model)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self._step_key is not None:
            self.clicked.emit(self._step_key)
        super().mousePressEvent(event)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.setCursor(Qt.PointingHandCursor)
        self._frame.setObjectName("resultCardFrame")
        self._frame.setFrameShape(QFrame.StyledPanel)
        self._frame.setCursor(Qt.PointingHandCursor)
        self._title_label.setObjectName("resultCardTitle")
        self._status_label.setObjectName("resultCardStatus")
        self._rank_label.setObjectName("resultCardRank")
        self._mode_label.setObjectName("resultCardMode")
        self._metrics_label.setObjectName("resultCardMetrics")
        self._params_label.setObjectName("resultCardParams")
        self._save_state_label.setObjectName("resultCardSaveState")
        self._hint_label.setObjectName("resultCardHint")

        card_layout = QVBoxLayout(self._frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)

        self._metrics_label.setWordWrap(True)
        self._params_label.setWordWrap(True)
        self._save_state_label.setWordWrap(True)
        self._hint_label.setWordWrap(True)
        self._rank_label.setWordWrap(True)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        header_layout.addWidget(self._title_label, 1)
        header_layout.addWidget(self._status_label, 0)

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self._rank_label)
        card_layout.addWidget(self._mode_label)
        card_layout.addWidget(self._metrics_label)
        card_layout.addWidget(self._params_label)
        card_layout.addWidget(self._save_state_label)
        card_layout.addWidget(self._hint_label)
        root_layout.addWidget(self._frame)

    def _refresh_style(
        self,
        status: ScenarioTrainingStepStatus,
        is_selected: bool,
        is_best_model: bool,
    ) -> None:
        status_palette = {
            ScenarioTrainingStepStatus.RUNNING: ("#9a6700", "#fff7e6", "#f4c86a"),
            ScenarioTrainingStepStatus.SUCCEEDED: ("#17643a", "#ecfdf3", "#8fd3a8"),
            ScenarioTrainingStepStatus.FAILED: ("#b42318", "#fef3f2", "#f3a7a0"),
        }
        status_color, status_background, status_border = status_palette[status]
        border_color = "#7aa2f7" if is_selected else "#d0d5dd"
        background = "#f5f8ff" if is_selected else "#ffffff"
        title_color = "#17643a" if is_best_model else "#101828"
        save_state_color = "#17643a" if is_best_model else "#344054"
        self._frame.setStyleSheet(
            f"""
            QFrame#resultCardFrame {{
                background-color: {background};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#resultCardTitle {{
                color: {title_color};
                font-size: 16px;
                font-weight: 600;
            }}
            QLabel#resultCardStatus {{
                color: {status_color};
                background-color: {status_background};
                border: 1px solid {status_border};
                border-radius: 10px;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 8px;
            }}
            QLabel#resultCardMode {{
                color: #475467;
                font-size: 12px;
                font-weight: 500;
            }}
            QLabel#resultCardRank {{
                color: #17643a;
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#resultCardMetrics {{
                color: #101828;
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#resultCardParams {{
                color: #344054;
                font-size: 12px;
            }}
            QLabel#resultCardSaveState {{
                color: {save_state_color};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#resultCardHint {{
                color: #667085;
                font-size: 12px;
            }}
            """
        )


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

        self._selected_step_key: str | None = None
        self._result_cards: dict[str, _ScenarioTrainingResultCard] = {}
        self._results_scroll_area = QScrollArea()
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._task_details_label = QLabel()
        self._task_details_label.setWordWrap(True)
        self._output_file_path: str | None = None
        self._output_file_label = QLabel()
        self._output_file_label.setWordWrap(True)
        self._open_output_button = QPushButton()
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
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(12)
        self._results_scroll_area.setWidgetResizable(True)
        self._results_scroll_area.setFrameShape(QScrollArea.NoFrame)
        self._results_scroll_area.setWidget(self._results_container)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self._run_again_button)
        actions.addWidget(self._continue_button)
        actions.addStretch(1)

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
        layout.addWidget(self._results_scroll_area)
        return self._step_group

    def _build_detail_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        detail_layout = QVBoxLayout(self._detail_group)
        detail_layout.addWidget(self._task_details_label)
        detail_layout.addWidget(self._output_file_label)
        detail_layout.addWidget(self._open_output_button)
        detail_layout.addWidget(self._task_log_view, 1)
        layout.addWidget(self._detail_group, 1)
        return widget

    def _wire_events(self) -> None:
        self._run_again_button.clicked.connect(self._start_training_run)
        self._continue_button.clicked.connect(self._continue_to_prediction)
        self._open_output_button.clicked.connect(self._open_selected_output_file)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Training Dashboard"))
        self._title_label.setText(localized_template_display_name(self._template))
        if self._continues_to_prediction():
            self._summary_label.setText(
                self.tr("The selected model plan is running in the background. Review the result and continue when a best model is ready.")
            )
        elif self._is_key_driver_template():
            self._summary_label.setText(
                self.tr("The selected key-driver analysis plan is running in the background. Review the saved driver outputs when each result is ready.")
            )
        elif self._is_anomaly_template():
            self._summary_label.setText(
                self.tr("The selected anomaly detection plan is running in the background. Review the saved anomaly score outputs when each result is ready.")
            )
        else:
            self._summary_label.setText(
                self.tr("The selected clustering plan is running in the background. Review the saved clustering outputs when each result is ready.")
        )
        self._run_again_button.setText(self.tr("Run Selected Plan Again"))
        if self._continues_to_prediction():
            self._continue_button.setText(self.tr("Continue to Prediction"))
        else:
            self._continue_button.setText(self.tr("Close Results"))
        self._step_group.setTitle(self.tr("Model Results"))
        self._detail_group.setTitle(self.tr("Advanced Task Details"))
        self._open_output_button.setText(self.tr("Open Output CSV"))
        self._continue_button.setVisible(True)
        if self._current_snapshot is None:
            self._status_summary_label.setText(self.tr("Preparing the training plan..."))
            self._best_model_label.setText(self._build_empty_best_model_text())
            self._task_details_label.setText(self.tr("Select a model result card to inspect task details."))
            self._clear_output_file_action()

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
        self._refresh_result_cards(self._current_snapshot)
        if self._continues_to_prediction():
            self._continue_button.setEnabled(self._current_snapshot.can_proceed_to_inference)
        else:
            self._continue_button.setEnabled(self._current_snapshot.is_terminal)
        if self._current_snapshot.is_terminal:
            self._timer.stop()

    def _refresh_summary(self, snapshot: ScenarioTrainingRunSnapshot) -> None:
        succeeded_count = sum(1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED)
        failed_count = sum(1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.FAILED)
        if self._continues_to_prediction() and snapshot.can_proceed_to_inference:
            self._status_summary_label.setText(
                self.tr("Training finished. {succeeded_count} model result(s) succeeded and the best model is ready.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        elif failed_count > 0 and snapshot.is_terminal:
            self._status_summary_label.setText(
                self.tr(
                    "Training finished with partial failure. {succeeded_count} model result(s) succeeded and {failed_count} model result(s) failed."
                ).format(
                    succeeded_count=str(succeeded_count),
                    failed_count=str(failed_count),
                )
            )
        elif self._template.supervised_required and not self._continues_to_prediction() and snapshot.is_terminal:
            self._status_summary_label.setText(
                self.tr("Analysis finished. {succeeded_count} model result(s) are ready for review.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        elif self._is_anomaly_template() and snapshot.is_terminal:
            self._status_summary_label.setText(
                self.tr("Anomaly detection finished. {succeeded_count} model result(s) are ready for review.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        elif not self._template.supervised_required and snapshot.is_terminal:
            self._status_summary_label.setText(
                self.tr("Clustering finished. {succeeded_count} model result(s) are ready for review.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        else:
            self._status_summary_label.setText(
                self.tr("Training is running. {succeeded_count} model result(s) completed so far.").format(
                    succeeded_count=str(succeeded_count)
                )
            )
        self._best_model_label.setText(self._build_best_model_text(snapshot))

    def _build_best_model_text(self, snapshot: ScenarioTrainingRunSnapshot) -> str:
        if self._is_key_driver_template():
            succeeded_models = sum(
                1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED
            )
            if succeeded_models == 0:
                return self.tr("Key driver outputs: waiting for successful model results.")
            return self.tr("Key driver outputs: {count} saved report(s) are ready.").format(
                count=str(succeeded_models)
            )
        if self._is_anomaly_template():
            succeeded_models = sum(
                1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED
            )
            if succeeded_models == 0:
                return self.tr("Anomaly outputs: waiting for successful model results.")
            return self.tr("Anomaly outputs: {count} saved score file(s) are ready.").format(
                count=str(succeeded_models)
            )
        if not self._template.supervised_required:
            succeeded_models = sum(
                1 for step in snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED
            )
            if succeeded_models == 0:
                return self.tr("Clustering outputs: waiting for successful model results.")
            return self.tr("Clustering outputs: {count} saved model result(s) are ready.").format(
                count=str(succeeded_models)
            )
        if snapshot.best_trained_model_id is None:
            return self.tr("Best model: waiting for evaluation.")

        trained_models = self._ml_service.list_trained_models(snapshot.work_item_id)
        best_model_display_name = str(snapshot.best_trained_model_id)
        for model in trained_models:
            if model.id == snapshot.best_trained_model_id:
                metadata = parse_trained_model_metadata(model.metadata_payload)
                if metadata is not None and metadata.saved_name:
                    best_model_display_name = metadata.saved_name
                    break
                best_model_display_name = self._model_display_name(model.model_key)
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
                    model_key=best_model_display_name,
                    metric_name=metric_name,
                    metric_value=str(metric_value),
                )
        return self.tr("Best model: {model_key}").format(model_key=best_model_display_name)

    def _refresh_result_cards(self, snapshot: ScenarioTrainingRunSnapshot) -> None:
        valid_step_keys = {step.step_key for step in snapshot.step_snapshots}
        for step_key in list(self._result_cards):
            if step_key in valid_step_keys:
                continue
            card = self._result_cards.pop(step_key)
            self._results_layout.removeWidget(card)
            card.deleteLater()

        ordered_steps = self._ordered_step_snapshots(snapshot)
        rank_by_step_key = self._rank_by_step_key(ordered_steps)
        for index, step in enumerate(ordered_steps):
            card = self._result_cards.get(step.step_key)
            if card is None:
                card = _ScenarioTrainingResultCard(self._results_container)
                card.clicked.connect(self._select_step_key)
                self._result_cards[step.step_key] = card
            self._results_layout.insertWidget(index, card)
            is_best_model = step.trained_model_id is not None and step.trained_model_id == snapshot.best_trained_model_id
            card.set_snapshot(
                step,
                is_selected=self._selected_step_key == step.step_key,
                is_best_model=is_best_model,
                metrics_text=self._build_metrics_text(step),
                params_text=self._build_params_text(step),
                save_state_text=self._build_save_state_text(step, is_best_model=is_best_model),
                hint_text=self._build_hint_text(step, is_best_model=is_best_model),
                mode_text=self._build_mode_text(step),
                rank_text=self._build_rank_text(step, rank_by_step_key),
                status_text=self._translate_step_status(step.status),
            )

        if ordered_steps and self._selected_step_key not in valid_step_keys:
            self._selected_step_key = ordered_steps[0].step_key
            self._load_selected_step_details()
            self._refresh_result_cards(snapshot)
            return
        if not ordered_steps:
            self._selected_step_key = None
            self._task_details_label.setText(self.tr("Select a model result card to inspect task details."))
            self._clear_output_file_action()
            self._task_log_view.clear()
            return
        if self._selected_step_key is None:
            self._selected_step_key = ordered_steps[0].step_key
            self._load_selected_step_details()
            self._refresh_result_cards(snapshot)
            return
        self._load_selected_step_details()

    def _ordered_step_snapshots(self, snapshot: ScenarioTrainingRunSnapshot) -> list[ScenarioTrainingStepSnapshot]:
        steps = list(snapshot.step_snapshots)
        if not self._template.supervised_required:
            return steps
        if not any(step.primary_metric_value is not None for step in steps):
            return steps
        try:
            problem_kind = get_model_catalog_entry(steps[0].model_key).problem_kind
            direction = get_default_policy(problem_kind).primary_metric_direction
        except Exception:
            direction = MetricDirection.MAX

        def sort_key(step: ScenarioTrainingStepSnapshot) -> tuple[int, float, str]:
            if step.status is ScenarioTrainingStepStatus.SUCCEEDED and step.primary_metric_value is not None:
                status_order = 0
            elif step.status is ScenarioTrainingStepStatus.SUCCEEDED:
                status_order = 1
            elif step.status is ScenarioTrainingStepStatus.RUNNING:
                status_order = 2
            else:
                status_order = 3
            metric_value = step.primary_metric_value
            if metric_value is None:
                normalized_metric = 0.0
            elif direction is MetricDirection.MAX:
                normalized_metric = -metric_value
            else:
                normalized_metric = metric_value
            return status_order, normalized_metric, step.model_display_name

        return sorted(steps, key=sort_key)

    def _rank_by_step_key(self, steps: list[ScenarioTrainingStepSnapshot]) -> dict[str, int]:
        if not self._template.supervised_required:
            return {}
        ranked_steps = [
            step
            for step in steps
            if step.status is ScenarioTrainingStepStatus.SUCCEEDED and step.primary_metric_value is not None
        ]
        return {step.step_key: index + 1 for index, step in enumerate(ranked_steps)}

    def _build_rank_text(
        self,
        step: ScenarioTrainingStepSnapshot,
        rank_by_step_key: dict[str, int],
    ) -> str:
        rank = rank_by_step_key.get(step.step_key)
        if rank is None:
            return ""
        metric_name = step.primary_metric_name or self.tr("primary metric")
        return self.tr("Rank #{rank} by {metric_name}").format(
            rank=str(rank),
            metric_name=metric_name,
        )

    def _select_step_key(self, step_key: str) -> None:
        self._selected_step_key = step_key
        self._load_selected_step_details()
        if self._current_snapshot is not None:
            self._refresh_result_cards(self._current_snapshot)

    def _load_selected_step_details(self) -> None:
        snapshot = self._current_snapshot
        if snapshot is None:
            return
        step_key = self._selected_step_key
        if step_key is None:
            self._task_details_label.setText(self.tr("Select a model result card to inspect task details."))
            self._clear_output_file_action()
            self._task_log_view.clear()
            return

        selected_snapshot = next((step for step in snapshot.step_snapshots if step.step_key == step_key), None)
        if selected_snapshot is None:
            self._clear_output_file_action()
            return

        task_id = selected_snapshot.evaluate_task_id or selected_snapshot.root_task_id
        try:
            details = self._ml_service.get_task_details(task_id)
        except XenixError:
            self._task_details_label.setText(
                self.tr("Task details are temporarily unavailable for the selected model result.")
            )
            self._clear_output_file_action()
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
        output_file_path = self._find_openable_output_file(details.artifacts)
        if output_file_path is None and selected_snapshot.evaluate_task_id is not None:
            try:
                root_details = self._ml_service.get_task_details(selected_snapshot.root_task_id)
                output_file_path = self._find_openable_output_file(root_details.artifacts)
            except XenixError:
                output_file_path = None
        self._set_output_file_action(output_file_path)
        self._task_log_view.set_logs(details.logs)

    def _build_mode_text(self, step: ScenarioTrainingStepSnapshot) -> str:
        if step.operation is ScenarioTrainingOperation.FIT:
            return self.tr("Mode: Fit training")
        candidate_suffix = ""
        if step.candidate_count is not None:
            candidate_suffix = self.tr(" · {count} candidates").format(count=str(step.candidate_count))
        return self.tr("Mode: Hyperparameter tuning{candidate_suffix}").format(candidate_suffix=candidate_suffix)

    def _build_metrics_text(self, step: ScenarioTrainingStepSnapshot) -> str:
        if (
            self._template.supervised_required
            and not self._continues_to_prediction()
            and step.result_summary.get("key_driver_report") is True
        ):
            top_driver_text = self._format_top_key_drivers(step.result_summary)
            if top_driver_text:
                return self.tr("Top drivers: {drivers}").format(drivers=top_driver_text)
        if self._is_anomaly_template() and step.result_summary:
            anomaly_count = step.result_summary.get("anomaly_count")
            row_count = step.result_summary.get("row_count")
            anomaly_rate = step.result_summary.get("anomaly_rate")
            parts: list[str] = []
            if isinstance(anomaly_count, int):
                parts.append(self.tr("Anomalies {value}").format(value=str(anomaly_count)))
            if isinstance(row_count, int):
                parts.append(self.tr("Rows {value}").format(value=str(row_count)))
            if isinstance(anomaly_rate, (int, float)):
                parts.append(self.tr("Rate {value}").format(value=f"{float(anomaly_rate):.2%}"))
            if parts:
                return " · ".join(parts)
        if step.result_summary:
            cluster_count = step.result_summary.get("cluster_count")
            noise_count = step.result_summary.get("noise_count")
            row_count = step.result_summary.get("row_count")
            parts: list[str] = []
            if isinstance(cluster_count, int):
                parts.append(self.tr("Clusters {value}").format(value=str(cluster_count)))
            if isinstance(noise_count, int):
                parts.append(self.tr("Noise {value}").format(value=str(noise_count)))
            if isinstance(row_count, int):
                parts.append(self.tr("Rows {value}").format(value=str(row_count)))
            if parts:
                return " · ".join(parts)
        if not step.evaluation_metrics:
            if step.status is ScenarioTrainingStepStatus.FAILED:
                return self.tr("Metrics: evaluation did not complete.")
            if step.evaluate_status is not None:
                return self.tr("Metrics: evaluation is in progress.")
            return self.tr("Metrics: waiting for evaluation.")

        metrics = step.evaluation_metrics
        if "r2" in metrics:
            mse_value = metrics.get("mse")
            if mse_value is None and "rmse" in metrics:
                mse_value = metrics["rmse"] ** 2
            metric_parts = [self.tr("R² {value}").format(value=self._format_metric_value(metrics["r2"]))]
            if mse_value is not None:
                metric_parts.append(self.tr("MSE {value}").format(value=self._format_metric_value(mse_value)))
            if "mae" in metrics:
                metric_parts.append(self.tr("MAE {value}").format(value=self._format_metric_value(metrics["mae"])))
            return " · ".join(metric_parts)

        metric_parts: list[str] = []
        for metric_name in ("f1_weighted", "accuracy", "precision_weighted", "recall_weighted"):
            if metric_name not in metrics:
                continue
            metric_parts.append(
                self.tr("{label} {value}").format(
                    label=self._translate_metric_name(metric_name),
                    value=self._format_metric_value(metrics[metric_name]),
                )
            )
        return " · ".join(metric_parts) if metric_parts else self.tr("Metrics: available in task details.")

    def _build_params_text(self, step: ScenarioTrainingStepSnapshot) -> str:
        if step.best_params:
            return self.tr("Best params: {params}").format(params=self._format_mapping(step.best_params))
        if step.training_params:
            return self.tr("Parameters: {params}").format(params=self._format_mapping(step.training_params))
        return self.tr("Parameters: default model configuration")

    def _build_save_state_text(self, step: ScenarioTrainingStepSnapshot, *, is_best_model: bool) -> str:
        if step.trained_model_id is None:
            return self.tr("Save state: waiting for persisted model")
        metadata = self._trained_model_metadata(step.trained_model_id)
        if metadata is not None and metadata.artifact_file_name:
            if is_best_model:
                return self.tr("Save state: saved automatically as {file_name} and leading this run").format(
                    file_name=metadata.artifact_file_name
                )
            return self.tr("Save state: saved automatically as {file_name}").format(
                file_name=metadata.artifact_file_name
            )
        if is_best_model:
            return self.tr("Save state: saved automatically and leading this run")
        return self.tr("Save state: saved automatically")

    def _build_hint_text(self, step: ScenarioTrainingStepSnapshot, *, is_best_model: bool) -> str:
        has_key_driver_report = step.result_summary.get("key_driver_report") is True
        has_anomaly_output = self._is_anomaly_template() and bool(step.result_summary)
        if step.status is ScenarioTrainingStepStatus.RUNNING:
            if has_key_driver_report:
                return self.tr("Hint: the key-driver report is ready; evaluation is still running.")
            if has_anomaly_output:
                return self.tr("Hint: anomaly score output is being finalized in the background.")
            if step.result_summary:
                return self.tr("Hint: clustering output is being finalized in the background.")
            if not self._template.supervised_required:
                if self._is_anomaly_template():
                    return self.tr("Hint: anomaly detection is progressing in the background.")
                return self.tr("Hint: clustering is progressing in the background.")
            return self.tr("Hint: training and evaluation are progressing in the background.")
        if step.status is ScenarioTrainingStepStatus.FAILED:
            return self.tr("Hint: open the advanced task details to inspect the failure summary and logs.")
        if has_key_driver_report:
            return self.tr("Hint: open the output CSV to review ranked business drivers.")
        if has_anomaly_output:
            return self.tr("Hint: open the output CSV to review ranked anomaly scores.")
        if step.result_summary:
            return self.tr("Hint: review the saved clustering output file from the task artifacts or advanced details.")
        if is_best_model:
            return self.tr("Hint: this model currently gives the strongest result for the prepared dataset.")
        return self.tr("Hint: this saved model remains available for comparison and later reuse.")

    def _format_top_key_drivers(self, result_summary: dict[str, Any]) -> str:
        top_drivers = result_summary.get("top_key_drivers")
        if not isinstance(top_drivers, list):
            return ""
        names: list[str] = []
        for item in top_drivers[:3]:
            if not isinstance(item, dict):
                continue
            feature = item.get("feature")
            if isinstance(feature, str) and feature:
                names.append(feature)
        return ", ".join(names)

    def _format_mapping(self, payload: dict[str, Any]) -> str:
        if not payload:
            return self.tr("(empty)")
        segments: list[str] = []
        for index, (key, value) in enumerate(payload.items()):
            if index >= 3:
                segments.append("...")
                break
            segments.append(f"{key}={value}")
        return ", ".join(segments)

    def _format_metric_value(self, value: float) -> str:
        return f"{value:.4f}"

    def _translate_metric_name(self, metric_name: str) -> str:
        labels = {
            "f1_weighted": self.tr("F1"),
            "accuracy": self.tr("Accuracy"),
            "precision_weighted": self.tr("Precision"),
            "recall_weighted": self.tr("Recall"),
        }
        return labels.get(metric_name, metric_name)

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
        if isinstance(result_payload.get("result_summary"), dict):
            summary = result_payload["result_summary"]
            if summary.get("key_driver_report") is True:
                drivers = self._format_top_key_drivers(summary)
                if drivers:
                    return self.tr("top drivers={drivers}").format(drivers=drivers)
                return self.tr("key driver report ready")
            if "anomaly_count" in summary:
                anomaly_count = summary.get("anomaly_count")
                anomaly_rate = summary.get("anomaly_rate")
                return self.tr("anomalies={anomaly_count}, rate={anomaly_rate}").format(
                    anomaly_count=str(anomaly_count if anomaly_count is not None else ""),
                    anomaly_rate=f"{float(anomaly_rate):.2%}" if isinstance(anomaly_rate, (int, float)) else "",
                )
            cluster_count = summary.get("cluster_count")
            noise_count = summary.get("noise_count")
            return self.tr("clusters={cluster_count}, noise={noise_count}").format(
                cluster_count=str(cluster_count if cluster_count is not None else ""),
                noise_count=str(noise_count if noise_count is not None else ""),
            )
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
        if self._current_snapshot is None:
            return
        if not self._continues_to_prediction():
            if self._current_snapshot.is_terminal:
                self.close()
            return
        if not self._current_snapshot.can_proceed_to_inference:
            return
        self.continue_to_prediction_requested.emit(self._preparation_result)
        self.close()

    def _build_empty_best_model_text(self) -> str:
        if self._continues_to_prediction():
            return self.tr("Best model: waiting for evaluation.")
        if self._is_key_driver_template():
            return self.tr("Key driver outputs: waiting for successful model results.")
        if self._is_anomaly_template():
            return self.tr("Anomaly outputs: waiting for successful model results.")
        return self.tr("Clustering outputs: waiting for successful model results.")

    def _find_openable_output_file(self, artifacts: list[Any]) -> str | None:
        for artifact in artifacts:
            artifact_kind = getattr(artifact, "artifact_kind", None)
            is_export = artifact_kind in {MLTaskArtifactKind.EXPORT_FILE, MLTaskArtifactKind.EXPORT_FILE.value}
            if not is_export or not getattr(artifact, "ready_to_open", False):
                continue
            absolute_path = getattr(artifact, "absolute_path", None)
            if isinstance(absolute_path, str) and absolute_path:
                return absolute_path
        return None

    def _set_output_file_action(self, output_file_path: str | None) -> None:
        self._output_file_path = output_file_path
        if output_file_path is None:
            self._clear_output_file_action()
            return
        output_path = Path(output_file_path)
        self._output_file_label.setText(
            self.tr("Output file: {file_name}").format(file_name=output_path.name)
        )
        self._output_file_label.setToolTip(str(output_path))
        self._output_file_label.show()
        self._open_output_button.setToolTip(str(output_path))
        self._open_output_button.setEnabled(True)
        self._open_output_button.show()

    def _clear_output_file_action(self) -> None:
        self._output_file_path = None
        self._output_file_label.clear()
        self._output_file_label.setToolTip("")
        self._output_file_label.hide()
        self._open_output_button.setToolTip("")
        self._open_output_button.setEnabled(False)
        self._open_output_button.hide()

    def _open_selected_output_file(self) -> None:
        if self._output_file_path is None:
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_file_path))
        if not opened:
            QMessageBox.warning(
                self,
                self.tr("Open Output Failed"),
                self.tr("The output file could not be opened."),
            )

    def _trained_model_metadata(self, trained_model_id: str) -> Any:
        if self._current_snapshot is None:
            return None
        for model in self._ml_service.list_trained_models(self._current_snapshot.work_item_id):
            if model.id != trained_model_id:
                continue
            return parse_trained_model_metadata(model.metadata_payload)
        return None

    def _model_display_name(self, model_key: str) -> str:
        try:
            return self._ml_service.get_model(model_key).display_name
        except Exception:
            return model_key

    def _continues_to_prediction(self) -> bool:
        return self._template.supervised_required and self._template.continues_to_prediction

    def _is_key_driver_template(self) -> bool:
        return self._template.key == "key_driver_analysis.v1"

    def _is_anomaly_template(self) -> bool:
        return self._template.key == "anomaly_detection.v1"
