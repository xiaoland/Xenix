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
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.agent import AgentSettings, AgentSettingsService, AimockSettings


class SettingsDialog(QDialog):
    agent_settings_saved = Signal()

    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        agent_settings_service: AgentSettingsService,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._agent_settings_service = agent_settings_service

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

        self._app_home_label = QLabel()
        self._state_label = QLabel()
        self._artifacts_label = QLabel()
        self._database_label = QLabel()
        self._current_log_file_label = QLabel()
        self._llm_title_label = QLabel()
        self._llm_base_url_label = QLabel()
        self._llm_api_key_label = QLabel()
        self._llm_model_label = QLabel()
        self._llm_timeout_label = QLabel()
        self._llm_streaming_label = QLabel()
        self._aimock_title_label = QLabel()
        self._aimock_enabled_label = QLabel()
        self._aimock_base_url_label = QLabel()
        self._aimock_api_key_label = QLabel()

        self._app_home_value = QLabel(str(self._paths.home))
        self._state_value = QLabel(str(self._paths.state))
        self._artifacts_value = QLabel(str(self._paths.artifacts))
        self._database_value = QLabel(str(self._db_path))
        self._current_log_file_value = QLabel(str(self._log_path))
        self._llm_base_url_input = QLineEdit()
        self._llm_api_key_input = QLineEdit()
        self._llm_model_input = QLineEdit()
        self._llm_timeout_input = QSpinBox()
        self._llm_streaming_checkbox = QCheckBox()
        self._aimock_enabled_checkbox = QCheckBox()
        self._aimock_base_url_input = QLineEdit()
        self._aimock_api_key_input = QLineEdit()

        self.resize(760, 680)
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

        for value_label in (
            self._app_home_value,
            self._state_value,
            self._artifacts_value,
            self._database_value,
            self._current_log_file_value,
        ):
            value_label.setWordWrap(True)

        self._runtime_card_layout.addRow(self._app_home_label, self._app_home_value)
        self._runtime_card_layout.addRow(self._state_label, self._state_value)
        self._runtime_card_layout.addRow(self._artifacts_label, self._artifacts_value)
        self._runtime_card_layout.addRow(self._database_label, self._database_value)
        self._runtime_card_layout.addRow(self._current_log_file_label, self._current_log_file_value)

        self._llm_api_key_input.setEchoMode(QLineEdit.Password)
        self._aimock_api_key_input.setEchoMode(QLineEdit.Password)
        self._llm_timeout_input.setRange(1, 3600)
        self._llm_timeout_input.setSuffix(" s")
        self._llm_card_layout.addRow(self._llm_title_label)
        self._llm_card_layout.addRow(self._llm_base_url_label, self._llm_base_url_input)
        self._llm_card_layout.addRow(self._llm_api_key_label, self._llm_api_key_input)
        self._llm_card_layout.addRow(self._llm_model_label, self._llm_model_input)
        self._llm_card_layout.addRow(self._llm_timeout_label, self._llm_timeout_input)
        self._llm_card_layout.addRow(self._llm_streaming_label, self._llm_streaming_checkbox)

        self._aimock_card_layout.addRow(self._aimock_title_label)
        self._aimock_card_layout.addRow(self._aimock_enabled_label, self._aimock_enabled_checkbox)
        self._aimock_card_layout.addRow(self._aimock_base_url_label, self._aimock_base_url_input)
        self._aimock_card_layout.addRow(self._aimock_api_key_label, self._aimock_api_key_input)
        self._aimock_card.setVisible(self._agent_settings_service.is_development())

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._open_logs_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._save_button)

        layout.addWidget(self._llm_card)
        layout.addWidget(self._aimock_card)
        layout.addWidget(self._runtime_card)
        layout.addLayout(actions_layout)
        layout.addStretch(1)

    def _wire_events(self) -> None:
        self._open_logs_button.clicked.connect(self._open_logs_dir)
        self._language_selector.currentIndexChanged.connect(self._on_language_changed)
        self._save_button.clicked.connect(self._save_agent_settings)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
        self._llm_title_label.setText(self.tr("LLM provider"))
        self._llm_base_url_label.setText(self.tr("Base URL"))
        self._llm_api_key_label.setText(self.tr("API key"))
        self._llm_model_label.setText(self.tr("Model"))
        self._llm_timeout_label.setText(self.tr("Timeout"))
        self._llm_streaming_label.setText(self.tr("Streaming"))
        self._aimock_title_label.setText(self.tr("AIMock"))
        self._aimock_enabled_label.setText(self.tr("Use AIMock"))
        self._aimock_base_url_label.setText(self.tr("AIMock base URL"))
        self._aimock_api_key_label.setText(self.tr("AIMock API key"))
        self._app_home_label.setText(self.tr("App home"))
        self._state_label.setText(self.tr("State"))
        self._artifacts_label.setText(self.tr("Artifacts"))
        self._database_label.setText(self.tr("Database"))
        self._current_log_file_label.setText(self.tr("Current log file"))
        self._open_logs_button.setText(self.tr("Open log directory"))
        self._save_button.setText(self.tr("Save"))
        self._reload_language_options()

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
        settings = self._agent_settings_service.load()
        self._llm_base_url_input.setText(settings.base_url)
        self._llm_api_key_input.setText(settings.api_key)
        self._llm_model_input.setText(settings.model)
        self._llm_timeout_input.setValue(settings.timeout_seconds)
        self._llm_streaming_checkbox.setChecked(settings.streaming_enabled)
        self._aimock_enabled_checkbox.setChecked(settings.aimock.enabled)
        self._aimock_base_url_input.setText(settings.aimock.base_url)
        self._aimock_api_key_input.setText(settings.aimock.api_key)

    def _save_agent_settings(self) -> None:
        settings = AgentSettings(
            base_url=self._llm_base_url_input.text().strip(),
            api_key=self._llm_api_key_input.text(),
            model=self._llm_model_input.text().strip(),
            timeout_seconds=self._llm_timeout_input.value(),
            streaming_enabled=self._llm_streaming_checkbox.isChecked(),
            aimock=AimockSettings(
                enabled=self._aimock_enabled_checkbox.isChecked(),
                base_url=self._aimock_base_url_input.text().strip(),
                api_key=self._aimock_api_key_input.text(),
            ),
        )
        self._agent_settings_service.save(settings)
        self.agent_settings_saved.emit()
