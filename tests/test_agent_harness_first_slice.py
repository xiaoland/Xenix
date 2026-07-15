from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import NotFoundError
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    LLMConversationService,
    ProviderResponse,
    ProviderToolCall,
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
