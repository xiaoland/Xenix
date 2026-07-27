from pathlib import Path
from types import SimpleNamespace

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.knowledge_tool import register_knowledge_lookup_tool
from xenix.services.knowledge_service import (
    KnowledgeRetrievalResult,
    KnowledgeRetrievalUnavailable,
    KnowledgeService,
)
from xenix.services.llm import AgentToolRegistry, ToolExecutionContext, ToolFailure, ToolSuccess
from xenix.services.storage import StorageBootstrapService
from tests.knowledge_test_support import seed_knowledge_text


def _registry(monkeypatch, tmp_path: Path) -> tuple[AgentToolRegistry, KnowledgeService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    service = KnowledgeService(context.session_factory)
    registry = AgentToolRegistry()
    register_knowledge_lookup_tool(registry, service)
    return registry, service


def _invoke_service(service, arguments: dict) -> ToolSuccess | ToolFailure:
    registry = AgentToolRegistry()
    register_knowledge_lookup_tool(registry, service)
    return registry.invoke(
        tool_name="knowledge.lookup",
        provider_name="knowledge_lookup",
        arguments=arguments,
        context=ToolExecutionContext(thread_id="thread-1"),
    )


def test_lookup_tool_returns_one_minimal_value_for_auto_and_keyword(monkeypatch, tmp_path: Path) -> None:
    registry, service = _registry(monkeypatch, tmp_path)
    seed_knowledge_text(service,
        title="华东备货规则",
        text="雨具目标库存为三周平均销量，补货量扣除现有库存。",
    )

    outcomes = [
        registry.invoke(
            tool_name="knowledge.lookup",
            provider_name="knowledge_lookup",
            arguments=arguments,
            context=ToolExecutionContext(thread_id="thread-1"),
        )
        for arguments in (
            {"query": "雨具补货"},
            {"query": "雨具补货", "mode": "keyword"},
        )
    ]

    expected = {
        "mode": "keyword",
        "results": [
            {
                "source": "华东备货规则",
                "location": "passage 1",
                "excerpt": "雨具目标库存为三周平均销量，补货量扣除现有库存。",
            }
        ],
    }
    assert all(isinstance(outcome, ToolSuccess) for outcome in outcomes)
    assert [outcome.value for outcome in outcomes if isinstance(outcome, ToolSuccess)] == [
        expected,
        expected,
    ]


def test_lookup_tool_empty_result_is_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    registry, _service = _registry(monkeypatch, tmp_path)
    context = ToolExecutionContext(thread_id="thread-1")

    empty = registry.invoke(
        tool_name="knowledge.lookup",
        provider_name="knowledge_lookup",
        arguments={"query": "不存在的规则"},
        context=context,
    )
    assert isinstance(empty, ToolSuccess)
    assert empty.value == {"mode": "keyword", "results": []}


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_lookup_tool_reports_unavailable_modes_without_keyword_fallback(mode: str) -> None:
    class _NeverLookup:
        def retrieve(self, _query: str, **_kwargs):
            raise KnowledgeRetrievalUnavailable(
                requested_mode=mode,
                available_modes=["keyword"],
            )

    outcome = _invoke_service(_NeverLookup(), {"query": "雨季规则", "mode": mode})

    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "knowledge_retrieval_mode_unavailable"
    assert outcome.details == {
        "requested_mode": mode,
        "available_modes": ["keyword"],
    }
    assert outcome.repair_hints == ("Use 'auto' or 'keyword' for this lookup.",)
    assert outcome.retryable is False


@pytest.mark.parametrize(
    "private_path",
    [
        r"F:\private\rules.pdf",
        "../../private/rules.pdf",
        "~/private/rules.pdf",
        "private/secrets/rules.pdf",
        "https://example.invalid/private/rules.pdf?token=secret",
    ],
)
def test_lookup_tool_allowlists_location_and_sanitizes_failures(private_path: str) -> None:
    class _UnsafeMatchService:
        def retrieve(self, _query: str, **_kwargs):
            return KnowledgeRetrievalResult(
                mode="keyword",
                matches=[
                    SimpleNamespace(
                        title=private_path,
                        locator={"path": private_path, "page": 2},
                        quote="雨具补货使用三周平均需求。",
                    )
                ],
            )

    success = _invoke_service(_UnsafeMatchService(), {"query": "雨具补货"})

    assert isinstance(success, ToolSuccess)
    assert success.value == {
        "mode": "keyword",
        "results": [
            {
                "source": "rules.pdf",
                "location": "page 2",
                "excerpt": "雨具补货使用三周平均需求。",
            }
        ],
    }
    assert private_path not in str(success.value)

    class _BrokenService:
        def retrieve(self, _query: str, **_kwargs):
            raise RuntimeError(f"database failed at {private_path}")

    failure = _invoke_service(_BrokenService(), {"query": "雨具补货"})

    assert isinstance(failure, ToolFailure)
    assert failure.code == "knowledge_lookup_failed"
    assert private_path not in str(failure.to_value())
