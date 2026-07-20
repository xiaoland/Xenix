"""Headless composition coverage for the shared desktop/benchmark service graph."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.observability import NullLLMUsageObservability
from xenix.services.agent.composition import HeadlessAgentServices, build_headless_agent_services
from xenix.services.agent.skill_catalog import AgentSkill, AgentSkillCatalog
from xenix.services.llm import LLMService, LLMSettingsService
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
    assert {"data.clean", "agent.skill.activate", "agent.skill.read_reference"} <= tool_names
