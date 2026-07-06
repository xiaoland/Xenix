import json
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AgentToolSpec,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
    ProviderMessage,
)


def _settings_service(monkeypatch, tmp_path: Path) -> LLMSettingsService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return LLMSettingsService(ensure_app_dirs(get_app_paths()))


def test_llm_service_retries_invalid_tool_arguments_until_valid(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="mock",
                    base_url="http://mock.local",
                    api_key="secret",
                    models=["chat"],
                )
            ],
            default_fq_model_key="mock/chat",
            retry_attempts=3,
        )
    )
    llm_service = LLMService(settings_service)
    calls = 0

    class FakeResponse:
        def __init__(self, body: dict) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self):
            return json.dumps(self._body).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        nonlocal calls
        calls += 1
        arguments = "{\"dataset_id\": " if calls < 3 else "{\"dataset_id\": \"dataset-1\"}"
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-graph",
                                    "function": {
                                        "name": "analysis_graph",
                                        "arguments": arguments,
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("xenix.services.llm.providers.request.urlopen", fake_urlopen)
    retry_events = []
    response = llm_service.complete(
        messages=[ProviderMessage(role="user", content="draw")],
        tools=[
            AgentToolSpec(
                name="analysis.graph",
                provider_name="analysis_graph",
                description="Draw a graph.",
                parameters_schema={"type": "object"},
            )
        ],
        retry_callback=retry_events.append,
    )

    assert calls == 3
    assert [event.attempt_number for event in retry_events] == [2, 3]
    assert response.tool_calls[0].arguments == {"dataset_id": "dataset-1"}


def test_llm_service_does_not_retry_non_retryable_validation_error(monkeypatch, tmp_path: Path) -> None:
    settings_service = _settings_service(monkeypatch, tmp_path)
    settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="mock",
                    base_url="http://mock.local",
                    api_key="",
                    models=["chat"],
                )
            ],
            default_fq_model_key="mock/chat",
            retry_attempts=3,
        )
    )
    llm_service = LLMService(settings_service)
    retry_events = []

    with pytest.raises(ValidationError, match="LLM API key is required"):
        llm_service.complete(
            messages=[ProviderMessage(role="user", content="hello")],
            tools=[],
            retry_callback=retry_events.append,
        )

    assert retry_events == []
