"""Read-only runtime handles for embedding/diagnostics, never a UI dependency bag.

The application owns these services and their shutdown. Observers may use them
only during that application's lifetime; widgets receive feature-specific ports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.agent.composition import HeadlessAgentServices
    from .services.knowledge_derivation_service import KnowledgeDerivationService
    from .services.knowledge_import_service import KnowledgeImportService
    from .services.knowledge_index_service import KnowledgeIndexService
    from .services.knowledge_task_query import KnowledgeTaskQueryService


@dataclass(frozen=True)
class ApplicationServices:
    agent: HeadlessAgentServices
    knowledge_import: KnowledgeImportService
    knowledge_derivation: KnowledgeDerivationService
    knowledge_index: KnowledgeIndexService
    knowledge_tasks: KnowledgeTaskQueryService
