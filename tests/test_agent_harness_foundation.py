from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import (
    AppendAgentMessageInput,
    CompleteToolCallInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateToolCallInput,
    StartTurnInput,
)
from xenix.services.artifact_service import (
    ArtifactService,
    RegisterArtifactInput,
    build_artifact_markdown_link,
    build_artifact_uri,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentToolCallStatus,
    AgentTurnStatus,
    ArtifactKind,
)


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ConversationStore, ArtifactService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return ConversationStore(context.session_factory), ArtifactService(context.session_factory)


def test_conversation_store_persists_thread_turn_messages_and_turn_end(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="First analysis"))
    turn, user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Analyze this file"}],
        )
    )
    assistant_message = conversations.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[{"type": "markdown", "text": "I will inspect the dataset."}],
        )
    )
    _tool_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="turn_end",
            arguments_payload={},
        )
    )
    result_message, completed_tool_call = conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"status": "ended"},
        )
    )
    ended_turn = conversations.end_turn(thread.id, turn.id, result_message.id)

    snapshot = conversations.get_thread_snapshot(thread.id)

    assert ended_turn.status is AgentTurnStatus.ENDED
    assert ended_turn.user_message_id == user_message.id
    assert ended_turn.end_message_id == result_message.id
    assert completed_tool_call.result_message_id == result_message.id
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.TOOL_CALL,
        AgentMessageKind.TOOL_CALL_RESULT,
    ]
    assert snapshot.messages[1].id == assistant_message.id
    assert snapshot.messages[2].content_blocks == [{"type": "turn_end"}]
    assert snapshot.tool_calls[0].tool_name == "turn_end"
    assert snapshot.tool_calls[0].arguments_payload == {}


def test_artifact_service_registers_and_resolves_artifact_links(monkeypatch, tmp_path: Path) -> None:
    conversations, artifacts = _build_services(monkeypatch, tmp_path)
    thread = conversations.create_thread(CreateAgentThreadInput(title="Artifact links"))
    turn, user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Use this dataset"}],
        )
    )
    artifact_path = tmp_path / "cleaned.csv"
    artifact_path.write_text("age,label\n30,1\n", encoding="utf-8")

    row = artifacts.register_artifact(
        RegisterArtifactInput(
            thread_id=thread.id,
            turn_id=turn.id,
            message_id=user_message.id,
            kind=ArtifactKind.DATASET,
            title="Cleaned dataset",
            absolute_path=str(artifact_path.resolve()),
            mime_type="text/csv",
            preview_payload={"columns": ["age", "label"], "rows": 1},
        )
    )

    uri = build_artifact_uri(row.id, view="preview")
    resolved = artifacts.resolve_uri(uri)
    markdown = build_artifact_markdown_link(row)
    listed = artifacts.list_thread_artifacts(thread.id)

    assert uri == f"artifact://{row.id}?view=preview"
    assert markdown == f"[Cleaned dataset](artifact://{row.id}?view=preview)"
    assert resolved.artifact_id == row.id
    assert resolved.exists is True
    assert resolved.preview_payload == {"columns": ["age", "label"], "rows": 1}
    assert [artifact.id for artifact in listed] == [row.id]


def test_artifact_service_rejects_mismatched_turn_owner(monkeypatch, tmp_path: Path) -> None:
    conversations, artifacts = _build_services(monkeypatch, tmp_path)
    first_thread = conversations.create_thread(CreateAgentThreadInput(title="First"))
    second_thread = conversations.create_thread(CreateAgentThreadInput(title="Second"))
    second_turn, _message = conversations.start_turn(
        StartTurnInput(
            thread_id=second_thread.id,
            user_content_blocks=[{"type": "text", "text": "Different thread"}],
        )
    )
    artifact_path = tmp_path / "metrics.json"
    artifact_path.write_text('{"score": 0.91}', encoding="utf-8")

    with pytest.raises(ValidationError):
        artifacts.register_artifact(
            RegisterArtifactInput(
                thread_id=first_thread.id,
                turn_id=second_turn.id,
                kind=ArtifactKind.METRICS,
                title="Metrics",
                absolute_path=str(artifact_path.resolve()),
            )
        )
