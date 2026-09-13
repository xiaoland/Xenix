from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

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
from xenix.services.llm.tooling import AgentTool


def test_harness_returns_invalid_arguments_to_model_for_repair(storage) -> None:
    class InspectInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        row_limit: int

    executed = []
    registry = AgentToolRegistry()
    registry.register(AgentTool(
        name="data.inspect", provider_name="data_inspect", description="inspect",
        input_model=InspectInput,
        implementation=lambda arguments, _context: (
            executed.append(arguments.row_limit) or ToolSuccess(value={"rows": arguments.row_limit})
        ),
    ))

    class RepairingProvider:
        calls = 0

        def complete(self, messages, _tools):
            self.calls += 1
            if self.calls == 2:
                failure = messages[-1].tool_result_value
                assert failure["type"] == "tool_failure"
                assert failure["details"]["validation_errors"][0]["field"] == "row_limit"
            if self.calls <= 2:
                return ProviderResponse(tool_calls=[ProviderToolCall(
                    provider_call_id=f"inspect-{self.calls}", tool_name="data.inspect",
                    provider_name="data_inspect",
                    arguments={"row_limit": "invalid" if self.calls == 1 else 3},
                )])
            return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])

    provider = RepairingProvider()
    harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=storage.session_factory, tool_registry=registry,
        ),
        provider=provider,
    )
    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Inspect three rows"))
    assert executed == [3]
    assert provider.calls == 3
    assert [message.kind.value for message in snapshot.messages] == [
        "user", "tool_call", "tool_result", "tool_call", "tool_result", "assistant",
    ]
    assert snapshot.messages[2].value_payload["type"] == "tool_failure"
    assert snapshot.messages[4].value_payload == {"rows": 3}


def test_paged_skill_activation_unlocks_tools_and_survives_history_reload(storage, tmp_path):
    from dataclasses import replace
    from xenix.services.agent.composition import (
        agent_skill_activated_skill_names, agent_skill_context_messages,
        agent_skill_tool_scope_names, register_agent_skill_tools,
    )
    from xenix.services.agent.skill_catalog import AgentSkillCatalog

    registry = AgentToolRegistry(paged_results_dir=tmp_path / "pages")
    catalog = AgentSkillCatalog([
        replace(skill, body=skill.body + "\nExtended instructions. " * 4000)
        for skill in AgentSkillCatalog.from_default_catalog().list_skills()
    ])
    executed = []
    for name in ("data.query", "data.transform"):
        registry.register(
            AgentToolSpec(name=name, provider_name=name.replace(".", "_"), description=name),
            lambda _args, context: executed.append(context.tool_call_message_id) or ToolSuccess({"ok": True}),
        )
    conversation = LLMConversationService(
        session_factory=storage.session_factory, tool_registry=registry,
        context_messages_provider=lambda snapshot: agent_skill_context_messages(catalog, snapshot),
    )
    register_agent_skill_tools(registry, catalog, activated_skill_names_provider=lambda thread_id:
        agent_skill_activated_skill_names(conversation.get_thread_snapshot(thread_id)))

    class Provider:
        calls = 0
        page_id = None

        def complete(self, messages, tools):
            self.calls += 1
            names = {tool.name for tool in tools}
            assert "result.page" in names
            if self.calls == 1:
                assert "data.query" not in names
                name, arguments = "agent.skill.activate", {"name": "xenix-data-analysis"}
            elif self.calls == 2:
                assert {"data.query", "data.transform"} <= names
                page = messages[-1].tool_result_value
                self.page_id = page["result_id"]
                name, arguments = "result.page", {"result_id": self.page_id, "offset": 1024, "limit": 4096}
            elif self.calls == 3:
                assert messages[-1].tool_result_value["result_id"] == self.page_id
                assert messages[-1].tool_result_value["offset"] == 1024
                name, arguments = "data.query", {}
            else:
                return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])
            return ProviderResponse(tool_calls=[ProviderToolCall(
                provider_call_id=f"call-{self.calls}", tool_name=name,
                provider_name=name.replace(".", "_"), arguments=arguments,
            )])

    harness = AgentHarnessService(
        conversation_service=conversation, provider=Provider(),
        tool_name_scope_provider=agent_skill_tool_scope_names,
    )
    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="分析数据"))
    reloaded = conversation.get_thread_snapshot(snapshot.thread.id)
    assert agent_skill_activated_skill_names(reloaded) == {"xenix-data-analysis"}
    assert "data.transform" in agent_skill_tool_scope_names(reloaded)
    assert executed == [snapshot.messages[-3].id]


class ToolThenTextProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[ProviderToolCall(
                    provider_call_id="provider-call-1", tool_name="data.inspect",
                    provider_name="data_inspect", arguments={"dataset_id": 101},
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
    assert result.value_payload == {"dataset_id": 101, "ok": True}
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
