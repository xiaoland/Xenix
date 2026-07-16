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
    MAX_TOOL_FAILURE_MESSAGE_CHARS,
    ToolFailure,
    canonical_tool_result_value,
)
from xenix.services.storage import StorageBootstrapService


class _TextProvider:
    def complete(self, _messages, _tools):
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])


class _SingleToolProvider:
    def __init__(self, tool_name: str = "test.tool") -> None:
        self._tool_name = tool_name

    def complete(self, _messages, _tools):
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="provider-call-1",
                    tool_name=self._tool_name,
                    provider_name=self._tool_name.replace(".", "_"),
                    arguments={},
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
        raise RuntimeError(r"F:\\private\\dataset.csv: " + "x" * 10_000)

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
    assert result.value_payload["type"] == "tool_failure"
    assert result.value_payload["code"] == "tool_execution_failed"
    assert r"F:\\private" in result.value_payload["message"]
    assert result.value_payload["details"] == {"exception_type": "RuntimeError"}
    assert len(result.value_payload["message"]) <= MAX_TOOL_FAILURE_MESSAGE_CHARS


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


def test_legacy_failed_result_keeps_a_bounded_diagnostic_value_as_typed_failure_detail() -> None:
    value = canonical_tool_result_value(
        value={"error_code": "old_query_error", "sql": "SELECT * FROM missing"},
        failed=True,
        legacy_error_summary="Tool execution failed.",
    )

    assert value == {
        "type": "tool_failure",
        "code": "legacy_tool_failure",
        "message": "Tool execution failed.",
        "details": {"error_code": "old_query_error", "sql": "SELECT * FROM missing"},
    }


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


def test_invalid_tool_scope_is_rejected_before_creating_pending(monkeypatch, tmp_path: Path) -> None:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="test.invalid-schema",
            provider_name="test_invalid_schema",
            description="invalid test schema",
            parameters_schema={"not_json": {1}},
        ),
        lambda _arguments, _context: {"ok": True},
    )
    service = _conversation(monkeypatch, tmp_path, registry)
    thread_id, frontier_id = _user_frontier(service)

    with pytest.raises(ValidationError, match="not JSON serializable"):
        service.begin_sampling(thread_id=thread_id, expected_frontier_id=frontier_id)

    assert [message.kind.value for message in service.get_thread_snapshot(thread_id).messages] == ["user"]
