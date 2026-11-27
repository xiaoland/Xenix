from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox, QWidget

from ...services.ai_providers import AIModelOption
from ...services.ai_settings import KnowledgeEmbeddingSettings
from ...services.embedding_service import MAX_EMBEDDING_DIMENSIONS
from ..semantic_identity import identify
from .model_selection import replace_model_options


class EmbeddingSettings(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._options: list[AIModelOption] = []
        self._title_label = QLabel()
        self._enabled_label = QLabel()
        self._model_label = QLabel()
        self._dimensions_label = QLabel()
        self._batch_size_label = QLabel()
        self._enabled_checkbox = QCheckBox()
        self._model_selector = QComboBox()
        self._dimensions_input = QSpinBox()
        self._dimensions_input.setRange(0, MAX_EMBEDDING_DIMENSIONS)
        self._batch_size_input = QSpinBox()
        self._batch_size_input.setRange(1, 2_048)

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(self._title_label)
        for label, widget, semantic_id in (
            (self._model_label, self._model_selector, "settings.embedding.model"),
            (self._enabled_label, self._enabled_checkbox, "settings.embedding.enabled"),
            (self._dimensions_label, self._dimensions_input, "settings.embedding.dimensions"),
            (self._batch_size_label, self._batch_size_input, "settings.embedding.batch-size"),
        ):
            identify(widget, semantic_id)
            layout.addRow(label, widget)
        self.load_settings(KnowledgeEmbeddingSettings())
        self.retranslate_ui()

    def load_settings(self, settings: KnowledgeEmbeddingSettings) -> None:
        self._replace_choices(settings.fq_model_key)
        self._enabled_checkbox.setChecked(settings.enabled)
        self._dimensions_input.setValue(settings.dimensions or 0)
        self._batch_size_input.setValue(settings.batch_size)

    def current_settings(self) -> KnowledgeEmbeddingSettings:
        return KnowledgeEmbeddingSettings(
            fq_model_key=self._model_selector.currentData() or "",
            enabled=self._enabled_checkbox.isChecked(),
            dimensions=self._dimensions_input.value() or None,
            batch_size=self._batch_size_input.value(),
        )

    def set_model_options(self, options: list[AIModelOption]) -> None:
        self._options = options
        self._replace_choices(self._model_selector.currentData() or "")

    def _replace_choices(self, selection: str) -> None:
        replace_model_options(
            self._model_selector, self._options, selection,
            blank_label=QCoreApplication.translate("SettingsDialog", "None"),
        )

    def retranslate_ui(self) -> None:
        self._title_label.setText(QCoreApplication.translate("SettingsDialog", "Text vectors"))
        self._enabled_label.setText(QCoreApplication.translate("SettingsDialog", "Enabled"))
        self._model_label.setText(QCoreApplication.translate("SettingsDialog", "Embedding model"))
        self._dimensions_label.setText(QCoreApplication.translate("SettingsDialog", "Dimensions"))
        self._dimensions_input.setSpecialValueText(
            QCoreApplication.translate("SettingsDialog", "Provider default (0)")
        )
        self._batch_size_label.setText(QCoreApplication.translate("SettingsDialog", "Batch size"))
        self._replace_choices(self._model_selector.currentData() or "")

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
