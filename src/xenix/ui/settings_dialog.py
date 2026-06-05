from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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
    QVBoxLayout,
    QWidget,
)

from ..build_info import BUILD_COMMIT, BUILD_COMMIT_DISPLAY
from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.llm import (
    AimockSettings,
    LLMDialect,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
    PACKAGED_TRIAL_SECRET_SOURCE,
)
from ..services.ml.worker_settings import MLWorkerKind, MLWorkerSettingsService
from .ssh_worker_setup_wizard import SshWorkerSetupWizard


class SettingsDialog(QDialog):
    agent_settings_saved = Signal()
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
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._llm_service = llm_service
        self._llm_settings_service = llm_settings_service
        self._ml_worker_settings_service = ml_worker_settings_service
        self._provider_configs: list[LLMProviderConfig] = []
        self._loading_provider = False
        self._ssh_worker_wizard: SshWorkerSetupWizard | None = None

        self._language_label = QLabel()
        self._language_selector = QComboBox()
        self._open_logs_button = QPushButton()
        self._save_button = QPushButton()

        self._runtime_card = QFrame()
        self._runtime_card.setFrameShape(QFrame.StyledPanel)
        self._runtime_card_layout = QFormLayout(self._runtime_card)
        self._runtime_card_layout.setContentsMargins(12, 12, 12, 12)

        self._llm_card = QFrame()
        self._llm_card.setFrameShape(QFrame.StyledPanel)
        self._llm_card_layout = QFormLayout(self._llm_card)
        self._llm_card_layout.setContentsMargins(12, 12, 12, 12)

        self._aimock_card = QFrame()
        self._aimock_card.setFrameShape(QFrame.StyledPanel)
        self._aimock_card_layout = QFormLayout(self._aimock_card)
        self._aimock_card_layout.setContentsMargins(12, 12, 12, 12)

        self._ml_workers_card = QFrame()
        self._ml_workers_card.setFrameShape(QFrame.StyledPanel)
        self._ml_workers_card_layout = QFormLayout(self._ml_workers_card)
        self._ml_workers_card_layout.setContentsMargins(12, 12, 12, 12)

        self._app_home_label = QLabel()
        self._state_label = QLabel()
        self._artifacts_label = QLabel()
        self._database_label = QLabel()
        self._current_log_file_label = QLabel()
        self._build_commit_label = QLabel()

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

        self._aimock_title_label = QLabel()
        self._aimock_enabled_label = QLabel()
        self._aimock_base_url_label = QLabel()
        self._aimock_api_key_label = QLabel()

        self._ml_workers_title_label = QLabel()
        self._ml_workers_summary_label = QLabel()
        self._ml_workers_setup_button = QPushButton()

        self._app_home_value = QLabel(str(self._paths.home))
        self._state_value = QLabel(str(self._paths.state))
        self._artifacts_value = QLabel(str(self._paths.artifacts))
        self._database_value = QLabel(str(self._db_path))
        self._current_log_file_value = QLabel(str(self._log_path))
        self._build_commit_value = QLabel(BUILD_COMMIT_DISPLAY)
        if BUILD_COMMIT_DISPLAY != BUILD_COMMIT:
            self._build_commit_value.setToolTip(BUILD_COMMIT)

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

        self._aimock_enabled_checkbox = QCheckBox()
        self._aimock_base_url_input = QLineEdit()
        self._aimock_api_key_input = QLineEdit()
        self._aimock_api_key_input.setEchoMode(QLineEdit.Password)

        self.resize(760, 760)
        self._build_ui()
        self._wire_events()
        self._load_agent_settings()
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

        provider_selector_row = QHBoxLayout()
        provider_selector_row.setSpacing(8)
        provider_selector_row.addWidget(self._provider_selector, 1)
        provider_selector_row.addWidget(self._add_provider_button)
        provider_selector_row.addWidget(self._remove_provider_button)

        self._provider_dialect_selector.addItem("OpenAI-compatible", LLMDialect.OPENAI_COMPATIBLE.value)
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
        self._llm_card_layout.addRow(self._llm_default_model_label, self._llm_default_model_selector)
        self._llm_card_layout.addRow(self._llm_guard_model_label, self._llm_guard_model_selector)
        self._llm_card_layout.addRow(
            self._llm_thread_title_model_label,
            self._llm_thread_title_model_selector,
        )

        self._aimock_card_layout.addRow(self._aimock_title_label)
        self._aimock_card_layout.addRow(self._aimock_enabled_label, self._aimock_enabled_checkbox)
        self._aimock_card_layout.addRow(self._aimock_base_url_label, self._aimock_base_url_input)
        self._aimock_card_layout.addRow(self._aimock_api_key_label, self._aimock_api_key_input)
        self._aimock_card.setVisible(self._llm_settings_service.is_development())

        self._ml_workers_summary_label.setWordWrap(True)
        self._ml_workers_card_layout.addRow(self._ml_workers_title_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_summary_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_setup_button)

        scroll_layout.addWidget(self._llm_card)
        scroll_layout.addWidget(self._aimock_card)
        scroll_layout.addWidget(self._ml_workers_card)
        scroll_layout.addWidget(self._runtime_card)
        scroll_layout.addStretch(1)
        layout.addWidget(scroll, 1)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._open_logs_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._save_button)
        layout.addLayout(actions_layout)

    def _wire_events(self) -> None:
        self._open_logs_button.clicked.connect(self._open_logs_dir)
        self._language_selector.currentIndexChanged.connect(self._on_language_changed)
        self._save_button.clicked.connect(self._save_agent_settings)
        self._provider_selector.currentIndexChanged.connect(self._on_provider_changed)
        self._add_provider_button.clicked.connect(self._add_provider)
        self._remove_provider_button.clicked.connect(self._remove_provider)
        self._ml_workers_setup_button.clicked.connect(self._open_ssh_worker_wizard)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
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
        self._add_provider_button.setText(self.tr("Add"))
        self._remove_provider_button.setText(self.tr("Remove"))
        self._provider_dialect_selector.setItemText(0, self.tr("OpenAI-compatible"))
        self._refresh_provider_field_state()
        self._aimock_title_label.setText(self.tr("AIMock"))
        self._aimock_enabled_label.setText(self.tr("Use AIMock"))
        self._aimock_base_url_label.setText(self.tr("AIMock base URL"))
        self._aimock_api_key_label.setText(self.tr("AIMock API key"))
        self._ml_workers_title_label.setText(self.tr("ML workers"))
        self._ml_workers_setup_button.setText(self.tr("Add SSH worker..."))
        self._app_home_label.setText(self.tr("App home"))
        self._state_label.setText(self.tr("State"))
        self._artifacts_label.setText(self.tr("Artifacts"))
        self._database_label.setText(self.tr("Database"))
        self._current_log_file_label.setText(self.tr("Current log file"))
        self._build_commit_label.setText(self.tr("Build commit"))
        self._open_logs_button.setText(self.tr("Open log directory"))
        self._save_button.setText(self.tr("Save"))
        self._reload_language_options()
        self._refresh_model_selectors(
            default_key=self._llm_default_model_selector.currentData(),
            guard_key=self._llm_guard_model_selector.currentData(),
            title_key=self._llm_thread_title_model_selector.currentData(),
        )
        self._refresh_ml_worker_summary()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

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
        except Exception as exc:
            self._reload_language_options()
            QMessageBox.critical(
                self,
                self.tr("Language Switch Failed"),
                self.tr("Unable to switch the application language.\n\n{details}").format(details=str(exc)),
            )

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))

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
        self._aimock_enabled_checkbox.setChecked(settings.aimock.enabled)
        self._aimock_base_url_input.setText(settings.aimock.base_url)
        self._aimock_api_key_input.setText(settings.aimock.api_key)

    def _save_agent_settings(self) -> None:
        try:
            self._store_current_provider_fields()
            settings = LLMSettings(
                providers=self._provider_configs,
                default_fq_model_key=str(self._llm_default_model_selector.currentData() or ""),
                turn_completion_guard_fq_model_key=str(self._llm_guard_model_selector.currentData() or ""),
                thread_title_fq_model_key=str(self._llm_thread_title_model_selector.currentData() or ""),
                aimock=AimockSettings(
                    enabled=self._aimock_enabled_checkbox.isChecked(),
                    base_url=self._aimock_base_url_input.text().strip(),
                    api_key=self._aimock_api_key_input.text(),
                ),
            )
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        self._llm_settings_service.save(settings)
        self.agent_settings_saved.emit()

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
        provider = self._provider_configs[max(0, min(index, len(self._provider_configs) - 1))]
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
        self._loading_provider = False

    def _store_current_provider_fields(self) -> None:
        if self._loading_provider or not self._provider_configs:
            return
        index = max(0, self._provider_selector.currentIndex())
        if index >= len(self._provider_configs):
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
        self._reload_provider_selector(index)
        self._apply_provider_field_state(self._provider_configs[index])

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
