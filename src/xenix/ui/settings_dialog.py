from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QEvent, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..build_info import BUILD_COMMIT, BUILD_COMMIT_DISPLAY
from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from ..services.llm import (
    LLMDialect,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
    PACKAGED_TRIAL_SECRET_SOURCE,
)
from ..services.ml.worker_settings import MLWorkerKind, MLWorkerSettingsService
from ..services.knowledge_index_service import (
    KnowledgeIndexKind,
    KnowledgeIndexService,
)
from ..services.paddle_ocr_service import (
    PaddleOcrDeploymentService,
    PaddleOcrStatus,
)
from ..services.update_service import UpdateService, UpdateState, UpdateStatus
from .ocr_deployment_tasks import OcrInstallTask, OcrStatusTask
from .knowledge_index_ui import KnowledgeIndexRebuildDialog
from .ssh_worker_setup_wizard import SshWorkerSetupWizard


class SettingsTab(StrEnum):
    AI = "ai"
    KNOWLEDGE_BASE = "knowledge_base"
    ML_WORKERS = "ml_workers"


class AboutDialog(QDialog):
    _update_finished = Signal(object)
    _quit_for_update = Signal()

    def __init__(
        self,
        *,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        update_service: UpdateService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._update_service = update_service

        self._runtime_card = QFrame()
        self._runtime_card.setFrameShape(QFrame.StyledPanel)
        self._runtime_card_layout = QFormLayout(self._runtime_card)
        self._runtime_card_layout.setContentsMargins(12, 12, 12, 12)

        self._app_home_label = QLabel()
        self._state_label = QLabel()
        self._artifacts_label = QLabel()
        self._database_label = QLabel()
        self._current_log_file_label = QLabel()
        self._build_commit_label = QLabel()
        self._open_logs_button = QPushButton()
        self._check_updates_button = QPushButton()
        self._update_status_value = QLabel()

        self._app_home_value = QLabel(str(self._paths.home))
        self._state_value = QLabel(str(self._paths.state))
        self._artifacts_value = QLabel(str(self._paths.artifacts))
        self._database_value = QLabel(str(self._db_path))
        self._current_log_file_value = QLabel(str(self._log_path))
        self._build_commit_value = QLabel(BUILD_COMMIT_DISPLAY)
        if BUILD_COMMIT_DISPLAY != BUILD_COMMIT:
            self._build_commit_value.setToolTip(BUILD_COMMIT)

        self.resize(640, 360)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        for value_label in (
            self._app_home_value,
            self._state_value,
            self._artifacts_value,
            self._database_value,
            self._current_log_file_value,
            self._build_commit_value,
        ):
            value_label.setWordWrap(True)

        self._runtime_card_layout.addRow(self._app_home_label, self._app_home_value)
        self._runtime_card_layout.addRow(self._state_label, self._state_value)
        self._runtime_card_layout.addRow(self._artifacts_label, self._artifacts_value)
        self._runtime_card_layout.addRow(self._database_label, self._database_value)
        self._runtime_card_layout.addRow(self._current_log_file_label, self._current_log_file_value)
        self._runtime_card_layout.addRow(self._build_commit_label, self._build_commit_value)

        layout.addWidget(self._runtime_card)
        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._open_logs_button)
        actions_layout.addWidget(self._check_updates_button)
        actions_layout.addStretch(1)
        layout.addLayout(actions_layout)

    def _wire_events(self) -> None:
        self._open_logs_button.clicked.connect(self._open_logs_dir)
        self._check_updates_button.clicked.connect(self._check_for_updates)
        self._update_finished.connect(self._handle_update_status)
        self._quit_for_update.connect(QApplication.instance().quit)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("About"))
        self._app_home_label.setText(self.tr("App home"))
        self._state_label.setText(self.tr("State"))
        self._artifacts_label.setText(self.tr("Artifacts"))
        self._database_label.setText(self.tr("Database"))
        self._current_log_file_label.setText(self.tr("Current log file"))
        self._build_commit_label.setText(self.tr("Build commit"))
        self._open_logs_button.setText(self.tr("Open log directory"))
        self._check_updates_button.setText(self.tr("Check for updates"))
        if self._update_service is None:
            self._check_updates_button.setEnabled(False)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))

    def _run_update_operation(self, operation) -> None:
        self._check_updates_button.setEnabled(False)

        def run() -> None:
            try:
                result = operation()
            except Exception as exc:
                result = UpdateStatus(UpdateState.FAILED, "", message=str(exc))
            self._update_finished.emit(result)

        import threading

        threading.Thread(target=run, name="xenix-update", daemon=True).start()

    def _check_for_updates(self) -> None:
        if self._update_service is not None:
            self._run_update_operation(self._update_service.check)

    def _handle_update_status(self, status: UpdateStatus) -> None:
        self._check_updates_button.setEnabled(True)
        if status.state is UpdateState.UNAVAILABLE:
            QMessageBox.information(self, self.tr("Updates"), self.tr("Updates are unavailable in this build."))
        elif status.state is UpdateState.IDLE:
            QMessageBox.information(self, self.tr("Updates"), self.tr("Xenix is up to date."))
        elif status.state is UpdateState.FAILED:
            QMessageBox.warning(self, self.tr("Updates"), status.message)
        elif status.state is UpdateState.UPDATE_AVAILABLE and self._update_service is not None:
            answer = QMessageBox.question(
                self,
                self.tr("Update available"),
                self.tr("Xenix {version} is available. Download it now?").format(version=status.target_version),
            )
            if answer == QMessageBox.Yes:
                self._run_update_operation(self._update_service.download)
        elif status.state is UpdateState.READY and self._update_service is not None:
            answer = QMessageBox.question(
                self,
                self.tr("Update ready"),
                self.tr("Restart Xenix now to apply version {version}?").format(version=status.target_version),
            )
            if answer == QMessageBox.Yes:
                self._run_update_operation(lambda: self._apply_update(status))

    def _apply_update(self, status: UpdateStatus) -> UpdateStatus:
        assert self._update_service is not None
        self._update_service.apply(self._quit_for_update.emit)
        return UpdateStatus(UpdateState.APPLYING, status.installed_version, status.target_version)


class SettingsDialog(QDialog):
    agent_settings_saved = Signal()
    embedding_settings_saved = Signal()
    ml_worker_settings_saved = Signal()

    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        llm_service: LLMService,
        llm_settings_service: LLMSettingsService,
        ml_worker_settings_service: MLWorkerSettingsService,
        embedding_settings_service: EmbeddingSettingsService,
        update_service: UpdateService | None = None,
        paddle_ocr_deployment: PaddleOcrDeploymentService | None = None,
        knowledge_index_service: KnowledgeIndexService | None = None,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._llm_service = llm_service
        self._llm_settings_service = llm_settings_service
        self._embedding_settings_service = embedding_settings_service
        self._ml_worker_settings_service = ml_worker_settings_service
        self._update_service = update_service
        self._paddle_ocr_deployment = paddle_ocr_deployment
        self._knowledge_index_service = knowledge_index_service
        self._provider_configs: list[LLMProviderConfig] = []
        self._loading_provider = False
        self._active_provider_index = 0
        self._embedding_settings_snapshot = EmbeddingSettings()
        self._ssh_worker_wizard: SshWorkerSetupWizard | None = None
        self._about_dialog: AboutDialog | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._lifecycle_generation = 0
        self._active = False
        self._cached_ocr_status: PaddleOcrStatus | None = None
        self._ocr_status_task: OcrStatusTask | None = None
        self._ocr_install_task: OcrInstallTask | None = None
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._knowledge_refresh_timer = QTimer(self)
        self._knowledge_refresh_timer.setInterval(1_000)
        self._knowledge_refresh_timer.timeout.connect(self._render_index_status)

        self._language_label = QLabel()
        self._language_selector = QComboBox()
        self._about_button = QPushButton()
        self._save_button = QPushButton()

        self._tabs = QTabWidget()
        self._llm_card = QFrame()
        self._llm_card.setFrameShape(QFrame.StyledPanel)
        self._llm_card_layout = QFormLayout(self._llm_card)
        self._llm_card_layout.setContentsMargins(12, 12, 12, 12)

        self._embedding_card = QFrame()
        self._embedding_card.setFrameShape(QFrame.StyledPanel)
        self._embedding_card_layout = QFormLayout(self._embedding_card)
        self._embedding_card_layout.setContentsMargins(12, 12, 12, 12)

        self._ocr_card = QFrame()
        self._ocr_card.setFrameShape(QFrame.StyledPanel)
        self._ocr_card_layout = QFormLayout(self._ocr_card)
        self._ocr_card_layout.setContentsMargins(12, 12, 12, 12)

        self._index_card = QFrame()
        self._index_card.setFrameShape(QFrame.StyledPanel)
        self._index_card_layout = QFormLayout(self._index_card)
        self._index_card_layout.setContentsMargins(12, 12, 12, 12)

        self._global_models_card = QFrame()
        self._global_models_card.setFrameShape(QFrame.StyledPanel)
        self._global_models_card_layout = QFormLayout(self._global_models_card)
        self._global_models_card_layout.setContentsMargins(12, 12, 12, 12)

        self._ml_workers_card = QFrame()
        self._ml_workers_card.setFrameShape(QFrame.StyledPanel)
        self._ml_workers_card_layout = QFormLayout(self._ml_workers_card)
        self._ml_workers_card_layout.setContentsMargins(12, 12, 12, 12)

        self._global_models_title_label = QLabel()
        self._llm_title_label = QLabel()
        self._provider_selector_label = QLabel()
        self._provider_key_label = QLabel()
        self._provider_name_label = QLabel()
        self._provider_dialect_label = QLabel()
        self._provider_base_url_label = QLabel()
        self._provider_api_key_label = QLabel()
        self._provider_models_label = QLabel()
        self._provider_timeout_label = QLabel()
        self._provider_streaming_label = QLabel()
        self._llm_default_model_label = QLabel()
        self._llm_guard_model_label = QLabel()
        self._llm_thread_title_model_label = QLabel()
        self._llm_retry_attempts_label = QLabel()

        self._embedding_title_label = QLabel()
        self._embedding_enabled_label = QLabel()
        self._embedding_base_url_label = QLabel()
        self._embedding_api_key_label = QLabel()
        self._embedding_model_label = QLabel()
        self._embedding_dimensions_label = QLabel()
        self._embedding_batch_size_label = QLabel()
        self._embedding_timeout_label = QLabel()

        self._ocr_title_label = QLabel()
        self._ocr_status_label = QLabel()
        self._ocr_setup_button = QPushButton()

        self._index_title_label = QLabel()
        self._index_status_label = QLabel()
        self._index_status_label.setWordWrap(True)
        self._index_rebuild_button = QPushButton()

        self._ml_workers_title_label = QLabel()
        self._ml_workers_summary_label = QLabel()
        self._ml_workers_setup_button = QPushButton()

        self._provider_selector = QComboBox()
        self._add_provider_button = QPushButton()
        self._remove_provider_button = QPushButton()
        self._provider_key_input = QLineEdit()
        self._provider_name_input = QLineEdit()
        self._provider_dialect_selector = QComboBox()
        self._provider_base_url_input = QLineEdit()
        self._provider_api_key_input = QLineEdit()
        self._provider_api_key_input.setEchoMode(QLineEdit.Password)
        self._provider_models_input = QPlainTextEdit()
        self._provider_models_input.setFixedHeight(82)
        self._provider_timeout_input = QSpinBox()
        self._provider_timeout_input.setRange(1, 3600)
        self._provider_timeout_input.setSuffix(" s")
        self._provider_streaming_checkbox = QCheckBox()
        self._llm_default_model_selector = QComboBox()
        self._llm_guard_model_selector = QComboBox()
        self._llm_thread_title_model_selector = QComboBox()
        self._llm_retry_attempts_input = QSpinBox()
        self._llm_retry_attempts_input.setRange(1, 20)

        self._embedding_enabled_checkbox = QCheckBox()
        self._embedding_base_url_input = QLineEdit()
        self._embedding_api_key_input = QLineEdit()
        self._embedding_api_key_input.setEchoMode(QLineEdit.Password)
        self._embedding_model_input = QLineEdit()
        self._embedding_dimensions_input = QSpinBox()
        self._embedding_dimensions_input.setRange(0, 65_536)
        self._embedding_batch_size_input = QSpinBox()
        self._embedding_batch_size_input.setRange(1, 2_048)
        self._embedding_timeout_input = QSpinBox()
        self._embedding_timeout_input.setRange(1, 3_600)
        self._embedding_timeout_input.setSuffix(" s")
        self._tab_indexes: dict[SettingsTab, int] = {}

        self.resize(760, 760)
        self._build_ui()
        self._wire_events()
        self._load_agent_settings()
        self._load_embedding_settings()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.addWidget(self._language_label)
        header_layout.addWidget(self._language_selector)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        scroll.setWidget(scroll_content)

        provider_selector_row = QHBoxLayout()
        provider_selector_row.setSpacing(8)
        provider_selector_row.addWidget(self._provider_selector, 1)
        provider_selector_row.addWidget(self._add_provider_button)
        provider_selector_row.addWidget(self._remove_provider_button)

        self._provider_dialect_selector.addItem("OpenAI-compatible", LLMDialect.OPENAI_COMPATIBLE.value)
        self._global_models_card_layout.addRow(self._global_models_title_label)
        self._global_models_card_layout.addRow(self._llm_default_model_label, self._llm_default_model_selector)
        self._global_models_card_layout.addRow(self._llm_guard_model_label, self._llm_guard_model_selector)
        self._global_models_card_layout.addRow(
            self._llm_thread_title_model_label,
            self._llm_thread_title_model_selector,
        )
        self._global_models_card_layout.addRow(self._llm_retry_attempts_label, self._llm_retry_attempts_input)

        self._llm_card_layout.addRow(self._llm_title_label)
        self._llm_card_layout.addRow(self._provider_selector_label, provider_selector_row)
        self._llm_card_layout.addRow(self._provider_key_label, self._provider_key_input)
        self._llm_card_layout.addRow(self._provider_name_label, self._provider_name_input)
        self._llm_card_layout.addRow(self._provider_dialect_label, self._provider_dialect_selector)
        self._llm_card_layout.addRow(self._provider_base_url_label, self._provider_base_url_input)
        self._llm_card_layout.addRow(self._provider_api_key_label, self._provider_api_key_input)
        self._llm_card_layout.addRow(self._provider_models_label, self._provider_models_input)
        self._llm_card_layout.addRow(self._provider_timeout_label, self._provider_timeout_input)
        self._llm_card_layout.addRow(self._provider_streaming_label, self._provider_streaming_checkbox)

        self._embedding_card_layout.addRow(self._embedding_title_label)
        self._embedding_card_layout.addRow(self._embedding_enabled_label, self._embedding_enabled_checkbox)
        self._embedding_card_layout.addRow(self._embedding_base_url_label, self._embedding_base_url_input)
        self._embedding_card_layout.addRow(self._embedding_api_key_label, self._embedding_api_key_input)
        self._embedding_card_layout.addRow(self._embedding_model_label, self._embedding_model_input)
        self._embedding_card_layout.addRow(self._embedding_dimensions_label, self._embedding_dimensions_input)
        self._embedding_card_layout.addRow(self._embedding_batch_size_label, self._embedding_batch_size_input)
        self._embedding_card_layout.addRow(self._embedding_timeout_label, self._embedding_timeout_input)

        self._ocr_status_label.setWordWrap(True)
        self._ocr_card_layout.addRow(self._ocr_title_label)
        self._ocr_card_layout.addRow(self._ocr_status_label)
        self._ocr_card_layout.addRow(self._ocr_setup_button)

        self._index_card_layout.addRow(self._index_title_label)
        self._index_card_layout.addRow(self._index_status_label)
        self._index_card_layout.addRow(self._index_rebuild_button)

        self._ml_workers_summary_label.setWordWrap(True)
        self._ml_workers_card_layout.addRow(self._ml_workers_title_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_summary_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_setup_button)

        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(16)
        ai_layout.addWidget(self._global_models_card)
        ai_layout.addWidget(self._llm_card)
        ai_layout.addStretch(1)

        knowledge_tab = QWidget()
        knowledge_layout = QVBoxLayout(knowledge_tab)
        knowledge_layout.setContentsMargins(12, 12, 12, 12)
        knowledge_layout.setSpacing(16)
        knowledge_layout.addWidget(self._embedding_card)
        knowledge_layout.addWidget(self._ocr_card)
        knowledge_layout.addWidget(self._index_card)
        knowledge_layout.addStretch(1)

        ml_workers_tab = QWidget()
        ml_workers_layout = QVBoxLayout(ml_workers_tab)
        ml_workers_layout.setContentsMargins(12, 12, 12, 12)
        ml_workers_layout.setSpacing(16)
        ml_workers_layout.addWidget(self._ml_workers_card)
        ml_workers_layout.addStretch(1)

        self._tab_indexes = {
            SettingsTab.AI: self._tabs.addTab(ai_tab, ""),
            SettingsTab.KNOWLEDGE_BASE: self._tabs.addTab(knowledge_tab, ""),
            SettingsTab.ML_WORKERS: self._tabs.addTab(ml_workers_tab, ""),
        }
        scroll_layout.addWidget(self._tabs)
        scroll_layout.addStretch(1)
        layout.addWidget(scroll, 1)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._about_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._save_button)
        layout.addLayout(actions_layout)

    def _wire_events(self) -> None:
        self._about_button.clicked.connect(self._open_about_dialog)
        self._language_selector.currentIndexChanged.connect(self._on_language_changed)
        self._save_button.clicked.connect(self._save_agent_settings)
        self._provider_selector.currentIndexChanged.connect(self._on_provider_changed)
        self._add_provider_button.clicked.connect(self._add_provider)
        self._remove_provider_button.clicked.connect(self._remove_provider)
        self._ml_workers_setup_button.clicked.connect(self._open_ssh_worker_wizard)
        self._ocr_setup_button.clicked.connect(self._install_ocr)
        self._index_rebuild_button.clicked.connect(self._open_index_rebuild)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
        self._tabs.setTabText(self._tab_indexes[SettingsTab.AI], self.tr("AI"))
        self._tabs.setTabText(
            self._tab_indexes[SettingsTab.KNOWLEDGE_BASE],
            self.tr("Knowledge Base"),
        )
        self._tabs.setTabText(
            self._tab_indexes[SettingsTab.ML_WORKERS],
            self.tr("ML Workers"),
        )
        self._global_models_title_label.setText(self.tr("Global models"))
        self._llm_title_label.setText(self.tr("LLM providers"))
        self._provider_selector_label.setText(self.tr("Provider"))
        self._provider_key_label.setText(self.tr("Provider key"))
        self._provider_name_label.setText(self.tr("Provider name"))
        self._provider_dialect_label.setText(self.tr("Dialect"))
        self._provider_base_url_label.setText(self.tr("Base URL"))
        self._provider_api_key_label.setText(self.tr("API key"))
        self._provider_models_label.setText(self.tr("Models"))
        self._provider_timeout_label.setText(self.tr("Timeout"))
        self._provider_streaming_label.setText(self.tr("Streaming"))
        self._llm_default_model_label.setText(self.tr("Default model"))
        self._llm_guard_model_label.setText(self.tr("Turn guard model"))
        self._llm_thread_title_model_label.setText(self.tr("Thread title model"))
        self._llm_retry_attempts_label.setText(self.tr("LLM retry attempts"))
        self._embedding_title_label.setText(self.tr("Embedding provider"))
        self._embedding_enabled_label.setText(self.tr("Enabled"))
        self._embedding_base_url_label.setText(self.tr("Base URL"))
        self._embedding_api_key_label.setText(self.tr("API key"))
        self._embedding_model_label.setText(self.tr("Model"))
        self._embedding_dimensions_label.setText(self.tr("Dimensions"))
        self._embedding_dimensions_input.setSpecialValueText(self.tr("Provider default (0)"))
        self._embedding_batch_size_label.setText(self.tr("Batch size"))
        self._embedding_timeout_label.setText(self.tr("Timeout"))
        self._ocr_title_label.setText(self.tr("OCR"))
        self._ocr_setup_button.setText(self.tr("Set up local PaddleOCR"))
        self._index_title_label.setText(self.tr("Indexes"))
        self._index_rebuild_button.setText(self.tr("Rebuild indexes..."))
        self._add_provider_button.setText(self.tr("Add"))
        self._remove_provider_button.setText(self.tr("Remove"))
        self._provider_dialect_selector.setItemText(0, self.tr("OpenAI-compatible"))
        self._refresh_provider_field_state()
        self._ml_workers_title_label.setText(self.tr("ML workers"))
        self._ml_workers_setup_button.setText(self.tr("Add SSH worker..."))
        self._about_button.setText(self.tr("About"))
        self._save_button.setText(self.tr("Save"))
        self._reload_language_options()
        self._refresh_model_selectors(
            default_key=self._llm_default_model_selector.currentData(),
            guard_key=self._llm_guard_model_selector.currentData(),
            title_key=self._llm_thread_title_model_selector.currentData(),
        )
        self._refresh_ml_worker_summary()
        self._render_ocr_status()
        self._render_index_status()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def show_tab(self, tab: SettingsTab) -> None:
        self._tabs.setCurrentIndex(self._tab_indexes[SettingsTab(tab)])

    def _install_ocr(self) -> None:
        if self._paddle_ocr_deployment is None or self._ocr_install_task is not None:
            return
        self._ocr_setup_button.setEnabled(False)
        generation = self._lifecycle_generation
        task = OcrInstallTask(self._paddle_ocr_deployment, generation)
        task.signals.phase.connect(self._on_ocr_phase)
        task.signals.finished.connect(self._on_ocr_setup_finished)
        self._ocr_install_task = task
        self._thread_pool.start(task)

    def _on_ocr_phase(self, generation: int, phase: str) -> None:
        if generation != self._lifecycle_generation or not self._active:
            return
        translations = {
            "downloading_python": self.tr("Downloading embedded Python"),
            "installing_pip": self.tr("Installing package manager"),
            "installing_worker": self.tr("Installing OCR runtime"),
            "downloading_models": self.tr("Preparing OCR models"),
            "ready": self.tr("Ready"),
        }
        translated = translations.get(phase, self.tr("Preparing local OCR"))
        self._ocr_status_label.setText(
            self.tr("Local OCR setup: %1").replace("%1", translated)
        )

    def _on_ocr_setup_finished(
        self,
        generation: int,
        status: PaddleOcrStatus | None,
    ) -> None:
        self._ocr_install_task = None
        if status is not None:
            self._cached_ocr_status = status
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._schedule_ocr_status_probe()
            return
        self._ocr_setup_button.setEnabled(self._paddle_ocr_deployment is not None)
        self._render_ocr_status()
        if status is None:
            QMessageBox.warning(
                self,
                self.tr("Local OCR Setup Failed"),
                self.tr("Local OCR setup could not be completed."),
            )

    def _schedule_ocr_status_probe(self) -> None:
        if (
            not self._active
            or self._paddle_ocr_deployment is None
            or self._ocr_status_task is not None
            or self._ocr_install_task is not None
        ):
            return
        generation = self._lifecycle_generation
        task = OcrStatusTask(self._paddle_ocr_deployment, generation)
        task.signals.finished.connect(self._on_ocr_status_finished)
        self._ocr_status_task = task
        self._thread_pool.start(task)

    def _on_ocr_status_finished(self, generation: int, status: PaddleOcrStatus) -> None:
        self._ocr_status_task = None
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._schedule_ocr_status_probe()
            return
        self._cached_ocr_status = status
        self._render_ocr_status()

    def _render_ocr_status(self) -> None:
        status = self._cached_ocr_status
        if self._paddle_ocr_deployment is None:
            text = self.tr("Local PaddleOCR service is unavailable")
            enabled = False
        elif status is None:
            text = self.tr("Checking local PaddleOCR status")
            enabled = self._ocr_install_task is None
        elif status.installed and status.models_ready:
            text = self.tr("Local PaddleOCR is ready")
            enabled = self._ocr_install_task is None
        elif status.installed:
            text = self.tr(
                "Local PaddleOCR runtime is installed; models are not ready"
            )
            enabled = self._ocr_install_task is None
        else:
            text = self.tr("Local PaddleOCR is not installed")
            enabled = self._ocr_install_task is None
        self._ocr_status_label.setText(text)
        self._ocr_setup_button.setEnabled(enabled)

    def showEvent(self, event) -> None:
        self._active = True
        self._lifecycle_generation += 1
        self._render_ocr_status()
        self._render_index_status()
        super().showEvent(event)
        self._knowledge_refresh_timer.start()
        self._schedule_ocr_status_probe()

    def hideEvent(self, event) -> None:
        self._deactivate_ocr()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate_ocr()
        super().closeEvent(event)

    def _deactivate_ocr(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._knowledge_refresh_timer.stop()
        if self._index_dialog is not None:
            self._index_dialog.hide()

    def _reload_language_options(self) -> None:
        current_locale = self._translation_manager.current_locale()
        labels = {
            "en_US": self.tr("English"),
            "zh_CN": self.tr("Simplified Chinese"),
        }
        self._language_selector.blockSignals(True)
        self._language_selector.clear()
        for locale_code in self._translation_manager.supported_locales():
            self._language_selector.addItem(labels[locale_code], locale_code)
        index = self._language_selector.findData(current_locale)
        if index >= 0:
            self._language_selector.setCurrentIndex(index)
        self._language_selector.blockSignals(False)

    def _on_language_changed(self, _index: int) -> None:
        locale_code = self._language_selector.currentData()
        if locale_code is None:
            return
        try:
            self._translation_manager.set_locale(str(locale_code))
            self.retranslate_ui()
            if self._about_dialog is not None:
                self._about_dialog.retranslate_ui()
        except Exception as exc:
            self._reload_language_options()
            QMessageBox.critical(
                self,
                self.tr("Language Switch Failed"),
                self.tr("Unable to switch the application language.\n\n{details}").format(details=str(exc)),
            )

    def _open_about_dialog(self) -> None:
        if self._about_dialog is None:
            self._about_dialog = AboutDialog(
                paths=self._paths,
                log_path=self._log_path,
                db_path=self._db_path,
                update_service=self._update_service,
                parent=self,
            )
        self._about_dialog.show()
        self._about_dialog.raise_()
        self._about_dialog.activateWindow()

    def _load_agent_settings(self) -> None:
        settings = self._llm_settings_service.load()
        self._provider_configs = [provider.model_copy(deep=True) for provider in settings.providers]
        self._reload_provider_selector(0)
        self._load_provider_fields(0)
        self._refresh_model_selectors(
            default_key=settings.default_fq_model_key,
            guard_key=settings.turn_completion_guard_fq_model_key,
            title_key=settings.thread_title_fq_model_key,
        )
        self._llm_retry_attempts_input.setValue(settings.retry_attempts)

    def _load_embedding_settings(self) -> None:
        settings = self._embedding_settings_service.load()
        self._embedding_settings_snapshot = settings.model_copy(deep=True)
        self._embedding_enabled_checkbox.setChecked(settings.enabled)
        self._embedding_base_url_input.setText(settings.base_url)
        self._embedding_api_key_input.setText(settings.api_key)
        self._embedding_model_input.setText(settings.model)
        self._embedding_dimensions_input.setValue(settings.dimensions or 0)
        self._embedding_batch_size_input.setValue(settings.batch_size)
        self._embedding_timeout_input.setValue(settings.timeout_seconds)

    def _save_agent_settings(self) -> None:
        rebuild_choice = "none"
        try:
            self._store_current_provider_fields()
            llm_settings = LLMSettings(
                providers=self._provider_configs,
                default_fq_model_key=str(self._llm_default_model_selector.currentData() or ""),
                turn_completion_guard_fq_model_key=str(self._llm_guard_model_selector.currentData() or ""),
                thread_title_fq_model_key=str(self._llm_thread_title_model_selector.currentData() or ""),
                retry_attempts=self._llm_retry_attempts_input.value(),
            )
            embedding_settings = self._embedding_settings_from_fields()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        try:
            confirmation_required = (
                self._knowledge_index_service is not None
                and self._knowledge_index_service.embedding_change_requires_confirmation(
                    self._embedding_settings_snapshot,
                    embedding_settings,
                )
            )
        except Exception:
            QMessageBox.warning(
                self,
                self.tr("Knowledge Indexes"),
                self.tr("Knowledge index status is unavailable"),
            )
            return
        if confirmation_required:
            rebuild_choice = self._confirm_embedding_compatibility_change()
            if rebuild_choice == "cancel":
                return
        try:
            self._llm_settings_service.save(llm_settings)
            self._embedding_settings_service.save(embedding_settings)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        self._embedding_settings_snapshot = embedding_settings.model_copy(deep=True)
        self.agent_settings_saved.emit()
        self.embedding_settings_saved.emit()
        if rebuild_choice == "rebuild" and self._knowledge_index_service is not None:
            try:
                self._knowledge_index_service.enqueue_rebuild(
                    (KnowledgeIndexKind.TEXT_VECTOR,),
                    trigger="settings_change",
                )
            except Exception:
                QMessageBox.warning(
                    self,
                    self.tr("Knowledge Indexes"),
                    self.tr(
                        "Embedding settings were saved, but the vector rebuild "
                        "could not be queued."
                    ),
                )
        self._render_index_status()

    def _confirm_embedding_compatibility_change(self) -> str:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle(self.tr("Rebuild text vectors?"))
        message.setText(
            self.tr(
                "This change uses a different embedding space. Existing text "
                "vectors cannot be reused for current Knowledge content."
            )
        )
        rebuild = message.addButton(
            self.tr("Save and rebuild now"),
            QMessageBox.AcceptRole,
        )
        save_only = message.addButton(
            self.tr("Save; rebuild later"),
            QMessageBox.ActionRole,
        )
        cancel = message.addButton(QMessageBox.Cancel)
        message.setDefaultButton(rebuild)
        message.exec()
        selected = message.clickedButton()
        if selected is rebuild:
            return "rebuild"
        if selected is save_only:
            return "later"
        if selected is cancel:
            return "cancel"
        return "cancel"

    def _embedding_settings_from_fields(self) -> EmbeddingSettings:
        dimensions = self._embedding_dimensions_input.value()
        current = self._embedding_settings_snapshot
        return EmbeddingSettings(
            schema_version=current.schema_version,
            enabled=self._embedding_enabled_checkbox.isChecked(),
            provider_key=current.provider_key,
            dialect=current.dialect,
            base_url=self._embedding_base_url_input.text(),
            api_key=self._embedding_api_key_input.text(),
            model=self._embedding_model_input.text(),
            dimensions=dimensions or None,
            batch_size=self._embedding_batch_size_input.value(),
            timeout_seconds=self._embedding_timeout_input.value(),
        )

    def _open_index_rebuild(self) -> None:
        if self._knowledge_index_service is None:
            return
        if self._index_dialog is None:
            self._index_dialog = KnowledgeIndexRebuildDialog(
                self._knowledge_index_service,
                self,
            )
            self._index_dialog.submitted.connect(
                lambda _task_id: self._render_index_status()
            )
        self._index_dialog.open()

    def _render_index_status(self) -> None:
        if self._knowledge_index_service is None:
            self._index_status_label.setText(
                self.tr("Knowledge index service is unavailable")
            )
            self._index_rebuild_button.setEnabled(False)
            return
        try:
            status = self._knowledge_index_service.status()
        except Exception:
            self._index_status_label.setText(
                self.tr("Knowledge index status is unavailable")
            )
            self._index_rebuild_button.setEnabled(False)
            return
        self._index_status_label.setText(
            self.tr("Keyword: %1\nText vectors: %2")
            .replace("%1", self._translated_index_state(status.keyword_state))
            .replace(
                "%2", self._translated_index_state(status.text_vector_state)
            )
        )
        self._index_rebuild_button.setEnabled(status.unit_count > 0)

    def _translated_index_state(self, state: str) -> str:
        translations = {
            "ready": self.tr("Ready"),
            "building": self.tr("Building"),
            "needs_rebuild": self.tr("Needs rebuild"),
            "unavailable": self.tr("Unavailable"),
            "needs_attention": self.tr("Needs attention"),
        }
        return translations.get(state, self.tr("Unknown status"))

    def _refresh_ml_worker_summary(self) -> None:
        settings = self._ml_worker_settings_service.load()
        enabled = [worker for worker in settings.workers if worker.enabled]
        local_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.LOCAL)
        ssh_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.SSH)
        total_slots = sum(worker.max_concurrent_tasks for worker in enabled)
        self._ml_workers_summary_label.setText(
            self.tr("{local_count} local, {ssh_count} SSH, {slots} execution slot(s).").format(
                local_count=local_count,
                ssh_count=ssh_count,
                slots=total_slots,
            )
        )

    def _open_ssh_worker_wizard(self) -> None:
        wizard = SshWorkerSetupWizard(
            self._ml_worker_settings_service,
            parent=self,
        )
        wizard.worker_saved.connect(self._refresh_ml_worker_summary)
        wizard.worker_saved.connect(self.ml_worker_settings_saved.emit)
        self._ssh_worker_wizard = wizard
        wizard.show()
        wizard.raise_()
        wizard.activateWindow()

    def _on_provider_changed(self, index: int) -> None:
        if self._loading_provider:
            return
        try:
            self._store_current_provider_fields()
        except Exception:
            pass
        self._load_provider_fields(index)
        self._refresh_model_selectors(
            default_key=self._llm_default_model_selector.currentData(),
            guard_key=self._llm_guard_model_selector.currentData(),
            title_key=self._llm_thread_title_model_selector.currentData(),
        )

    def _add_provider(self) -> None:
        try:
            self._store_current_provider_fields()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        existing = {provider.key for provider in self._provider_configs}
        index = 2
        key = "provider2"
        while key in existing:
            index += 1
            key = f"provider{index}"
        self._provider_configs.append(
            LLMProviderConfig(
                key=key,
                display_name=f"Provider {index}",
                models=["gpt-4o-mini"],
            )
        )
        self._reload_provider_selector(len(self._provider_configs) - 1)
        self._load_provider_fields(len(self._provider_configs) - 1)
        self._refresh_model_selectors()

    def _remove_provider(self) -> None:
        if len(self._provider_configs) <= 1:
            return
        index = max(0, self._provider_selector.currentIndex())
        self._provider_configs.pop(index)
        next_index = min(index, len(self._provider_configs) - 1)
        self._reload_provider_selector(next_index)
        self._load_provider_fields(next_index)
        self._refresh_model_selectors()

    def _reload_provider_selector(self, selected_index: int) -> None:
        self._loading_provider = True
        self._provider_selector.clear()
        for provider in self._provider_configs:
            label = provider.display_name or provider.key
            self._provider_selector.addItem(label, provider.key)
        if self._provider_configs:
            self._provider_selector.setCurrentIndex(max(0, min(selected_index, len(self._provider_configs) - 1)))
        self._loading_provider = False

    def _load_provider_fields(self, index: int) -> None:
        if not self._provider_configs:
            return
        provider_index = max(0, min(index, len(self._provider_configs) - 1))
        provider = self._provider_configs[provider_index]
        self._loading_provider = True
        self._provider_key_input.setText(provider.key)
        self._provider_name_input.setText(provider.display_name)
        dialect_index = self._provider_dialect_selector.findData(provider.dialect.value)
        if dialect_index >= 0:
            self._provider_dialect_selector.setCurrentIndex(dialect_index)
        self._provider_base_url_input.setText(provider.base_url)
        self._provider_api_key_input.setText(provider.api_key)
        self._provider_models_input.setPlainText("\n".join(provider.models))
        self._provider_timeout_input.setValue(provider.timeout_seconds)
        self._provider_streaming_checkbox.setChecked(provider.streaming_enabled)
        self._apply_provider_field_state(provider)
        self._active_provider_index = provider_index
        self._loading_provider = False

    def _store_current_provider_fields(self) -> None:
        if self._loading_provider or not self._provider_configs:
            return
        index = self._active_provider_index
        if index < 0 or index >= len(self._provider_configs):
            return
        current = self._provider_configs[index]
        packaged_trial = self._is_packaged_trial_provider(current)
        self._provider_configs[index] = LLMProviderConfig(
            key=self._provider_key_input.text().strip(),
            display_name=self._provider_name_input.text().strip(),
            dialect=LLMDialect(str(self._provider_dialect_selector.currentData())),
            base_url=current.base_url if packaged_trial else self._provider_base_url_input.text().strip(),
            api_key="" if packaged_trial else self._provider_api_key_input.text(),
            models=self._model_lines(),
            timeout_seconds=self._provider_timeout_input.value(),
            streaming_enabled=self._provider_streaming_checkbox.isChecked(),
            dialect_config=current.dialect_config,
        )
        self._update_provider_selector_item(index)
        if index == self._provider_selector.currentIndex():
            self._apply_provider_field_state(self._provider_configs[index])

    def _update_provider_selector_item(self, index: int) -> None:
        if index < 0 or index >= len(self._provider_configs) or index >= self._provider_selector.count():
            return
        provider = self._provider_configs[index]
        self._provider_selector.setItemText(index, provider.display_name or provider.key)
        self._provider_selector.setItemData(index, provider.key)

    def _refresh_provider_field_state(self) -> None:
        index = self._provider_selector.currentIndex()
        if 0 <= index < len(self._provider_configs):
            self._apply_provider_field_state(self._provider_configs[index])

    def _apply_provider_field_state(self, provider: LLMProviderConfig) -> None:
        packaged_trial = self._is_packaged_trial_provider(provider)
        self._provider_base_url_input.setReadOnly(packaged_trial)
        self._provider_api_key_input.setReadOnly(packaged_trial)
        if packaged_trial:
            self._provider_api_key_input.setPlaceholderText(self.tr("Built into packaged app"))
        else:
            self._provider_api_key_input.setPlaceholderText("")

    def _is_packaged_trial_provider(self, provider: LLMProviderConfig) -> bool:
        return provider.dialect_config.get("secret_source") == PACKAGED_TRIAL_SECRET_SOURCE

    def _refresh_model_selectors(
        self,
        *,
        default_key: object | None = None,
        guard_key: object | None = None,
        title_key: object | None = None,
    ) -> None:
        if not self._provider_configs:
            return
        try:
            settings = LLMSettings(providers=self._provider_configs)
        except Exception:
            return
        options = LLMService.model_options_from_settings(settings)
        self._replace_model_selector_items(
            self._llm_default_model_selector,
            options,
            selected_key=str(default_key or settings.default_fq_model_key),
            include_blank=False,
        )
        self._replace_model_selector_items(
            self._llm_guard_model_selector,
            options,
            selected_key=str(guard_key or ""),
            include_blank=True,
        )
        self._replace_model_selector_items(
            self._llm_thread_title_model_selector,
            options,
            selected_key=str(title_key or ""),
            include_blank=True,
        )

    def _replace_model_selector_items(
        self,
        selector: QComboBox,
        options,
        *,
        selected_key: str,
        include_blank: bool,
    ) -> None:
        selector.blockSignals(True)
        selector.clear()
        if include_blank:
            selector.addItem(self.tr("None"), "")
        for option in options:
            selector.addItem(option.label, option.fq_model_key)
        index = selector.findData(selected_key)
        if index < 0:
            index = 0
        selector.setCurrentIndex(index)
        selector.blockSignals(False)

    def _model_lines(self) -> list[str]:
        text = self._provider_models_input.toPlainText().replace(",", "\n")
        return [line.strip() for line in text.splitlines() if line.strip()]
