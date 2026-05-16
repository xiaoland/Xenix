import json
import threading
import time
from pathlib import Path
from typing import Any

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import (
    AgentHarnessService,
    ConversationStore,
    ContinueStepBudgetInput,
    OpenAICompatibleChatProvider,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentToolSpec
from xenix.services.agent.tools import ToolExecutionContext, ToolExecutionResult
from xenix.services.storage import StorageBootstrapService
from xenix.exceptions import ValidationError
from xenix.services.storage.models import AgentMessageKind, AgentRunStatus, AgentToolCallStatus, AgentTurnStatus


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


class BudgetedProviderFixture:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Step one."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-dummy",
                        tool_name="dummy.step",
                        arguments={},
                    )
                ],
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Finished after extension."}],
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-turn-end",
                    tool_name="turn_end",
                    arguments={},
                )
            ],
        )


class BudgetedRegistry(TurnEndOnlyRegistry):
    def list_specs(self) -> list[AgentToolSpec]:
        return [
            *super().list_specs(),
            AgentToolSpec(
                name="dummy.step",
                provider_name="dummy_step",
                description="Consume one harness step.",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
        ]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        if tool_name == "dummy.step":
            return ToolExecutionResult(
                payload={"dummy_step": True},
                content_blocks=[{"type": "markdown", "text": "Dummy step completed."}],
            )
        return super().execute(tool_name, arguments, context)


class BlockingToolProvider:
    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            assistant_content_blocks=[],
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-block",
                    tool_name="blocking.step",
                    arguments={},
                )
            ],
        )


class BlockingToolRegistry:
    def __init__(self) -> None:
        self.started = threading.Event()

    def list_specs(self) -> list[AgentToolSpec]:
        return [
            AgentToolSpec(
                name="blocking.step",
                provider_name="blocking_step",
                description="Block until cancellation.",
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
        self.started.set()
        while not context.cancel_requested():
            time.sleep(0.01)
        raise ValidationError("Agent run was cancelled.")


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
    assert "thinking_started" in [event.kind for event in events]
    assert "thinking_finished" in [event.kind for event in events]


def test_agent_harness_pauses_for_step_budget_confirmation_and_resumes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = BudgetedProviderFixture()
    conversations = ConversationStore(context.session_factory)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=BudgetedRegistry(),
        conversation_store=conversations,
        initial_step_limit=1,
        step_extension_limit=2,
        max_total_steps=4,
    )

    events = list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="run a long task")))
    pause_event = events[-1]
    paused_snapshot = pause_event.snapshot

    assert pause_event.kind == "step_confirmation_required"
    assert pause_event.used_steps == 1
    assert pause_event.suggested_steps == 2
    assert pause_event.thread_id is not None
    assert pause_event.turn_id is not None
    assert pause_event.run_id is not None
    assert paused_snapshot is not None
    assert paused_snapshot.turns[0].status is AgentTurnStatus.OPEN
    assert any(
        block.get("type") == "step_confirmation"
        for message in paused_snapshot.messages
        for block in message.content_blocks
    )
    assert conversations.get_run(pause_event.run_id).status is AgentRunStatus.AWAITING_CONFIRMATION

    resumed_events = list(
        harness.continue_step_budget_stream(
            ContinueStepBudgetInput(
                thread_id=pause_event.thread_id,
                turn_id=pause_event.turn_id,
                run_id=pause_event.run_id,
                additional_steps=pause_event.suggested_steps,
            )
        )
    )
    resumed_snapshot = resumed_events[-1].snapshot

    assert resumed_events[0].kind == "turn_resumed"
    assert resumed_snapshot is not None
    assert resumed_snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert conversations.get_run(pause_event.run_id).status is AgentRunStatus.SUCCEEDED
    assert [tool.tool_name for tool in resumed_snapshot.tool_calls] == ["dummy.step", "turn_end"]
    assert provider.calls == 2


def test_agent_harness_cancel_run_stops_active_tool_call(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    registry = BlockingToolRegistry()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=BlockingToolProvider(),
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )
    events: list[Any] = []

    def run_harness() -> None:
        for event in harness.submit_user_turn_stream(SubmitUserTurnInput(text="start blocking tool")):
            events.append(event)

    thread = threading.Thread(target=run_harness)
    thread.start()
    assert registry.started.wait(timeout=5)
    run_id = next(event.run_id for event in events if event.kind == "turn_started")

    harness.cancel_run(run_id)
    thread.join(timeout=5)

    assert not thread.is_alive()
    snapshot = events[-1].snapshot
    assert snapshot is not None
    assert snapshot.turns[0].status is AgentTurnStatus.CANCELLED
    assert snapshot.tool_calls[0].status is AgentToolCallStatus.CANCELLED
    assert ConversationStore(context.session_factory).get_run(run_id).status is AgentRunStatus.CANCELLED


def test_streaming_provider_fixture_can_return_non_streaming_response() -> None:
    provider = StreamingProviderFixture("same fixture content", chunk_size=4)

    response = provider.complete([], TurnEndOnlyRegistry().list_specs())
    events = list(provider.stream([], TurnEndOnlyRegistry().list_specs()))

    assert response.assistant_content_blocks == [{"type": "markdown", "text": "same fixture content"}]
    assert "".join(event.delta_text for event in events if isinstance(event, ProviderStreamEvent)) == "same fixture content"
