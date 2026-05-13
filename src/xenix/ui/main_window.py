from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.agent import AgentHarnessService, SubmitUserTurnInput, ThreadSnapshot
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
from .chat_box import ThreadDetailView
from .dataset_workspace import DatasetWorkspace
from .inference_history_dialog import InferenceHistoryDialog
from .inference_workspace import InferenceWorkspace
from .layout_debug import dump_layout_if_enabled
from .ml_workspace import MLWorkspace
from .scenario_data_preparation_dialog import ScenarioDataPreparationDialog
from .scenario_home_view import ScenarioHomeView
from .scenario_inference_dialog import ScenarioInferenceDialog
from .scenario_model_source_dialog import ScenarioModelSourceDialog, ScenarioModelSourceKind
from .scenario_training_dialog import ScenarioTrainingDialog
from .scenario_training_selection_dialog import ScenarioTrainingSelectionDialog
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    _harness_snapshot_ready = Signal(object)
    _harness_failed = Signal(str)

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
        agent_harness_service: AgentHarnessService | None = None,
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
        self._agent_harness_service = agent_harness_service
        self._agent_thread_id: str | None = None
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
        self._title_label = QLabel(parent=self)
        self._settings_button = QPushButton(parent=self)
        self._settings_button.clicked.connect(self._open_settings)
        self._history_sidebar = QFrame(parent=self)
        self._history_sidebar.setObjectName("historySidebar")
        self._history_label = QLabel(parent=self._history_sidebar)
        self._history_list = QListWidget(parent=self._history_sidebar)
        self._history_list.itemClicked.connect(self._open_history_thread)
        self._refreshing_history = False
        self._thread_detail_view = ThreadDetailView(parent=self)
        self._chat_box = self._thread_detail_view
        self._chat_box.message_submitted.connect(self._submit_chat_message)
        self._chat_box.stop_requested.connect(self._request_harness_stop)
        self._harness_snapshot_ready.connect(self._render_harness_snapshot)
        self._harness_failed.connect(self._render_harness_error)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("mainWindowRoot")
        layout = QVBoxLayout(root)
        layout.setObjectName("mainWindowRootLayout")
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        self._home_view.open_settings_requested.connect(self._open_settings)
        self._home_view.open_history_requested.connect(self._open_history)
        self._home_view.scenario_selected.connect(self._open_scenario)
        header_layout = QHBoxLayout()
        header_layout.setObjectName("mainHeaderLayout")
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        self._title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._settings_button.setMinimumWidth(96)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self._settings_button)
        layout.addLayout(header_layout)

        sidebar_layout = QVBoxLayout(self._history_sidebar)
        sidebar_layout.setObjectName("historySidebarLayout")
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(8)
        self._history_sidebar.setFixedWidth(248)
        self._history_label.setObjectName("historySidebarTitle")
        self._history_list.setObjectName("historyList")
        sidebar_layout.addWidget(self._history_label)
        sidebar_layout.addWidget(self._history_list, 1)

        content_layout = QHBoxLayout()
        content_layout.setObjectName("mainContentLayout")
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._history_sidebar)
        content_layout.addWidget(self._chat_box, 1)
        layout.addLayout(content_layout, 1)

        self.setCentralWidget(root)
        self._refresh_history_sidebar()
        current_item = self._history_list.currentItem()
        if current_item is not None:
            self._open_history_thread(current_item)
        self._apply_shell_style()
        dump_layout_if_enabled(root, reason="main-window-setup")

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        self._title_label.setText(self.tr("Xenix"))
        self._settings_button.setText(self.tr("Settings"))
        self._history_label.setText(self.tr("History"))
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

    def _submit_chat_message(self, text: str, file_paths: list[str]) -> None:
        if self._agent_harness_service is None:
            self._chat_box.show_error("Agent Harness service is unavailable.")
            return
        user_blocks = []
        if text:
            user_blocks.append({"type": "text", "text": text})
        for file_path in file_paths:
            user_blocks.append({"type": "file", "path": file_path})
        self._chat_box.add_message("You", user_blocks)
        self._chat_box.set_running(True)

        def run_harness() -> None:
            try:
                snapshot = self._agent_harness_service.submit_user_turn(
                    SubmitUserTurnInput(
                        thread_id=self._agent_thread_id,
                        text=text,
                        file_paths=file_paths,
                    )
                )
                self._harness_snapshot_ready.emit(snapshot)
            except Exception as exc:
                self._harness_failed.emit(str(exc))

        threading.Thread(target=run_harness, name="xenix-agent-harness", daemon=True).start()

    def _render_harness_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self._agent_thread_id = snapshot.thread.id
        self._chat_box.render_snapshot(snapshot)
        self._chat_box.set_running(False)
        self._refresh_history_sidebar(selected_thread_id=snapshot.thread.id)

    def _render_harness_error(self, message: str) -> None:
        self._chat_box.show_error(message)
        self._chat_box.set_running(False)

    def _request_harness_stop(self) -> None:
        self._chat_box.show_error("Stop requested. Xenix will stop after the active step returns.")

    def _refresh_history_sidebar(self, *, selected_thread_id: str | None = None) -> None:
        self._history_list.clear()
        if self._agent_harness_service is None:
            return
        self._refreshing_history = True
        try:
            selected_row = -1
            for index, thread in enumerate(self._agent_harness_service.list_threads()):
                title = thread.title or "Untitled conversation"
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, thread.id)
                self._history_list.addItem(item)
                if thread.id == selected_thread_id:
                    selected_row = index
            if selected_row >= 0:
                self._history_list.setCurrentRow(selected_row)
            elif selected_thread_id is None and self._agent_thread_id is None and self._history_list.count() > 0:
                self._history_list.setCurrentRow(0)
        finally:
            self._refreshing_history = False

    def _open_history_thread(self, item: QListWidgetItem) -> None:
        if self._refreshing_history or self._agent_harness_service is None:
            return
        thread_id = item.data(Qt.UserRole)
        if not isinstance(thread_id, str):
            return
        snapshot = self._agent_harness_service.get_thread_snapshot(thread_id)
        self._agent_thread_id = thread_id
        self._chat_box.render_snapshot(snapshot)

    def _apply_shell_style(self) -> None:
        self.setStyleSheet(
            """
            #historySidebar {
                background: #ffffff;
                border: 1px solid #d8dde6;
                border-radius: 8px;
            }
            #historySidebarTitle {
                font-weight: 600;
                color: #303640;
            }
            #historyList {
                background: transparent;
                border: 0;
                outline: 0;
            }
            #historyList::item {
                padding: 8px 9px;
                border-radius: 6px;
                color: #303640;
            }
            #historyList::item:selected {
                background: #e9f0ff;
                color: #1f3b70;
            }
            #historyList::item:hover {
                background: #f1f3f6;
            }
            """
        )
