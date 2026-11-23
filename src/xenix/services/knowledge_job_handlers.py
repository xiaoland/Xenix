from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .job_scheduler import JobCapabilities, JobOutcome
from .job_status import knowledge_job_status
from .storage.models import JobDomain, JobRow

if TYPE_CHECKING:
    from .knowledge_derivation_service import KnowledgeDerivationService
    from .knowledge_import_service import KnowledgeImportService
    from .knowledge_index_service import KnowledgeIndexService


class KnowledgeJobService(Protocol):
    def recover_pending(self) -> list[int]: ...

    def run_unit(self, reference: int) -> None: ...

    def job_outcome(self, reference: int) -> tuple[str, str | None]: ...


class _KnowledgeHandler:
    domain = JobDomain.KNOWLEDGE
    concurrency_limit = 1
    kind: str
    _can_cancel = False
    _can_view_log = False

    def __init__(self, service: KnowledgeJobService) -> None:
        self._service = service

    def recover(self) -> list[int]:
        return self._service.recover_pending()

    def run(self, job: JobRow) -> JobOutcome:
        self._service.run_unit(job.reference)
        status, summary = self._service.job_outcome(job.reference)
        return JobOutcome(knowledge_job_status(status), summary)

    def request_cancel(self, job: JobRow) -> None:
        """Only import has a cancellation command; derived work is not cancellable."""

    def capabilities(self, job: JobRow) -> JobCapabilities:
        return JobCapabilities(
            can_cancel=self._can_cancel,
            can_view_log=self._can_view_log,
        )


class KnowledgeImportHandler(_KnowledgeHandler):
    kind = "import"
    _can_cancel = True
    _can_view_log = True

    def __init__(self, service: "KnowledgeImportService") -> None:
        super().__init__(service)
        self._cancel = service.cancel_unit

    def request_cancel(self, job: JobRow) -> None:
        self._cancel(job.reference)


class KnowledgeDerivationHandler(_KnowledgeHandler):
    kind = "content_preparation"

    def __init__(self, service: "KnowledgeDerivationService") -> None:
        super().__init__(service)


class KnowledgeIndexHandler(_KnowledgeHandler):
    kind = "index_build"

    def __init__(self, service: "KnowledgeIndexService") -> None:
        super().__init__(service)


__all__ = [
    "KnowledgeDerivationHandler",
    "KnowledgeImportHandler",
    "KnowledgeIndexHandler",
]
