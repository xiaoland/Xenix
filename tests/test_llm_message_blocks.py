import json

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.llm import (
    AppendUserMessageInput,
    AgentToolRegistry,
    AgentToolSpec,
    AssistantOutputItem,
    DatasetBlock,
    LLMConversationService,
    MarkdownBlock,
    OpenAICompatibleChatProvider,
    ProviderMessage,
    SourceAttachmentBlock,
    TextBlock,
    blocks_from_payload,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    ConversationMessageKind,
    ConversationMessageRow,
    ConversationThreadRow,
    ConversationToolResultStatus,
)
from xenix.services.llm.conversation import ConversationSnapshot


def test_typed_blocks_round_trip_and_fallback_is_bounded_and_path_safe() -> None:
    block = DatasetBlock(
        dataset_id="dataset-1",
        name="Revenue",
        row_count=12,
        column_count=3,
    )

    payload = block.to_json()
    restored = blocks_from_payload({"blocks": [payload]})[0]

    assert restored == block
    assert payload == {
        "type": "dataset",
        "dataset_id": "dataset-1",
        "name": "Revenue",
        "row_count": 12,
        "column_count": 3,
    }
    assert "C:\\Users" not in block.to_markdown()
    assert "revenue.xlsx" not in block.to_markdown()
    assert "column names" not in block.to_markdown()
    assert "dataset_id: dataset-1" in block.to_markdown()
    assert len(block.to_markdown()) <= 4096


def test_legacy_visible_alias_is_decoded_but_new_json_is_explicit() -> None:
    block = blocks_from_payload(
        {
            "blocks": [
                {
                    "type": "dataset",
                    "dataset_id": "dataset-legacy",
                    "visible": False,
                }
            ]
        }
    )[0]
    assert isinstance(block, DatasetBlock)
    assert "visible" not in block.to_json()
    assert set(block.to_json()) == {
        "type",
        "dataset_id",
        "name",
        "row_count",
        "column_count",
    }


def test_legacy_dataset_preview_columns_are_discarded_before_validation() -> None:
    block = blocks_from_payload(
        {
            "blocks": [
                {
                    "type": "dataset",
                    "dataset_id": "dataset-legacy",
                    "name": "Legacy sales",
                    "row_count": 5,
                    "column_count": 50,
                    "preview_columns": [f"column-{index}" for index in range(50)],
                    "file_name": r"C:\private\sales.csv",
                    "source_format": "csv",
                    "visible": False,
                }
            ]
        }
    )[0]

    assert isinstance(block, DatasetBlock)
    assert block.to_json() == {
        "type": "dataset",
        "dataset_id": "dataset-legacy",
        "name": "Legacy sales",
        "row_count": 5,
        "column_count": 50,
    }


@pytest.mark.parametrize(
    ("factory", "keyword"),
    [
        (DatasetBlock, "dataset_id"),
        (SourceAttachmentBlock, "artifact_id"),
    ],
)
def test_attachment_identifiers_reject_local_paths(factory, keyword: str) -> None:
    with pytest.raises(ValidationError, match="must not be a path"):
        factory(**{keyword: r"C:\\Users\\secret\\input.csv"})


def test_chat_completions_serializes_all_blocks_even_when_hidden() -> None:
    provider = OpenAICompatibleChatProvider(api_key="test", model="mock")
    payload = provider._build_payload(
        [
            ProviderMessage(
                role="user",
                content_blocks=[
                    TextBlock("Inspect these files."),
                    DatasetBlock(
                        dataset_id="dataset-1",
                        name="Revenue",
                        row_count=12,
                        column_count=3,
                    ),
                    SourceAttachmentBlock(
                        artifact_id="artifact-1",
                        file_name="notes.csv",
                        source_format="csv",
                    ),
                ],
            )
        ],
        [],
        stream=False,
    )

    content = payload["messages"][0]["content"]
    assert "Inspect these files." in content
    assert "dataset_id: dataset-1" in content
    assert "artifact_id" not in content
    assert "notes.csv" not in content
    assert "source_format" not in content


def test_captured_chat_completion_request_contains_dataset_fallback() -> None:
    provider = OpenAICompatibleChatProvider(api_key="test", model="mock", streaming_enabled=False)
    captured: list[dict] = []

    def fake_post(payload):
        captured.append(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    provider._post_json = fake_post  # type: ignore[method-assign]
    provider.complete(
        [
            ProviderMessage(
                role="user",
                content_blocks=[
                    DatasetBlock(
                        dataset_id="dataset-captured",
                        name="Sales",
                        row_count=7,
                        column_count=2,
                    )
                ],
            )
        ],
        [],
    )

    wire_content = captured[0]["messages"][0]["content"]
    assert "dataset_id: dataset-captured" in wire_content
    assert "rows: 7" in wire_content


def test_openai_adapter_carries_direct_tool_result_values_without_reinterpreting_them() -> None:
    provider = OpenAICompatibleChatProvider(api_key="test", model="mock")
    xtt = "shape: 1 rows × 1 columns\n\ndata:\n| # | total |\n|---:|---:|\n| 1 | 42 |"
    direct_json = {"dataset_id": "dataset-1", "ok": True}

    payload = provider._build_payload(
        [
            ProviderMessage(
                role="tool",
                tool_result_value=xtt,
                provider_payload={"tool_call_id": "call-xtt"},
            ),
            ProviderMessage(
                role="tool",
                tool_result_value=direct_json,
                provider_payload={"tool_call_id": "call-json"},
            ),
        ],
        [],
        stream=False,
    )

    wire_messages = payload["messages"]
    assert wire_messages[0]["content"] == xtt
    assert wire_messages[0]["tool_call_id"] == "call-xtt"
    assert json.loads(wire_messages[1]["content"]) == direct_json
    assert wire_messages[1]["tool_call_id"] == "call-json"


def test_conversation_persists_json_and_reloads_typed_blocks(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    service = LLMConversationService(session_factory=context.session_factory)
    thread = service.create_thread().thread
    snapshot = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="submission-1",
            content_blocks=[DatasetBlock(dataset_id="dataset-1")],
        )
    )

    reloaded = service.get_thread_snapshot(thread.id)
    assert reloaded.messages[0].content_payload == snapshot.messages[0].content_payload
    block = blocks_from_payload(reloaded.messages[0].content_payload)[0]
    assert isinstance(block, DatasetBlock)
    assert block.dataset_id == "dataset-1"
    assert set(reloaded.messages[0].content_payload["blocks"][0]) == {
        "type",
        "dataset_id",
        "name",
        "row_count",
        "column_count",
    }


def test_historical_wide_dataset_payload_reopens_without_rewriting_row(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    service = LLMConversationService(session_factory=context.session_factory)
    thread = service.create_thread().thread
    historical_payload = {
        "blocks": [
            {
                "type": "dataset",
                "dataset_id": "legacy-wide-dataset",
                "name": "Legacy sales",
                "row_count": 10,
                "column_count": 50,
                "preview_columns": [f"column-{index}" for index in range(50)],
                "file_name": r"C:\private\sales.xlsx",
                "source_format": "xlsx",
                "visible": False,
            }
        ]
    }
    with service._session_factory() as session:  # type: ignore[union-attr]
        service._repository.append_message(
            session,
            ConversationMessageRow(
                thread_id=thread.id,
                sequence_index=0,
                kind=ConversationMessageKind.USER,
                client_submission_id="legacy-wide",
                content_payload=historical_payload,
            ),
        )
        session.commit()

    reloaded = service.get_thread_snapshot(thread.id)
    assert reloaded.messages[0].content_payload == historical_payload
    block = blocks_from_payload(reloaded.messages[0].content_payload)[0]
    assert isinstance(block, DatasetBlock)
    assert block.to_json() == {
        "type": "dataset",
        "dataset_id": "legacy-wide-dataset",
        "name": "Legacy sales",
        "row_count": 10,
        "column_count": 50,
    }


def test_new_append_rejects_legacy_source_block_but_reads_persisted_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    service = LLMConversationService(session_factory=context.session_factory)
    thread = service.create_thread().thread

    with pytest.raises(ValidationError, match="legacy presentation block"):
        service.append_user_message(
            AppendUserMessageInput(
                thread_id=thread.id,
                client_submission_id="legacy-source-new-write",
                content_blocks=[
                    SourceAttachmentBlock(
                        artifact_id="artifact-legacy",
                        file_name="historical.xlsx",
                        source_format="xlsx",
                    )
                ],
            )
        )
    assert service.get_thread_snapshot(thread.id).messages == []

    # A historical row may still contain the legacy block; loading it is a
    # read-path compatibility obligation, not a new-write capability.
    with service._session_factory() as session:  # type: ignore[union-attr]
        service._repository.append_message(
            session,
            ConversationMessageRow(
                thread_id=thread.id,
                sequence_index=0,
                kind=ConversationMessageKind.USER,
                client_submission_id="legacy-source-persisted",
                content_payload={
                    "blocks": [
                        {
                            "type": "source_attachment",
                            "artifact_id": "artifact-legacy",
                            "file_name": r"C:\private\historical.xlsx",
                            "source_format": "xlsx",
                        }
                    ]
                },
            ),
        )
        session.commit()

    snapshot = service.get_thread_snapshot(thread.id)
    blocks = blocks_from_payload(snapshot.messages[0].content_payload)
    assert isinstance(blocks[0], SourceAttachmentBlock)
    assert blocks[0].file_name == "historical.xlsx"


def test_provider_history_keeps_one_assistant_envelope_and_provider_tool_name() -> None:
    thread = ConversationThreadRow(id="thread-1", system_prompt="system")
    rows = [
        ConversationMessageRow(
            id="user-1",
            thread_id=thread.id,
            sequence_index=0,
            kind=ConversationMessageKind.USER,
            content_payload={"blocks": [{"type": "text", "text": "Run it."}]},
        ),
        ConversationMessageRow(
            id="assistant-1",
            thread_id=thread.id,
            sequence_index=1,
            kind=ConversationMessageKind.ASSISTANT,
            text="Done.",
        ),
        ConversationMessageRow(
            id="call-1",
            thread_id=thread.id,
            sequence_index=2,
            kind=ConversationMessageKind.TOOL_CALL,
            tool_id="canonical.tool",
            provider_call_id="provider-call-1",
            arguments_payload={"dataset_id": "dataset-1"},
            content_payload={"tool_name": "canonical.tool", "provider_name": "provider_tool"},
        ),
        ConversationMessageRow(
            id="result-1",
            thread_id=thread.id,
            sequence_index=3,
            kind=ConversationMessageKind.TOOL_RESULT,
            tool_call_message_id="call-1",
            result_status=ConversationToolResultStatus.SUCCEEDED,
            value_payload={"ok": True},
        ),
    ]
    service = LLMConversationService(session_factory=None)  # type: ignore[arg-type]

    messages = service._provider_messages(ConversationSnapshot(thread=thread, messages=rows))

    assert [message.role for message in messages] == ["system", "user", "assistant", "tool"]
    assistant_messages = [message for message in messages if message.role == "assistant"]
    assert len(assistant_messages) == 1
    tool_calls = assistant_messages[0].provider_payload["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "provider_tool"
    assert json.loads(tool_calls[0]["function"]["arguments"]) == {"dataset_id": "dataset-1"}


def test_provider_history_repairs_legacy_tool_name_from_llm_owned_registry() -> None:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="canonical.tool",
            provider_name="provider_tool",
            description="test tool",
        ),
        lambda _arguments, _context: {},
    )
    service = LLMConversationService(session_factory=None, tool_registry=registry)  # type: ignore[arg-type]
    call = ConversationMessageRow(
        id="call-1",
        thread_id="thread-1",
        sequence_index=0,
        kind=ConversationMessageKind.TOOL_CALL,
        tool_id="canonical.tool",
        provider_call_id="provider-call-1",
        content_payload={"tool_name": "canonical.tool"},
    )

    payload = service._provider_call_payload(call)

    assert payload["function"]["name"] == "provider_tool"


def test_assistant_output_blocks_normalize_to_the_existing_text_field() -> None:
    output = AssistantOutputItem(content_blocks=(MarkdownBlock("Visible answer."),))

    assert output.text == "Visible answer."
    assert output.content_blocks == (MarkdownBlock("Visible answer."),)

    scalar_output = AssistantOutputItem(text="Already canonical.")
    assert scalar_output.text == "Already canonical."
    assert scalar_output.content_blocks == ()
