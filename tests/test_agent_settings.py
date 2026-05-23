from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AimockSettings,
    LLMDialect,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
)


def test_llm_settings_persist_multi_provider_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    llm_service = LLMService(settings_service)

    settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="deepseek",
                    display_name="DeepSeek",
                    dialect=LLMDialect.OPENAI_COMPATIBLE,
                    base_url="https://llm.example.test",
                    api_key="secret",
                    models=["deepseek-chat", "qwen-lite", "qwen-title"],
                    timeout_seconds=45,
                    streaming_enabled=False,
                ),
                LLMProviderConfig(
                    key="openai",
                    display_name="OpenAI",
                    models=["gpt-4o-mini"],
                ),
            ],
            default_fq_model_key="deepseek/deepseek-chat",
            turn_completion_guard_fq_model_key="deepseek/qwen-lite",
            thread_title_fq_model_key="deepseek/qwen-title",
        )
    )

    loaded = settings_service.load()
    provider = llm_service.build_provider("deepseek/deepseek-chat")
    guard_provider = llm_service.build_turn_completion_guard_provider()
    title_provider = llm_service.build_thread_title_provider()
    options = llm_service.model_options()

    assert loaded.default_fq_model_key == "deepseek/deepseek-chat"
    assert loaded.turn_completion_guard_fq_model_key == "deepseek/qwen-lite"
    assert loaded.thread_title_fq_model_key == "deepseek/qwen-title"
    assert [option.fq_model_key for option in options] == [
        "deepseek/deepseek-chat",
        "deepseek/qwen-lite",
        "deepseek/qwen-title",
        "openai/gpt-4o-mini",
    ]
    assert provider.provider_key == "deepseek"
    assert provider._base_url == "https://llm.example.test"
    assert provider._api_key == "secret"
    assert provider._model == "deepseek-chat"
    assert provider._streaming_enabled is False
    assert guard_provider is not None
    assert guard_provider.provider_key == "deepseek"
    assert guard_provider._model == "qwen-lite"
    assert title_provider is not None
    assert title_provider.provider_key == "deepseek"
    assert title_provider._model == "qwen-title"


def test_llm_settings_migrate_legacy_flat_provider_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    settings_service.settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_service.settings_path.write_text(
        """{
  "base_url": "https://legacy.example.test",
  "api_key": "legacy-secret",
  "model": "legacy-chat",
  "turn_completion_guard_model": "legacy-guard",
  "thread_title_model": "legacy-title",
  "timeout_seconds": 55,
  "streaming_enabled": false
}""",
        encoding="utf-8",
    )

    loaded = settings_service.load()

    assert len(loaded.providers) == 1
    provider = loaded.providers[0]
    assert provider.key == "openai"
    assert provider.base_url == "https://legacy.example.test"
    assert provider.api_key == "legacy-secret"
    assert provider.models == ["legacy-chat", "legacy-guard", "legacy-title"]
    assert provider.timeout_seconds == 55
    assert provider.streaming_enabled is False
    assert loaded.default_fq_model_key == "openai/legacy-chat"
    assert loaded.turn_completion_guard_fq_model_key == "openai/legacy-guard"
    assert loaded.thread_title_fq_model_key == "openai/legacy-title"


def test_llm_settings_ignore_llm_environment_variables(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setenv("XENIX_LLM_BASE_URL", "https://env.example.test")
    monkeypatch.setenv("XENIX_LLM_API_KEY", "env-secret")
    monkeypatch.setenv("XENIX_LLM_MODEL", "env-model")
    paths = ensure_app_dirs(get_app_paths())
    llm_service = LLMService(LLMSettingsService(paths))

    provider = llm_service.build_provider()

    assert provider._base_url == "https://api.openai.com"
    assert provider._api_key == ""
    assert provider._model == "gpt-4o-mini"
    assert llm_service.build_turn_completion_guard_provider() is None
    assert llm_service.build_thread_title_provider() is None


def test_llm_settings_use_aimock_only_in_development(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setenv("XENIX_ENV", "development")
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="openai",
                    base_url="https://llm.example.test",
                    api_key="secret",
                    models=["gpt-test", "guard-test", "title-test"],
                )
            ],
            default_fq_model_key="openai/gpt-test",
            turn_completion_guard_fq_model_key="openai/guard-test",
            thread_title_fq_model_key="openai/title-test",
            aimock=AimockSettings(
                enabled=True,
                base_url="http://127.0.0.1:4010",
                api_key="test",
            ),
        )
    )
    llm_service = LLMService(settings_service)

    provider = llm_service.build_provider()
    guard_provider = llm_service.build_turn_completion_guard_provider()
    title_provider = llm_service.build_thread_title_provider()

    assert settings_service.is_development() is True
    assert provider._base_url == "http://127.0.0.1:4010"
    assert provider._api_key == "test"
    assert provider._model == "gpt-test"
    assert guard_provider is not None
    assert guard_provider._base_url == "http://127.0.0.1:4010"
    assert guard_provider._api_key == "test"
    assert guard_provider._model == "guard-test"
    assert title_provider is not None
    assert title_provider._base_url == "http://127.0.0.1:4010"
    assert title_provider._api_key == "test"
    assert title_provider._model == "title-test"


def test_llm_service_rejects_slashes_inside_provider_or_model_keys() -> None:
    with pytest.raises(Exception, match="Provider key cannot contain"):
        LLMProviderConfig(key="bad/provider", models=["model"])
    with pytest.raises(Exception, match="Model key cannot contain"):
        LLMProviderConfig(key="provider", models=["bad/model"])
    with pytest.raises(ValidationError, match="provider/model"):
        LLMService.parse_fq_model_key("provider/model/extra")
