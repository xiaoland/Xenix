from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..datetime_utils import format_datetime_for_display
from ..services.scenario_model_source_service import (
    CompatibleTrainedModelOption,
    ListCompatibleTrainedModelsInput,
    ScenarioModelSourceService,
)
from ..services.scenario_template_service import ScenarioTemplate
from ..services.scenario_workflow_service import ScenarioWorkItemPreparationResult
from .native_widgets import emphasize_label
from .scenario_template_text import localized_template_display_name


class ScenarioModelSourceKind(StrEnum):
    TRAIN_NEW = "train_new"
    TRAINED_MODEL = "trained_model"


class ScenarioModelSourceDialog(QDialog):
    def __init__(
        self,
        template: ScenarioTemplate,
        preparation_result: ScenarioWorkItemPreparationResult,
        model_source_service: ScenarioModelSourceService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._preparation_result = preparation_result
        self._model_source_service = model_source_service
        self._selected_source_kind: ScenarioModelSourceKind | None = None
        self._compatible_models = self._model_source_service.list_compatible_trained_models(
            ListCompatibleTrainedModelsInput(
                template_key=self._template.key,
                feature_columns=self._preparation_result.feature_columns,
                target_columns=self._preparation_result.target_columns,
            )
        )

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._selection_label = QLabel()
        self._train_title_label = QLabel()
        self._train_description_label = QLabel()
        self._train_new_button = QPushButton()
        self._trained_title_label = QLabel()
        self._trained_description_label = QLabel()
        self._compatible_count_label = QLabel()
        self._model_list = QListWidget()
        self._selected_model_label = QLabel()
        self._selected_model_detail_label = QLabel()
        self._use_trained_button = QPushButton()
        self._close_button = QPushButton()

        self.resize(840, 620)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        self._refresh_model_selection_state()

    def selected_source_kind(self) -> ScenarioModelSourceKind | None:
        return self._selected_source_kind

    def compatible_models(self) -> list[CompatibleTrainedModelOption]:
        return list(self._compatible_models)

    def selected_trained_model(self) -> CompatibleTrainedModelOption | None:
        current_item = self._model_list.currentItem()
        if current_item is None:
            return None
        option_index = current_item.data(Qt.UserRole)
        if not isinstance(option_index, int):
            return None
        if option_index < 0 or option_index >= len(self._compatible_models):
            return None
        return self._compatible_models[option_index]

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        emphasize_label(self._title_label, point_delta=2)
        self._summary_label.setWordWrap(True)
        self._selection_label.setWordWrap(True)
        emphasize_label(self._train_title_label)
        self._train_description_label.setWordWrap(True)
        emphasize_label(self._trained_title_label)
        self._trained_description_label.setWordWrap(True)
        self._compatible_count_label.setWordWrap(True)
        self._selected_model_label.setWordWrap(True)
        self._selected_model_detail_label.setWordWrap(True)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        actions_layout.addWidget(self._train_new_button, 0)
        actions_layout.addWidget(self._use_trained_button, 0)
        actions_layout.addStretch(1)

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._close_button, 0)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._selection_label)
        layout.addWidget(self._train_title_label)
        layout.addWidget(self._train_description_label)
        layout.addWidget(self._trained_title_label)
        layout.addWidget(self._trained_description_label)
        layout.addWidget(self._compatible_count_label)
        layout.addWidget(self._model_list, 1)
        layout.addWidget(self._selected_model_label)
        layout.addWidget(self._selected_model_detail_label)
        layout.addLayout(actions_layout)
        layout.addLayout(footer_layout)

    def _wire_events(self) -> None:
        self._train_new_button.clicked.connect(self._choose_training_branch)
        self._use_trained_button.clicked.connect(self._choose_trained_model_branch)
        self._close_button.clicked.connect(self.reject)
        self._model_list.itemSelectionChanged.connect(self._refresh_model_selection_state)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Choose Model Source"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr("The dataset is ready. Choose whether to train a new model set or continue from a compatible trained model.")
        )
        self._selection_label.setText(
            self.tr("Input columns: {features}\nPrediction target: {targets}").format(
                features=", ".join(self._preparation_result.feature_columns),
                targets=", ".join(self._preparation_result.target_columns),
            )
        )
        self._train_title_label.setText(self.tr("Choose Models and Train"))
        self._train_description_label.setText(
            self.tr("Continue to model selection and training with the prepared dataset.")
        )
        self._trained_title_label.setText(self.tr("Choose Trained Model"))
        self._trained_description_label.setText(
            self.tr("Compatible trained models with the same scenario and column selection appear below.")
        )
        if self._compatible_models:
            self._compatible_count_label.setText(
                self.tr("{count} compatible trained models found.").format(
                    count=len(self._compatible_models)
                )
            )
        else:
            self._compatible_count_label.setText(
                self.tr("No compatible trained models are available yet for the current selection.")
            )
        self._train_new_button.setText(self.tr("Continue to Training"))
        self._use_trained_button.setText(self.tr("Continue with Trained Model"))
        self._close_button.setText(self.tr("Close"))
        self._reload_model_items()
        self._refresh_model_selection_state()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _reload_model_items(self) -> None:
        selected_model_id = None
        selected_option = self.selected_trained_model()
        if selected_option is not None:
            selected_model_id = selected_option.trained_model_id

        self._model_list.clear()
        for index, option in enumerate(self._compatible_models):
            suffix = self.tr(" [Best]") if option.is_best_for_work_item else ""
            metric_text = self._format_metric_summary(option)
            item = QListWidgetItem(
                self.tr("{model_name} | {work_item_name} | {created_at}{suffix}{metric_text}").format(
                    model_name=option.saved_name or option.model_display_name,
                    work_item_name=option.work_item_name,
                    created_at=self._format_created_at(option),
                    suffix=suffix,
                    metric_text=f" | {metric_text}" if metric_text else "",
                )
            )
            item.setData(Qt.UserRole, index)
            self._model_list.addItem(item)
            if selected_model_id is not None and option.trained_model_id == selected_model_id:
                self._model_list.setCurrentItem(item)

    def _refresh_model_selection_state(self) -> None:
        option = self.selected_trained_model()
        self._use_trained_button.setEnabled(option is not None)
        if option is None:
            if self._compatible_models:
                self._selected_model_label.setText(
                    self.tr("Select one compatible trained model to continue.")
                )
                self._selected_model_detail_label.setText(
                    self.tr("The selected model summary appears here, including saved name, source dataset, metrics, and sample preview.")
                )
            else:
                self._selected_model_label.setText(
                    self.tr("Training a new model set is available immediately.")
                )
                self._selected_model_detail_label.setText("")
            return

        self._selected_model_label.setText(
            self.tr("Selected model: {model_name}").format(
                model_name=option.saved_name or option.model_display_name
            )
        )
        self._selected_model_detail_label.setText(self._build_selected_model_detail_text(option))

    def _format_created_at(self, option: CompatibleTrainedModelOption) -> str:
        return format_datetime_for_display(option.created_at, format_string="%Y-%m-%d %H:%M")

    def _choose_training_branch(self) -> None:
        self._selected_source_kind = ScenarioModelSourceKind.TRAIN_NEW
        self.accept()

    def _choose_trained_model_branch(self) -> None:
        if self.selected_trained_model() is None:
            return
        self._selected_source_kind = ScenarioModelSourceKind.TRAINED_MODEL
        self.accept()

    def _build_selected_model_detail_text(self, option: CompatibleTrainedModelOption) -> str:
        lines = [
            self.tr("Model family: {model_name}").format(model_name=option.model_display_name),
            self.tr("Source work item: {work_item_name}").format(work_item_name=option.work_item_name),
            self.tr("Created at: {created_at}").format(created_at=self._format_created_at(option)),
        ]
        if option.source_dataset_name:
            dataset_text = option.source_dataset_name
            if option.source_dataset_file_name:
                dataset_text = self.tr("{dataset_name} ({file_name})").format(
                    dataset_name=option.source_dataset_name,
                    file_name=option.source_dataset_file_name,
                )
            lines.append(self.tr("Source dataset: {dataset_name}").format(dataset_name=dataset_text))
        lines.append(
            self.tr("Input columns: {features}\nPrediction target: {targets}").format(
                features=", ".join(option.feature_columns),
                targets=", ".join(option.target_columns),
            )
        )
        if option.dataset_row_count is not None and option.dataset_column_count is not None:
            lines.append(
                self.tr("Captured sample context: {row_count} rows, {column_count} columns.").format(
                    row_count=str(option.dataset_row_count),
                    column_count=str(option.dataset_column_count),
                )
            )
        if option.preview_columns and option.preview_rows:
            lines.append(
                self.tr("Preview columns: {columns}\nPreview first row: {first_row}").format(
                    columns=", ".join(option.preview_columns),
                    first_row=" | ".join(option.preview_rows[0]),
                )
            )
        metric_text = self._format_metric_summary(option)
        if metric_text:
            lines.append(self.tr("Evaluation: {metrics}").format(metrics=metric_text))
        if option.artifact_file_name:
            lines.append(
                self.tr("Saved file: {file_name}").format(file_name=option.artifact_file_name)
            )
        if option.save_note:
            lines.append(self.tr("Note: {note}").format(note=option.save_note))
        return "\n".join(lines)

    def _format_metric_summary(self, option: CompatibleTrainedModelOption) -> str:
        if option.evaluation_primary_metric_name and option.evaluation_primary_metric_value is not None:
            return (
                f"{option.evaluation_primary_metric_name}="
                f"{option.evaluation_primary_metric_value:.4f}"
            )
        if option.evaluation_metrics:
            first_metric_name = next(iter(option.evaluation_metrics))
            return f"{first_metric_name}={option.evaluation_metrics[first_metric_name]:.4f}"
        return ""
