from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.observability import (
    LLMTokenUsage,
    LLMUsageObservation,
    LocalLLMUsageObservability,
)
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.agent.chatbot_events import ChatbotEventKind
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    LLMConversationService,
    ProviderResponse,
    ProviderStreamEvent,
    ProviderToolCall,
)
from xenix.services.storage import StorageBootstrapService


def _context(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))


class _UsageProvider:
    def complete(self, _messages, _tools):
        return ProviderResponse(
            assistant_content_blocks=[{"type": "text", "text": "Done."}],
            usage_payload={
                "input_tokens": 12,
                "cached_input_tokens": 3,
                "output_tokens": 5,
                "total_tokens": 17,
                "provider_usage": {"raw_secret": "must-not-persist"},
            },
        )


class _ToolLoopUsageProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="usage-tool-call",
                        tool_name="data.inspect",
                        provider_name="data_inspect",
                        arguments={"dataset_id": "dataset-1"},
                    )
                ],
                usage_payload={"input_tokens": 11, "output_tokens": 4, "total_tokens": 15},
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "text", "text": "Inspection complete."}],
            usage_payload={"input_tokens": 19, "cached_input_tokens": 2, "output_tokens": 7, "total_tokens": 26},
        )


class _StreamingGateway:
    def thread_title_fq_model_key(self):
        return None

    def stream(self, **_kwargs):
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[{"type": "text", "text": "Streamed."}],
                usage_payload={"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 5, "total_tokens": 17},
            )
        )


class _TitleGateway:
    def thread_title_fq_model_key(self):
        return "titles/compact"

    def complete(self, **_kwargs):
        return ProviderResponse(
            assistant_content_blocks=[{"type": "text", "text": "Usage test title"}],
            usage_payload={"input_tokens": 99, "output_tokens": 8, "total_tokens": 107},
        )


class _BrokenUsageObservability:
    def record_llm_usage(self, _observation) -> None:
        raise RuntimeError("journal unavailable")

    def query_primary_usage(self, **_kwargs):
        raise RuntimeError("journal unavailable")


def _usage_events(harness: AgentHarnessService, snapshot):
    return [event for event in harness.project_chatbot_events(snapshot) if event.kind is ChatbotEventKind.USAGE]


def test_usage_journal_reopens_without_canonical_message_usage(monkeypatch, tmp_path: Path) -> None:
    context = _context(monkeypatch, tmp_path)
    journal_path = tmp_path / "usage-observability" / "llm-usage.jsonl"
    journal = LocalLLMUsageObservability(journal_path)
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
        usage_observability=journal,
    )
    harness = AgentHarnessService(conversation_service=conversation, provider=_UsageProvider())

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Analyze this"))
    projected = harness.project_chatbot_events(snapshot)
    event = _usage_events(harness, snapshot)[0]

    assert [event.kind for event in projected] == [
        ChatbotEventKind.TEXT,
        ChatbotEventKind.TEXT,
        ChatbotEventKind.USAGE,
    ]
    assert projected[-1].id == f"{snapshot.messages[-1].id}:usage"
    assert event.usage_payload == {
        "request_count": 1,
        "input_tokens": 12,
        "cached_input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 17,
    }
    assert all("usage" not in message.content_payload for message in snapshot.messages)

    reopened_conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
        usage_observability=LocalLLMUsageObservability(journal_path),
    )
    reopened_harness = AgentHarnessService(conversation_service=reopened_conversation)
    reopened = reopened_harness.get_thread_snapshot(snapshot.thread.id)

    assert _usage_events(reopened_harness, reopened)[0].usage_payload == event.usage_payload
    journal_text = journal_path.read_text(encoding="utf-8")
    assert "raw_secret" not in journal_text
    assert snapshot.thread.id not in journal_text
    assert snapshot.messages[0].id not in journal_text


def test_usage_overview_aggregates_primary_tool_loop_requests(monkeypatch, tmp_path: Path) -> None:
    context = _context(monkeypatch, tmp_path)
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="data.inspect", provider_name="data_inspect", description="inspect"),
        lambda arguments, context: {"dataset_id": arguments["dataset_id"], "ok": True},
    )
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=registry,
        usage_observability=LocalLLMUsageObservability(tmp_path / "tool-loop-usage.jsonl"),
    )
    harness = AgentHarnessService(
        conversation_service=conversation,
        provider=_ToolLoopUsageProvider(),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Inspect it"))
    events = _usage_events(harness, snapshot)

    assert len(events) == 1
    assert events[0].usage_payload == {
        "request_count": 2,
        "input_tokens": 30,
        "cached_input_tokens": 2,
        "output_tokens": 11,
        "total_tokens": 41,
    }
    assert events[0].source_message_ids == [snapshot.messages[0].id, snapshot.messages[-1].id]


def test_stream_usage_matches_normalized_terminal_usage(monkeypatch, tmp_path: Path) -> None:
    context = _context(monkeypatch, tmp_path)
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        llm_service=_StreamingGateway(),  # type: ignore[arg-type]
        tool_registry=AgentToolRegistry(),
        usage_observability=LocalLLMUsageObservability(tmp_path / "stream-usage.jsonl"),
    )
    harness = AgentHarnessService(conversation_service=conversation)

    events = list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="Stream this")))
    final = next(event for event in reversed(events) if event.snapshot is not None)

    assert final.snapshot is not None
    usage_events = _usage_events(harness, final.snapshot)
    assert len(usage_events) == 1
    assert usage_events[0].usage_payload == {
        "request_count": 1,
        "input_tokens": 12,
        "cached_input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 17,
    }


def test_title_model_usage_is_observed_but_excluded_from_conversation_overview(monkeypatch, tmp_path: Path) -> None:
    context = _context(monkeypatch, tmp_path)
    journal_path = tmp_path / "title-usage.jsonl"
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        llm_service=_TitleGateway(),  # type: ignore[arg-type]
        tool_registry=AgentToolRegistry(),
        usage_observability=LocalLLMUsageObservability(journal_path),
    )
    harness = AgentHarnessService(conversation_service=conversation, provider=_UsageProvider())

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Name and analyze this"))

    assert snapshot.thread.title == "Usage test title"
    assert _usage_events(harness, snapshot)[0].usage_payload["request_count"] == 1
    journal_text = journal_path.read_text(encoding="utf-8")
    assert '"operation":"thread_title"' in journal_text
    assert '"operation":"primary"' in journal_text


def test_usage_observability_failure_never_blocks_canonical_completion(monkeypatch, tmp_path: Path) -> None:
    context = _context(monkeypatch, tmp_path)
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
        usage_observability=_BrokenUsageObservability(),
    )
    harness = AgentHarnessService(conversation_service=conversation, provider=_UsageProvider())

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Continue despite telemetry failure"))

    assert [message.kind.value for message in snapshot.messages] == ["user", "assistant"]
    assert _usage_events(harness, snapshot) == []


def test_usage_journal_deduplicates_one_pending_sampling_identity(tmp_path: Path) -> None:
    journal = LocalLLMUsageObservability(tmp_path / "usage.jsonl")
    observation = LLMUsageObservation(
        operation="primary",
        usage=LLMTokenUsage(input_tokens=4, cached_input_tokens=1, output_tokens=2, total_tokens=6),
        thread_id="thread-1",
        root_user_message_id="user-1",
        frontier_message_id="user-1",
        pending_message_id="pending-1",
    )

    journal.record_llm_usage(observation)
    journal.record_llm_usage(observation)

    aggregate = journal.query_primary_usage(thread_id="thread-1", root_user_message_ids=["user-1"])["user-1"]
    assert aggregate.to_payload() == {
        "request_count": 1,
        "input_tokens": 4,
        "cached_input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 6,
    }


@pytest.mark.parametrize("value", [-1, 1_000_000_001])
def test_token_usage_rejects_negative_and_huge_counts(value: int) -> None:
    assert LLMTokenUsage.from_payload({"input_tokens": value}) is None


def test_token_usage_accepts_explicit_zero() -> None:
    usage = LLMTokenUsage.from_payload({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

    assert usage is not None
    assert usage.to_payload() == {
        "request_count": 1,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_token_usage_malformed_present_field_makes_observation_unknown() -> None:
    assert LLMTokenUsage.from_payload({"input_tokens": 3, "output_tokens": "unknown"}) is None


def test_usage_journal_rejects_directly_constructed_invalid_usage(tmp_path: Path) -> None:
    journal_path = tmp_path / "usage.jsonl"
    journal = LocalLLMUsageObservability(journal_path)
    journal.record_llm_usage(
        LLMUsageObservation(
            operation="primary",
            usage=LLMTokenUsage(input_tokens=-1, cached_input_tokens=0, output_tokens=0, total_tokens=0),
        )
    )

    assert not journal_path.exists()


def test_usage_journal_rejects_unallowlisted_operation(tmp_path: Path) -> None:
    journal_path = tmp_path / "usage.jsonl"
    journal = LocalLLMUsageObservability(journal_path)
    journal.record_llm_usage(
        LLMUsageObservation(
            operation="arbitrary.operation",
            usage=LLMTokenUsage(input_tokens=1, cached_input_tokens=0, output_tokens=1, total_tokens=2),
        )
    )

    assert not journal_path.exists()
