import json
from pathlib import Path
from typing import Any

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import (
    AgentHarnessService,
    ConversationStore,
    OpenAICompatibleChatProvider,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentToolSpec
from xenix.services.agent.tools import ToolExecutionContext, ToolExecutionResult
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import AgentMessageKind, AgentTurnStatus


class StreamingProviderFixture:
    def __init__(self, text: str, chunk_size: int = 6) -> None:
        self._text = text
        self._chunk_size = chunk_size

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": self._text}],
            tool_calls=[self._turn_end_call()],
        )

    def stream(self, messages: list[Any], tools: list[Any]):
        for index in range(0, len(self._text), self._chunk_size):
            yield ProviderStreamEvent(delta_text=self._text[index : index + self._chunk_size])
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": self._text}],
                tool_calls=[self._turn_end_call()],
            )
        )

    def _turn_end_call(self) -> ProviderToolCall:
        return ProviderToolCall(
            provider_call_id="fixture-turn-end",
            tool_name="turn_end",
            arguments={},
        )


class TurnEndOnlyRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return [
            AgentToolSpec(
                name="turn_end",
                provider_name="turn_end",
                description="End the current turn.",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        ]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            payload={"turn_end": True},
            content_blocks=[],
        )


def test_openai_compatible_provider_streams_sse_text_and_tool_calls(monkeypatch) -> None:
    captured_payload: dict[str, Any] = {}

    class FakeSSE:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def __iter__(self):
            chunks = [
                {"choices": [{"delta": {"content": "Hel"}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_turn_end",
                                        "type": "function",
                                        "function": {
                                            "name": "turn_end",
                                            "arguments": "{",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": "}",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            ]
            for chunk in chunks:
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

    def fake_urlopen(http_request, timeout):
        captured_payload.update(json.loads(http_request.data.decode("utf-8")))
        return FakeSSE()

    monkeypatch.setattr("xenix.services.agent.providers.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(base_url="http://aimock.local", api_key="test", model="mock-model")
    events = list(
        provider.stream(
            [],
            TurnEndOnlyRegistry().list_specs(),
        )
    )

    assert captured_payload["stream"] is True
    assert "".join(event.delta_text for event in events if event.is_delta) == "Hello"
    final_response = [event.response for event in events if event.is_complete][0]
    assert final_response is not None
    assert final_response.assistant_content_blocks == [{"type": "markdown", "text": "Hello"}]
    assert final_response.tool_calls[0].tool_name == "turn_end"
    assert final_response.tool_calls[0].arguments == {}


def test_agent_harness_streams_deltas_and_persists_final_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=StreamingProviderFixture("streamed assistant text", chunk_size=6),
        tool_registry=TurnEndOnlyRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    events = list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="show streaming")))
    delta_text = "".join(event.delta_text for event in events if event.kind == "assistant_delta")
    snapshot = events[-1].snapshot

    assert delta_text == "streamed assistant text"
    assert snapshot is not None
    assert snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.TOOL_CALL,
        AgentMessageKind.TOOL_CALL_RESULT,
    ]
    assert snapshot.messages[1].content_blocks == [{"type": "markdown", "text": "streamed assistant text"}]
    assert snapshot.messages[2].content_blocks == [{"type": "turn_end"}]
    assert snapshot.messages[3].content_blocks == [{"type": "tool_result_payload", "payload": {"turn_end": True}}]
    assert snapshot.tool_calls[0].tool_name == "turn_end"
    assert snapshot.tool_calls[0].arguments_payload == {}


def test_streaming_provider_fixture_can_return_non_streaming_response() -> None:
    provider = StreamingProviderFixture("same fixture content", chunk_size=4)

    response = provider.complete([], TurnEndOnlyRegistry().list_specs())
    events = list(provider.stream([], TurnEndOnlyRegistry().list_specs()))

    assert response.assistant_content_blocks == [{"type": "markdown", "text": "same fixture content"}]
    assert "".join(event.delta_text for event in events if isinstance(event, ProviderStreamEvent)) == "same fixture content"
