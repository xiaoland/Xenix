"""Headless composition root for the Agent service graph.

The caller owns runtime paths, storage, model configuration, observability,
and shutdown.  This module only joins the domain services at the Agent
boundary, so it is safe for both the desktop startup path and a headless
benchmark process.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

    from ...config import AppPaths
    from ...observability import LLMUsageObservability
    from ..artifact_service import ArtifactService
    from ..dataset_service import DatasetService
    from ..llm import LLMService
    from ..ml.worker_settings import MLWorkerSettingsService
    from ..ml_service import MLService
    from .harness_service import AgentHarnessService
    from .skill_catalog import AgentSkillCatalog


# This is an advertisement policy, not a second tool registry.  The LLM
# boundary remains the authority for registered definitions and validates the
# frozen scope before accepting or invoking any provider Tool Call.
_AGENT_SKILL_COMMON_TOOL_NAMES = (
    "agent.skill.activate",
    "agent.skill.read_reference",
    "agent.skill.read_asset",
    "data.query",
)
_AGENT_SKILL_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "xenix-data-preprocessing": (
        "data.integrate",
        "data.clean",
        "data.clean.metadata",
        "data.tokenize",
        "data.transform",
        "data.feature.select",
    ),
    "xenix-data-analysis": (
        "data.transform",
        "analysis.graph",
    ),
    "xenix-data-modeling": (
        "data.transform",
        "data.feature.select",
        "model.metadata",
        "model.train",
        "model.hyper_train",
        "model.apply",
        "model.task.query",
        "analysis.graph",
    ),
}


@dataclass(frozen=True)
class HeadlessAgentServices:
    """Public handles for the headless Agent graph.

    Conversation, concrete Tool, preprocessing, and Skill catalog instances
    remain graph details.  Their owners are exposed through the Harness and
    domain-facing service handles instead of adding a second authority.
    """

    harness: AgentHarnessService
    datasets: DatasetService
    artifacts: ArtifactService
    ml: MLService
    llm: LLMService


def build_headless_agent_services(
    *,
    paths: AppPaths,
    session_factory: sessionmaker,
    llm: LLMService,
    ml_worker_settings: MLWorkerSettingsService,
    usage_observability: LLMUsageObservability,
) -> HeadlessAgentServices:
    """Build the production Agent graph without owning its runtime lifecycle.

    Lazy proxies intentionally match desktop startup behavior.  They defer
    domain implementation loading, but resolve to the same services and worker
    policy when a Tool needs them.  The supplied ``llm`` remains the only real
    provider gateway: leaving Harness ``provider`` as ``None`` preserves its
    Conversation -> ``LLMService.stream`` path.
    """

    # Preserve delayed domain imports for desktop startup and headless
    # preflight; they are needed only when a caller actually builds the graph.
    from ..artifact_service import ArtifactService
    from ..lazy_ml_service import LazyMLService
    from ..lazy_services import LazyServiceProxy
    from ..llm import AgentToolRegistry as LLMToolRegistry
    from ..llm import LLMConversationService
    from .harness_service import AgentHarnessService
    from .lazy_tools import LazyAgentToolRegistry
    from .skill_catalog import AgentSkillCatalog

    datasets = LazyServiceProxy(
        "xenix.services.dataset_service",
        "DatasetService",
        session_factory,
        paths,
    )
    data_cleaning_service = LazyServiceProxy(
        "xenix.services.data_cleaning",
        "DataCleaningService",
        paths,
    )
    data_transform_service = LazyServiceProxy(
        "xenix.services.data_transform",
        "DataQueryTransformService",
        paths,
    )
    ml_task_service = LazyServiceProxy(
        "xenix.services.ml_task_service",
        "MLTaskService",
        session_factory,
        paths,
        worker_settings_service=ml_worker_settings,
    )
    ml = LazyMLService(
        paths=paths,
        session_factory=session_factory,
        dataset_service=datasets,
        ml_task_service=ml_task_service,
    )
    artifacts = ArtifactService(session_factory)

    concrete_tools = LazyAgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=data_cleaning_service,
        data_transform_service=data_transform_service,
        ml_service=ml,
        artifact_service=artifacts,
    )
    llm_tools = LLMToolRegistry()
    concrete_tools.register_with_llm(llm_tools)

    skill_catalog = AgentSkillCatalog.from_default_catalog()
    conversation = LLMConversationService(
        session_factory=session_factory,
        llm_service=llm,
        tool_registry=llm_tools,
        context_messages_provider=lambda snapshot: agent_skill_context_messages(skill_catalog, snapshot),
        usage_observability=usage_observability,
    )
    register_agent_skill_tools(
        llm_tools,
        skill_catalog,
        activated_skill_names_provider=lambda thread_id: agent_skill_activated_skill_names(
            conversation.get_thread_snapshot(thread_id)
        ),
    )
    conversation.discard_stale_pending_messages()

    harness = AgentHarnessService(
        conversation_service=conversation,
        tool_presentation_registry=concrete_tools,
        provider=None,
        llm_service=llm,
        dataset_service=datasets,
        tool_name_scope_provider=agent_skill_tool_scope_names,
    )
    return HeadlessAgentServices(
        harness=harness,
        datasets=datasets,
        artifacts=artifacts,
        ml=ml,
        llm=llm,
    )


def register_agent_skill_tools(
    registry: Any,
    catalog: AgentSkillCatalog,
    *,
    activated_skill_names_provider: Callable[[str], set[str]] | None = None,
) -> None:
    """Register catalog-backed Skill operations with the LLM-owned registry."""

    from .skill_catalog import AGENT_SKILL_READ_REFERENCE_TOOL_NAME

    activation = catalog.activation_tool_spec()
    if activation is not None:
        registry.register(
            activation,
            lambda arguments, _context: catalog.activate(str(arguments["name"])),
        )

    def active_skill_names(context: Any) -> set[str]:
        if activated_skill_names_provider is None:
            return set()
        return set(activated_skill_names_provider(context.thread_id))

    all_skill_names = {skill.name for skill in catalog.list_skills()}
    for spec in catalog.resource_tool_specs(activated_skill_names=all_skill_names):
        if spec.name == AGENT_SKILL_READ_REFERENCE_TOOL_NAME:
            implementation = lambda arguments, _context: catalog.read_reference(
                skill_name=str(arguments["skill_name"]),
                path=str(arguments["path"]),
                activated_skill_names=active_skill_names(_context),
            )
        else:
            implementation = lambda arguments, _context: catalog.read_asset(
                skill_name=str(arguments["skill_name"]),
                path=str(arguments["path"]),
                activated_skill_names=active_skill_names(_context),
            )
        registry.register(spec, implementation)


def agent_skill_activated_skill_names(snapshot: Any) -> set[str]:
    """Project successfully activated Skills from canonical conversation data."""

    activation_call_ids = {
        message.id
        for message in snapshot.messages
        if getattr(message, "tool_id", None) == "agent.skill.activate"
    }
    activated: set[str] = set()
    for message in snapshot.messages:
        if getattr(message, "tool_call_message_id", None) not in activation_call_ids:
            continue
        status = getattr(message, "result_status", None)
        if getattr(status, "value", status) != "succeeded":
            continue
        payload = getattr(message, "value_payload", None)
        if isinstance(payload, dict) and isinstance(payload.get("skill_name"), str):
            activated.add(payload["skill_name"])
    return activated


def agent_skill_context_messages(catalog: AgentSkillCatalog, snapshot: Any) -> list[Any]:
    """Build the bounded provider context projection for the active Skills."""

    message = catalog.catalog_provider_message(
        activated_skill_names=agent_skill_activated_skill_names(snapshot)
    )
    return [message] if message is not None else []


def agent_skill_tool_scope_names(snapshot: Any) -> tuple[str, ...] | None:
    """Project relevant Tool names after a known Skill becomes active."""

    active = agent_skill_activated_skill_names(snapshot)
    if not active or any(name not in _AGENT_SKILL_TOOL_NAMES for name in active):
        return None
    names = list(_AGENT_SKILL_COMMON_TOOL_NAMES)
    for skill_name, skill_tools in _AGENT_SKILL_TOOL_NAMES.items():
        if skill_name in active:
            names.extend(skill_tools)
    return tuple(dict.fromkeys(names))
