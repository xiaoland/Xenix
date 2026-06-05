import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

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
    AgentProviderRequestStatus,
    AgentRunStatus,
    AgentToolCallStatus,
    AgentTurnStatus,
)


class StreamingProviderFixture:
    def __init__(self, text: str, chunk_size: int = 6, usage_payload: dict[str, Any] | None = None) -> None:
        self._text = text
        self._chunk_size = chunk_size
        self._usage_payload = usage_payload

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": self._text}],
            tool_calls=[],
            usage_payload=self._usage_payload,
        )

    def stream(self, messages: list[Any], tools: list[Any]):
        for index in range(0, len(self._text), self._chunk_size):
            yield ProviderStreamEvent(delta_text=self._text[index : index + self._chunk_size])
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": self._text}],
                tool_calls=[],
                usage_payload=self._usage_payload,
            )
        )


class ToolCaptureStreamingProvider:
    def __init__(self) -> None:
        self.tools_by_call: list[list[str]] = []

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        self.tools_by_call.append([tool.name for tool in tools])
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Ready."}],
            tool_calls=[],
        )

    def stream(self, messages: list[Any], tools: list[Any]):
        self.tools_by_call.append([tool.name for tool in tools])
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Ready."}],
                tool_calls=[],
            )
        )


class HiddenToolCallStreamingProvider:
    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-hidden-train",
                    tool_name="model.train",
                    arguments={},
                )
            ],
        )

    def stream(self, messages: list[Any], tools: list[Any]):
        yield ProviderStreamEvent(
            response=ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-hidden-train",
                        tool_name="model.train",
                        arguments={},
                    )
                ],
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


class ThreadTitleProviderFixture:
    def __init__(self, title: str) -> None:
        self._title = title
        self.messages_by_call: list[list[ProviderMessage]] = []

    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        self.messages_by_call.append(list(messages))
        assert tools == []
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": self._title}],
            tool_calls=[],
        )


class FailingThreadTitleProvider:
    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        raise ValidationError("title provider unavailable")


class UnexpectedThreadTitleProvider:
    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        raise AssertionError("Thread title provider should not be called.")


class SequencedProviderFixture:
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = list(responses)
        self.messages_by_call: list[list[ProviderMessage]] = []

    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        self.messages_by_call.append(list(messages))
        if not self._responses:
            raise AssertionError("No provider responses left.")
        return self._responses.pop(0)


class GuardProviderFixture:
    def __init__(self, verdicts: list[tuple[str, str]]) -> None:
        self._verdicts = list(verdicts)
        self.messages_by_call: list[list[ProviderMessage]] = []

    def complete(self, messages: list[ProviderMessage], tools: list[Any]) -> ProviderResponse:
        self.messages_by_call.append(list(messages))
        if not self._verdicts:
            raise AssertionError("No guard verdicts left.")
        verdict, reason = self._verdicts.pop(0)
        return ProviderResponse(
            assistant_content_blocks=[
                {"type": "markdown", "text": json.dumps({"verdict": verdict, "reason": reason})}
            ],
            tool_calls=[],
        )


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


class StaticSpecRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return [
            self._spec(tool_name)
            for tool_name in [
                "model.metadata",
                "model.task.query",
                "analysis.profile",
                "analysis.graph",
                "data.peek",
                "data.integrate",
                "data.clean",
                "data.clean.metadata",
                "data.query",
                "data.transform",
                "data.feature.select",
                "model.train",
                "model.hyper_train",
                "model.apply",
            ]
        ]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        raise AssertionError(f"Unexpected tool execution: {tool_name}")

    def _spec(self, tool_name: str) -> AgentToolSpec:
        return AgentToolSpec(
            name=tool_name,
            provider_name=tool_name.replace(".", "_"),
            description=f"{tool_name} test tool",
            parameters_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )


class BudgetedProviderFixture:
    def __init__(self, *, provider_key: str = "test", model: str = "budgeted") -> None:
        self.calls = 0
        self.provider_key = provider_key
        self.model = model

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


class SwitchingLLMServiceFixture:
    def __init__(self) -> None:
        self.first_provider = BudgetedProviderFixture(provider_key="openai", model="first")
        self.second_provider = BudgetedProviderFixture(provider_key="openai", model="second")
        self.build_requests: list[str | None] = []

    def default_fq_model_key(self) -> str:
        return "openai/first"

    def validate_fq_model_key(self, fq_model_key: str) -> str:
        if fq_model_key not in {"openai/first", "openai/second"}:
            raise ValidationError(f"Unknown model: {fq_model_key}")
        return fq_model_key

    def build_provider(self, fq_model_key: str | None = None):
        selected = fq_model_key or self.default_fq_model_key()
        self.build_requests.append(selected)
        if selected == "openai/second":
            return self.second_provider
        return self.first_provider

    def model_options(self) -> list[Any]:
        return []


class DummyToolRegistry:
    def list_specs(self) -> list[AgentToolSpec]:
        return [
            AgentToolSpec(
                name="dummy.step",
                provider_name="dummy_step",
                description="Run a dummy step.",
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
                payload={"ok": True},
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
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 1240,
                        "completion_tokens": 260,
                        "total_tokens": 1500,
                        "prompt_tokens_details": {"cached_tokens": 400},
                    },
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
    assert captured_payload["stream_options"] == {"include_usage": True}
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
    assert final_response.usage_payload == {
        "input_tokens": 1240,
        "cached_input_tokens": 400,
        "output_tokens": 260,
        "total_tokens": 1500,
        "provider_usage": {
            "prompt_tokens": 1240,
            "completion_tokens": 260,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 400},
        },
    }


def test_openai_compatible_provider_omits_tool_choice_without_tools(monkeypatch) -> None:
    captured_payload: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": "complete"}}],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 5,
                        "total_tokens": 17,
                        "prompt_tokens_details": {"cached_tokens": 3},
                    },
                }
            ).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        captured_payload.update(json.loads(http_request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("xenix.services.agent.providers.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(base_url="http://aimock.local", api_key="test", model="mock-model")

    response = provider.complete([ProviderMessage(role="user", content="classify")], [])

    assert response.assistant_content_blocks == [{"type": "markdown", "text": "complete"}]
    assert response.usage_payload == {
        "input_tokens": 12,
        "cached_input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 17,
        "provider_usage": {
            "prompt_tokens": 12,
            "completion_tokens": 5,
            "total_tokens": 17,
            "prompt_tokens_details": {"cached_tokens": 3},
        },
    }
    assert "tools" not in captured_payload
    assert "tool_choice" not in captured_payload


def test_agent_harness_streams_assistant_as_message_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    usage_payload = {
        "input_tokens": 12430,
        "cached_input_tokens": 9800,
        "output_tokens": 2630,
        "total_tokens": 15060,
    }
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=StreamingProviderFixture("streamed assistant text", chunk_size=6, usage_payload=usage_payload),
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
    thinking_events = [
        event.chatbot_event
        for event in events
        if event.kind == "chatbot_event"
        and event.chatbot_event is not None
        and event.chatbot_event.kind is ChatbotEventKind.THINKING
    ]
    snapshot = events[-1].snapshot

    assert [event.status for event in thinking_events] == [
        ChatbotEventStatus.IN_PROGRESS,
        ChatbotEventStatus.COMPLETED,
    ]
    assert thinking_events[0].content_blocks == [{"type": "thinking", "text": "Thinking..."}]
    assert events.index(next(event for event in events if event.chatbot_event is thinking_events[-1])) < events.index(
        assistant_events[0]
    )
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
        AgentMessageKind.SYSTEM,
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
    ]
    assert snapshot.messages[2].content_blocks == [{"type": "markdown", "text": "streamed assistant text"}]
    assert snapshot.tool_calls == []
    assert len(snapshot.provider_requests) == 1
    provider_request = snapshot.provider_requests[0]
    assert provider_request.status is AgentProviderRequestStatus.SUCCEEDED
    assert provider_request.input_message_ids == [snapshot.messages[0].id, snapshot.messages[1].id]
    assert provider_request.output_message_ids == [snapshot.messages[2].id]
    assert provider_request.usage_payload == usage_payload


def test_agent_harness_stream_filters_tools_by_thread_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home-no-file"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = ToolCaptureStreamingProvider()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=StaticSpecRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="hello")))

    tool_names = provider.tools_by_call[0]
    assert "model.metadata" in tool_names
    assert "model.task.query" in tool_names
    assert "analysis.profile" not in tool_names
    assert "analysis.graph" not in tool_names
    assert "analysis.lambda" not in tool_names
    assert "data.peek" not in tool_names
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names
    assert "model.apply" not in tool_names

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home-with-file"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = ToolCaptureStreamingProvider()
    source_file = tmp_path / "source.csv"
    source_file.write_text("value\n1\n", encoding="utf-8")
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=StaticSpecRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    events = list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(
                text="inspect file",
                file_paths=[str(source_file.resolve())],
            )
        )
    )

    tool_names = provider.tools_by_call[0]
    assert "data.peek" in tool_names
    assert "data.integrate" in tool_names
    assert "analysis.profile" not in tool_names
    assert "analysis.graph" not in tool_names
    assert "analysis.lambda" not in tool_names
    assert "data.clean" not in tool_names
    assert "data.clean.metadata" not in tool_names
    assert "data.transform" not in tool_names
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names
    assert "model.apply" not in tool_names

    list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(
                thread_id=events[-1].snapshot.thread.id,
                text="inspect the same file again",
            )
        )
    )

    tool_names = provider.tools_by_call[1]
    assert "data.peek" in tool_names
    assert "data.integrate" in tool_names
    assert "analysis.profile" not in tool_names
    assert "analysis.graph" not in tool_names
    assert "analysis.lambda" not in tool_names
    assert "data.clean" not in tool_names
    assert "data.clean.metadata" not in tool_names
    assert "data.transform" not in tool_names
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names
    assert "model.apply" not in tool_names


def test_agent_harness_stream_rejects_provider_tool_call_that_was_not_exposed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=HiddenToolCallStreamingProvider(),
        tool_registry=StaticSpecRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )
    thread = harness.create_thread("Hidden streaming tool call")

    with pytest.raises(ValidationError, match="not attached to this request"):
        list(harness.submit_user_turn_stream(SubmitUserTurnInput(thread_id=thread.thread.id, text="train now")))

    snapshot = harness.get_thread_snapshot(thread.thread.id)
    assert snapshot.provider_requests[0].status is AgentProviderRequestStatus.FAILED
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

    assert snapshot.messages[0].kind is AgentMessageKind.SYSTEM
    assert snapshot.messages[1].kind is AgentMessageKind.USER
    assert provider.messages[0].role == "system"
    assert provider.messages[0].content == snapshot.thread.system_prompt
    assert provider.messages[0].source_message_id == snapshot.messages[0].id
    assert provider.messages[1].role == "user"
    assert provider.messages[1].content == "show me the data"


def test_agent_harness_uses_thread_title_model_for_implicit_thread(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    title_provider = ThreadTitleProviderFixture('"Churn Risk Review."')
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        thread_title_provider=title_provider,
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Please analyze why churn increased last month."))

    assert snapshot.thread.title == "Churn Risk Review"
    assert len(title_provider.messages_by_call) == 1
    assert title_provider.messages_by_call[0][0].role == "system"
    assert "Please analyze why churn increased last month." in title_provider.messages_by_call[0][1].content
    assert len(snapshot.provider_requests) == 1


def test_agent_harness_auto_titles_precreated_empty_thread(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    title_provider = ThreadTitleProviderFixture("Customer Segmentation")
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        thread_title_provider=title_provider,
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )
    thread = harness.create_thread()

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread.thread.id,
            text="Group customers into practical market segments.",
        )
    )

    assert snapshot.thread.title == "Customer Segmentation"
    assert len(title_provider.messages_by_call) == 1


def test_agent_harness_thread_title_falls_back_when_model_is_unconfigured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(text="  Analyze weekly revenue by region and product.  ")
    )

    assert snapshot.thread.title == "Analyze weekly revenue by region and product"


def test_agent_harness_thread_title_falls_back_when_model_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        thread_title_provider=FailingThreadTitleProvider(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="", file_paths=[str(tmp_path / "orders.csv")]))

    assert snapshot.thread.title == "orders"


def test_agent_harness_thread_title_does_not_overwrite_existing_title(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        thread_title_provider=UnexpectedThreadTitleProvider(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )
    thread = harness.create_thread("Manual title")

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(thread_id=thread.thread.id, text="This should not rename the thread.")
    )

    assert snapshot.thread.title == "Manual title"


def test_agent_harness_generates_manual_thread_title_from_all_messages(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )
    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Summarize this quarter's revenue."))
    title_provider = ThreadTitleProviderFixture("Quarterly Revenue Review")
    harness.set_thread_title_provider(title_provider)

    proposal = harness.generate_thread_title(snapshot.thread.id)

    assert proposal == "Quarterly Revenue Review"
    assert len(title_provider.messages_by_call) == 1
    prompt = title_provider.messages_by_call[0][1].content
    assert '"kind": "system"' in prompt
    assert '"kind": "user"' in prompt
    assert '"kind": "assistant"' in prompt
    assert "Summarize this quarter's revenue." in prompt
    assert "Done." in prompt


def test_agent_harness_manual_thread_title_requires_configured_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=CapturingProviderFixture(),
        tool_registry=EmptyToolRegistry(),
        conversation_store=ConversationStore(context.session_factory),
    )

    with pytest.raises(ValidationError, match="Thread title model is not configured"):
        harness.generate_thread_title("thread-id")


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
    assert [message.kind for message in snapshot.messages] == [AgentMessageKind.SYSTEM, AgentMessageKind.USER]
    assert snapshot.tool_calls == []


def test_turn_completion_guard_persists_system_message_and_retries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = SequencedProviderFixture(
        [
            ProviderResponse(
                assistant_content_blocks=[
                    {
                        "type": "markdown",
                        "text": "Now let me check which classification models are available for training.",
                    }
                ],
                tool_calls=[],
            ),
            ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-dummy",
                        tool_name="dummy.step",
                        arguments={},
                    )
                ],
            ),
            ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Done."}],
                tool_calls=[],
            ),
        ]
    )
    guard_provider = GuardProviderFixture(
        [
            ("continue", "The assistant stated a next action."),
            ("complete", "The assistant provided a final answer."),
        ]
    )
    conversations = ConversationStore(context.session_factory)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        turn_completion_guard_provider=guard_provider,
        tool_registry=DummyToolRegistry(),
        conversation_store=conversations,
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="predict churn"))

    assert snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.SYSTEM,
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.SYSTEM,
        AgentMessageKind.TOOL_CALL,
        AgentMessageKind.TOOL_CALL_RESULT,
        AgentMessageKind.ASSISTANT,
    ]
    assert "did not complete it" in snapshot.messages[3].content_blocks[0]["text"]
    assert provider.messages_by_call[1][-1].role == "system"
    assert "did not complete it" in provider.messages_by_call[1][-1].content
    guard_rows = conversations.list_turn_completion_guards(snapshot.turns[0].id)
    assert [row.attempt_index for row in guard_rows] == [0, 1]
    assert guard_rows[0].input == {
        "last_assistant_text": "Now let me check which classification models are available for training."
    }
    assert guard_rows[0].output["verdict"] == "continue"
    assert guard_rows[1].output["verdict"] == "complete"
    assert [tool.tool_name for tool in snapshot.tool_calls] == ["dummy.step"]


def test_turn_completion_guard_stops_after_two_continue_retries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    provider = SequencedProviderFixture(
        [
            ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Now I will inspect the data."}],
                tool_calls=[],
            ),
            ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Now I will inspect the data."}],
                tool_calls=[],
            ),
            ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Now I will inspect the data."}],
                tool_calls=[],
            ),
        ]
    )
    guard_provider = GuardProviderFixture(
        [
            ("continue", "Still promises action."),
            ("continue", "Still promises action."),
        ]
    )
    conversations = ConversationStore(context.session_factory)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        turn_completion_guard_provider=guard_provider,
        tool_registry=EmptyToolRegistry(),
        conversation_store=conversations,
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="inspect data"))

    assert snapshot.turns[0].status is AgentTurnStatus.ENDED
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.SYSTEM,
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.SYSTEM,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.SYSTEM,
        AgentMessageKind.ASSISTANT,
    ]
    assert len(provider.messages_by_call) == 3
    guard_rows = conversations.list_turn_completion_guards(snapshot.turns[0].id)
    assert [row.output["verdict"] for row in guard_rows] == ["continue", "continue"]
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


def test_agent_harness_locks_model_for_step_budget_resume(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    llm_service = SwitchingLLMServiceFixture()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        llm_service=llm_service,
        tool_registry=BudgetedRegistry(),
        conversation_store=ConversationStore(context.session_factory),
        initial_step_limit=1,
        step_extension_limit=2,
        max_total_steps=4,
    )

    events = list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(text="run a long task", fq_model_key="openai/first")
        )
    )
    pause_event = events[-1]
    assert pause_event.thread_id is not None
    assert pause_event.turn_id is not None
    assert pause_event.run_id is not None

    harness.set_thread_model(pause_event.thread_id, "openai/second")
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

    assert resumed_snapshot is not None
    assert resumed_snapshot.thread.selected_fq_model_key == "openai/second"
    assert llm_service.build_requests == ["openai/first", "openai/first"]
    assert llm_service.first_provider.calls == 2
    assert llm_service.second_provider.calls == 0
    assert [request.model for request in resumed_snapshot.provider_requests] == ["first", "first"]


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
