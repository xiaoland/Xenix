from pathlib import Path
from types import SimpleNamespace

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    AppendUserMessageInput,
    LLMConversationService,
    ProviderResponse,
    ProviderToolCall,
)
from xenix.services.llm.tooling import (
    ToolFailure,
    canonical_tool_result_value,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    ConversationMessageKind,
    ConversationMessageRow,
    ConversationToolResultStatus,
)


class _TextProvider:
    def complete(self, _messages, _tools):
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])


class _SingleToolProvider:
    def __init__(self, tool_name: str = "test.tool", arguments: dict | None = None) -> None:
        self._tool_name = tool_name
        self._arguments = dict(arguments or {})

    def complete(self, _messages, _tools):
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="provider-call-1",
                    tool_name=self._tool_name,
                    provider_name=self._tool_name.replace(".", "_"),
                    arguments=dict(self._arguments),
                )
            ]
        )


def _conversation(monkeypatch, tmp_path: Path, registry: AgentToolRegistry | None = None) -> LLMConversationService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    return LLMConversationService(session_factory=context.session_factory, tool_registry=registry)


def _user_frontier(service: LLMConversationService) -> tuple[str, str]:
    thread = service.create_thread().thread
    snapshot = service.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.id,
            client_submission_id="submission-1",
            content_blocks=[{"type": "text", "text": "Run the tool."}],
        )
    )
    return thread.id, snapshot.messages[-1].id


def _registry(implementation) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="test.tool", provider_name="test_tool", description="test"),
        implementation,
    )
    return registry


def test_cancel_during_tool_callback_is_a_noop_at_the_revoked_capability(monkeypatch, tmp_path: Path) -> None:
    pending_id: list[str] = []
    service: LLMConversationService

    def _cancel_from_tool(_arguments, _context):
        service.cancel_sampling(pending_id[0])
        return {"ok": True}

    service = _conversation(monkeypatch, tmp_path, _registry(_cancel_from_tool))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )
    pending_id.append(pending.pending_message_id)

    result = service.invoke_staged_tool(
        pending_message_id=pending.pending_message_id,
        staged_call_message_id=pending.staged_calls[0].staged_call_id,
    )

    assert result is None
    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]
    resumed = service.begin_sampling(thread_id=thread_id, expected_frontier_id=frontier_id)
    service.cancel_sampling(resumed.pending_message_id)


def test_result_budget_failure_discards_the_pending_placeholder(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path, _registry(lambda _arguments, _context: {"ok": True}))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )
    monkeypatch.setattr("xenix.services.llm.conversation.MAX_EXCHANGE_RESULT_BYTES", 1)

    with pytest.raises(ValidationError, match="exceeds its byte limit"):
        service.invoke_staged_tool(
            pending_message_id=pending.pending_message_id,
            staged_call_message_id=pending.staged_calls[0].staged_call_id,
        )

    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]
    resumed = service.begin_sampling(thread_id=thread_id, expected_frontier_id=frontier_id)
    service.cancel_sampling(resumed.pending_message_id)


def test_finalization_failure_discards_the_pending_placeholder(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_TextProvider(),
    )

    def _fail_final_rows(*_args, **_kwargs):
        raise RuntimeError("forced storage preparation failure")

    monkeypatch.setattr(service, "_final_message_rows", _fail_final_rows)
    with pytest.raises(RuntimeError, match="forced storage preparation failure"):
        service.finalize_pending_assistant(pending.pending_message_id)

    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]
    resumed = service.begin_sampling(thread_id=thread_id, expected_frontier_id=frontier_id)
    service.cancel_sampling(resumed.pending_message_id)


def test_tool_exception_is_a_typed_and_bounded_canonical_failure(monkeypatch, tmp_path: Path) -> None:
    def _raise_sensitive_error(_arguments, _context):
        error = RuntimeError(r"F:\\private\\dataset.csv: " + "x" * 10_000)
        error.error_code = "forged_public_error"
        error.error_details = {"api_token": "credential-must-not-persist"}
        error.repair_hints = ["Open F:\\private\\dataset.csv."]
        error.retryable = True
        raise error

    service = _conversation(monkeypatch, tmp_path, _registry(_raise_sensitive_error))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )

    final = service.invoke_staged_tool(
        pending_message_id=pending.pending_message_id,
        staged_call_message_id=pending.staged_calls[0].staged_call_id,
    )

    assert final is not None
    result = next(message for message in final.messages if message.kind.value == "tool_result")
    assert result.error_summary is None
    assert result.value_payload == {
        "type": "tool_failure",
        "code": "tool_execution_failed",
        "message": "Tool execution failed.",
    }
    assert r"F:\\private" not in str(result.value_payload)
    assert "credential-must-not-persist" not in str(result.value_payload)


def test_direct_tool_failure_is_persisted_without_a_second_summary(monkeypatch, tmp_path: Path) -> None:
    failure = ToolFailure(
        code="invalid_query",
        message="The selected SQL expression is invalid.",
        details={"sql": "SELECT * FROM missing"},
        repair_hints=("Select an existing relation.",),
        retryable=False,
    )
    service = _conversation(monkeypatch, tmp_path, _registry(lambda _arguments, _context: failure))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )

    final = service.invoke_staged_tool(
        pending_message_id=pending.pending_message_id,
        staged_call_message_id=pending.staged_calls[0].staged_call_id,
    )

    assert final is not None
    result = next(message for message in final.messages if message.kind.value == "tool_result")
    assert result.error_summary is None
    assert result.value_payload == failure.to_value()


def test_legacy_failed_result_keeps_public_allowlisted_detail() -> None:
    value = canonical_tool_result_value(
        value={"sql": "SELECT * FROM missing"},
        failed=True,
        legacy_error_summary="Tool execution failed.",
    )

    assert value == {
        "type": "tool_failure",
        "code": "legacy_tool_failure",
        "message": "Tool execution failed.",
        "details": {"sql": "SELECT * FROM missing"},
    }


def test_legacy_failed_result_drops_private_summary_and_details() -> None:
    private_values = (
        r"F:\private\customers.csv",
        "https://internal.example/tool-result",
        "legacy-credential-value",
        "legacy-password-value",
        "legacy-token-value",
        "legacy-secret-value",
    )
    value = canonical_tool_result_value(
        value={
            "sql": "SELECT * FROM missing",
            "source_path": private_values[0],
            "result_uri": private_values[1],
            "credential": private_values[2],
            "password": private_values[3],
            "api_token": private_values[4],
            "secret": private_values[5],
        },
        failed=True,
        legacy_error_summary=(
            f"Failure at {private_values[0]}; see {private_values[1]}; "
            f"credential={private_values[2]}; password={private_values[3]}; "
            f"token={private_values[4]}; secret={private_values[5]}."
        ),
    )

    assert value == {
        "type": "tool_failure",
        "code": "legacy_tool_failure",
        "message": "Tool execution failed.",
    }
    projected = str(value)
    assert all(private_value not in projected for private_value in private_values)


def test_reopened_legacy_failure_projects_one_safe_value_without_rewriting_row(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread = service.create_thread().thread
    private_summary = r"Query failed at F:\private\customers.csv with token=legacy-token-value."
    legacy_details = {"sql": "SELECT * FROM customer_missing"}
    call = ConversationMessageRow(
        id="legacy-call",
        thread_id=thread.id,
        sequence_index=0,
        kind=ConversationMessageKind.TOOL_CALL,
        provider_call_id="legacy-provider-call",
        tool_id="data.query",
        arguments_payload={"sql": "SELECT * FROM customer_missing"},
        content_payload={"tool_name": "data.query", "provider_name": "data_query"},
    )
    result = ConversationMessageRow(
        id="legacy-result",
        thread_id=thread.id,
        sequence_index=1,
        kind=ConversationMessageKind.TOOL_RESULT,
        tool_call_message_id=call.id,
        result_status=ConversationToolResultStatus.FAILED,
        value_payload=legacy_details,
        error_summary=private_summary,
    )
    with service._session_factory() as session:  # type: ignore[union-attr]
        session.add(call)
        session.flush()
        session.add(result)
        session.commit()

    reopened_conversation = LLMConversationService(session_factory=service._session_factory)
    reopened_harness = AgentHarnessService(conversation_service=reopened_conversation)
    reopened = reopened_harness.get_thread_snapshot(thread.id)
    provider_message = next(
        message
        for message in reopened_conversation._provider_messages(reopened)  # noqa: SLF001 - replay boundary
        if message.role == "tool"
    )
    chatbot_event = next(
        event
        for event in reopened_harness.project_chatbot_events(reopened)
        if event.tool_call_id == call.id
    )
    expected = {
        "type": "tool_failure",
        "code": "legacy_tool_failure",
        "message": "Tool execution failed.",
        "details": legacy_details,
    }

    assert provider_message.tool_result_value == expected
    assert chatbot_event.tool_result_value == expected
    assert private_summary not in str(provider_message)
    assert private_summary not in str(chatbot_event)
    with service._session_factory() as session:  # type: ignore[union-attr]
        persisted = session.get(ConversationMessageRow, result.id)
        assert persisted is not None
        assert persisted.error_summary == private_summary
        assert persisted.value_payload == legacy_details


def test_conversation_recognizes_a_string_legacy_failed_status() -> None:
    value = LLMConversationService._canonical_tool_result_value(  # noqa: SLF001 - compatibility boundary
        SimpleNamespace(
            result_status="failed",
            value_payload=None,
            error_summary="Historical tool failure.",
        )
    )

    assert value == {
        "type": "tool_failure",
        "code": "legacy_tool_failure",
        "message": "Historical tool failure.",
    }


def test_validation_error_diagnostics_are_preserved_in_tool_failure(monkeypatch, tmp_path: Path) -> None:
    def invalid_tool(_arguments, _context):
        raise ValidationError(
            "DuckDB Binder Error: table customer_missing does not exist.",
            error_code="data_query_invalid",
            error_details={"sql": "SELECT * FROM customer_missing"},
            repair_hints=["Use a registered dataset alias."],
            retryable=False,
        )

    service = _conversation(monkeypatch, tmp_path, _registry(invalid_tool))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )

    final = service.invoke_staged_tool(
        pending_message_id=pending.pending_message_id,
        staged_call_message_id=pending.staged_calls[0].staged_call_id,
    )

    assert final is not None
    result = next(message for message in final.messages if message.kind.value == "tool_result")
    assert result.value_payload == {
        "type": "tool_failure",
        "code": "data_query_invalid",
        "message": "DuckDB Binder Error: table customer_missing does not exist.",
        "details": {"sql": "SELECT * FROM customer_missing"},
        "repair_hints": ["Use a registered dataset alias."],
        "retryable": False,
    }


def test_validation_error_with_private_diagnostics_is_persisted_as_opaque_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    private_path = r"F:\private\customers.csv"
    credential = "api-token-must-not-persist"

    def invalid_tool(_arguments, _context):
        raise ValidationError(
            f"Dataset failed at {private_path}",
            error_code="data_query_invalid",
            error_details={"source_path": private_path, "api_token": credential},
            repair_hints=[f"Retry with {credential}."],
            retryable=True,
        )

    service = _conversation(monkeypatch, tmp_path, _registry(invalid_tool))
    thread_id, frontier_id = _user_frontier(service)
    pending = service.sample_existing_frontier(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
        provider=_SingleToolProvider(),
    )

    final = service.invoke_staged_tool(
        pending_message_id=pending.pending_message_id,
        staged_call_message_id=pending.staged_calls[0].staged_call_id,
    )

    assert final is not None
    result = next(message for message in final.messages if message.kind.value == "tool_result")
    assert result.value_payload == {
        "type": "tool_failure",
        "code": "tool_validation_failed",
        "message": "Tool input is invalid.",
        "retryable": False,
    }
    persisted = str(result.value_payload)
    assert private_path not in persisted
    assert credential not in persisted


def test_schema_invalid_provider_call_is_rejected_before_staging_or_invocation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict] = []
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="test.tool",
            provider_name="test_tool",
            description="test",
            parameters_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        lambda arguments, _context: calls.append(arguments) or {"ok": True},
    )
    service = _conversation(monkeypatch, tmp_path, registry)
    thread_id, frontier_id = _user_frontier(service)
    with pytest.raises(ValidationError) as exc_info:
        service.sample_existing_frontier(
            thread_id=thread_id,
            expected_frontier_id=frontier_id,
            provider=_SingleToolProvider(
                arguments={"query": "rules", "private_token": "must-not-persist"}
            ),
        )

    assert exc_info.value.error_code == "llm_tool_arguments_invalid"
    assert exc_info.value.error_details == {"schema_keyword": "additionalProperties"}
    assert calls == []
    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]
    assert "must-not-persist" not in str(exc_info.value)


def test_abandoning_a_service_stream_after_thinking_discards_pending(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    thread_id, frontier_id = _user_frontier(service)
    stream = service.sample_existing_frontier_stream(
        thread_id=thread_id,
        expected_frontier_id=frontier_id,
    )

    started = next(stream)
    stream.close()

    assert started.kind == "sampling_started"
    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]


def test_abandoning_a_harness_stream_after_thinking_discards_pending(monkeypatch, tmp_path: Path) -> None:
    service = _conversation(monkeypatch, tmp_path)
    harness = AgentHarnessService(conversation_service=service, provider=_TextProvider())
    stream = harness.submit_user_turn_stream(SubmitUserTurnInput(text="Stop after thinking."))

    first = next(stream)
    thinking = next(stream)
    stream.close()

    assert first.snapshot is not None
    assert thinking.kind == "thinking"
    assert [message.kind.value for message in service.get_thread_snapshot(first.snapshot.thread.id).messages] == ["user"]
