import json
import threading
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AgentToolSpec,
    MAX_TOOL_CALLS,
    MAX_TOOL_PAYLOAD_BYTES,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    LLMSettingsService,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
    OpenAICompatibleChatProvider,
)


def _settings_service(monkeypatch, tmp_path: Path) -> LLMSettingsService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return LLMSettingsService(ensure_app_dirs(get_app_paths()))


def test_llm_service_fails_closed_on_invalid_tool_arguments_without_retry(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
                                        "arguments": "{\"dataset_id\": ",
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
    with pytest.raises(ValidationError, match="not valid JSON"):
        llm_service.complete(
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

    assert calls == 1
    assert retry_events == []


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


def test_llm_service_yields_tool_call_delta_progress_before_buffered_completion(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
            retry_attempts=1,
        )
    )
    llm_service = LLMService(settings_service)
    release_completion = threading.Event()

    class FakeStreamingProvider:
        def stream(self, messages, tools):
            yield ProviderStreamEvent(tool_call_delta=True)
            assert release_completion.wait(timeout=2)
            yield ProviderStreamEvent(delta_text="Visible text.")
            yield ProviderStreamEvent(
                response=ProviderResponse(
                    assistant_content_blocks=[{"type": "markdown", "text": "Visible text."}],
                )
            )

    monkeypatch.setattr(
        llm_service,
        "_build_provider_from_settings",
        lambda _settings, _fq_model_key: FakeStreamingProvider(),
    )

    stream = llm_service.stream(
        messages=[ProviderMessage(role="user", content="draw")],
        tools=[],
    )

    first_event = next(stream)
    assert first_event.is_tool_call_delta
    assert not release_completion.is_set()

    release_completion.set()
    remaining_events = list(stream)
    assert "".join(event.delta_text for event in remaining_events if event.is_delta) == "Visible text."
    assert remaining_events[-1].is_complete


def _provider_for_normalization() -> OpenAICompatibleChatProvider:
    return OpenAICompatibleChatProvider(api_key="test", model="mock")


def _normalization_tool() -> AgentToolSpec:
    return AgentToolSpec(
        name="data.query",
        provider_name="data_query",
        description="Query a dataset.",
        parameters_schema={"type": "object"},
    )


@pytest.mark.parametrize("choices", [[], [{"message": {}}] * 2])
def test_chat_completion_requires_exactly_one_choice(choices) -> None:
    with pytest.raises(ValidationError, match="exactly one choice"):
        _provider_for_normalization()._parse_chat_completion(
            {"choices": choices},
            [_normalization_tool()],
        )


def test_chat_completion_normalizes_reasoning_and_refusal() -> None:
    response = _provider_for_normalization()._parse_chat_completion(
        {
            "choices": [
                {
                    "message": {
                        "content": "answer",
                        "reasoning_content": "because",
                        "refusal": None,
                    }
                }
            ]
        },
        [_normalization_tool()],
    )

    assert len(response.output_items) == 1
    assistant = response.output_items[0]
    assert assistant.text == "answer"
    assert assistant.reasoning == "because"
    assert assistant.refusal is None


@pytest.mark.parametrize(
    "tool_call",
    [
        {"id": "", "function": {"name": "data_query", "arguments": "{}"}},
        {"id": "call-1", "function": {"name": "missing", "arguments": "{}"}},
    ],
)
def test_chat_completion_rejects_blank_or_unknown_tool_ids(tool_call) -> None:
    with pytest.raises(ValidationError):
        _provider_for_normalization()._parse_chat_completion(
            {"choices": [{"message": {"tool_calls": [tool_call]}}]},
            [_normalization_tool()],
        )


def test_chat_completion_rejects_duplicate_tool_ids() -> None:
    call = {"id": "call-1", "function": {"name": "data_query", "arguments": "{}"}}
    with pytest.raises(ValidationError, match="duplicated"):
        _provider_for_normalization()._parse_chat_completion(
            {"choices": [{"message": {"tool_calls": [call, call]}}]},
            [_normalization_tool()],
        )


def test_chat_completion_rejects_empty_output_without_calls() -> None:
    with pytest.raises(ValidationError, match="empty assistant output"):
        _provider_for_normalization()._parse_chat_completion(
            {"choices": [{"message": {"content": None}}]},
            [_normalization_tool()],
        )


def test_chat_completion_enforces_call_and_argument_bounds() -> None:
    tool = _normalization_tool()
    too_many_calls = [
        {"id": f"call-{index}", "function": {"name": "data_query", "arguments": "{}"}}
        for index in range(MAX_TOOL_CALLS + 1)
    ]
    with pytest.raises(ValidationError, match="more than"):
        _provider_for_normalization()._parse_chat_completion(
            {"choices": [{"message": {"tool_calls": too_many_calls}}]},
            [tool],
        )

    oversized = {"value": "x" * MAX_TOOL_PAYLOAD_BYTES}
    with pytest.raises(ValidationError, match="exceeds"):
        _provider_for_normalization()._parse_chat_completion(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-big",
                                    "function": {
                                        "name": "data_query",
                                        "arguments": json.dumps(oversized),
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
            [tool],
        )


def _stream_events(chunks: list[dict]) -> list[ProviderStreamEvent]:
    provider = _provider_for_normalization()
    provider._post_stream = lambda _payload: iter(chunks)
    return list(provider.stream([ProviderMessage(role="user", content="query")], [_normalization_tool()]))


def test_stream_indexes_are_strict_and_arrival_order_is_not_canonical() -> None:
    events = _stream_events(
        [
            {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call-1", "function": {"name": "data_query", "arguments": "{}"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-0", "function": {"name": "data_query", "arguments": "{}"}}]}}]},
            {"choices": [], "usage": {"prompt_tokens": 1}},
        ]
    )
    response = events[-1].response
    assert response is not None
    assert [call.provider_call_id for call in response.tool_calls] == ["call-0", "call-1"]

    with pytest.raises(ValidationError, match="contiguous"):
        _stream_events(
            [
                {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call-1", "function": {"name": "data_query", "arguments": "{}"}}]}}]},
                {"choices": []},
            ]
        )


@pytest.mark.parametrize("index", [-1, None, True])
def test_stream_rejects_invalid_indexes(index) -> None:
    delta = {"index": index, "id": "call-1", "function": {"name": "data_query", "arguments": "{}"}}
    with pytest.raises(ValidationError, match="index"):
        _stream_events([{"choices": [{"delta": {"tool_calls": [delta]}}]}])


def test_normal_and_stream_paths_have_the_same_semantic_output() -> None:
    tool = _normalization_tool()
    body = {
        "choices": [
            {
                "message": {
                    "content": "answer",
                    "reasoning_content": "because",
                    "tool_calls": [
                        {
                            "id": "call-0",
                            "function": {"name": "data_query", "arguments": "{\"dataset_id\":\"d1\"}"},
                        }
                    ],
                }
            }
        ]
    }
    provider = _provider_for_normalization()
    normal = provider._parse_chat_completion(body, [tool])
    provider._post_stream = lambda _payload: iter(
        [
            {"choices": [{"delta": {"content": "answer", "reasoning_content": "because"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-0", "function": {"name": "data_query", "arguments": "{\"dataset_id\":\"d1\"}"}}]}}]},
            {"choices": []},
        ]
    )
    stream = list(provider.stream([ProviderMessage(role="user", content="query")], [tool]))[-1].response
    assert stream is not None
    assert [(type(item), getattr(item, "text", None), getattr(item, "reasoning", None), getattr(item, "provider_call_id", None), getattr(item, "arguments", None)) for item in normal.output_items] == [
        (type(item), getattr(item, "text", None), getattr(item, "reasoning", None), getattr(item, "provider_call_id", None), getattr(item, "arguments", None))
        for item in stream.output_items
    ]
