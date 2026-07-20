from pathlib import Path

import pytest

import xenix.services.llm.service as llm_service_module
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.llm import (
    FrozenLLMSettingsSource,
    LLMDialect,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
    PACKAGED_TRIAL_SECRET_SOURCE,
    PackagedTrialLLMConfig,
)


def test_frozen_llm_settings_source_isolates_snapshot_and_loaded_settings() -> None:
    caller_settings = LLMSettings(
        providers=[
            LLMProviderConfig(
                key="benchmark",
                base_url="https://llm.example.test",
                api_key="benchmark-secret",
                models=["chat"],
                dialect_config={"nested": {"setting": "original"}},
            )
        ],
        default_fq_model_key="benchmark/chat",
    )
    source = FrozenLLMSettingsSource(caller_settings)

    caller_settings.providers[0].models.append("caller-mutated")
    caller_settings.providers[0].dialect_config["nested"]["setting"] = "caller-mutated"
    first_load = source.load()
    first_load.providers[0].models.append("load-mutated")
    first_load.providers[0].dialect_config["nested"]["setting"] = "load-mutated"
    second_load = source.load()

    assert second_load.providers[0].models == ["chat"]
    assert second_load.providers[0].dialect_config == {"nested": {"setting": "original"}}
    assert "benchmark-secret" not in repr(source)


def test_frozen_llm_settings_source_builds_real_provider_and_rejects_writes() -> None:
    source = FrozenLLMSettingsSource(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="benchmark",
                    base_url="https://llm.example.test",
                    api_key="benchmark-secret",
                    models=["chat"],
                    timeout_seconds=45,
                )
            ],
            default_fq_model_key="benchmark/chat",
        )
    )
    llm_service = LLMService(source)

    provider = llm_service.build_provider()

    assert provider.provider_key == "benchmark"
    assert provider._base_url == "https://llm.example.test"
    assert provider._api_key == "benchmark-secret"
    assert provider._model == "chat"
    assert provider._timeout_seconds == 45
    with pytest.raises(ValidationError, match="read-only") as exc_info:
        llm_service.save_settings(LLMSettings())
    assert exc_info.value.error_code == "llm_settings_read_only"
    assert "benchmark-secret" not in str(exc_info.value)
    assert source.load().default_fq_model_key == "benchmark/chat"


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


def test_llm_settings_seed_packaged_trial_provider_when_available(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setattr(
        llm_service_module,
        "load_packaged_trial_llm_config",
        lambda: PackagedTrialLLMConfig(
            base_url="https://trial.example.test",
            api_key="trial-secret",
            model="vendor-real-model",
        ),
    )
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    llm_service = LLMService(settings_service)

    loaded = settings_service.load()
    provider_config = loaded.providers[0]
    provider = llm_service.build_provider()

    assert provider_config.key == "trial"
    assert provider_config.display_name == "Trial"
    assert provider_config.base_url == "https://trial.example.test"
    assert provider_config.api_key == ""
    assert provider_config.models == ["vendor-real-model"]
    assert provider_config.dialect_config["secret_source"] == PACKAGED_TRIAL_SECRET_SOURCE
    assert loaded.default_fq_model_key == "trial/vendor-real-model"
    assert provider._base_url == "https://trial.example.test"
    assert provider._api_key == "trial-secret"
    assert provider._model == "vendor-real-model"


def test_llm_settings_save_does_not_persist_packaged_trial_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setattr(
        llm_service_module,
        "load_packaged_trial_llm_config",
        lambda: PackagedTrialLLMConfig(
            base_url="https://trial.example.test",
            api_key="trial-secret",
            model="vendor-real-model",
        ),
    )
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    loaded = settings_service.load()
    loaded.providers[0].api_key = "trial-secret"

    settings_service.save(loaded)

    saved = settings_service.settings_path.read_text(encoding="utf-8")
    assert "trial-secret" not in saved
    assert '"api_key": ""' in saved


def test_llm_settings_drop_legacy_aimock_from_modern_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    settings_service = LLMSettingsService(paths)
    settings_service.settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_service.settings_path.write_text(
        """{
  "providers": [{
    "key": "openai",
    "base_url": "https://llm.example.test",
    "api_key": "provider-secret",
    "models": ["gpt-test"]
  }],
  "default_fq_model_key": "openai/gpt-test",
  "aimock": {
    "enabled": true,
    "base_url": "http://deprecated.example.test",
    "api_key": "deprecated-secret"
  }
}""",
        encoding="utf-8",
    )

    loaded = settings_service.load()
    settings_service.save(loaded)
    saved = settings_service.settings_path.read_text(encoding="utf-8")

    assert loaded.default_fq_model_key == "openai/gpt-test"
    assert loaded.providers[0].api_key == "provider-secret"
    assert '"aimock"' not in saved
    assert "deprecated-secret" not in saved


def test_llm_service_rejects_slashes_inside_provider_or_model_keys() -> None:
    with pytest.raises(Exception, match="Provider key cannot contain"):
        LLMProviderConfig(key="bad/provider", models=["model"])
    with pytest.raises(Exception, match="Model key cannot contain"):
        LLMProviderConfig(key="provider", models=["bad/model"])
    with pytest.raises(ValidationError, match="provider/model"):
        LLMService.parse_fq_model_key("provider/model/extra")
