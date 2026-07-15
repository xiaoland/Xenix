from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.llm import AgentToolRegistry, LLMConversationService, ProviderResponse
from xenix.services.storage import StorageBootstrapService


class UsageProvider:
    def complete(self, _messages, _tools):
        return ProviderResponse(
            assistant_content_blocks=[{"type": "text", "text": "Done."}],
            usage_payload={"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
        )


def test_provider_usage_is_not_part_of_canonical_conversation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=context.session_factory, tool_registry=AgentToolRegistry(),
        ),
        provider=UsageProvider(),
    )

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Analyze this"))

    assert [message.kind.value for message in snapshot.messages] == ["user", "assistant"]
    assert all("usage" not in message.content_payload for message in snapshot.messages)
