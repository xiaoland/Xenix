from __future__ import annotations

import logging

from pydantic import ValidationError as PydanticValidationError
from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
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

from ...services.ai_providers import AIProtocol, AIProviderConfig
from ..semantic_identity import identify
from ._card import Card


class ProviderSettingsEditor(QWidget):
    """Edit provider connections and the two model lists they publish."""

    providers_changed = Signal(list)

    def __init__(self, providers: list[AIProviderConfig], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider_configs: list[AIProviderConfig] = []
        self._loading_provider = False
        self._active_provider_index = 0

        self._llm_card = Card()
        self._llm_title_label = QLabel()
        self._provider_selector_label = QLabel()
        self._provider_key_label = QLabel()
        self._provider_name_label = QLabel()
        self._provider_dialect_label = QLabel()
        self._provider_base_url_label = QLabel()
        self._provider_api_key_label = QLabel()
        self._provider_models_label = QLabel()
        self._embedding_models_label = QLabel()
        self._provider_timeout_label = QLabel()
        self._provider_streaming_label = QLabel()
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
        self._embedding_models_input = QPlainTextEdit()
        self._embedding_models_input.setFixedHeight(82)
        self._provider_timeout_input = QSpinBox()
        self._provider_timeout_input.setRange(1, 3600)
        self._provider_timeout_input.setSuffix(" s")
        self._provider_streaming_checkbox = QCheckBox()
        self._assign_semantic_identities()
        self._build_ui()
        self._wire_events()
        self.load_providers(providers)
        self.retranslate_ui()

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
            (self._embedding_models_input, "settings.ai.provider.embedding-models"),
            (self._provider_timeout_input, "settings.llm.provider.timeout"),
            (self._provider_streaming_checkbox, "settings.llm.provider.streaming"),
        ):
            identify(widget, semantic_id)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        provider_content = QWidget()
        provider_layout = QFormLayout(provider_content)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        selector_row.addWidget(self._provider_selector, 1)
        selector_row.addWidget(self._add_provider_button)
        selector_row.addWidget(self._remove_provider_button)
        self._provider_dialect_selector.addItem("OpenAI-compatible", AIProtocol.OPENAI_COMPATIBLE.value)
        provider_layout.addRow(self._llm_title_label)
        provider_layout.addRow(self._provider_selector_label, selector_row)
        provider_layout.addRow(self._provider_key_label, self._provider_key_input)
        provider_layout.addRow(self._provider_name_label, self._provider_name_input)
        provider_layout.addRow(self._provider_dialect_label, self._provider_dialect_selector)
        provider_layout.addRow(self._provider_base_url_label, self._provider_base_url_input)
        provider_layout.addRow(self._provider_api_key_label, self._provider_api_key_input)
        provider_layout.addRow(self._provider_models_label, self._provider_models_input)
        provider_layout.addRow(self._embedding_models_label, self._embedding_models_input)
        provider_layout.addRow(self._provider_timeout_label, self._provider_timeout_input)
        provider_layout.addRow(self._provider_streaming_label, self._provider_streaming_checkbox)
        self._llm_card.set_content(provider_content)

        layout.addWidget(self._llm_card)
        layout.addStretch(1)

    def _wire_events(self) -> None:
        self._provider_selector.currentIndexChanged.connect(self._on_provider_changed)
        self._add_provider_button.clicked.connect(self._add_provider)
        self._remove_provider_button.clicked.connect(self._remove_provider)
        self._provider_models_input.textChanged.connect(self._on_provider_identity_changed)
        self._embedding_models_input.textChanged.connect(self._on_provider_identity_changed)
        self._provider_key_input.editingFinished.connect(self._on_provider_identity_changed)
        self._provider_name_input.editingFinished.connect(self._on_provider_identity_changed)

    def retranslate_ui(self) -> None:
        self._llm_title_label.setText(QCoreApplication.translate("SettingsDialog", "AI providers"))
        self._provider_selector_label.setText(QCoreApplication.translate("SettingsDialog", "Provider"))
        self._provider_key_label.setText(QCoreApplication.translate("SettingsDialog", "Provider key"))
        self._provider_name_label.setText(QCoreApplication.translate("SettingsDialog", "Provider name"))
        self._provider_dialect_label.setText(QCoreApplication.translate("SettingsDialog", "Protocol"))
        self._provider_base_url_label.setText(QCoreApplication.translate("SettingsDialog", "Base URL"))
        self._provider_api_key_label.setText(QCoreApplication.translate("SettingsDialog", "API key"))
        self._provider_models_label.setText(QCoreApplication.translate("SettingsDialog", "Chat models"))
        self._embedding_models_label.setText(QCoreApplication.translate("SettingsDialog", "Embedding models"))
        model_hint = QCoreApplication.translate("SettingsDialog", "One model ID per line")
        self._provider_models_input.setPlaceholderText(model_hint)
        self._embedding_models_input.setPlaceholderText(model_hint)
        self._provider_timeout_label.setText(QCoreApplication.translate("SettingsDialog", "Timeout"))
        self._provider_streaming_label.setText(QCoreApplication.translate("SettingsDialog", "Streaming"))
        self._add_provider_button.setText(QCoreApplication.translate("SettingsDialog", "Add"))
        self._remove_provider_button.setText(QCoreApplication.translate("SettingsDialog", "Remove"))
        self._provider_dialect_selector.setItemText(
            0, QCoreApplication.translate("SettingsDialog", "OpenAI-compatible")
        )

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def load_providers(self, providers: list[AIProviderConfig]) -> None:
        self._provider_configs = [provider.model_copy(deep=True) for provider in providers]
        self._reload_provider_selector(0)
        self._load_provider_fields(0)
        self.providers_changed.emit(self._provider_configs)

    def current_providers(self) -> list[AIProviderConfig]:
        self._store_current_provider_fields()
        return self._provider_configs

    def _on_provider_changed(self, index: int) -> None:
        if self._loading_provider:
            return
        try:
            self._store_current_provider_fields()
        except Exception as exc:
            logging.getLogger(__name__).exception("UI operation failed: %s", exc)
            self._revert_provider_selection()
            QMessageBox.warning(
                self,
                QCoreApplication.translate("SettingsDialog", "Settings"),
                str(exc),
            )
            return
        self._load_provider_fields(index)
        self.providers_changed.emit(self._provider_configs)

    def _revert_provider_selection(self) -> None:
        """Return the selector to the currently loaded provider after a failed switch."""

        self._loading_provider = True
        try:
            self._provider_selector.setCurrentIndex(self._active_provider_index)
        finally:
            self._loading_provider = False

    def _add_provider(self) -> None:
        try:
            self._store_current_provider_fields()
        except Exception as exc:
            logging.getLogger(__name__).exception("UI operation failed: %s", exc)
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
            AIProviderConfig(key=f"provider{index}", display_name=f"Provider {index}", models=["gpt-4o-mini"])
        )
        self._reload_provider_selector(len(self._provider_configs) - 1)
        self._load_provider_fields(len(self._provider_configs) - 1)
        self.providers_changed.emit(self._provider_configs)

    def _remove_provider(self) -> None:
        if len(self._provider_configs) <= 1:
            return
        index = max(0, self._provider_selector.currentIndex())
        self._provider_configs.pop(index)
        next_index = min(index, len(self._provider_configs) - 1)
        self._reload_provider_selector(next_index)
        self._load_provider_fields(next_index)
        self.providers_changed.emit(self._provider_configs)

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
        self._embedding_models_input.setPlainText("\n".join(provider.embedding_models))
        self._provider_timeout_input.setValue(provider.timeout_seconds)
        self._provider_streaming_checkbox.setChecked(provider.streaming_enabled)
        self._active_provider_index = provider_index
        self._loading_provider = False

    def _store_current_provider_fields(self) -> None:
        if self._loading_provider or not self._provider_configs:
            return
        index = self._active_provider_index
        if not 0 <= index < len(self._provider_configs):
            return
        current = self._provider_configs[index]
        self._provider_configs[index] = AIProviderConfig(
            key=self._provider_key_input.text().strip(),
            display_name=self._provider_name_input.text().strip(),
            dialect=AIProtocol(str(self._provider_dialect_selector.currentData())),
            base_url=self._provider_base_url_input.text().strip(),
            api_key=self._provider_api_key_input.text(),
            models=self._model_lines(self._provider_models_input),
            embedding_models=self._model_lines(self._embedding_models_input),
            timeout_seconds=self._provider_timeout_input.value(),
            streaming_enabled=self._provider_streaming_checkbox.isChecked(),
            dialect_config=current.dialect_config,
            embedding_profile_key=current.embedding_profile_key,
        )
        provider = self._provider_configs[index]
        self._provider_selector.setItemText(index, provider.display_name or provider.key)
        self._provider_selector.setItemData(index, provider.key)

    def _on_provider_identity_changed(self) -> None:
        if self._loading_provider:
            return
        try:
            self._store_current_provider_fields()
        except PydanticValidationError:
            return
        keys = {provider.key for provider in self._provider_configs}
        if len(keys) == len(self._provider_configs):
            self.providers_changed.emit(self._provider_configs)

    @staticmethod
    def _model_lines(editor: QPlainTextEdit) -> list[str]:
        return editor.toPlainText().replace(",", "\n").splitlines()
