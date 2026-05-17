from __future__ import annotations

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import XenixError
from ..services.ml.types import ModelCatalogEntry
from ..services.scenario_template_service import (
    ScenarioTemplate,
    ScenarioTrainingOperation,
    ScenarioTrainingPlanStep,
    build_scenario_training_step_key,
)
from ..services.scenario_training_preset_service import ScenarioTrainingPresetService
from ..services.scenario_workflow_service import ScenarioWorkItemPreparationResult
from .native_widgets import emphasize_label, mark_status_label
from .scenario_template_text import localized_template_display_name
from .widgets.json_schema_form import JsonSchemaFormWidget


class _ScenarioTrainingOptionCard(QFrame):
    selection_changed = Signal()

    def __init__(
        self,
        catalog_entry: ModelCatalogEntry,
        initial_step: ScenarioTrainingPlanStep | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog_entry = catalog_entry
        self._initial_step = initial_step
        self._step_keys_by_operation: dict[ScenarioTrainingOperation, str] = {}
        if initial_step is not None:
            self._step_keys_by_operation[initial_step.operation] = initial_step.step_key
        self._supported_operations = self._build_supported_operations()
        self._fit_values = dict(initial_step.params) if initial_step and initial_step.operation is ScenarioTrainingOperation.FIT else {}
        self._tuning_values = (
            {key: list(values) for key, values in initial_step.param_grid.items()}
            if initial_step and initial_step.operation is ScenarioTrainingOperation.HYPERPARAMETER_TUNING
            else {}
        )
        self._current_operation: ScenarioTrainingOperation | None = None

        self._selected_checkbox = QCheckBox()
        self._model_name_label = QLabel(self._catalog_entry.display_name)
        self._metadata_label = QLabel()
        self._guidance_label = QLabel()
        self._operation_label = QLabel()
        self._operation_selector = QComboBox()
        self._operation_summary_label = QLabel()
        self._config_form = JsonSchemaFormWidget()

        self._build_ui()
        self._wire_events()
        self._reload_operation_selector()

        initial_operation = self._resolve_initial_operation(initial_step)
        operation_index = self._operation_selector.findData(initial_operation)
        if operation_index >= 0:
            self._operation_selector.setCurrentIndex(operation_index)
        self._selected_checkbox.setChecked(initial_step is not None)
        self._sync_form_for_operation()
        self.retranslate_ui()

    def selected_step(self) -> ScenarioTrainingPlanStep | None:
        if not self._selected_checkbox.isChecked():
            return None

        self._store_current_values()
        operation = self.current_operation()
        step_key = self._step_keys_by_operation.get(
            operation,
            build_scenario_training_step_key(self._catalog_entry.model_key, operation),
        )
        if operation is ScenarioTrainingOperation.FIT:
            return ScenarioTrainingPlanStep(
                step_key=step_key,
                operation=operation,
                model_key=self._catalog_entry.model_key,
                params=dict(self._fit_values),
                param_grid={},
            )
        return ScenarioTrainingPlanStep(
            step_key=step_key,
            operation=operation,
            model_key=self._catalog_entry.model_key,
            params={},
            param_grid={key: list(values) for key, values in self._tuning_values.items()},
        )

    def retranslate_ui(self) -> None:
        self._selected_checkbox.setText(self.tr("Include this model"))
        self._metadata_label.setText(
            self.tr("{family} · {recommendation}").format(
                family=self._catalog_entry.family,
                recommendation=self._translate_recommendation_tier(self._catalog_entry.recommendation_tier),
            )
        )
        self._guidance_label.setText(
            self._catalog_entry.guidance or self.tr("General-purpose model for this scenario.")
        )
        self._operation_label.setText(self.tr("Training mode"))
        self._reload_operation_selector()
        self._refresh_operation_summary()
        self._config_form.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        emphasize_label(self._model_name_label)
        emphasize_label(self._metadata_label)
        self._metadata_label.setWordWrap(True)
        self._guidance_label.setWordWrap(True)
        self._operation_summary_label.setWordWrap(True)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        header_layout.addWidget(self._selected_checkbox)
        header_layout.addWidget(self._model_name_label)
        header_layout.addWidget(self._metadata_label)
        header_layout.addWidget(self._guidance_label)

        operation_row = QHBoxLayout()
        operation_row.setSpacing(10)
        operation_row.addWidget(self._operation_label)
        operation_row.addWidget(self._operation_selector, 1)

        layout.addLayout(header_layout)
        layout.addLayout(operation_row)
        layout.addWidget(self._operation_summary_label)
        layout.addWidget(self._config_form)

    def _wire_events(self) -> None:
        self._selected_checkbox.toggled.connect(lambda _checked: self._refresh_enabled_state())
        self._selected_checkbox.toggled.connect(lambda _checked: self.selection_changed.emit())
        self._operation_selector.currentIndexChanged.connect(lambda _index: self._sync_form_for_operation())

    def _build_supported_operations(self) -> list[ScenarioTrainingOperation]:
        operations: list[ScenarioTrainingOperation] = []
        if self._catalog_entry.supports_fit:
            operations.append(ScenarioTrainingOperation.FIT)
        if self._catalog_entry.supports_hyperparameter_tuning and self._catalog_entry.param_grid_schema is not None:
            operations.append(ScenarioTrainingOperation.HYPERPARAMETER_TUNING)
        return operations

    def _resolve_initial_operation(self, initial_step: ScenarioTrainingPlanStep | None) -> ScenarioTrainingOperation:
        if initial_step is not None and initial_step.operation in self._supported_operations:
            return initial_step.operation
        return self._supported_operations[0]

    def _reload_operation_selector(self) -> None:
        current_operation = self.current_operation() if self._operation_selector.count() > 0 else None
        self._operation_selector.blockSignals(True)
        self._operation_selector.clear()
        for operation in self._supported_operations:
            self._operation_selector.addItem(self._translate_operation(operation), operation)
        if current_operation is not None:
            index = self._operation_selector.findData(current_operation)
            if index >= 0:
                self._operation_selector.setCurrentIndex(index)
        self._operation_selector.blockSignals(False)

    def current_operation(self) -> ScenarioTrainingOperation:
        operation = self._operation_selector.currentData()
        if isinstance(operation, ScenarioTrainingOperation):
            return operation
        if isinstance(operation, str):
            return ScenarioTrainingOperation(operation)
        return self._supported_operations[0]

    def _sync_form_for_operation(self) -> None:
        self._store_current_values()
        self._current_operation = self.current_operation()
        if self._current_operation is ScenarioTrainingOperation.FIT:
            self._config_form.set_schema(self._catalog_entry.param_schema, initial_values=self._fit_values)
        else:
            self._config_form.set_schema(self._catalog_entry.param_grid_schema or {}, initial_values=self._tuning_values)
        self._refresh_operation_summary()
        self._refresh_enabled_state()

    def _store_current_values(self) -> None:
        if self._current_operation is None:
            return
        values = self._config_form.values()
        if self._current_operation is ScenarioTrainingOperation.FIT:
            self._fit_values = values
            return
        self._tuning_values = {key: list(value) if isinstance(value, list) else value for key, value in values.items()}

    def _refresh_enabled_state(self) -> None:
        enabled = self._selected_checkbox.isChecked()
        self._operation_label.setEnabled(enabled)
        self._operation_selector.setEnabled(enabled)
        self._operation_summary_label.setEnabled(enabled)
        self._config_form.setEnabled(enabled)

    def _refresh_operation_summary(self) -> None:
        operation = self.current_operation()
        if operation is ScenarioTrainingOperation.FIT:
            self._operation_summary_label.setText(
                self.tr("Train this model once with a concrete parameter set.")
            )
        else:
            self._operation_summary_label.setText(
                self.tr("Search across a parameter grid and keep the best result.")
            )

    def _translate_operation(self, operation: ScenarioTrainingOperation) -> str:
        labels = {
            ScenarioTrainingOperation.FIT: self.tr("Fit"),
            ScenarioTrainingOperation.HYPERPARAMETER_TUNING: self.tr("Hyperparameter Tuning"),
        }
        return labels[operation]

    def _translate_recommendation_tier(self, tier: int) -> str:
        if tier <= 20:
            return self.tr("Recommended")
        if tier <= 40:
            return self.tr("Strong alternative")
        if tier <= 60:
            return self.tr("Advanced option")
        return self.tr("Specialized option")


class ScenarioTrainingSelectionDialog(QDialog):
    def __init__(
        self,
        template: ScenarioTemplate,
        preparation_result: ScenarioWorkItemPreparationResult,
        training_preset_service: ScenarioTrainingPresetService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._preparation_result = preparation_result
        self._training_preset_service = training_preset_service
        self._available_models = self._training_preset_service.list_available_models(self._template.key)
        self._default_steps = self._training_preset_service.load_default_steps(self._template.key)
        self._model_cards: dict[str, _ScenarioTrainingOptionCard] = {}
        self._section_labels: dict[str, QLabel] = {}

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._selection_label = QLabel()
        self._message_label = QLabel()
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        self._scroll_area = QScrollArea()
        self._save_defaults_button = QPushButton()
        self._start_training_button = QPushButton()
        self._close_button = QPushButton()

        self.resize(960, 760)
        self._build_ui()
        self._build_cards()
        self._wire_events()
        self.retranslate_ui()
        self._refresh_action_state()

    def selected_steps(self) -> list[ScenarioTrainingPlanStep]:
        selected_steps: list[ScenarioTrainingPlanStep] = []
        for card in self._model_cards.values():
            step = card.selected_step()
            if step is not None:
                selected_steps.append(step)
        return selected_steps

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Choose Models and Train"))
        self._title_label.setText(localized_template_display_name(self._template))
        self._summary_label.setText(
            self.tr(
                "Choose one or more models for this scenario, adjust their parameters, and save the current combination as the default when needed."
            )
        )
        self._selection_label.setText(self._build_selection_text())
        self._save_defaults_button.setText(self.tr("Save as Default"))
        self._start_training_button.setText(self.tr("Start Training"))
        self._close_button.setText(self.tr("Close"))
        if not self._available_models:
            self._message_label.setText(self.tr("No compatible models are available for this scenario template yet."))
        elif not self._message_label.text():
            self._message_label.setText(self.tr("Select at least one model to continue."))
        if "recommended" in self._section_labels:
            self._section_labels["recommended"].setText(self.tr("Recommended plan"))
        if "additional" in self._section_labels:
            self._section_labels["additional"].setText(self.tr("Additional compatible models"))
        for card in self._model_cards.values():
            card.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        emphasize_label(self._title_label, point_delta=2)
        self._summary_label.setWordWrap(True)
        self._selection_label.setWordWrap(True)
        self._message_label.setWordWrap(True)

        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setWidget(self._cards_container)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        actions_layout.addWidget(self._save_defaults_button)
        actions_layout.addWidget(self._start_training_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._close_button)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._selection_label)
        layout.addWidget(self._scroll_area, 1)
        layout.addWidget(self._message_label)
        layout.addLayout(actions_layout)

    def _build_cards(self) -> None:
        default_steps_by_model = {step.model_key: step for step in self._default_steps}
        current_section: str | None = None
        for entry in self._ordered_models():
            section_key = "recommended" if entry.model_key in default_steps_by_model else "additional"
            if section_key != current_section:
                section_label = QLabel(parent=self._cards_container)
                emphasize_label(section_label)
                self._cards_layout.addWidget(section_label)
                self._section_labels[section_key] = section_label
                current_section = section_key
            card = _ScenarioTrainingOptionCard(
                catalog_entry=entry,
                initial_step=default_steps_by_model.get(entry.model_key),
                parent=self._cards_container,
            )
            card.selection_changed.connect(self._refresh_action_state)
            self._cards_layout.addWidget(card)
            self._model_cards[entry.model_key] = card
        self._cards_layout.addStretch(1)

    def _ordered_models(self) -> list[ModelCatalogEntry]:
        priority_keys = [step.model_key for step in self._default_steps]
        priority_index = {model_key: index for index, model_key in enumerate(priority_keys)}
        return sorted(
            self._available_models,
            key=lambda entry: (
                0 if entry.model_key in priority_index else 1,
                priority_index.get(entry.model_key, len(priority_index)),
                entry.recommendation_tier,
                entry.family,
                entry.display_name,
            ),
        )

    def _wire_events(self) -> None:
        self._save_defaults_button.clicked.connect(self._save_defaults)
        self._start_training_button.clicked.connect(self._accept_training_selection)
        self._close_button.clicked.connect(self.reject)

    def _refresh_action_state(self) -> None:
        has_selection = bool(self.selected_steps())
        self._save_defaults_button.setEnabled(has_selection)
        self._start_training_button.setEnabled(has_selection)
        if not self._available_models:
            self._message_label.setText(self.tr("No compatible models are available for this scenario template yet."))
            mark_status_label(self._message_label, is_error=True)
            return
        if has_selection:
            self._set_message(
                self.tr("Ready to train {count} model selection(s).").format(count=str(len(self.selected_steps()))),
                is_error=False,
            )
        else:
            self._set_message(self.tr("Select at least one model to continue."), is_error=True)

    def _save_defaults(self) -> None:
        try:
            self._training_preset_service.save_default_steps(self._template.key, self.selected_steps())
        except XenixError as exc:
            self._set_message(str(exc), is_error=True)
            return
        self._set_message(self.tr("Saved the current model selection as the default."), is_error=False)

    def _accept_training_selection(self) -> None:
        if not self.selected_steps():
            self._set_message(self.tr("Select at least one model to continue."), is_error=True)
            return
        self.accept()

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._message_label.setText(message)
        mark_status_label(self._message_label, is_error=is_error)

    def _build_selection_text(self) -> str:
        if self._template.required_target_count == 0:
            return self.tr("Input columns: {features}\nPrediction target: not required").format(
                features=", ".join(self._preparation_result.feature_columns)
            )
        return self.tr("Input columns: {features}\nPrediction target: {targets}").format(
            features=", ".join(self._preparation_result.feature_columns),
            targets=", ".join(self._preparation_result.target_columns),
        )
