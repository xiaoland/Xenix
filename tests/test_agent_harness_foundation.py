import json
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import NotFoundError, ValidationError
from xenix.services.agent import (
    AppendAgentMessageInput,
    ChatbotEventKind,
    ChatbotEventStatus,
    CompleteToolCallInput,
    CompleteProviderRequestInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateProviderRequestInput,
    CreateToolCallInput,
    RenameAgentThreadInput,
    StartAgentRunInput,
    StartTurnInput,
    project_chatbot_events,
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
    AgentProviderRequestKind,
    AgentProviderRequestStatus,
    AgentToolCallStatus,
    AgentTurnStatus,
    ArtifactKind,
    DEFAULT_AGENT_THREAD_SYSTEM_PROMPT,
)


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ConversationStore, ArtifactService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return ConversationStore(context.session_factory), ArtifactService(context.session_factory)


def test_conversation_store_persists_thread_turn_messages_and_tool_calls(monkeypatch, tmp_path: Path) -> None:
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
            tool_name="data.peek",
            arguments_payload={"name": "First analysis"},
        )
    )
    result_message, completed_tool_call = conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"dataset_id": "dataset-1"},
        )
    )
    final_assistant_message = conversations.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[{"type": "markdown", "text": "The dataset is ready."}],
        )
    )
    ended_turn = conversations.end_turn(thread.id, turn.id)

    snapshot = conversations.get_thread_snapshot(thread.id)
    provider_messages = snapshot.provider_messages()

    assert snapshot.thread.system_prompt == DEFAULT_AGENT_THREAD_SYSTEM_PROMPT
    assert ended_turn.status is AgentTurnStatus.ENDED
    assert ended_turn.user_message_id == user_message.id
    assert completed_tool_call.result_message_id == result_message.id
    assert [message.kind for message in snapshot.messages] == [
        AgentMessageKind.SYSTEM,
        AgentMessageKind.USER,
        AgentMessageKind.ASSISTANT,
        AgentMessageKind.TOOL_CALL,
        AgentMessageKind.TOOL_CALL_RESULT,
        AgentMessageKind.ASSISTANT,
    ]
    assert snapshot.messages[0].turn_id == turn.id
    assert snapshot.messages[0].content_blocks == [{"type": "text", "text": DEFAULT_AGENT_THREAD_SYSTEM_PROMPT}]
    assert result_message.content_blocks == []
    assert snapshot.messages[2].id == assistant_message.id
    assert snapshot.messages[5].id == final_assistant_message.id
    assert snapshot.tool_calls[0].tool_name == "data.peek"
    assert snapshot.tool_calls[0].arguments_payload == {"name": "First analysis"}
    assert provider_messages[0].role == "system"
    assert provider_messages[0].content == DEFAULT_AGENT_THREAD_SYSTEM_PROMPT
    assert provider_messages[0].source_message_id == snapshot.messages[0].id
    assert [message.role for message in provider_messages[1:]] == ["user", "assistant", "tool", "assistant"]
    tool_result_content = json.loads(provider_messages[3].content)
    assert tool_result_content == {
        "tool_name": "data.peek",
        "status": "succeeded",
        "result": {"dataset_id": "dataset-1"},
    }


def test_chatbot_event_projection_pairs_tool_call_messages(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Tool projection"))
    turn, user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Inspect the dataset"}],
        )
    )
    request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="data.peek",
            arguments_payload={"source_path": "sample.csv"},
        )
    )

    pending_events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))
    pending_tool_events = [event for event in pending_events if event.kind is ChatbotEventKind.TOOL]

    assert [event.id for event in pending_events] == [user_message.id, tool_call.id]
    assert len(pending_tool_events) == 1
    assert pending_tool_events[0].status is ChatbotEventStatus.PENDING
    assert pending_tool_events[0].summary == "Inspecting dataset..."
    assert pending_tool_events[0].source_message_ids == [request_message.id]

    result_message, completed_tool_call = conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.FAILED,
            error_summary="Source file is missing.",
            result_payload={"error": "Source file is missing."},
        )
    )

    final_events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))
    final_tool_events = [event for event in final_events if event.kind is ChatbotEventKind.TOOL]

    assert completed_tool_call.result_message_id == result_message.id
    assert [event.id for event in final_events] == [user_message.id, tool_call.id]
    assert len(final_tool_events) == 1
    assert final_tool_events[0].status is ChatbotEventStatus.FAILED
    assert final_tool_events[0].summary == "Failed to inspect dataset"
    assert final_tool_events[0].detail_blocks
    detail_text = final_tool_events[0].detail_blocks[0]["text"]
    assert "Status: `failed`" in detail_text
    assert "Source file is missing." in detail_text
    assert '"source_path": "sample.csv"' in detail_text
    assert '"error": "Source file is missing."' in detail_text
    assert final_tool_events[0].source_message_ids == [request_message.id, result_message.id]


def test_chatbot_event_projection_adds_turn_usage_overview(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Usage projection"))
    turn, user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Summarize token use"}],
        )
    )
    snapshot = conversations.get_thread_snapshot(thread.id)
    system_message = next(message for message in snapshot.messages if message.kind is AgentMessageKind.SYSTEM)
    provider_request = conversations.create_provider_request(
        CreateProviderRequestInput(
            thread_id=thread.id,
            turn_id=turn.id,
            provider_name="TestProvider",
            model="usage-model",
            request_kind=AgentProviderRequestKind.PRIMARY,
            input_message_ids=[system_message.id, user_message.id],
        )
    )
    conversations.complete_provider_request(
        CompleteProviderRequestInput(
            provider_request_id=provider_request.id,
            status=AgentProviderRequestStatus.SUCCEEDED,
            usage_payload={
                "input_tokens": 9800,
                "cached_input_tokens": 1900,
                "output_tokens": 2630,
                "total_tokens": 12430,
            },
        )
    )
    conversations.end_turn(thread.id, turn.id)

    events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))

    assert [event.kind for event in events] == [ChatbotEventKind.TEXT, ChatbotEventKind.USAGE]
    assert events[-1].id == f"{turn.id}:usage"
    assert events[-1].usage_payload == {
        "request_count": 1,
        "input_tokens": 9800,
        "cached_input_tokens": 1900,
        "output_tokens": 2630,
        "total_tokens": 12430,
    }


def test_chatbot_event_projection_exposes_tool_task_actions(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Task actions"))
    turn, _user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Train a model"}],
        )
    )
    _request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="model.train",
            arguments_payload={"binding_id": "binding-1", "models": ["regression.linear"]},
        )
    )
    conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "async_state": "running_background",
                "task_ids": ["task-1"],
            },
        )
    )

    events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))
    tool_event = next(event for event in events if event.kind is ChatbotEventKind.TOOL)

    assert tool_event.summary == "Model training running in background"
    assert tool_event.actions == [
        {"type": "open_tool_call_detail", "task_ids": ["task-1"]},
    ]


def test_chatbot_event_projection_builds_analysis_lambda_detail_from_payload(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Lambda detail"))
    turn, _user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Run custom analysis"}],
        )
    )
    _request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="analysis.lambda",
            arguments_payload={"code": "def analyze(ctx, inputs, params): return {}", "datasets": {"data": "dataset-1"}},
        )
    )
    conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={
                "result": {
                    "output": {
                        "report": "Custom analysis finished.",
                        "metric": 42,
                    }
                },
                "artifacts": [
                    {
                        "title": "Predictions",
                        "uri": "artifact://artifact-1",
                        "kind": "file",
                    }
                ],
            },
        )
    )

    events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))
    tool_event = next(event for event in events if event.kind is ChatbotEventKind.TOOL)

    assert tool_event.detail_blocks
    detail_text = tool_event.detail_blocks[0]["text"]
    assert "Custom analysis finished." in detail_text
    assert '"metric": 42' in detail_text
    assert "[Predictions](artifact://artifact-1)" in detail_text


def test_chatbot_event_projection_omits_task_query_detail_action(monkeypatch, tmp_path: Path) -> None:
    conversations, _artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Task query"))
    turn, _user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Check task status"}],
        )
    )
    _request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="model.task.query",
            arguments_payload={"task_ids": ["task-1"]},
        )
    )
    conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            status=AgentToolCallStatus.SUCCEEDED,
            result_payload={"task_ids": ["task-1"]},
        )
    )

    events = project_chatbot_events(conversations.get_thread_snapshot(thread.id))
    tool_event = next(event for event in events if event.kind is ChatbotEventKind.TOOL)

    assert tool_event.summary == "Checked model task"
    assert tool_event.actions == []


def test_conversation_store_renames_and_deletes_thread_records(monkeypatch, tmp_path: Path) -> None:
    conversations, artifacts = _build_services(monkeypatch, tmp_path)

    thread = conversations.create_thread(CreateAgentThreadInput(title="Original"))
    renamed = conversations.rename_thread(RenameAgentThreadInput(thread_id=thread.id, title="Renamed"))
    turn, user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Analyze this file"}],
        )
    )
    _assistant_message = conversations.append_message(
        AppendAgentMessageInput(
            thread_id=thread.id,
            turn_id=turn.id,
            kind=AgentMessageKind.ASSISTANT,
            ui_author=AgentMessageAuthor.ASSISTANT,
            content_blocks=[{"type": "markdown", "text": "Done."}],
        )
    )
    conversations.start_run(StartAgentRunInput(thread_id=thread.id, turn_id=turn.id, provider_name="test"))
    conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="data.peek",
            arguments_payload={"source_path": "attached.csv"},
        )
    )
    artifact_path = tmp_path / "result.csv"
    artifact_path.write_text("prediction\n1\n", encoding="utf-8")
    artifacts.register_artifact(
        RegisterArtifactInput(
            thread_id=thread.id,
            turn_id=turn.id,
            message_id=user_message.id,
            kind=ArtifactKind.PREDICTION,
            title="Prediction",
            absolute_path=str(artifact_path.resolve()),
        )
    )

    conversations.delete_thread(thread.id)

    assert renamed.title == "Renamed"
    assert all(row.id != thread.id for row in conversations.list_threads())
    with pytest.raises(NotFoundError):
        conversations.get_thread_snapshot(thread.id)


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
    assert markdown == f"[Cleaned dataset](artifact://{row.id})"
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
