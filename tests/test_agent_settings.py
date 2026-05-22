from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import AgentSettings, AgentSettingsService, AimockSettings


def test_agent_settings_persist_llm_provider_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    service = AgentSettingsService(paths)

    service.save(
        AgentSettings(
            base_url="https://llm.example.test",
            api_key="secret",
            model="deepseek-chat",
            turn_completion_guard_model="qwen-lite",
            thread_title_model="qwen-title",
            timeout_seconds=45,
            streaming_enabled=False,
        )
    )

    loaded = service.load()
    provider = service.build_provider()
    guard_provider = service.build_turn_completion_guard_provider()
    title_provider = service.build_thread_title_provider()

    assert loaded.base_url == "https://llm.example.test"
    assert loaded.api_key == "secret"
    assert loaded.model == "deepseek-chat"
    assert loaded.turn_completion_guard_model == "qwen-lite"
    assert loaded.thread_title_model == "qwen-title"
    assert loaded.timeout_seconds == 45
    assert loaded.streaming_enabled is False
    assert provider._base_url == "https://llm.example.test"
    assert provider._api_key == "secret"
    assert provider._model == "deepseek-chat"
    assert provider._streaming_enabled is False
    assert guard_provider is not None
    assert guard_provider._base_url == "https://llm.example.test"
    assert guard_provider._api_key == "secret"
    assert guard_provider._model == "qwen-lite"
    assert guard_provider._streaming_enabled is False
    assert title_provider is not None
    assert title_provider._base_url == "https://llm.example.test"
    assert title_provider._api_key == "secret"
    assert title_provider._model == "qwen-title"
    assert title_provider._streaming_enabled is False


def test_agent_settings_ignore_llm_environment_variables(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setenv("XENIX_LLM_BASE_URL", "https://env.example.test")
    monkeypatch.setenv("XENIX_LLM_API_KEY", "env-secret")
    monkeypatch.setenv("XENIX_LLM_MODEL", "env-model")
    paths = ensure_app_dirs(get_app_paths())
    service = AgentSettingsService(paths)

    provider = service.build_provider()

    assert provider._base_url == "https://api.openai.com"
    assert provider._api_key == ""
    assert provider._model == "gpt-4o-mini"
    assert service.build_turn_completion_guard_provider() is None
    assert service.build_thread_title_provider() is None


def test_agent_settings_use_aimock_only_in_development(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setenv("XENIX_ENV", "development")
    paths = ensure_app_dirs(get_app_paths())
    service = AgentSettingsService(paths)
    service.save(
        AgentSettings(
            base_url="https://llm.example.test",
            api_key="secret",
            model="gpt-test",
            turn_completion_guard_model="guard-test",
            thread_title_model="title-test",
            aimock=AimockSettings(
                enabled=True,
                base_url="http://127.0.0.1:4010",
                api_key="test",
            ),
        )
    )

    provider = service.build_provider()
    guard_provider = service.build_turn_completion_guard_provider()
    title_provider = service.build_thread_title_provider()

    assert service.is_development() is True
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
