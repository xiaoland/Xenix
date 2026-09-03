"""Background tasks and drop handling shared by the Knowledge Workspace dialogs."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QRunnable, Signal

if TYPE_CHECKING:
    from ...services.knowledge_document_lifecycle_service import (
        KnowledgeDocumentLifecycleService,
    )
    from ...services.knowledge_task_query import KnowledgeTaskQueryService
    from ...services.knowledge_workspace_service import KnowledgeWorkspaceService

TASK_POLL_INTERVAL_MS = 500
WORKSPACE_ACTIVE_POLL_INTERVAL_MS = 1_000


class _WorkspaceLoadSignals(QObject):
    finished = Signal(int, int, object)


class _DocumentsLoadTask(QRunnable):
    def __init__(
        self,
        service: KnowledgeWorkspaceService,
        generation: int,
        request_id: int,
    ) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self._request_id = request_id
        self.signals = _WorkspaceLoadSignals()

    def run(self) -> None:
        try:
            result = self._service.load_documents()
        except Exception:
            result = None
        self.signals.finished.emit(self._generation, self._request_id, result)


class _StatusLoadTask(QRunnable):
    def __init__(
        self,
        service: KnowledgeWorkspaceService,
        generation: int,
        request_id: int,
    ) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self._request_id = request_id
        self.signals = _WorkspaceLoadSignals()

    def run(self) -> None:
        try:
            result = self._service.load_status()
        except Exception:
            result = None
        self.signals.finished.emit(self._generation, self._request_id, result)


class _DocumentRemovalSignals(QObject):
    finished = Signal(int, object)


class _DocumentRemovalTask(QRunnable):
    def __init__(
        self,
        service: KnowledgeDocumentLifecycleService,
        generation: int,
        document_id: str,
    ) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self._document_id = document_id
        self.signals = _DocumentRemovalSignals()

    def run(self) -> None:
        try:
            result: object = self._service.remove_document(self._document_id)
        except Exception as exc:
            result = exc
        self.signals.finished.emit(self._generation, result)


class _DocumentViewportState(StrEnum):
    COLD = "cold"
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class _TaskListSignals(QObject):
    finished = Signal(int, object)


class _TaskListLoad(QRunnable):
    def __init__(self, query: KnowledgeTaskQueryService, generation: int) -> None:
        super().__init__()
        self._query = query
        self._generation = generation
        self.signals = _TaskListSignals()

    def run(self) -> None:
        try:
            tasks = self._query.list_tasks()
        except Exception:
            tasks = []
        self.signals.finished.emit(self._generation, tasks)


class _KnowledgeFileDropAdapter(QObject):
    """Project local file URLs into one Workspace submission callback."""

    files_dropped = Signal(object)

    def attach(self, target: QObject) -> None:
        set_accept_drops = getattr(target, "setAcceptDrops", None)
        if callable(set_accept_drops):
            set_accept_drops(True)
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() not in {QEvent.DragEnter, QEvent.DragMove, QEvent.Drop}:
            return super().eventFilter(watched, event)
        mime_data = getattr(event, "mimeData", lambda: None)()
        paths = _local_file_drop_paths(mime_data)
        if not paths:
            event.ignore()
            return True
        event.acceptProposedAction()
        if event.type() == QEvent.Drop:
            self.files_dropped.emit(paths)
        return True


def _local_file_drop_paths(mime_data: object | None) -> list[str]:
    if mime_data is None:
        return []
    urls = getattr(mime_data, "urls", lambda: ())()
    return [
        url.toLocalFile()
        for url in urls
        if url.isLocalFile() and url.toLocalFile()
    ]
