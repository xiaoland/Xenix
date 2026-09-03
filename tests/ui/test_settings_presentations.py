from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from xenix.services.llm import (
    LLMProviderConfig,
    LLMSettings,
    PACKAGED_TRIAL_SECRET_SOURCE,
)
from xenix.services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from xenix.ui.settings.ocr import OcrSettings
from xenix.ui.settings.provider import ProviderSettingsEditor


def test_provider_editor_round_trips_provider_and_global_choices(qapp: QApplication, qtbot: QtBot) -> None:
    editor = ProviderSettingsEditor(
        LLMSettings(providers=[LLMProviderConfig(key="one", display_name="One", models=["small"])]),
    )
    qtbot.addWidget(editor)
    editor._add_provider()
    editor._provider_name_input.setText("Two")
    editor._provider_models_input.setPlainText("large\nvision")
    settings = editor.current_settings()
    assert [provider.display_name for provider in settings.providers] == ["One", "Two"]
    assert settings.providers[1].models == ["large", "vision"]
    editor.load_settings(settings)
    assert editor._provider_selector.count() == 2


def test_add_provider_preserves_global_model_choices(qapp: QApplication, qtbot: QtBot) -> None:
    editor = ProviderSettingsEditor(
        LLMSettings(
            providers=[LLMProviderConfig(key="one", display_name="One", models=["a", "b"])],
            default_fq_model_key="one/b",
            turn_completion_guard_fq_model_key="one/b",
            thread_title_fq_model_key="one/b",
        )
    )
    qtbot.addWidget(editor)
    assert editor._llm_default_model_selector.currentData() == "one/b"
    assert editor._llm_guard_model_selector.currentData() == "one/b"
    assert editor._llm_thread_title_model_selector.currentData() == "one/b"

    editor._add_provider()

    assert editor._llm_default_model_selector.currentData() == "one/b"
    assert editor._llm_guard_model_selector.currentData() == "one/b"
    assert editor._llm_thread_title_model_selector.currentData() == "one/b"


def test_editing_models_refreshes_global_model_selectors(qapp: QApplication, qtbot: QtBot) -> None:
    editor = ProviderSettingsEditor(
        LLMSettings(
            providers=[LLMProviderConfig(key="one", display_name="One", models=["a", "b"])],
            default_fq_model_key="one/a",
        )
    )
    qtbot.addWidget(editor)
    assert editor._llm_default_model_selector.count() == 2

    editor._provider_models_input.setPlainText("a\nb\nc")

    assert editor._llm_default_model_selector.count() == 3
    assert [editor._llm_default_model_selector.itemData(i) for i in range(3)] == [
        "one/a",
        "one/b",
        "one/c",
    ]


def test_provider_switch_with_invalid_draft_warns_and_preserves_input(
    qapp: QApplication,
    qtbot: QtBot,
    monkeypatch,
) -> None:
    editor = ProviderSettingsEditor(
        LLMSettings(
            providers=[
                LLMProviderConfig(key="one", display_name="One", models=["a"]),
                LLMProviderConfig(key="two", display_name="Two", models=["b"]),
            ]
        )
    )
    qtbot.addWidget(editor)
    editor._provider_key_input.setText("")
    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))

    editor._provider_selector.setCurrentIndex(1)

    assert warnings
    assert editor._provider_selector.currentIndex() == 0
    assert editor._provider_key_input.text() == ""


def test_provider_editor_masks_packaged_trial_secret_and_rejects_invalid_draft(
    qapp: QApplication,
    qtbot: QtBot,
    monkeypatch,
) -> None:
    editor = ProviderSettingsEditor(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="trial",
                    display_name="Trial",
                    base_url="https://trial.example.test",
                    api_key="not-persisted",
                    models=["trial-model"],
                    dialect_config={"secret_source": PACKAGED_TRIAL_SECRET_SOURCE},
                )
            ]
        )
    )
    qtbot.addWidget(editor)
    assert editor._provider_base_url_input.isReadOnly()
    assert editor._provider_api_key_input.isReadOnly()
    assert editor._provider_api_key_input.placeholderText() == "Built into packaged app"

    editor._provider_api_key_input.setText("attempted-secret")
    saved = editor.current_settings()
    assert saved.providers[0].base_url == "https://trial.example.test"
    assert saved.providers[0].api_key == ""

    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    editor._provider_key_input.setText("")
    editor._add_provider()
    assert editor._provider_selector.count() == 1
    assert warnings and "Provider key cannot be empty" in str(warnings[0][-1])


def test_provider_retranslation_refreshes_model_labels_without_losing_draft(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    class Translator(QTranslator):
        def translate(
            self,
            context: str,
            source_text: str,
            disambiguation: str | None = None,
            n: int = -1,
        ) -> str:
            del context, disambiguation, n
            return "No model" if source_text == "None" else source_text

    editor = ProviderSettingsEditor(
        LLMSettings(
            providers=[LLMProviderConfig(key="one", display_name="One", models=["small"])]
        )
    )
    qtbot.addWidget(editor)
    editor._provider_name_input.setText("Unsaved provider name")
    selected_values = (
        editor._llm_default_model_selector.currentData(),
        editor._llm_guard_model_selector.currentData(),
        editor._llm_thread_title_model_selector.currentData(),
    )
    translator = Translator()
    qapp.installTranslator(translator)
    try:
        QCoreApplication.sendEvent(editor, QEvent(QEvent.LanguageChange))
        assert editor._llm_guard_model_selector.itemText(0) == "No model"
        assert editor._llm_thread_title_model_selector.itemText(0) == "No model"
        assert (
            editor._llm_default_model_selector.currentData(),
            editor._llm_guard_model_selector.currentData(),
            editor._llm_thread_title_model_selector.currentData(),
        ) == selected_values
        assert editor._provider_name_input.text() == "Unsaved provider name"
    finally:
        qapp.removeTranslator(translator)


def test_ocr_card_ignores_status_completion_after_deactivate(qapp: QApplication, qtbot: QtBot) -> None:
    class Deployment:
        def status_snapshot(self) -> PaddleOcrStatus:
            return PaddleOcrStatus(PaddleOcrState.READY)

        def verify_active(self) -> PaddleOcrStatus:
            return PaddleOcrStatus(PaddleOcrState.READY)

        def install(self, progress=None) -> PaddleOcrStatus:
            return PaddleOcrStatus(PaddleOcrState.READY)

    card = OcrSettings(Deployment())
    qtbot.addWidget(card)
    card.activate()
    generation = card._generation
    card.deactivate()
    card._on_status_finished(generation, PaddleOcrStatus(PaddleOcrState.READY))
    assert card._status is None
    card.shutdown()


def test_ocr_card_ignores_late_generation_phase_and_status(qapp: QApplication, qtbot: QtBot) -> None:
    card = OcrSettings(None)
    qtbot.addWidget(card)
    card.activate()
    old_generation = card._generation
    card.deactivate()
    card.activate()
    card._on_phase(old_generation, "ready")
    card._on_status_finished(old_generation, PaddleOcrStatus(PaddleOcrState.READY))

    assert card._status is None
    assert card._status_label.text() == "Local PaddleOCR service is unavailable"
    card.shutdown()
