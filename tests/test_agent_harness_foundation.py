from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import NotFoundError, ValidationError
from xenix.services.agent import AgentHarnessService
from xenix.services.llm import (
    AppendUserMessageInput,
    DatasetBlock,
    LLMConversationService,
    ProviderResponse,
    TextBlock,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ConversationMessageKind


def _conversation(monkeypatch, tmp_path: Path) -> LLMConversationService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    return LLMConversationService(session_factory=context.session_factory)


def test_conversation_persists_only_canonical_thread_and_messages(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread = service.create_thread().thread
    snapshot = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="submission-1",
            content_blocks=[{"type": "text", "text": "Analyze this file"}],
        )
    )

    assert [(message.kind, message.sequence_index) for message in snapshot.messages] == [
        (ConversationMessageKind.USER, 0),
    ]
    assert snapshot.messages[0].content_payload == {
        "blocks": [{"type": "text", "text": "Analyze this file"}],
    }
    assert service.get_thread_snapshot(thread.id).messages[0].id == snapshot.messages[0].id


def test_second_client_message_is_blocked_until_llm_finishes(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread = service.create_thread().thread
    first = service.append_user_message(
        AppendUserMessageInput(thread_id=thread.id, client_submission_id="one", content_blocks=[])
    )

    with pytest.raises(ValidationError, match="sampled"):
        service.append_user_message(
            AppendUserMessageInput(thread_id=thread.id, client_submission_id="two", content_blocks=[]),
            expected_frontier_id=first.messages[-1].id,
        )


def test_delete_thread_rejects_pending_sampling_without_discarding_it(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread = service.create_thread().thread
    snapshot = service.append_user_message(
        AppendUserMessageInput(thread_id=thread.id, client_submission_id="one", content_blocks=[])
    )
    pending = service.begin_sampling(
        thread_id=thread.id,
        expected_frontier_id=snapshot.messages[-1].id,
    )

    with pytest.raises(ValidationError, match="Cannot delete.*pending"):
        service.delete_thread(thread.id)

    after_rejection = service.get_thread_snapshot(thread.id)
    assert [message.id for message in after_rejection.messages] == [
        snapshot.messages[-1].id,
        pending.pending_message_id,
    ]
    assert after_rejection.messages[-1].kind is ConversationMessageKind.PENDING_LLM_SAMPLING


class _CaptureProvider:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages, _tools):
        self.messages = list(messages)
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Ready."}])


def test_legacy_dataset_block_is_reduced_in_provider_neutral_context(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread = service.create_thread().thread
    snapshot = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="dataset-attachment",
            content_blocks=[
                {"type": "text", "text": "Train a churn model."},
                {
                    "type": "dataset",
                    "visible": False,
                    "dataset_id": "dataset-churn",
                    "name": "customer_churn",
                    "file_name": "customer_churn.xlsx",
                    "row_count": 7043,
                    "column_count": 6,
                    "preview_columns": ["Account Balance", "Customer Churn"],
                },
            ],
        )
    )
    provider = _CaptureProvider()

    pending = service.sample_existing_frontier(
        thread_id=thread.id,
        expected_frontier_id=snapshot.messages[-1].id,
        provider=provider,
    )
    service.finalize_pending_assistant(pending.pending_message_id)

    user_message = next(message for message in provider.messages if message.role == "user")
    assert user_message.content == ""
    assert isinstance(user_message.content_blocks[0], TextBlock)
    assert user_message.content_blocks[0].text == "Train a churn model."
    dataset = next(block for block in user_message.content_blocks if isinstance(block, DatasetBlock))
    assert dataset.dataset_id == "dataset-churn"
    assert dataset.row_count == 7043
    assert dataset.column_count == 6
    assert dataset.name == "customer_churn"
    assert dataset.to_json() == {
        "type": "dataset",
        "dataset_id": "dataset-churn",
        "name": "customer_churn",
        "row_count": 7043,
        "column_count": 6,
    }
    assert not hasattr(dataset, "preview_columns")
    assert not hasattr(dataset, "chatbot_visible")


def test_late_cancel_does_not_create_a_ghost_pending_entry() -> None:
    class _Conversation:
        def __init__(self) -> None:
            self.cancelled: list[str] = []

        def cancel_sampling(self, pending_message_id: str) -> None:
            self.cancelled.append(pending_message_id)

    conversation = _Conversation()
    harness = AgentHarnessService(conversation_service=conversation)

    harness.cancel_sampling("late-pending")

    assert conversation.cancelled == ["late-pending"]
    assert harness._cancel_events == {}
    assert harness._pending_threads == {}


def test_cancelled_pending_callback_after_thread_deletion_cleans_local_state(monkeypatch) -> None:
    class _Conversation:
        def cancel_sampling(self, _pending_message_id: str) -> None:
            pass

    harness = AgentHarnessService(conversation_service=_Conversation())
    harness._register_cancel_event("pending-1", "thread-1")
    harness.cancel_sampling("pending-1")
    monkeypatch.setattr(
        harness,
        "get_thread_snapshot",
        lambda _thread_id: (_ for _ in ()).throw(NotFoundError("deleted")),
    )

    assert list(harness._cancelled_pending_events("thread-1", "pending-1")) == []
    assert harness._cancel_events == {}
    assert harness._pending_threads == {}
