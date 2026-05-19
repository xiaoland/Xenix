import json
import threading
import time
from pathlib import Path
from typing import Any

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import (
    AgentHarnessService,
    ChatbotEventKind,
    ChatbotEventStatus,
    ConversationStore,
    ContinueStepBudgetInput,
    OpenAICompatibleChatProvider,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentToolSpec
from xenix.services.agent.tools import ToolExecutionContext, ToolExecutionResult
from xenix.services.storage import StorageBootstrapService
from xenix.exceptions import ValidationError
from xenix.services.storage.models import (
    AgentMessageKind,
    AgentMessageStatus,
    AgentRunStatus,
    AgentToolCallStatus,
    AgentTurnStatus,
)


class StreamingProviderFixture:
    def __init__(self, text: str, chunk_size: int = 6) -> None:
        self._text = text
        self._chunk_size = chunk_size

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": self._text}],
            tool_calls=[],
        )

    def stream(self, messages: list[Any], tools: list[Any]):
        for index in range(0, len(self._text), self._chunk_size):
            yield ProviderStreamEvent(delta_text=self._text[index : index + self._chunk_size])
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": self._text}],
                tool_calls=[],
            )
        )


class CapturingProviderFixture:
    def __init__(self) -> None:
        self.messages: list[ProviderMessage] = []

    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        self.messages = list(messages)
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Done."}],
            tool_calls=[],
        )


class EmptyProviderFixture:
    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse()


class EmptyToolRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return []

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        raise AssertionError(f"Unexpected tool execution: {tool_name}")


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
            tool_calls=[],
        )


class BudgetedRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return [
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
        raise AssertionError(f"Unexpected tool execution: {tool_name}")


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
                                            "id": "call_data_peek",
                                            "type": "function",
                                            "function": {
                                                "name": "data_peek",
                                                "arguments": "{\"name\": \"",
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
                                            "arguments": "sample\"}",
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
            [
                ProviderMessage(role="system", content="You are Xenix."),
                ProviderMessage(role="user", content="Hello"),
            ],
            [
                AgentToolSpec(
                    name="data.peek",
                    provider_name="data_peek",
                    description="Inspect a dataset.",
                    parameters_schema={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "additionalProperties": False,
                    },
                )
            ],
        )
    )

    assert captured_payload["stream"] is True
    assert captured_payload["messages"][:2] == [
        {"role": "system", "content": "You are Xenix."},
        {"role": "user", "content": "Hello"},
    ]
    assert "".join(event.delta_text for event in events if event.is_delta) == "Hello"
    final_response = [event.response for event in events if event.is_complete][0]
    assert final_response is not None
    assert final_response.assistant_content_blocks == [{"type": "markdown", "text": "Hello"}]
    assert final_response.tool_calls[0].tool_name == "data.peek"
    assert final_response.tool_calls[0].arguments == {"name": "sample"}


def test_agent_harness_streams_assistant_as_message_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=StreamingProviderFixture("streamed assistant text", chunk_size=6),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    events = list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="show streaming")))
    message_events = [
        event
        for event in events
        if event.kind in {"message_created", "message_updated", "message_finalized"}
    ]
    assistant_events = [
        event
        for event in message_events
        if event.message is not None and event.message.kind is AgentMessageKind.ASSISTANT
    ]
    snapshot = events[-1].snapshot

    assert [event.kind for event in assistant_events][0] == "message_created"
    assert [event.kind for event in assistant_events][-1] == "message_finalized"
    assert len({event.message.id for event in assistant_events if event.message is not None}) == 1
    assert assistant_events[0].message is not None
    assert assistant_events[0].message.status is AgentMessageStatus.IN_PROGRESS
    assert assistant_events[0].chatbot_event is not None
    assert assistant_events[0].chatbot_event.status is ChatbotEventStatus.IN_PROGRESS
    assert assistant_events[-1].message is not None
    assert assistant_events[-1].message.status is AgentMessageStatus.COMPLETED
    assert assistant_events[-1].chatbot_event is not None
    assert assistant_events[-1].chatbot_event.status is ChatbotEventStatus.COMPLETED
    assert assistant_events[-1].message.content_blocks == [{"type": "markdown", "text": "streamed assistant text"}]
    assert snapshot is not None
    assert events[0].kind == "snapshot"
    assert events[0].is_final is False
    assert events[-1].kind == "snapshot"
    assert events[-1].is_final is True
    assert snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
    ]
    assert snapshot.messages[1].content_blocks == [{"type": "markdown", "text": "streamed assistant text"}]
    assert snapshot.tool_calls == []


def test_agent_harness_projects_thread_system_prompt_as_first_provider_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = CapturingProviderFixture()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="show me the data"))

    assert snapshot.messages[0].kind is AgentMessageKind.USER
    assert provider.messages[0].role == "system"
    assert provider.messages[0].content == snapshot.thread.system_prompt
    assert provider.messages[1].role == "user"
    assert provider.messages[1].content == "show me the data"


def test_agent_harness_ends_turn_on_empty_provider_response(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=EmptyProviderFixture(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="wait for next input"))

    assert snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert [message.kind for message in snapshot.messages] == [AgentMessageKind.USER]
    assert snapshot.tool_calls == []


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
    message_events = [
        event
        for event in events
        if event.kind == "message_created" and event.message is not None
    ]
    assert [event.message.kind for event in message_events] == [
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.TOOL_CALL,
        AgentMessageKind.TOOL_CALL_RESULT,
        AgentMessageKind.SYSTEM,
    ]
    tool_events = [
        event.chatbot_event
        for event in message_events
        if event.chatbot_event is not None and event.chatbot_event.kind is ChatbotEventKind.TOOL
    ]
    assert [event.status for event in tool_events] == [
        ChatbotEventStatus.PENDING,
        ChatbotEventStatus.COMPLETED,
    ]
    assert tool_events[0].id == tool_events[1].id

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

    assert resumed_events[0].kind == "snapshot"
    assert resumed_events[0].is_final is False
    assert resumed_snapshot is not None
    assert resumed_snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert conversations.get_run(pause_event.run_id).status is AgentRunStatus.SUCCEEDED
    assert [tool.tool_name for tool in resumed_snapshot.tool_calls] == ["dummy.step"]
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
    run_id = next(event.run_id for event in events if event.kind == "snapshot" and not event.is_final)

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

    response = provider.complete([], EmptyToolRegistry().list_specs())
    events = list(provider.stream([], EmptyToolRegistry().list_specs()))

    assert response.assistant_content_blocks == [{"type": "markdown", "text": "same fixture content"}]
    assert "".join(event.delta_text for event in events if isinstance(event, ProviderStreamEvent)) == "same fixture content"
