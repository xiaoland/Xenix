from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from xenix.services.llm import (
    DEFAULT_FQ_MODEL_KEY,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
)
from xenix.services.paddle_ocr import PaddleOcrState, PaddleOcrStatus
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


@pytest.mark.parametrize("has_custom_provider", [False, True])
def test_provider_editor_upgrades_saved_trial_settings(
    qapp: QApplication,
    qtbot: QtBot,
    app_paths,
    has_custom_provider: bool,
) -> None:
    service = LLMSettingsService(app_paths)
    legacy_provider = {
        "key": "renamed",
        "display_name": "Trial",
        "base_url": "https://trial.example.test",
        "models": ["old-model"],
        "dialect_config": {"secret_source": "packaged_trial"},
    }
    providers = [legacy_provider]
    if has_custom_provider:
        providers.append({
            "key": "trial",
            "display_name": "My provider",
            "base_url": "https://custom.example.test",
            "api_key": "custom-key",
            "models": ["custom-model"],
        })
    title_model = "trial/custom-model" if has_custom_provider else ""
    service.settings_path.write_text(
        json.dumps({
            "providers": providers,
            "default_fq_model_key": "renamed/old-model",
            "turn_completion_guard_fq_model_key": "renamed/old-model",
            "thread_title_fq_model_key": title_model,
            "retry_attempts": 3,
        }),
        encoding="utf-8",
    )
    assert [option.fq_model_key for option in LLMService(service).model_options()] == [
        title_model or DEFAULT_FQ_MODEL_KEY
    ]
    editor = ProviderSettingsEditor(service.load())
    qtbot.addWidget(editor)
    assert editor._provider_selector.count() == 1
    assert editor._provider_api_key_input.text() == ("custom-key" if has_custom_provider else "")
    assert not editor._provider_base_url_input.isReadOnly()
    assert not editor._provider_api_key_input.isReadOnly()
    editor._provider_base_url_input.setText("https://configured.example.test")
    editor._provider_api_key_input.setText("edited-key")
    service.save(editor.current_settings())

    saved = service.load()
    assert "packaged_trial" not in service.settings_path.read_text(encoding="utf-8")
    assert saved.default_fq_model_key == (title_model or DEFAULT_FQ_MODEL_KEY)
    assert saved.turn_completion_guard_fq_model_key == ""
    assert saved.thread_title_fq_model_key == title_model
    assert saved.retry_attempts == 3
    assert saved.providers[0].base_url == "https://configured.example.test"
    assert saved.providers[0].api_key == "edited-key"


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
