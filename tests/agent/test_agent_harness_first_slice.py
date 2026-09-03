from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import NotFoundError
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    AppendUserMessageInput,
    LLMConversationService,
    ProviderResponse,
    ProviderToolCall,
    ToolSuccess,
)
from xenix.services.storage import StorageBootstrapService


class ToolThenTextProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[ProviderToolCall(
                    provider_call_id="provider-call-1", tool_name="data.inspect",
                    provider_name="data_inspect", arguments={"dataset_id": "dataset-1"},
                )]
            )
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Dataset inspected."}])


def test_harness_coordinates_tool_but_llm_service_commits_messages(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="data.inspect", provider_name="data_inspect", description="inspect"),
        lambda arguments, context: {"dataset_id": arguments["dataset_id"], "ok": True},
    )
    provider = ToolThenTextProvider()
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory, tool_registry=registry,
        ),
        provider=provider,
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Inspect it"))

    assert [message.kind.value for message in snapshot.messages] == [
        "user", "tool_call", "tool_result", "assistant",
    ]
    call, result = snapshot.messages[1:3]
    assert result.tool_call_message_id == call.id
    assert result.value_payload == {"dataset_id": "dataset-1", "ok": True}
    assert provider.calls == 2

    harness.delete_thread(snapshot.thread.id)
    with pytest.raises(NotFoundError):
        harness.get_thread_snapshot(snapshot.thread.id)


def test_direct_xtt_tool_result_has_one_value_across_storage_provider_and_chatbot(monkeypatch, tmp_path: Path) -> None:
    """The Tool itself chooses XTT; neither consumer derives another result."""

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    canonical_xtt = (
        "shape: 1 rows × 1 columns\n"
        "returned_rows: 1\n"
        "\n"
        "schema:\n"
        "  total: int\n"
        "\n"
        "data:\n"
        "| # | total |\n"
        "|---:|---:|\n"
        "| 1 | 42 |"
    )
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="data.query", provider_name="data_query", description="query"),
        lambda _arguments, _context: ToolSuccess(value=canonical_xtt),
    )
    class _CapturingProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.requests = []

        def complete(self, messages, _tools):
            self.requests.append(list(messages))
            self.calls += 1
            if self.calls == 1:
                return ProviderResponse(
                    tool_calls=[
                        ProviderToolCall(
                            provider_call_id="query-1",
                            tool_name="data.query",
                            provider_name="data_query",
                            arguments={},
                        )
                    ]
                )
            return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])

    provider = _CapturingProvider()
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory,
            tool_registry=registry,
        ),
        provider=provider,
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Query it"))

    result = next(message for message in snapshot.messages if message.kind.value == "tool_result")
    assert result.value_payload == canonical_xtt
    reloaded = harness.get_thread_snapshot(snapshot.thread.id)
    reloaded_result = next(message for message in reloaded.messages if message.kind.value == "tool_result")
    assert reloaded_result.value_payload == canonical_xtt
    provider_tool_message = next(message for message in provider.requests[1] if message.role == "tool")
    assert provider_tool_message.tool_result_value == canonical_xtt
    event = next(event for event in harness.project_chatbot_events(snapshot) if event.tool_name == "data.query")
    assert event.tool_result_value == canonical_xtt
    assert canonical_xtt in event.detail_blocks[0]["text"]


def test_paused_thread_admits_new_user_message_after_stop(monkeypatch, tmp_path: Path) -> None:
    """Stopping during a provider retry must not block the next User Message.

    A user-facing Stop abandons the provisional sampling placeholder, leaving a
    USER frontier.  The next submission re-enters from that frontier instead of
    failing with "the existing Client frontier must be sampled first".
    """

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    service = LLMConversationService(
        session_factory=context.session_factory,
        tool_registry=AgentToolRegistry(),
    )

    thread = service.create_thread().thread
    first = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="sub-1",
            content_blocks=[{"type": "text", "text": "First"}],
        )
    )
    first_id = first.messages[-1].id
    pending = service.begin_sampling(thread_id=thread.id, expected_frontier_id=first_id)

    # Simulate Stop: pause the Thread, then discard the provisional placeholder
    # the way the next provider admit would after a retry loop is interrupted.
    service.pause_thread(thread.id)
    service.cancel_sampling(pending.pending_message_id)

    claim = service.claim_user_submission(
        thread_id=thread.id,
        expected_frontier_id=first_id,
        client_submission_id="sub-2",
    )
    assert claim.existing_message_id is None
    second = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="sub-2",
            content_blocks=[{"type": "text", "text": "Second"}],
        ),
        expected_frontier_id=claim.expected_frontier_id,
    )
    assert [message.kind.value for message in second.messages] == ["user", "user"]
    context.engine.dispose()
