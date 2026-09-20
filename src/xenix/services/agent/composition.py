"""Headless composition root for the Agent service graph.

The caller owns runtime paths, storage, model configuration, observability,
and shutdown.  This module only joins the domain services at the Agent
boundary, so it is safe for both the desktop startup path and a headless
benchmark process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

    from ...config import AppPaths
    from ...observability import LLMUsageObservability
    from ..artifact_service import ArtifactService
    from ..dataset_service import DatasetService
    from ..data_cleaning import DataCleaningService
    from ..data_transform import DataQueryTransformService
    from ..embedding_service import EmbeddingService, EmbeddingSettingsService
    from ..job_scheduler import JobScheduler
    from ..knowledge_semantic_service import KnowledgeSemanticService
    from ..llm import LLMService
    from ..llm.tool_registry import AgentToolRegistry
    from ..knowledge_service import KnowledgeService
    from ..ml.worker_settings import MLWorkerSettingsService
    from ..ml_service import MLService
    from ..ml_task_service import MLTaskService
    from .harness_service import AgentHarnessService
    from .skill_catalog import AgentSkillCatalog
    from .tool_catalog import AgentToolCatalog


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
    knowledge: KnowledgeService
    embedding_settings: EmbeddingSettingsService
    embedding: EmbeddingService
    knowledge_semantic: KnowledgeSemanticService
    scheduler: JobScheduler


def build_headless_agent_services(
    *,
    paths: AppPaths,
    session_factory: sessionmaker,
    llm: LLMService,
    embedding_settings_service: EmbeddingSettingsService,
    ml_worker_settings: MLWorkerSettingsService,
    usage_observability: LLMUsageObservability,
    start_scheduler: bool = True,
) -> HeadlessAgentServices:
    """Build the production Agent graph without owning its runtime lifecycle.

    Desktop composition passes ``start_scheduler=False``, registers Knowledge
    handlers, then starts the complete graph once. No worker starts before the
    graph has been assembled successfully.

    Domain service factories retain desktop lazy construction while Tool
    registrations are assembled immediately. The supplied ``llm`` is the only
    provider gateway: leaving Harness ``provider`` as ``None`` preserves its
    Conversation -> ``LLMService.stream`` path.
    """

    # Preserve delayed domain imports for desktop startup and headless
    # preflight; they are needed only when a caller actually builds the graph.
    from ..artifact_service import ArtifactService
    from ..embedding_service import OpenAICompatibleEmbeddingService
    from ..knowledge_semantic_service import KnowledgeSemanticService
    from ..knowledge_service import KnowledgeService
    from ..knowledge_vector_store import LanceKnowledgeVectorStore
    from ..lazy_services import lazy_service
    from ..llm import AgentToolRegistry as LLMToolRegistry
    from ..llm import LLMConversationService
    from .harness_service import AgentHarnessService
    from .tools import build_agent_tools
    from .knowledge_tool import register_knowledge_lookup_tool
    from .skill_catalog import AgentSkillCatalog
    from .tool_catalog import AgentToolCatalog

    def create_datasets() -> DatasetService:
        from ..dataset_service import DatasetService

        return DatasetService(session_factory, paths)

    def create_cleaning() -> DataCleaningService:
        from ..data_cleaning import DataCleaningService

        return DataCleaningService(paths)

    def create_transforms() -> DataQueryTransformService:
        from ..data_transform import DataQueryTransformService

        return DataQueryTransformService(paths)

    def create_ml_tasks() -> MLTaskService:
        from ..ml_task_service import MLTaskService

        return MLTaskService(session_factory, paths, worker_settings_service=ml_worker_settings)

    datasets = lazy_service(create_datasets)
    data_cleaning_service = lazy_service(create_cleaning)
    data_transform_service = lazy_service(create_transforms)
    ml_task_service = lazy_service(create_ml_tasks)
    from ..job_scheduler import JobScheduler
    from ..ml_job_handler import MLJobHandler

    scheduler = JobScheduler(session_factory, [MLJobHandler(ml_task_service)])

    def create_ml() -> MLService:
        from ..ml_service import MLService

        return MLService(
            paths=paths,
            session_factory=session_factory,
            dataset_service=datasets,
            ml_task_service=ml_task_service,
            scheduler=scheduler,
        )

    ml = lazy_service(create_ml)
    artifacts = ArtifactService(session_factory)
    embedding = OpenAICompatibleEmbeddingService(embedding_settings_service)
    semantic_knowledge = KnowledgeSemanticService(
        session_factory,
        embedding_service=embedding,
        vector_store=LanceKnowledgeVectorStore(paths),
    )
    knowledge = KnowledgeService(
        session_factory,
        semantic_search=semantic_knowledge,
    )

    domain_tools = build_agent_tools(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=data_cleaning_service,
        data_transform_service=data_transform_service,
        ml_service=ml,
        artifact_service=artifacts,
    )
    llm_tools = LLMToolRegistry(
        domain_tools,
        paged_results_dir=paths.state / "paged_results",
    )
    register_knowledge_lookup_tool(llm_tools, knowledge)
    from .audit_tools import register_audit_tools

    register_audit_tools(llm_tools, session_factory)
    llm_tools.collect_garbage(max_age_seconds=7 * 24 * 60 * 60)

    skill_catalog = AgentSkillCatalog.from_default_catalog()
    conversation = LLMConversationService(
        session_factory=session_factory,
        llm_service=llm,
        tool_registry=llm_tools,
        context_messages_provider=lambda snapshot: agent_context_messages(skill_catalog, tool_catalog, snapshot),
        usage_observability=usage_observability,
    )
    register_agent_skill_tools(llm_tools, skill_catalog)
    tool_catalog = AgentToolCatalog(llm_tools.list_specs())
    llm_tools.register(tool_catalog.activation_tool())
    conversation.discard_stale_pending_messages()

    harness = AgentHarnessService(
        conversation_service=conversation,
        provider=None,
        llm_service=llm,
        dataset_service=datasets,
        tool_name_scope_provider=tool_catalog.scope_names,
    )
    if start_scheduler:
        scheduler.start()
    return HeadlessAgentServices(
        harness=harness,
        datasets=datasets,
        artifacts=artifacts,
        ml=ml,
        llm=llm,
        knowledge=knowledge,
        embedding_settings=embedding_settings_service,
        embedding=embedding,
        knowledge_semantic=semantic_knowledge,
        scheduler=scheduler,
    )


def register_agent_skill_tools(registry: AgentToolRegistry, catalog: AgentSkillCatalog) -> None:
    """Register guidance and resource readers without consulting conversation history."""
    activation = catalog.activation_tool()
    if activation is not None:
        registry.register(activation)
    for tool in catalog.resource_tools():
        registry.register(tool)


def agent_skill_activated_skill_names(snapshot: Any) -> set[str]:
    """Project successfully activated Skills from canonical conversation data."""

    activation_calls = {
        message.id: message for message in snapshot.messages if getattr(message, "tool_id", None) == "agent.skill.activate"
    }
    activated: set[str] = set()
    for message in snapshot.messages:
        call = activation_calls.get(getattr(message, "tool_call_message_id", None))
        if call is None:
            continue
        status = getattr(message, "result_status", None)
        if getattr(status, "value", status) != "succeeded":
            continue
        # Successful invocation validates the requested name. Its result may be
        # paged, so activation identity belongs to the paired canonical call.
        arguments = getattr(call, "arguments_payload", None) or {}
        name = arguments.get("name")
        if isinstance(name, str):
            activated.add(name.strip())
    return activated


def agent_skill_context_messages(catalog: AgentSkillCatalog, snapshot: Any) -> list[Any]:
    """Build the bounded provider context projection for the active Skills."""

    message = catalog.catalog_provider_message(activated_skill_names=agent_skill_activated_skill_names(snapshot))
    return [message] if message is not None else []


def agent_context_messages(
    skills: AgentSkillCatalog, tools: AgentToolCatalog, snapshot: Any,
) -> list[Any]:
    messages = agent_skill_context_messages(skills, snapshot)
    directory = tools.provider_message(snapshot)
    if directory is not None:
        messages.append(directory)
    return messages
