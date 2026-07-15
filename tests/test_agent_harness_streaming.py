import json
from pathlib import Path
import threading
from types import SimpleNamespace

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import (
    AgentHarnessService,
    ChatbotEventKind,
    SourceAttachmentInput,
    SubmitUserTurnInput,
    project_chatbot_events,
)
from xenix.services.agent.chatbot_events import enrich_chatbot_events_with_source_attachments
from xenix.services.dataset_service import DatasetService
from xenix.services.llm import (
    AgentToolRegistry,
    DatasetBlock,
    LLMConversationService,
    ProviderResponse,
    SourceAttachmentBlock,
    TextBlock,
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
    assert outcome and getattr(outcome[-1], "is_final") is True
    snapshot = outcome[-1].snapshot
    assert snapshot is not None
    assert [message.kind.value for message in snapshot.messages] == ["user"]


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
