"""Headless composition coverage for the shared desktop/benchmark service graph."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.observability import NullLLMUsageObservability
from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.agent.composition import HeadlessAgentServices, build_headless_agent_services
from xenix.services.agent.skill_catalog import AgentSkill, AgentSkillCatalog
from xenix.services.llm import (
    AgentToolRegistry,
    AgentToolSpec,
    LLMConversationService,
    LLMService,
    LLMSettingsService,
    ProviderResponse,
    ProviderToolCall,
    ToolSuccess,
)
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.storage import StorageBootstrapService


def test_headless_composition_module_imports_without_pyside() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    program = (
        "import importlib, sys; "
        f"sys.path.insert(0, {str(source_root)!r}); "
        "importlib.import_module('xenix.services.agent.composition'); "
        "from xenix.services.agent import HeadlessAgentServices, build_headless_agent_services; "
        "assert 'xenix.app' not in sys.modules; "
        "assert not any(name == 'PySide6' or name.startswith('PySide6.') for name in sys.modules)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_desktop_runtime_loads_the_shared_builder_lazily() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    program = (
        "import sys; "
        f"sys.path.insert(0, {str(source_root)!r}); "
        "import xenix.app as app; "
        "assert 'xenix.services.agent.composition' not in sys.modules; "
        "runtime = app._load_runtime_imports(); "
        "from xenix.services.agent.composition import build_headless_agent_services; "
        "assert runtime.build_headless_agent_services is build_headless_agent_services"
    )

    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_builder_wires_real_llm_graph_without_an_injected_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "runtime"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    llm = LLMService(LLMSettingsService(paths))
    worker_settings = MLWorkerSettingsService(paths)
    usage_observability = NullLLMUsageObservability()
    catalog = AgentSkillCatalog(
        [
            AgentSkill(
                name="composition-test-skill",
                description="Proves Skill registration in the shared graph.",
                body="Use the composition test skill only when it is relevant.",
                resources={"references": {"references/guide.md": "bounded guide"}, "assets": {}},
            )
        ]
    )
    monkeypatch.setattr(
        AgentSkillCatalog,
        "from_default_catalog",
        classmethod(lambda _cls: catalog),
    )

    services = build_headless_agent_services(
        paths=paths,
        session_factory=storage.session_factory,
        llm=llm,
        ml_worker_settings=worker_settings,
        usage_observability=usage_observability,
    )

    assert isinstance(services, HeadlessAgentServices)
    assert services.llm is llm
    assert services.harness._provider is None  # noqa: SLF001 - real gateway boundary
    assert services.harness._llm_service is llm  # noqa: SLF001 - graph identity
    assert services.harness._dataset_service is services.datasets  # noqa: SLF001 - graph identity

    conversation = services.harness._conversation_service  # noqa: SLF001 - graph identity
    assert conversation._llm_service is llm  # noqa: SLF001 - graph identity
    assert conversation._usage_observability is usage_observability  # noqa: SLF001 - graph identity
    tool_names = {spec.name for spec in conversation.tool_registry.list_specs()}
    assert {
        "data.clean",
        "knowledge.lookup",
        "agent.skill.activate",
        "agent.skill.read_reference",
    } <= tool_names
    knowledge_spec = next(
        spec
        for spec in conversation.tool_registry.list_specs()
        if spec.name == "knowledge.lookup"
    )
    assert knowledge_spec.provider_name == "knowledge_lookup"
    assert set(knowledge_spec.parameters_schema["properties"]) == {"query", "mode"}


class _KnowledgeThenTextProvider:
    def __init__(self) -> None:
        self.requests = []
        self.tool_specs = []

    def complete(self, messages, tools):
        self.requests.append(list(messages))
        self.tool_specs.append(list(tools))
        if len(self.requests) == 1:
            return ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="knowledge-call-1",
                        tool_name="knowledge.lookup",
                        provider_name="knowledge_lookup",
                        arguments={"query": "雨具补货规则", "mode": "auto"},
                    )
                ]
            )
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "完成。"}])


class _TextCaptureProvider:
    def __init__(self) -> None:
        self.requests = []

    def complete(self, messages, _tools):
        self.requests.append(list(messages))
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "继续完成。"}])


def test_production_knowledge_lookup_keeps_one_value_across_reload_provider_and_chatbot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "runtime"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    llm = LLMService(LLMSettingsService(paths))
    worker_settings = MLWorkerSettingsService(paths)
    usage_observability = NullLLMUsageObservability()
    services = build_headless_agent_services(
        paths=paths,
        session_factory=storage.session_factory,
        llm=llm,
        ml_worker_settings=worker_settings,
        usage_observability=usage_observability,
    )
    services.knowledge.index_plain_text(
        title="华东备货规则",
        text="雨具目标库存为三周平均销量，补货量扣除现有库存。",
    )
    provider = _KnowledgeThenTextProvider()
    services.harness.set_provider(provider)
    thread = services.harness.create_thread(title="Knowledge continuity")

    snapshot = services.harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread.thread.id,
            text="请应用知识库规则分析补货。",
            client_submission_id="knowledge-continuity-1",
        )
    )

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
    advertised = [spec for spec in provider.tool_specs[0] if spec.name == "knowledge.lookup"]
    assert len(advertised) == 1
    result = next(message for message in snapshot.messages if message.kind.value == "tool_result")
    assert result.value_payload == expected
    first_replay = next(message for message in provider.requests[1] if message.role == "tool")
    assert first_replay.tool_result_value == expected

    reopened_services = build_headless_agent_services(
        paths=paths,
        session_factory=storage.session_factory,
        llm=llm,
        ml_worker_settings=worker_settings,
        usage_observability=usage_observability,
    )
    reopened = reopened_services.harness.get_thread_snapshot(snapshot.thread.id)
    reopened_result = next(message for message in reopened.messages if message.kind.value == "tool_result")
    assert reopened_result.value_payload == expected
    event = next(
        event
        for event in reopened_services.harness.project_chatbot_events(reopened)
        if event.tool_name == "knowledge.lookup"
    )
    assert event.tool_result_value == expected

    capture = _TextCaptureProvider()
    reopened_services.harness.set_provider(capture)
    reopened_services.harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=snapshot.thread.id,
            text="请继续。",
            client_submission_id="knowledge-continuity-2",
        )
    )
    reopened_provider_value = next(
        message.tool_result_value
        for message in capture.requests[0]
        if message.role == "tool"
    )
    assert reopened_provider_value == expected


def test_historical_knowledge_result_is_not_rewritten_by_production_composition(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "runtime"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    legacy_value = {
        "query": "雨具补货规则",
        "mode_used": "keyword",
        "matches": [
            {
                "citation_id": "knowledge:legacy-unit",
                "document_id": "legacy-document",
                "document_generation_id": "legacy-generation",
                "source_artifact_id": None,
                "unit_id": "legacy-unit",
                "title": "历史备货规则",
                "locator": {"passage": 1},
                "quote": "雨具按三周平均需求补货。",
            }
        ],
    }
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="knowledge.lookup",
            provider_name="knowledge_lookup",
            description="Historical Knowledge Tool contract.",
        ),
        lambda _arguments, _context: ToolSuccess(value=legacy_value),
    )
    legacy_provider = _KnowledgeThenTextProvider()
    legacy_harness = AgentHarnessService(
        conversation_service=LLMConversationService(
            session_factory=storage.session_factory,
            tool_registry=registry,
        ),
        provider=legacy_provider,
    )
    thread = legacy_harness.create_thread(title="Historical Knowledge result")
    historical = legacy_harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread.thread.id,
            text="使用历史知识结果。",
            client_submission_id="legacy-knowledge-1",
        )
    )
    assert next(
        message.value_payload
        for message in historical.messages
        if message.kind.value == "tool_result"
    ) == legacy_value

    llm = LLMService(LLMSettingsService(paths))
    production = build_headless_agent_services(
        paths=paths,
        session_factory=storage.session_factory,
        llm=llm,
        ml_worker_settings=MLWorkerSettingsService(paths),
        usage_observability=NullLLMUsageObservability(),
    )
    reopened = production.harness.get_thread_snapshot(historical.thread.id)
    assert next(
        message.value_payload
        for message in reopened.messages
        if message.kind.value == "tool_result"
    ) == legacy_value
    event = next(
        event
        for event in production.harness.project_chatbot_events(reopened)
        if event.tool_name == "knowledge.lookup"
    )
    assert event.tool_result_value == legacy_value

    capture = _TextCaptureProvider()
    production.harness.set_provider(capture)
    production.harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=historical.thread.id,
            text="继续。",
            client_submission_id="legacy-knowledge-2",
        )
    )
    assert next(
        message.tool_result_value
        for message in capture.requests[0]
        if message.role == "tool"
    ) == legacy_value
