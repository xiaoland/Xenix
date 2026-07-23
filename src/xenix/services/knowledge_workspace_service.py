from __future__ import annotations

from dataclasses import dataclass

from .knowledge_index_service import KnowledgeIndexOverview, KnowledgeIndexService
from .knowledge_service import KnowledgeDocumentSummary, KnowledgeService
from .knowledge_task_query import KnowledgeTaskQueryService, KnowledgeTaskSummary
from .paddle_ocr_service import PaddleOcrDeploymentService, PaddleOcrState, PaddleOcrStatus


@dataclass(frozen=True)
class KnowledgeWorkspaceSnapshot:
    documents: tuple[KnowledgeDocumentSummary, ...]
    tasks: KnowledgeTaskSummary
    ocr: PaddleOcrStatus
    indexes: KnowledgeIndexOverview | None
    documents_available: bool = True

    @property
    def has_active_work(self) -> bool:
        return self.tasks.has_active_work or bool(
            self.indexes is not None and self.indexes.active_task_id
        )


class KnowledgeWorkspaceService:
    """Compose one background-safe, presentation-sized Workspace snapshot."""

    def __init__(
        self,
        *,
        knowledge_service: KnowledgeService | None,
        task_query: KnowledgeTaskQueryService,
        index_service: KnowledgeIndexService | None,
        ocr_deployment: PaddleOcrDeploymentService | None,
    ) -> None:
        self._knowledge = knowledge_service
        self._tasks = task_query
        self._indexes = index_service
        self._ocr = ocr_deployment

    def snapshot(self, *, library_id: str = "global") -> KnowledgeWorkspaceSnapshot:
        documents_available = True
        try:
            documents = tuple(
                self._knowledge.list_documents(library_id=library_id)
                if self._knowledge is not None
                else ()
            )
        except Exception:
            documents = ()
            documents_available = False
        try:
            tasks = self._tasks.summary(library_id=library_id)
        except Exception:
            tasks = KnowledgeTaskSummary(0, 0, 0)
        try:
            if self._ocr is None:
                ocr = PaddleOcrStatus(PaddleOcrState.NOT_INSTALLED, "service_unavailable")
            else:
                status_reader = getattr(self._ocr, "status_snapshot", None)
                if status_reader is None:
                    status_reader = self._ocr.status
                ocr = status_reader()
                if ocr.state is PaddleOcrState.CHECKING:
                    ocr = self._ocr.verify_active()
        except Exception:
            ocr = PaddleOcrStatus(PaddleOcrState.REPAIR_REQUIRED, "status_unavailable")
        try:
            indexes = (
                self._indexes.status(library_id=library_id)
                if self._indexes is not None
                else None
            )
        except Exception:
            indexes = None
        return KnowledgeWorkspaceSnapshot(
            documents=documents,
            tasks=tasks,
            ocr=ocr,
            indexes=indexes,
            documents_available=documents_available,
        )


__all__ = ["KnowledgeWorkspaceService", "KnowledgeWorkspaceSnapshot"]
