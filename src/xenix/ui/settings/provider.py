from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...services.llm import (
    LLMDialect,
    LLMModelOption,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    PACKAGED_TRIAL_SECRET_SOURCE,
)
from ..semantic_identity import identify


class ProviderSettingsEditor(QWidget):
    """AI-tab provider draft editor, including its dependent global model choices."""

    def __init__(self, settings: LLMSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider_configs: list[LLMProviderConfig] = []
        self._loading_provider = False
        self._active_provider_index = 0

        self._global_models_card = self._card()
        self._llm_card = self._card()
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
        self._provider_selector = QComboBox()
        self._add_provider_button = QPushButton()
        self._remove_provider_button = QPushButton()
        self._provider_key_input = QLineEdit()
        self._provider_name_input = QLineEdit()
        self._provider_dialect_selector = QComboBox()
        self._provider_base_url_input = QLineEdit()
        self._provider_api_key_input = QLineEdit()
        self._provider_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
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
        self._assign_semantic_identities()
        self._build_ui()
        self._wire_events()
        self.load_settings(settings)
        self.retranslate_ui()

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        return card

    def _assign_semantic_identities(self) -> None:
        for widget, semantic_id in (
            (self._provider_selector, "settings.llm.provider.selector"),
            (self._add_provider_button, "settings.llm.provider.add"),
            (self._remove_provider_button, "settings.llm.provider.remove"),
            (self._provider_key_input, "settings.llm.provider.key"),
            (self._provider_name_input, "settings.llm.provider.name"),
            (self._provider_dialect_selector, "settings.llm.provider.dialect"),
            (self._provider_base_url_input, "settings.llm.provider.base-url"),
            (self._provider_api_key_input, "settings.llm.provider.api-key"),
            (self._provider_models_input, "settings.llm.provider.models"),
            (self._provider_timeout_input, "settings.llm.provider.timeout"),
            (self._provider_streaming_checkbox, "settings.llm.provider.streaming"),
            (self._llm_default_model_selector, "settings.llm.default-model"),
            (self._llm_guard_model_selector, "settings.llm.turn-guard-model"),
            (self._llm_thread_title_model_selector, "settings.llm.thread-title-model"),
            (self._llm_retry_attempts_input, "settings.llm.retry-attempts"),
        ):
            identify(widget, semantic_id)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        global_layout = QFormLayout(self._global_models_card)
        global_layout.setContentsMargins(12, 12, 12, 12)
        global_layout.addRow(self._global_models_title_label)
        global_layout.addRow(self._llm_default_model_label, self._llm_default_model_selector)
        global_layout.addRow(self._llm_guard_model_label, self._llm_guard_model_selector)
        global_layout.addRow(self._llm_thread_title_model_label, self._llm_thread_title_model_selector)
        global_layout.addRow(self._llm_retry_attempts_label, self._llm_retry_attempts_input)
        provider_layout = QFormLayout(self._llm_card)
        provider_layout.setContentsMargins(12, 12, 12, 12)
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        selector_row.addWidget(self._provider_selector, 1)
        selector_row.addWidget(self._add_provider_button)
        selector_row.addWidget(self._remove_provider_button)
        self._provider_dialect_selector.addItem("OpenAI-compatible", LLMDialect.OPENAI_COMPATIBLE.value)
        provider_layout.addRow(self._llm_title_label)
        provider_layout.addRow(self._provider_selector_label, selector_row)
        provider_layout.addRow(self._provider_key_label, self._provider_key_input)
        provider_layout.addRow(self._provider_name_label, self._provider_name_input)
        provider_layout.addRow(self._provider_dialect_label, self._provider_dialect_selector)
        provider_layout.addRow(self._provider_base_url_label, self._provider_base_url_input)
        provider_layout.addRow(self._provider_api_key_label, self._provider_api_key_input)
        provider_layout.addRow(self._provider_models_label, self._provider_models_input)
        provider_layout.addRow(self._provider_timeout_label, self._provider_timeout_input)
        provider_layout.addRow(self._provider_streaming_label, self._provider_streaming_checkbox)
        layout.addWidget(self._global_models_card)
        layout.addWidget(self._llm_card)
        layout.addStretch(1)

    def _wire_events(self) -> None:
        self._provider_selector.currentIndexChanged.connect(self._on_provider_changed)
        self._add_provider_button.clicked.connect(self._add_provider)
        self._remove_provider_button.clicked.connect(self._remove_provider)

    def retranslate_ui(self) -> None:
        self._global_models_title_label.setText(QCoreApplication.translate("SettingsDialog", "Global models"))
        self._llm_title_label.setText(QCoreApplication.translate("SettingsDialog", "LLM providers"))
        self._provider_selector_label.setText(QCoreApplication.translate("SettingsDialog", "Provider"))
        self._provider_key_label.setText(QCoreApplication.translate("SettingsDialog", "Provider key"))
        self._provider_name_label.setText(QCoreApplication.translate("SettingsDialog", "Provider name"))
        self._provider_dialect_label.setText(QCoreApplication.translate("SettingsDialog", "Dialect"))
        self._provider_base_url_label.setText(QCoreApplication.translate("SettingsDialog", "Base URL"))
        self._provider_api_key_label.setText(QCoreApplication.translate("SettingsDialog", "API key"))
        self._provider_models_label.setText(QCoreApplication.translate("SettingsDialog", "Models"))
        self._provider_timeout_label.setText(QCoreApplication.translate("SettingsDialog", "Timeout"))
        self._provider_streaming_label.setText(QCoreApplication.translate("SettingsDialog", "Streaming"))
        self._llm_default_model_label.setText(QCoreApplication.translate("SettingsDialog", "Default model"))
        self._llm_guard_model_label.setText(QCoreApplication.translate("SettingsDialog", "Turn guard model"))
        self._llm_thread_title_model_label.setText(QCoreApplication.translate("SettingsDialog", "Thread title model"))
        self._llm_retry_attempts_label.setText(QCoreApplication.translate("SettingsDialog", "LLM retry attempts"))
        self._add_provider_button.setText(QCoreApplication.translate("SettingsDialog", "Add"))
        self._remove_provider_button.setText(QCoreApplication.translate("SettingsDialog", "Remove"))
        self._provider_dialect_selector.setItemText(
            0, QCoreApplication.translate("SettingsDialog", "OpenAI-compatible")
        )
        self._refresh_provider_field_state()
        self._refresh_model_selectors(
            default_key=self._llm_default_model_selector.currentData(),
            guard_key=self._llm_guard_model_selector.currentData(),
            title_key=self._llm_thread_title_model_selector.currentData(),
        )

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def load_settings(self, settings: LLMSettings) -> None:
        self._provider_configs = [provider.model_copy(deep=True) for provider in settings.providers]
        self._reload_provider_selector(0)
        self._load_provider_fields(0)
        self._refresh_model_selectors(
            default_key=settings.default_fq_model_key,
            guard_key=settings.turn_completion_guard_fq_model_key,
            title_key=settings.thread_title_fq_model_key,
        )
        self._llm_retry_attempts_input.setValue(settings.retry_attempts)

    def current_settings(self) -> LLMSettings:
        self._store_current_provider_fields()
        return LLMSettings(
            providers=self._provider_configs,
            default_fq_model_key=str(self._llm_default_model_selector.currentData() or ""),
            turn_completion_guard_fq_model_key=str(self._llm_guard_model_selector.currentData() or ""),
            thread_title_fq_model_key=str(self._llm_thread_title_model_selector.currentData() or ""),
            retry_attempts=self._llm_retry_attempts_input.value(),
        )

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
            QMessageBox.warning(
                self,
                QCoreApplication.translate("SettingsDialog", "Settings"),
                str(exc),
            )
            return
        existing = {provider.key for provider in self._provider_configs}
        index = 2
        while f"provider{index}" in existing:
            index += 1
        self._provider_configs.append(
            LLMProviderConfig(key=f"provider{index}", display_name=f"Provider {index}", models=["gpt-4o-mini"])
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
            self._provider_selector.addItem(provider.display_name or provider.key, provider.key)
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
        if not 0 <= index < len(self._provider_configs):
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
        provider = self._provider_configs[index]
        self._provider_selector.setItemText(index, provider.display_name or provider.key)
        self._provider_selector.setItemData(index, provider.key)
        if index == self._provider_selector.currentIndex():
            self._apply_provider_field_state(provider)

    def _refresh_provider_field_state(self) -> None:
        index = self._provider_selector.currentIndex()
        if 0 <= index < len(self._provider_configs):
            self._apply_provider_field_state(self._provider_configs[index])

    def _apply_provider_field_state(self, provider: LLMProviderConfig) -> None:
        packaged_trial = self._is_packaged_trial_provider(provider)
        self._provider_base_url_input.setReadOnly(packaged_trial)
        self._provider_api_key_input.setReadOnly(packaged_trial)
        self._provider_api_key_input.setPlaceholderText(
            QCoreApplication.translate("SettingsDialog", "Built into packaged app") if packaged_trial else ""
        )

    @staticmethod
    def _is_packaged_trial_provider(provider: LLMProviderConfig) -> bool:
        return provider.dialect_config.get("secret_source") == PACKAGED_TRIAL_SECRET_SOURCE

    def _refresh_model_selectors(
        self, *, default_key: object | None = None, guard_key: object | None = None, title_key: object | None = None
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
            self._llm_guard_model_selector, options, selected_key=str(guard_key or ""), include_blank=True
        )
        self._replace_model_selector_items(
            self._llm_thread_title_model_selector, options, selected_key=str(title_key or ""), include_blank=True
        )

    def _replace_model_selector_items(
        self, selector: QComboBox, options: list[LLMModelOption], *, selected_key: str, include_blank: bool
    ) -> None:
        selector.blockSignals(True)
        selector.clear()
        if include_blank:
            selector.addItem(QCoreApplication.translate("SettingsDialog", "None"), "")
        for option in options:
            selector.addItem(option.label, option.fq_model_key)
        selector.setCurrentIndex(max(0, selector.findData(selected_key)))
        selector.blockSignals(False)

    def _model_lines(self) -> list[str]:
        return [
            line.strip()
            for line in self._provider_models_input.toPlainText().replace(",", "\n").splitlines()
            if line.strip()
        ]
