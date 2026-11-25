from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QSpinBox, QWidget

from ...services.ai_providers import AIModelOption
from ...services.llm.service import ConversationSettings
from ..semantic_identity import identify
from .model_selection import replace_model_options


class ConversationSettingsEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._options: list[AIModelOption] = []
        self._default_model_selector = QComboBox()
        self._guard_model_selector = QComboBox()
        self._thread_title_model_selector = QComboBox()
        self._retry_attempts_input = QSpinBox()
        self._retry_attempts_input.setRange(1, 20)
        self._default_model_label = QLabel()
        self._guard_model_label = QLabel()
        self._thread_title_model_label = QLabel()
        self._retry_attempts_label = QLabel()
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for label, widget, semantic_id in (
            (self._default_model_label, self._default_model_selector, "settings.llm.default-model"),
            (self._guard_model_label, self._guard_model_selector, "settings.llm.turn-guard-model"),
            (self._thread_title_model_label, self._thread_title_model_selector, "settings.llm.thread-title-model"),
            (self._retry_attempts_label, self._retry_attempts_input, "settings.llm.retry-attempts"),
        ):
            identify(widget, semantic_id)
            layout.addRow(label, widget)
        self.retranslate_ui()

    def load_settings(self, settings: ConversationSettings) -> None:
        self._replace_choices(settings)
        self._retry_attempts_input.setValue(settings.retry_attempts)

    def current_settings(self) -> ConversationSettings:
        return ConversationSettings(
            default_fq_model_key=self._default_model_selector.currentData() or "",
            turn_completion_guard_fq_model_key=self._guard_model_selector.currentData() or "",
            thread_title_fq_model_key=self._thread_title_model_selector.currentData() or "",
            retry_attempts=self._retry_attempts_input.value(),
        )

    def set_model_options(self, options: list[AIModelOption]) -> None:
        selected = self.current_settings()
        self._options = options
        self._replace_choices(selected)

    def _replace_choices(self, settings: ConversationSettings) -> None:
        no_model = QCoreApplication.translate("SettingsDialog", "None")
        replace_model_options(self._default_model_selector, self._options, settings.default_fq_model_key)
        replace_model_options(
            self._guard_model_selector, self._options, settings.turn_completion_guard_fq_model_key,
            blank_label=no_model,
        )
        replace_model_options(
            self._thread_title_model_selector, self._options, settings.thread_title_fq_model_key,
            blank_label=no_model,
        )

    def retranslate_ui(self) -> None:
        self._default_model_label.setText(QCoreApplication.translate("SettingsDialog", "Default model"))
        self._guard_model_label.setText(QCoreApplication.translate("SettingsDialog", "Turn guard model"))
        self._thread_title_model_label.setText(QCoreApplication.translate("SettingsDialog", "Thread title model"))
        self._retry_attempts_label.setText(QCoreApplication.translate("SettingsDialog", "LLM retry attempts"))
        self._replace_choices(self.current_settings())

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
