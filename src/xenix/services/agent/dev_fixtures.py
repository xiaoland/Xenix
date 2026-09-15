"""Development-only Conversation fixtures built through the public writer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...exceptions import ValidationError
from ..llm import ProviderResponse, ProviderToolCall
from ..llm.tool_protocol import AgentTool, ToolSuccess
from .harness_service import AgentHarnessService, SubmitUserTurnInput


class EmptyToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


MESSAGE_RENDERING_FIXTURE_TITLE = "Message rendering fixture"


class _FixtureProvider:
    def __init__(self) -> None:
        self._calls = 0

    def complete(self, _messages, _tools):
        self._calls += 1
        if self._calls == 1:
            return ProviderResponse(tool_calls=[ProviderToolCall(
                provider_call_id="fixture-call", tool_name="fixture.noop",
                provider_name="fixture_noop", arguments={},
            )])
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Fixture assistant response."}]
        )


def ensure_mock_conversation_history(harness: AgentHarnessService) -> None:
    """Append a small, canonical history without reaching into storage rows."""

    existing = [thread for thread in harness.list_threads() if thread.title == MESSAGE_RENDERING_FIXTURE_TITLE]
    if existing:
        return
    previous = harness._provider  # noqa: SLF001 - explicit fixture-only seam
    try:
        registry = harness._conversation_service.tool_registry  # noqa: SLF001 - explicit fixture-only seam
        try:
            registry.get("fixture.noop")
        except ValidationError:
            registry.register(AgentTool(
                name="fixture.noop",
                provider_name="fixture_noop",
                description="fixture",
                input_model=EmptyToolInput,
                implementation=lambda _arguments, _context: ToolSuccess({"fixture": True}),
            ))
        harness.set_provider(_FixtureProvider())
        harness.submit_user_turn(
            SubmitUserTurnInput(text="Render a fixture conversation", client_submission_id="fixture-submission")
        )
        thread = harness.list_threads()[0]
        harness.rename_thread(thread.id, MESSAGE_RENDERING_FIXTURE_TITLE)
        harness.submit_user_turn(SubmitUserTurnInput(text="A second fixture conversation"))
    finally:
        harness.set_provider(previous)
