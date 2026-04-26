from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.analysis_scenario_service import AnalysisScenarioService
from ..services.dataset_service import DatasetService
from ..services.inference_history_service import InferenceHistoryService
from ..services.ml_service import MLService
from ..services.project_service import ProjectService
from ..services.scenario_model_source_service import ScenarioModelSourceService
from ..services.scenario_template_service import ScenarioTemplateService
from ..services.scenario_training_preset_service import ScenarioTrainingPresetService
from ..services.scenario_workflow_service import ScenarioWorkflowService
from ..services.work_item_service import WorkItemService
from .dataset_workspace import DatasetWorkspace
from .inference_history_dialog import InferenceHistoryDialog
from .inference_workspace import InferenceWorkspace
from .ml_workspace import MLWorkspace
from .scenario_data_preparation_dialog import ScenarioDataPreparationDialog
from .scenario_home_view import ScenarioHomeView
from .scenario_inference_dialog import ScenarioInferenceDialog
from .scenario_model_source_dialog import ScenarioModelSourceDialog, ScenarioModelSourceKind
from .scenario_training_dialog import ScenarioTrainingDialog
from .scenario_training_selection_dialog import ScenarioTrainingSelectionDialog
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        ml_service: MLService,
        inference_history_service: InferenceHistoryService,
        analysis_scenario_service: AnalysisScenarioService,
        scenario_model_source_service: ScenarioModelSourceService,
        scenario_template_service: ScenarioTemplateService,
        scenario_training_preset_service: ScenarioTrainingPresetService,
        scenario_workflow_service: ScenarioWorkflowService,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._inference_history_service = inference_history_service
        self._analysis_scenario_service = analysis_scenario_service
        self._scenario_model_source_service = scenario_model_source_service
        self._scenario_template_service = scenario_template_service
        self._scenario_training_preset_service = scenario_training_preset_service
        self._scenario_workflow_service = scenario_workflow_service
        self._settings_dialog: SettingsDialog | None = None
        self._scenario_data_preparation_dialog: ScenarioDataPreparationDialog | None = None
        self._scenario_model_source_dialog: ScenarioModelSourceDialog | None = None
        self._scenario_training_selection_dialog: ScenarioTrainingSelectionDialog | None = None
        self._scenario_training_dialog: ScenarioTrainingDialog | None = None
        self._scenario_inference_dialog: ScenarioInferenceDialog | None = None
        self._inference_history_dialog: InferenceHistoryDialog | None = None

        self._dataset_workspace = DatasetWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            parent=self,
        )
        self._ml_workspace = MLWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            ml_service=self._ml_service,
            parent=self,
        )
        self._inference_workspace = InferenceWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            ml_service=self._ml_service,
            parent=self,
        )
        self._home_view = ScenarioHomeView(self._analysis_scenario_service.list_scenarios(), parent=self)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self._home_view.open_settings_requested.connect(self._open_settings)
        self._home_view.open_history_requested.connect(self._open_history)
        self._home_view.scenario_selected.connect(self._open_scenario)
        layout.addWidget(self._home_view, 1)

        self.setCentralWidget(root)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        if self._settings_dialog is not None:
            self._settings_dialog.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(
                paths=self._paths,
                log_path=self._log_path,
                db_path=self._db_path,
                translation_manager=self._translation_manager,
                parent=self,
            )
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _open_history(self) -> None:
        if self._inference_history_dialog is None:
            self._inference_history_dialog = InferenceHistoryDialog(
                history_service=self._inference_history_service,
                dataset_service=self._dataset_service,
                ml_service=self._ml_service,
                parent=self,
            )
        else:
            self._inference_history_dialog.refresh_history()
        self._inference_history_dialog.show()
        self._inference_history_dialog.raise_()
        self._inference_history_dialog.activateWindow()

    def _open_scenario(self, analysis_scenario_key: str) -> None:
        analysis_scenario = self._analysis_scenario_service.get_scenario(analysis_scenario_key)
        if len(analysis_scenario.linked_template_keys) != 1:
            return
        template_key = analysis_scenario.linked_template_keys[0]
        template = self._scenario_template_service.get_template(template_key)
        self._scenario_data_preparation_dialog = ScenarioDataPreparationDialog(
            template=template,
            dataset_service=self._dataset_service,
            workflow_service=self._scenario_workflow_service,
            parent=self,
        )
        self._scenario_data_preparation_dialog.accepted.connect(self._open_model_source_after_preparation)
        self._scenario_data_preparation_dialog.show()
        self._scenario_data_preparation_dialog.raise_()
        self._scenario_data_preparation_dialog.activateWindow()

    def _open_model_source_after_preparation(self) -> None:
        if self._scenario_data_preparation_dialog is None:
            return
        result = self._scenario_data_preparation_dialog.preparation_result()
        if result is None:
            return
        template = self._scenario_template_service.get_template(result.template_key)
        if not template.supervised_required or not template.continues_to_prediction:
            self._scenario_training_selection_dialog = ScenarioTrainingSelectionDialog(
                template=template,
                preparation_result=result,
                training_preset_service=self._scenario_training_preset_service,
                parent=self,
            )
            self._scenario_training_selection_dialog.accepted.connect(self._continue_after_training_selection)
            self._scenario_training_selection_dialog.show()
            self._scenario_training_selection_dialog.raise_()
            self._scenario_training_selection_dialog.activateWindow()
            return
        self._scenario_model_source_dialog = ScenarioModelSourceDialog(
            template=template,
            preparation_result=result,
            model_source_service=self._scenario_model_source_service,
            parent=self,
        )
        self._scenario_model_source_dialog.accepted.connect(self._continue_after_model_source_selection)
        self._scenario_model_source_dialog.show()
        self._scenario_model_source_dialog.raise_()
        self._scenario_model_source_dialog.activateWindow()

    def _continue_after_model_source_selection(self) -> None:
        if self._scenario_data_preparation_dialog is None or self._scenario_model_source_dialog is None:
            return
        result = self._scenario_data_preparation_dialog.preparation_result()
        if result is None:
            return
        template = self._scenario_template_service.get_template(result.template_key)
        selection_kind = self._scenario_model_source_dialog.selected_source_kind()
        if selection_kind is ScenarioModelSourceKind.TRAIN_NEW:
            self._scenario_training_selection_dialog = ScenarioTrainingSelectionDialog(
                template=template,
                preparation_result=result,
                training_preset_service=self._scenario_training_preset_service,
                parent=self,
            )
            self._scenario_training_selection_dialog.accepted.connect(self._continue_after_training_selection)
            self._scenario_training_selection_dialog.show()
            self._scenario_training_selection_dialog.raise_()
            self._scenario_training_selection_dialog.activateWindow()
            return
        if selection_kind is ScenarioModelSourceKind.TRAINED_MODEL:
            selected_model = self._scenario_model_source_dialog.selected_trained_model()
            if selected_model is None:
                return
            self._open_inference_for_preparation(
                preparation_result=result,
                available_trained_models=self._scenario_model_source_dialog.compatible_models(),
                preferred_trained_model_id=selected_model.trained_model_id,
            )
            return

    def _continue_after_training_selection(self) -> None:
        if self._scenario_data_preparation_dialog is None or self._scenario_training_selection_dialog is None:
            return
        result = self._scenario_data_preparation_dialog.preparation_result()
        if result is None:
            return
        template = self._scenario_template_service.get_template(result.template_key)
        self._open_training_for_preparation(
            template=template,
            preparation_result=result,
            selected_steps=self._scenario_training_selection_dialog.selected_steps(),
        )

    def _open_training_for_preparation(self, template, preparation_result, *, selected_steps=None) -> None:
        self._scenario_training_dialog = ScenarioTrainingDialog(
            template=template,
            preparation_result=preparation_result,
            workflow_service=self._scenario_workflow_service,
            ml_service=self._ml_service,
            training_steps=selected_steps,
            parent=self,
        )
        self._scenario_training_dialog.continue_to_prediction_requested.connect(self._open_inference_after_training)
        self._scenario_training_dialog.show()
        self._scenario_training_dialog.raise_()
        self._scenario_training_dialog.activateWindow()

    def _open_inference_after_training(self, preparation_result) -> None:
        self._open_inference_for_preparation(preparation_result=preparation_result)

    def _open_inference_for_preparation(
        self,
        *,
        preparation_result,
        available_trained_models=None,
        preferred_trained_model_id=None,
    ) -> None:
        template = self._scenario_template_service.get_template(preparation_result.template_key)
        self._scenario_inference_dialog = ScenarioInferenceDialog(
            template=template,
            preparation_result=preparation_result,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            ml_service=self._ml_service,
            available_trained_models=available_trained_models,
            preferred_trained_model_id=preferred_trained_model_id,
            parent=self,
        )
        self._scenario_inference_dialog.show()
        self._scenario_inference_dialog.raise_()
        self._scenario_inference_dialog.activateWindow()
