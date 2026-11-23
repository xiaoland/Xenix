"""Read ML and Knowledge logs for the same Job Center details view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .ml.contracts import TaskLogEntry
from .storage.models import JobDomain
from .storage.repositories.knowledge import KnowledgeRepository

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session

    from .job_service import JobItem
    from .knowledge_task_logs import KnowledgeTaskLogEntry, KnowledgeTaskLogStore
    from .ml_service import MLTaskDetails


@dataclass(frozen=True)
class JobDetails:
    logs: list[TaskLogEntry]
    has_outputs: bool = False


def _event_time(entry: KnowledgeTaskLogEntry) -> datetime:
    timestamp = datetime.fromisoformat(entry.timestamp)
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


class JobDetailQueryService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        read_ml_details: Callable[[int], MLTaskDetails],
        knowledge_logs: KnowledgeTaskLogStore,
    ) -> None:
        self._session_factory = session_factory
        self._read_ml_details = read_ml_details
        self._knowledge_logs = knowledge_logs
        self._knowledge = KnowledgeRepository()

    def read(self, job: JobItem) -> JobDetails:
        if job.domain == JobDomain.ML:
            details = self._read_ml_details(job.raw_reference)
            return JobDetails(logs=details.logs, has_outputs=bool(details.artifacts))

        entries = list(self._knowledge_logs.read(job.raw_reference, kind=job.kind))
        if job.kind == "import":
            # The feed can fold content preparation into the import row.
            with self._session_factory() as session:
                derivation_ids = self._knowledge.list_import_derivation_ids(session, job.raw_reference)
            for derivation_id in derivation_ids:
                entries.extend(self._knowledge_logs.read(derivation_id, kind="content_preparation"))
            if derivation_ids:
                entries.sort(key=_event_time)
        return JobDetails(logs=[
            TaskLogEntry(
                timestamp=entry.timestamp,
                level=entry.level.upper(),
                message=f"{entry.phase.replace('_', ' ')} — {entry.event_code.replace('_', ' ')}",
            )
            for entry in entries
        ])
