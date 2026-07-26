import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import (
    AgentHarnessService,
    AttachmentImportStatus,
    ChatbotEventKind,
    SourceAttachmentInput,
    SubmitUserTurnInput,
    project_chatbot_events,
)
from xenix.services.agent.chatbot_events import enrich_chatbot_events_with_source_attachments
from xenix.services.dataset_service import DatasetService
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    DatasetBlock,
    LLMConversationService,
    ProviderResponse,
    SourceAttachmentBlock,
    TextBlock,
    ToolFailure,
    blocks_from_payload,
)
from xenix.services.storage import StorageBootstrapService


class TextProvider:
    def complete(self, _messages, _tools):
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Ready."}])


class BlockingProvider:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def complete(self, _messages, _tools):
        self.started.set()
        self.release.wait(timeout=5)
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Late response."}])


class RecordingTextProvider:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages, _tools):
        self.messages = list(messages)
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Imported."}])


class ToolThenTextProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            from xenix.services.llm import ProviderToolCall

            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="provider-call-1",
                        tool_name="test.tool",
                        provider_name="test_tool",
                        arguments={},
                    )
                ]
            )
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Should not run."}])


class BlockingImportDatasetService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def register_dataset_attachment(self, _input):
        self.started.set()
        if not self.release.wait(timeout=5):
            raise AssertionError("Dataset import test barrier timed out.")
        return SimpleNamespace(
            datasets=[
                SimpleNamespace(
                    dataset_id="imported-dataset",
                    name="blocked-import",
                    row_count=1,
                    column_count=2,
                )
            ]
        )


def test_thinking_event_is_live_chatbot_event_and_never_persisted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory, tool_registry=AgentToolRegistry(),
        ),
        provider=TextProvider(),
    )

    events = list(harness.submit_user_turn_stream(SubmitUserTurnInput(text="Hello")))
    thinking = [event.chatbot_event for event in events if event.kind == "thinking"]
    final = next(event.snapshot for event in events if event.is_final)

    assert thinking and thinking[0] is not None
    assert thinking[0].kind is ChatbotEventKind.THINKING
    assert all(message.kind.value != "pending_llm_sampling" for message in final.messages)


def test_cancelled_provider_completion_finishes_without_resurrecting_pending_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = BlockingProvider()
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory, tool_registry=AgentToolRegistry(),
        ),
        provider=provider,
    )
    stream = harness.submit_user_turn_stream(SubmitUserTurnInput(text="Cancel this"))
    next(stream)  # persisted user Message
    thinking = next(stream)
    assert thinking.pending_message_id is not None

    outcome: list[object] = []
    worker = threading.Thread(target=lambda: outcome.extend(stream), daemon=True)
    worker.start()
    assert provider.started.wait(timeout=2)
    harness.cancel_sampling(thinking.pending_message_id)
    provider.release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert outcome and outcome[-1].is_final is True
    snapshot = outcome[-1].snapshot
    assert snapshot is not None
    assert [message.kind.value for message in snapshot.messages] == ["user"]


def test_pause_before_provider_admission_sends_no_request_and_discards_placeholder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = BlockingProvider()
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
    )
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)
    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(text="Pause before the request.", client_submission_id="pause-before-request")
    )

    append_ack = next(stream)
    thinking = next(stream)
    assert append_ack.snapshot is not None
    assert thinking.thread_id == append_ack.thread_id
    assert thinking.client_submission_id == "pause-before-request"
    assert thinking.pending_message_id is not None
    thread_id = append_ack.snapshot.thread.id

    harness.pause_thread(thread_id)
    events = list(stream)

    assert provider.started.is_set() is False
    assert events and events[-1].is_final is True
    snapshot = events[-1].snapshot
    assert snapshot is not None
    assert [message.kind.value for message in snapshot.messages] == ["user"]
    assert all(message.kind.value != "pending_llm_sampling" for message in snapshot.messages)


def test_pause_after_tool_result_prevents_next_provider_sample(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = ToolThenTextProvider()
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="test.tool", provider_name="test_tool", description="test"),
        lambda _arguments, _context: {"ok": True},
    )
    conversation = LLMConversationService(session_factory=context.session_factory, tool_registry=registry)
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)
    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(text="Pause after the tool.", client_submission_id="pause-after-tool")
    )

    append_ack = next(stream)
    thinking = next(stream)
    assert append_ack.snapshot is not None
    assert thinking.kind == "thinking"
    tool_snapshot = next(
        event
        for event in stream
        if event.kind == "snapshot" and event.snapshot is not None
        and any(message.kind.value == "tool_result" for message in event.snapshot.messages)
    )
    assert tool_snapshot.is_final is False
    assert provider.calls == 1

    harness.pause_thread(append_ack.snapshot.thread.id)
    remaining = list(stream)

    assert provider.calls == 1
    assert remaining and remaining[-1].is_final is True
    final = remaining[-1].snapshot
    assert final is not None
    assert [message.kind.value for message in final.messages] == ["user", "tool_call", "tool_result"]


def test_new_user_message_reenters_paused_tool_result_frontier_without_replay(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = ToolThenTextProvider()
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="test.tool", provider_name="test_tool", description="test"),
        lambda _arguments, _context: {"ok": True},
    )
    conversation = LLMConversationService(session_factory=context.session_factory, tool_registry=registry)
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)
    first_stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(text="Create the paused tool result.", client_submission_id="paused-turn")
    )
    append_ack = next(first_stream)
    next(first_stream)  # Thinking
    tool_snapshot = next(
        event
        for event in first_stream
        if event.kind == "snapshot"
        and event.snapshot is not None
        and any(message.kind.value == "tool_result" for message in event.snapshot.messages)
    )
    assert append_ack.snapshot is not None
    thread_id = append_ack.snapshot.thread.id
    assert tool_snapshot.is_final is False
    harness.pause_thread(thread_id)
    paused_events = list(first_stream)
    assert paused_events and paused_events[-1].is_final is True
    paused_snapshot = paused_events[-1].snapshot
    assert paused_snapshot is not None
    assert [message.kind.value for message in paused_snapshot.messages] == ["user", "tool_call", "tool_result"]

    resumed_events = list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(
                thread_id=thread_id,
                text="Continue with a new explicit message.",
                client_submission_id="resumed-turn",
            )
        )
    )

    assert provider.calls == 2
    resumed_snapshot = next(event.snapshot for event in reversed(resumed_events) if event.snapshot is not None)
    assert [message.kind.value for message in resumed_snapshot.messages] == [
        "user",
        "tool_call",
        "tool_result",
        "user",
        "assistant",
    ]


def test_pause_during_tool_allows_tool_to_finish_without_continuation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = ToolThenTextProvider()
    started = threading.Event()
    release = threading.Event()

    def blocking_tool(_arguments, _context):
        started.set()
        assert release.wait(timeout=3), "Tool test barrier timed out."
        return {"ok": True}

    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="test.tool", provider_name="test_tool", description="test"),
        blocking_tool,
    )
    conversation = LLMConversationService(session_factory=context.session_factory, tool_registry=registry)
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)
    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(text="Pause during the tool.", client_submission_id="pause-during-tool")
    )
    append_ack = next(stream)
    next(stream)  # Thinking
    outcome: list[object] = []

    worker = threading.Thread(target=lambda: outcome.extend(stream), daemon=True)
    worker.start()
    assert started.wait(timeout=2)
    assert append_ack.snapshot is not None
    harness.pause_thread(append_ack.snapshot.thread.id)
    release.set()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert provider.calls == 1
    final_events = [event for event in outcome if getattr(event, "is_final", False)]
    assert final_events
    final = final_events[-1].snapshot
    assert final is not None
    assert [message.kind.value for message in final.messages] == ["user", "tool_call", "tool_result"]


def test_pause_allows_an_already_started_tool_exchange_to_commit_its_atomic_result_set(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class TwoToolThenTextProvider:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, _messages, _tools):
            self.calls += 1
            if self.calls == 1:
                from xenix.services.llm import ProviderToolCall

                return ProviderResponse(
                    tool_calls=[
                        ProviderToolCall(
                            provider_call_id="provider-call-a",
                            tool_name="test.tool_a",
                            provider_name="test_tool_a",
                            arguments={},
                        ),
                        ProviderToolCall(
                            provider_call_id="provider-call-b",
                            tool_name="test.tool_b",
                            provider_name="test_tool_b",
                            arguments={},
                        ),
                    ]
                )
            return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Should not run."}])

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    provider = TwoToolThenTextProvider()
    first_started = threading.Event()
    release_first = threading.Event()
    completed: list[str] = []

    def first_tool(_arguments, _context):
        first_started.set()
        assert release_first.wait(timeout=3), "First tool test barrier timed out."
        completed.append("a")
        return {"tool": "a"}

    def second_tool(_arguments, _context):
        completed.append("b")
        return {"tool": "b"}

    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="test.tool_a", provider_name="test_tool_a", description="test"),
        first_tool,
    )
    registry.register(
        AgentToolSpec(name="test.tool_b", provider_name="test_tool_b", description="test"),
        second_tool,
    )
    conversation = LLMConversationService(session_factory=context.session_factory, tool_registry=registry)
    harness = AgentHarnessService(conversation_service=conversation, provider=provider)
    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(text="Pause an admitted two-tool exchange.", client_submission_id="pause-tool-batch")
    )
    append_ack = next(stream)
    next(stream)  # Thinking
    outcome: list[object] = []
    worker = threading.Thread(target=lambda: outcome.extend(stream), daemon=True)
    worker.start()
    assert first_started.wait(timeout=2)
    assert append_ack.snapshot is not None

    harness.pause_thread(append_ack.snapshot.thread.id)
    release_first.set()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert completed == ["a", "b"]
    assert provider.calls == 1
    final_events = [event for event in outcome if getattr(event, "is_final", False)]
    assert final_events
    final = final_events[-1].snapshot
    assert final is not None
    assert [message.kind.value for message in final.messages] == [
        "user",
        "tool_call",
        "tool_call",
        "tool_result",
        "tool_result",
    ]


def test_snapshot_projection_preserves_assistant_fields_and_reasoning_only_event() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={"blocks": [{"type": "text", "text": "Train a model."}]},
            ),
            SimpleNamespace(
                id="internal-reasoning",
                kind="assistant",
                sequence_index=1,
                content_payload={},
                text=None,
                reasoning="The assistant is about to activate a tool.",
                refusal=None,
            ),
            SimpleNamespace(
                id="visible-answer",
                kind="assistant",
                sequence_index=2,
                content_payload={},
                text="The dataset is ready.",
                reasoning="Internal detail.",
                refusal=None,
            ),
        ]
    )

    events = project_chatbot_events(snapshot)

    assert [event.id for event in events] == ["user-message", "internal-reasoning", "visible-answer"]
    assert events[1].content_blocks == []
    assert events[1].reasoning == "The assistant is about to activate a tool."
    assert events[1].text is None
    assert events[1].refusal is None
    assert events[-1].content_blocks == []
    assert events[-1].text == "The dataset is ready."
    assert events[-1].reasoning == "Internal detail."


def test_snapshot_projection_preserves_refusal_and_tool_call_result_order() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={"blocks": [{"type": "text", "text": "Run it."}]},
            ),
            SimpleNamespace(
                id="assistant-with-call",
                kind="assistant",
                sequence_index=1,
                content_payload={},
                text=None,
                reasoning="Preparing the tool call.",
                refusal=None,
            ),
            SimpleNamespace(
                id="tool-call",
                kind="tool_call",
                sequence_index=2,
                content_payload={"tool_name": "data.inspect"},
                tool_id="data.inspect",
                arguments_payload={"dataset_id": "dataset-1"},
            ),
            SimpleNamespace(
                id="tool-result",
                kind="tool_result",
                sequence_index=3,
                tool_call_message_id="tool-call",
                result_status="succeeded",
                value_payload={"ok": True},
                error_summary=None,
            ),
            SimpleNamespace(
                id="assistant-refusal",
                kind="assistant",
                sequence_index=4,
                content_payload={},
                text=None,
                reasoning=None,
                refusal="I cannot do that.",
            ),
        ]
    )

    events = project_chatbot_events(snapshot)

    assert [event.id for event in events] == [
        "user-message",
        "assistant-with-call",
        "tool-call",
        "assistant-refusal",
    ]
    assert events[1].reasoning == "Preparing the tool call."
    assert events[2].source_message_ids == ["tool-call", "tool-result"]
    assert events[3].refusal == "I cannot do that."


def test_tool_failure_projection_uses_the_canonical_typed_value() -> None:
    failure = ToolFailure(
        code="query_invalid",
        message="Binder error: relation sales_missing does not exist.",
        details={"sql": "SELECT * FROM sales_missing"},
        repair_hints=("Inspect the registered dataset aliases.",),
    ).to_value()
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="tool-call",
                kind="tool_call",
                sequence_index=0,
                content_payload={"tool_name": "data.query"},
                tool_id="data.query",
                arguments_payload={"sql": "SELECT * FROM sales_missing"},
            ),
            SimpleNamespace(
                id="tool-result",
                kind="tool_result",
                sequence_index=1,
                tool_call_message_id="tool-call",
                result_status="failed",
                value_payload=failure,
                error_summary="legacy generic summary must not win",
            ),
        ]
    )

    event = project_chatbot_events(snapshot)[0]

    assert event.tool_result_value == failure
    detail = event.detail_blocks[0]["text"]
    assert "Binder error: relation sales_missing does not exist." in detail
    assert "legacy generic summary must not win" not in detail


def test_dataset_block_is_structural_until_optional_source_enrichment() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={
                    "blocks": [{"type": "dataset", "dataset_id": "dataset-1", "name": "Sales"}]
                },
            )
        ]
    )

    events = project_chatbot_events(snapshot)
    assert events[0].content_blocks == [
        {
            "type": "dataset",
            "dataset_id": "dataset-1",
            "name": "Sales",
            "row_count": None,
            "column_count": None,
        }
    ]

    enriched = enrich_chatbot_events_with_source_attachments(
        snapshot,
        events,
        lambda dataset_id: {
            "file_name": "sales.csv",
            "file_path": r"C:\private\sales.csv",
            "is_openable": True,
            "source_group_id": "source-1",
        },
    )
    assert enriched[0].content_blocks[-1] == {
        "type": "source_attachment",
        "dataset_id": "dataset-1",
        "chatbot_source_projection": True,
        "is_openable": True,
        "file_name": "sales.csv",
        "source_group_id": "source-1",
        "file_path": r"C:\private\sales.csv",
    }
    serialized = json.loads(enriched[0].model_dump_json())
    assert r"C:\private\sales.csv" not in json.dumps(serialized)
    assert "file_path" not in serialized["content_blocks"][-1]


def test_source_enrichment_soft_fails_without_resolver_result() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={
                    "blocks": [{"type": "dataset", "dataset_id": "dataset-1"}]
                },
            )
        ]
    )
    events = project_chatbot_events(snapshot)
    enriched = enrich_chatbot_events_with_source_attachments(snapshot, events, lambda _id: None)
    assert enriched == events


def test_source_enrichment_only_deduplicates_the_same_import_group() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={
                    "blocks": [
                        {"type": "dataset", "dataset_id": "dataset-1", "name": "North sales"},
                        {"type": "dataset", "dataset_id": "dataset-2", "name": "South sales"},
                    ]
                },
            )
        ]
    )
    events = project_chatbot_events(snapshot)
    enriched = enrich_chatbot_events_with_source_attachments(
        snapshot,
        events,
        lambda dataset_id: {
            "file_name": "sales.xlsx",
            "file_path": rf"C:\{dataset_id}\sales.xlsx",
            "is_openable": True,
            "source_group_id": f"import-{dataset_id}",
        },
    )

    attachments = [
        block
        for block in enriched[0].content_blocks
        if block.get("chatbot_source_projection")
    ]
    assert [block["source_group_id"] for block in attachments] == [
        "import-dataset-1",
        "import-dataset-2",
    ]


def test_source_enrichment_deduplicates_workbook_sheets_from_one_import() -> None:
    snapshot = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="user-message",
                kind="user",
                sequence_index=0,
                content_payload={
                    "blocks": [
                        {"type": "dataset", "dataset_id": "north", "name": "North"},
                        {"type": "dataset", "dataset_id": "south", "name": "South"},
                    ]
                },
            )
        ]
    )
    events = project_chatbot_events(snapshot)
    enriched = enrich_chatbot_events_with_source_attachments(
        snapshot,
        events,
        lambda _dataset_id: {
            "file_name": "sales.xlsx",
            "file_path": r"C:\imports\sales.xlsx",
            "is_openable": True,
            "source_group_id": "import-sales",
        },
    )

    attachments = [
        block
        for block in enriched[0].content_blocks
        if block.get("chatbot_source_projection")
    ]
    assert len(attachments) == 1
    assert attachments[0]["source_group_id"] == "import-sales"


def test_source_import_persists_only_dataset_context_and_reopens_when_source_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    source = tmp_path / "customers.csv"
    source.write_text("customer,value\nAcme,12\n", encoding="utf-8")
    provider = RecordingTextProvider()
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
    )
    harness = AgentHarnessService(
        conversation_service=conversation,
        provider=provider,
        dataset_service=DatasetService(context.session_factory, paths),
    )

    stream = list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(
                text="Analyze this source.",
                source_attachments=[SourceAttachmentInput(file_path=str(source))],
            )
        )
    )
    initial = next(event for event in stream if event.kind == "snapshot" and not event.is_final)
    assert initial.snapshot is not None
    user_message = initial.snapshot.messages[0]
    canonical_blocks = blocks_from_payload(user_message.content_payload)

    assert [type(block) for block in canonical_blocks] == [TextBlock, DatasetBlock]
    dataset = canonical_blocks[1]
    assert isinstance(dataset, DatasetBlock)
    assert set(dataset.to_json()) == {
        "type",
        "dataset_id",
        "name",
        "row_count",
        "column_count",
    }
    assert "customers.csv" not in str(user_message.content_payload)
    assert str(source) not in str(user_message.content_payload)
    assert all(
        not isinstance(block, SourceAttachmentBlock)
        for message in provider.messages
        for block in message.content_blocks
    )

    assert initial.chatbot_events is not None
    user_event = next(event for event in initial.chatbot_events if event.id == user_message.id)
    attachment = next(
        block
        for block in user_event.content_blocks
        if block.get("type") == "source_attachment" and block.get("chatbot_source_projection")
    )
    assert attachment["file_name"] == "customers.csv"
    assert attachment["file_path"] == str(source)
    assert attachment["is_openable"] is True

    source.unlink()
    reopened = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory,
            tool_registry=AgentToolRegistry(),
        ),
        dataset_service=DatasetService(context.session_factory, paths),
    )
    reopened_snapshot = reopened.get_thread_snapshot(initial.snapshot.thread.id)
    reopened_user_event = next(
        event
        for event in reopened.project_chatbot_events(reopened_snapshot)
        if event.id == user_message.id
    )
    unavailable = next(
        block
        for block in reopened_user_event.content_blocks
        if block.get("type") == "source_attachment" and block.get("chatbot_source_projection")
    )
    assert unavailable["file_name"] == "customers.csv"
    assert unavailable["file_path"] is None
    assert unavailable["is_openable"] is False


def test_source_import_progress_is_path_free_and_precedes_append_ack_and_thinking(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    source = tmp_path / "progress.csv"
    source.write_text("customer,value\nAcme,12\n", encoding="utf-8")
    submission_id = "import-progress"
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory,
            tool_registry=AgentToolRegistry(),
        ),
        provider=RecordingTextProvider(),
        dataset_service=DatasetService(context.session_factory, paths),
    )

    events = list(
        harness.submit_user_turn_stream(
            SubmitUserTurnInput(
                text="Analyze this source.",
                source_attachments=[SourceAttachmentInput(file_path=str(source))],
                client_submission_id=submission_id,
            )
        )
    )

    import_events = [event for event in events if event.kind == "attachment_import"]
    assert len(import_events) == 1
    progress_event = import_events[0]
    assert progress_event.thread_id is not None
    assert progress_event.client_submission_id == submission_id
    assert progress_event.attachment_import is not None
    assert progress_event.attachment_import.source_index == 0
    assert progress_event.attachment_import.status is AttachmentImportStatus.PENDING
    assert progress_event.snapshot is None
    assert progress_event.chatbot_event is None
    assert progress_event.chatbot_events is None
    assert progress_event.is_final is False
    assert str(source) not in repr(progress_event)

    import_index = events.index(progress_event)
    append_ack_index = next(
        index
        for index, event in enumerate(events)
        if event.kind == "snapshot" and not event.is_final
    )
    thinking_index = next(index for index, event in enumerate(events) if event.kind == "thinking")
    assert import_index < append_ack_index < thinking_index
    append_ack = events[append_ack_index]
    assert append_ack.snapshot is not None
    assert append_ack.snapshot.messages[0].kind.value == "user"


def test_source_import_pending_is_visible_while_materialization_blocks_append_and_sampling(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    source = tmp_path / "blocked.csv"
    source.write_text("customer,value\nAcme,12\n", encoding="utf-8")
    importer = BlockingImportDatasetService()
    provider = RecordingTextProvider()
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory,
            tool_registry=AgentToolRegistry(),
        ),
        provider=provider,
        dataset_service=importer,  # type: ignore[arg-type]
    )

    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(
            text="Analyze this source.",
            source_attachments=[SourceAttachmentInput(file_path=str(source))],
            client_submission_id="blocked-import",
        )
    )
    pending = next(stream)

    assert pending.kind == "attachment_import"
    assert pending.client_submission_id == "blocked-import"
    assert pending.attachment_import is not None
    assert pending.attachment_import.status is AttachmentImportStatus.PENDING
    assert pending.attachment_import.source_index == 0
    assert str(source) not in repr(pending)
    assert not importer.started.is_set()

    outcome: list[object] = []
    errors: list[Exception] = []

    def consume() -> None:
        try:
            outcome.extend(stream)
        except Exception as exc:  # Surface worker failures in the test thread.
            errors.append(exc)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert importer.started.wait(timeout=2)
    assert pending.thread_id is not None
    assert harness.get_thread_snapshot(pending.thread_id).messages == []
    assert provider.messages == []
    assert not any(event.kind == "thinking" for event in outcome)

    importer.release.set()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert errors == []
    events = [pending, *outcome]
    append_ack_index = next(
        index
        for index, event in enumerate(events)
        if event.kind == "snapshot" and not event.is_final
    )
    thinking_index = next(index for index, event in enumerate(events) if event.kind == "thinking")
    assert append_ack_index < thinking_index


def test_source_import_failure_emits_path_free_failed_event_without_append_or_thinking(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    source = tmp_path / "missing.csv"
    submission_id = "import-failure"
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory,
            tool_registry=AgentToolRegistry(),
        ),
        provider=TextProvider(),
        dataset_service=DatasetService(context.session_factory, paths),
    )

    stream = harness.submit_user_turn_stream(
        SubmitUserTurnInput(
            text="Analyze this source.",
            source_attachments=[SourceAttachmentInput(file_path=str(source))],
            client_submission_id=submission_id,
        )
    )
    pending = next(stream)
    failed = next(stream)

    assert pending.kind == failed.kind == "attachment_import"
    assert pending.thread_id == failed.thread_id
    assert pending.client_submission_id == failed.client_submission_id == submission_id
    assert pending.attachment_import is not None
    assert failed.attachment_import is not None
    assert pending.attachment_import.status is AttachmentImportStatus.PENDING
    assert failed.attachment_import.status is AttachmentImportStatus.FAILED
    assert pending.attachment_import.source_index == failed.attachment_import.source_index == 0
    assert str(source) not in repr(pending)
    assert str(source) not in repr(failed)

    with pytest.raises(ValidationError):
        next(stream)

    assert pending.thread_id is not None
    snapshot = harness.get_thread_snapshot(pending.thread_id)
    assert snapshot.messages == []
