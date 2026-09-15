"""Desktop composition root: construct services and inject feature-specific UI ports.

Import this module after the splash is visible. It owns wiring, while app.py owns
startup/recovery and ApplicationLifetime owns release. Widgets never receive the
composition root or an unrestricted service bag.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from .application_lifetime import ApplicationLifetime
from .application_services import ApplicationServices
from .config import AppPaths
from .i18n import TranslationManager
from .observability import LLM_USAGE_JOURNAL_FILE_NAME, LocalLLMUsageObservability
from .services.agent.composition import build_headless_agent_services
from .services.embedding_service import EmbeddingSettingsService
from .services.job_service import JobQueryService
from .services.knowledge_derivation_service import KnowledgeDerivationService
from .services.knowledge_document_lifecycle_service import KnowledgeDocumentLifecycleService
from .services.knowledge_import_service import KnowledgeImportService
from .services.knowledge_index_service import KnowledgeIndexService
from .services.knowledge_task_query import KnowledgeTaskQueryService
from .services.knowledge_workspace_service import KnowledgeWorkspaceService
from .services.link_router import LinkRouter
from .services.llm import LLMService, LLMSettingsService
from .services.ml.worker_settings import MLWorkerSettingsService
from .services.paddle_ocr_service import PaddleOcrDeploymentService
from .services.storage.layout import database_path
from .services.storage.repositories import KnowledgeRepository
from .ui.main_window import MainWindow

if TYPE_CHECKING:
    from .services.storage.bootstrap import StorageContext


def build_workbench_window(
    *,
    paths: AppPaths,
    context: StorageContext,
    translation_manager: TranslationManager,
    log_path: Path,
    lifetime: ApplicationLifetime,
    on_services_ready: Callable[[ApplicationServices], None] | None = None,
) -> MainWindow:
    """Assemble all handlers before recovery or dispatch starts."""
    ml_worker_settings_service = MLWorkerSettingsService(paths)
    llm_settings_service = LLMSettingsService(paths)
    embedding_settings_service = EmbeddingSettingsService(paths)
    llm_service = LLMService(llm_settings_service)
    agent_services = build_headless_agent_services(
        paths=paths,
        session_factory=context.session_factory,
        llm=llm_service,
        embedding_settings_service=embedding_settings_service,
        ml_worker_settings=ml_worker_settings_service,
        start_scheduler=False,
        usage_observability=LocalLLMUsageObservability(paths.logs / LLM_USAGE_JOURNAL_FILE_NAME),
    )
    scheduler = agent_services.scheduler
    link_router = LinkRouter(
        artifact_service=agent_services.artifacts,
    )
    from .services.update_service import UpdateService

    update_service = UpdateService(paths, database_path(paths))
    paddle_ocr_deployment = PaddleOcrDeploymentService(paths)
    knowledge_index_service = KnowledgeIndexService(
        session_factory=context.session_factory,
        semantic_service=agent_services.knowledge_semantic,
        embedding_service=agent_services.embedding,
        embedding_settings_source=embedding_settings_service,
        scheduler=scheduler,
    )
    lifetime.add_cleanup("knowledge_index_service", knowledge_index_service.shutdown)
    knowledge_derivation_service = KnowledgeDerivationService(
        paths=paths,
        session_factory=context.session_factory,
        retrieval_ready_notifier=knowledge_index_service.notify_corpus_changed,
        scheduler=scheduler,
    )
    lifetime.add_cleanup("knowledge_derivation_service", knowledge_derivation_service.shutdown)
    knowledge_import_service = KnowledgeImportService(
        paths=paths,
        session_factory=context.session_factory,
        artifact_service=agent_services.artifacts,
        knowledge_repository=KnowledgeRepository(),
        canonical_ready_notifier=knowledge_derivation_service.enqueue_generation,
        corpus_changed_notifier=knowledge_index_service.notify_corpus_changed,
        scheduler=scheduler,
    )
    lifetime.add_cleanup("knowledge_import_service", knowledge_import_service.shutdown)
    knowledge_document_lifecycle_service = KnowledgeDocumentLifecycleService(
        session_factory=context.session_factory,
        index_service=knowledge_index_service,
    )
    knowledge_task_query_service = KnowledgeTaskQueryService(context.session_factory)
    job_query_service = JobQueryService(
        context.session_factory,
        knowledge_task_query_service,
    )
    knowledge_workspace_service = KnowledgeWorkspaceService(
        knowledge_service=agent_services.knowledge,
        task_query=knowledge_task_query_service,
        index_service=knowledge_index_service,
        ocr_deployment=paddle_ocr_deployment,
    )
    from .services.knowledge_job_handlers import (
        KnowledgeDerivationHandler,
        KnowledgeImportHandler,
        KnowledgeIndexHandler,
    )

    knowledge_handlers = [
        KnowledgeImportHandler(knowledge_import_service),
        KnowledgeDerivationHandler(knowledge_derivation_service),
        KnowledgeIndexHandler(knowledge_index_service),
    ]
    for handler in knowledge_handlers:
        scheduler.register_handler(handler)
    lifetime.add_cleanup("job scheduler", scheduler.shutdown)

    from .ui.conversation.execution import ThreadedSubmissionExecutor
    from .ui.dataset_audit_dialog import DatasetAuditDialog
    from .ui.history import HarnessHistoryAdapter
    from .ui.job_center import JobCenterDialog
    from .ui.knowledge_workspace import KnowledgeWorkspaceDialog
    from .ui.settings_dialog import SettingsDialog
    from .ui.software_update import SoftwareUpdateController
    from .ui.tool_call_detail_view import ToolCallDetailView
    from .ui.windows.auxiliary import AuxiliaryWindowCoordinator

    def create_settings(owner: QWidget) -> SettingsDialog:
        return SettingsDialog(
            paths=paths,
            log_path=log_path,
            db_path=database_path(paths),
            translation_manager=translation_manager,
            llm_service=llm_service,
            llm_settings_service=llm_settings_service,
            embedding_settings_service=embedding_settings_service,
            ml_worker_settings_service=ml_worker_settings_service,
            update_service=update_service,
            paddle_ocr_deployment=paddle_ocr_deployment,
            knowledge_index_service=knowledge_index_service,
            parent=owner,
        )

    def create_knowledge(owner: QWidget, open_settings: Callable[[], None]) -> KnowledgeWorkspaceDialog:
        return KnowledgeWorkspaceDialog(
            import_service=knowledge_import_service,
            derivation_service=knowledge_derivation_service,
            knowledge_service=agent_services.knowledge,
            knowledge_index_service=knowledge_index_service,
            ocr_deployment=paddle_ocr_deployment,
            task_query_service=knowledge_task_query_service,
            workspace_service=knowledge_workspace_service,
            document_lifecycle_service=knowledge_document_lifecycle_service,
            open_knowledge_settings=open_settings,
            parent=owner,
        )

    def create_job_center(owner: QWidget) -> JobCenterDialog:
        return JobCenterDialog(
            job_query_service,
            scheduler=scheduler,
            parent=owner,
        )

    def create_dataset_audit(owner: QWidget, thread_id: int) -> DatasetAuditDialog:
        return DatasetAuditDialog(
            harness=agent_services.harness,
            thread_id=thread_id,
            parent=owner,
        )

    def create_auxiliary(owner: QWidget) -> AuxiliaryWindowCoordinator:
        return AuxiliaryWindowCoordinator(
            owner,
            settings_factory=create_settings,
            knowledge_factory=create_knowledge,
            detail_factory=lambda parent, task_ids: ToolCallDetailView(
                ml_service=agent_services.ml,
                task_ids=task_ids,
                parent=parent,
            ),
            job_center_factory=create_job_center,
            dataset_audit_factory=create_dataset_audit,
            update_controller=(SoftwareUpdateController(owner, update_service) if update_service is not None else None),
        )

    window = MainWindow(
        current_locale=translation_manager.current_locale,
        agent_harness_service=agent_services.harness,
        conversation_executor=ThreadedSubmissionExecutor(agent_services.harness.submit_user_turn_stream),
        llm_service=llm_service,
        artifact_service=agent_services.artifacts,
        link_router=link_router,
        history_port=HarnessHistoryAdapter(agent_services.harness),
        auxiliary_factory=create_auxiliary,
    )
    lifetime.add_cleanup("main window", window.close)
    scheduler.start()
    if on_services_ready is not None:
        on_services_ready(
            ApplicationServices(
                agent=agent_services,
                knowledge_import=knowledge_import_service,
                knowledge_derivation=knowledge_derivation_service,
                knowledge_index=knowledge_index_service,
                knowledge_tasks=knowledge_task_query_service,
            )
        )

    return window
