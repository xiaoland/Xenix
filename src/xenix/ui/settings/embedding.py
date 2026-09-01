"""Knowledge-tab embedding provider card."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from ...services.embedding_service import EmbeddingSettings
from ..semantic_identity import identify


class EmbeddingSettingsCard(QFrame):
    """Draft editor for the embedding provider, isolated from the save flow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._snapshot = EmbeddingSettings()

        self._title_label = QLabel()
        self._enabled_label = QLabel()
        self._base_url_label = QLabel()
        self._api_key_label = QLabel()
        self._model_label = QLabel()
        self._dimensions_label = QLabel()
        self._batch_size_label = QLabel()
        self._timeout_label = QLabel()

        self._enabled_checkbox = QCheckBox()
        self._base_url_input = QLineEdit()
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._model_input = QLineEdit()
        self._dimensions_input = QSpinBox()
        self._dimensions_input.setRange(0, 65_536)
        self._batch_size_input = QSpinBox()
        self._batch_size_input.setRange(1, 2_048)
        self._timeout_input = QSpinBox()
        self._timeout_input.setRange(1, 3_600)
        self._timeout_input.setSuffix(" s")

        identify(self._enabled_checkbox, "settings.embedding.enabled")
        identify(self._base_url_input, "settings.embedding.base-url")
        identify(self._api_key_input, "settings.embedding.api-key")
        identify(self._model_input, "settings.embedding.model")
        identify(self._dimensions_input, "settings.embedding.dimensions")
        identify(self._batch_size_input, "settings.embedding.batch-size")
        identify(self._timeout_input, "settings.embedding.timeout")

        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addRow(self._title_label)
        layout.addRow(self._enabled_label, self._enabled_checkbox)
        layout.addRow(self._base_url_label, self._base_url_input)
        layout.addRow(self._api_key_label, self._api_key_input)
        layout.addRow(self._model_label, self._model_input)
        layout.addRow(self._dimensions_label, self._dimensions_input)
        layout.addRow(self._batch_size_label, self._batch_size_input)
        layout.addRow(self._timeout_label, self._timeout_input)
        self.retranslate_ui()

    @property
    def snapshot(self) -> EmbeddingSettings:
        return self._snapshot

    def load_settings(self, settings: EmbeddingSettings) -> None:
        self._snapshot = settings.model_copy(deep=True)
        self._enabled_checkbox.setChecked(settings.enabled)
        self._base_url_input.setText(settings.base_url)
        self._api_key_input.setText(settings.api_key)
        self._model_input.setText(settings.model)
        self._dimensions_input.setValue(settings.dimensions or 0)
        self._batch_size_input.setValue(settings.batch_size)
        self._timeout_input.setValue(settings.timeout_seconds)

    def current_settings(self) -> EmbeddingSettings:
        dimensions = self._dimensions_input.value()
        current = self._snapshot
        return EmbeddingSettings(
            schema_version=current.schema_version,
            enabled=self._enabled_checkbox.isChecked(),
            provider_key=current.provider_key,
            dialect=current.dialect,
            base_url=self._base_url_input.text(),
            api_key=self._api_key_input.text(),
            model=self._model_input.text(),
            dimensions=dimensions or None,
            batch_size=self._batch_size_input.value(),
            timeout_seconds=self._timeout_input.value(),
        )

    def retranslate_ui(self) -> None:
        self._title_label.setText(QCoreApplication.translate("SettingsDialog", "Embedding provider"))
        self._enabled_label.setText(QCoreApplication.translate("SettingsDialog", "Enabled"))
        self._base_url_label.setText(QCoreApplication.translate("SettingsDialog", "Base URL"))
        self._api_key_label.setText(QCoreApplication.translate("SettingsDialog", "API key"))
        self._model_label.setText(QCoreApplication.translate("SettingsDialog", "Model"))
        self._dimensions_label.setText(QCoreApplication.translate("SettingsDialog", "Dimensions"))
        self._dimensions_input.setSpecialValueText(
            QCoreApplication.translate("SettingsDialog", "Provider default (0)")
        )
        self._batch_size_label.setText(QCoreApplication.translate("SettingsDialog", "Batch size"))
        self._timeout_label.setText(QCoreApplication.translate("SettingsDialog", "Timeout"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
