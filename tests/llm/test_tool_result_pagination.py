from __future__ import annotations

import os
from pathlib import Path

import pytest

from xenix.exceptions import ValidationError
from xenix.services.llm.tool_result_page_store import ToolResultPageStore
from xenix.services.llm.tooling import (
    AgentToolRegistry,
    AgentToolSpec,
    ToolExecutionContext,
    ToolSuccess,
    tool_failure_from_exception,
)


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(thread_id="thread-1", tool_call_message_id="call-1")


def _registry(tmp_path: Path) -> AgentToolRegistry:
    return AgentToolRegistry(paged_results_dir=tmp_path / "pages")


def test_store_saves_and_pages_by_codepoint(tmp_path: Path) -> None:
    store = ToolResultPageStore(tmp_path / "pages")
    text = "中文" * 2500  # 5000 Unicode code points
    result_id = store.save(thread_id="t1", tool_call_message_id="m1", text=text)

    first = store.read_page(result_id, offset=0, limit=1024)
    assert first.text == text[:1024]
    assert first.total_chars == len(text)
    assert first.has_more is True

    tail = store.read_page(result_id, offset=len(text) - 1024, limit=1024)
    assert tail.text == text[len(text) - 1024 :]
    assert tail.has_more is False


def test_store_rejects_unknown_or_malformed_id(tmp_path: Path) -> None:
    store = ToolResultPageStore(tmp_path / "pages")
    with pytest.raises(ValidationError):
        store.read_page("../../etc/passwd", offset=0, limit=10)
    with pytest.raises(ValidationError):
        store.read_page("0" * 32, offset=0, limit=10)


def test_store_delete_for_thread_and_gc(tmp_path: Path) -> None:
    store = ToolResultPageStore(tmp_path / "pages")
    store.save(thread_id="keep", tool_call_message_id=None, text="a" * 10)
    doomed = store.save(thread_id="drop", tool_call_message_id=None, text="b" * 10)

    assert store.delete_for_thread("drop") == 1
    with pytest.raises(ValidationError):
        store.read_page(doomed, offset=0, limit=10)

    old = store.save(thread_id="keep", tool_call_message_id=None, text="c" * 10)
    os.utime(tmp_path / "pages" / f"{old}.txt", (0, 0))
    assert store.collect_garbage(max_age_seconds=1) >= 1


def test_invoke_returns_small_result_inline(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.register(
        AgentToolSpec(name="data.small", provider_name="data_small", description="small"),
        lambda _args, _ctx: ToolSuccess(value={"ok": True}),
    )
    outcome = registry.invoke(
        tool_name="data.small",
        provider_name="data_small",
        arguments={},
        context=_context(),
    )
    assert isinstance(outcome, ToolSuccess)
    assert outcome.value == {"ok": True}


def test_inline_boundary_is_2048_chars(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.register(
        AgentToolSpec(name="data.inline", provider_name="data_inline", description="inline"),
        lambda _args, _ctx: ToolSuccess(value="x" * 2048),
    )
    registry.register(
        AgentToolSpec(name="data.paged", provider_name="data_paged", description="paged"),
        lambda _args, _ctx: ToolSuccess(value="y" * 2049),
    )
    inline = registry.invoke(
        tool_name="data.inline",
        provider_name="data_inline",
        arguments={},
        context=_context(),
    )
    assert isinstance(inline, ToolSuccess)
    assert inline.value == "x" * 2048

    paged = registry.invoke(
        tool_name="data.paged",
        provider_name="data_paged",
        arguments={},
        context=_context(),
    )
    assert isinstance(paged, ToolSuccess)
    assert "result_id" in paged.value


def test_invoke_pages_oversized_result_and_reads_next_page(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    large = "x" * 5000
    registry.register(
        AgentToolSpec(name="data.big", provider_name="data_big", description="big"),
        lambda _args, _ctx: ToolSuccess(value=large),
    )
    outcome = registry.invoke(
        tool_name="data.big",
        provider_name="data_big",
        arguments={},
        context=_context(),
    )
    assert isinstance(outcome, ToolSuccess)
    value = outcome.value
    assert value["total_chars"] == len(large)
    assert value["offset"] == 0
    assert value["page_size"] == 1024
    assert value["has_more"] is True
    assert value["text"] == large[:1024]

    page = registry.invoke(
        tool_name="result.page",
        provider_name="result_page",
        arguments={"result_id": value["result_id"], "offset": 1024, "limit": 1024},
        context=_context(),
    )
    assert isinstance(page, ToolSuccess)
    assert page.value["text"] == large[1024:2048]
    assert page.value["has_more"] is True
    assert page.value["total_chars"] == len(large)


def test_invoke_without_store_rejects_oversized_result(tmp_path: Path) -> None:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(name="data.big", provider_name="data_big", description="big"),
        lambda _args, _ctx: ToolSuccess(value="x" * 3000),
    )
    with pytest.raises(ValidationError):
        registry.invoke(
            tool_name="data.big",
            provider_name="data_big",
            arguments={},
            context=_context(),
        )


def test_tool_failure_preserves_unexpected_exception_message() -> None:
    failure = tool_failure_from_exception(RuntimeError("File C:\\data\\missing.csv was not found."))
    assert failure.code == "tool_execution_failed"
    assert failure.message == "File C:\\data\\missing.csv was not found."


def test_tool_failure_preserves_validation_details_and_hints() -> None:
    exc = ValidationError(
        "Column 'amount' is not numeric.",
        error_code="data_column_not_numeric",
        error_details={"field": "amount"},
        repair_hints=["Select a numeric column."],
    )
    failure = tool_failure_from_exception(exc)
    assert failure.code == "data_column_not_numeric"
    assert failure.message == "Column 'amount' is not numeric."
    assert failure.details == {"field": "amount"}
    assert failure.repair_hints == ("Select a numeric column.",)
