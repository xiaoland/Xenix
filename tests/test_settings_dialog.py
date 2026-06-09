from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.llm import LLMProviderConfig, LLMService, LLMSettings, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.ui.settings_dialog import SettingsDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_settings_dialog_provider_switch_preserves_distinct_provider_fields(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    llm_settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="bailian",
                    display_name="Bailian",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode",
                    api_key="bailian-secret",
                    models=["qwen-plus"],
                    timeout_seconds=60,
                ),
                LLMProviderConfig(
                    key="deepseek",
                    display_name="DeepSeek",
                    base_url="https://api.deepseek.com",
                    api_key="deepseek-secret",
                    models=["deepseek-chat"],
                    timeout_seconds=120,
                ),
                LLMProviderConfig(
                    key="kimi",
                    display_name="Kimi",
                    base_url="https://api.moonshot.cn/v1",
                    api_key="kimi-secret",
                    models=["kimi-k2"],
                    timeout_seconds=120,
                ),
            ],
            default_fq_model_key="bailian/qwen-plus",
        )
    )
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
    )

    try:
        dialog._provider_base_url_input.setText("https://edited-bailian.example.test")
        dialog._provider_api_key_input.setText("edited-bailian-secret")
        dialog._provider_models_input.setPlainText("edited-qwen\nedited-title")

        dialog._provider_selector.setCurrentIndex(dialog._provider_selector.findData("deepseek"))
        app.processEvents()

        assert dialog._provider_configs[0].base_url == "https://edited-bailian.example.test"
        assert dialog._provider_configs[0].api_key == "edited-bailian-secret"
        assert dialog._provider_configs[0].models == ["edited-qwen", "edited-title"]
        assert dialog._provider_configs[1].key == "deepseek"
        assert dialog._provider_configs[1].base_url == "https://api.deepseek.com"
        assert dialog._provider_key_input.text() == "deepseek"
        assert dialog._provider_base_url_input.text() == "https://api.deepseek.com"
        assert dialog._provider_models_input.toPlainText() == "deepseek-chat"
        assert _combo_values(dialog._llm_default_model_selector) == [
            "bailian/edited-qwen",
            "bailian/edited-title",
            "deepseek/deepseek-chat",
            "kimi/kimi-k2",
        ]

        dialog._save_agent_settings()
        loaded = llm_settings_service.load()

        assert [provider.key for provider in loaded.providers] == ["bailian", "deepseek", "kimi"]
        assert [provider.base_url for provider in loaded.providers] == [
            "https://edited-bailian.example.test",
            "https://api.deepseek.com",
            "https://api.moonshot.cn/v1",
        ]
        assert [provider.models for provider in loaded.providers] == [
            ["edited-qwen", "edited-title"],
            ["deepseek-chat"],
            ["kimi-k2"],
        ]
    finally:
        dialog.close()


def _combo_values(selector) -> list[str]:
    return [str(selector.itemData(index)) for index in range(selector.count())]
