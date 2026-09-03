from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import InvalidStateTransitionError
from .job_scheduler import JobCapabilities, JobOutcome
from .storage.models import JobDomain, JobRow, JobStatus, MLTaskStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .ml_task_service import MLTaskService


_ML_STATUS_TO_JOB: dict[MLTaskStatus, JobStatus] = {
    MLTaskStatus.PENDING: JobStatus.QUEUED,
    MLTaskStatus.RUNNING: JobStatus.RUNNING,
    MLTaskStatus.SUCCEEDED: JobStatus.SUCCEEDED,
    MLTaskStatus.FAILED: JobStatus.FAILED,
    MLTaskStatus.CANCELLED: JobStatus.CANCELLED,
}


class MLJobHandler:
    """JobScheduler adapter over MLTaskService.

    ML restart semantics stay permanent orphan: queued/running jobs are never
    auto-requeued or redispatched after a restart.
    """

    domain = JobDomain.ML

    def __init__(self, ml_task_service: "MLTaskService") -> None:
        self._ml_task_service = ml_task_service

    @property
    def concurrency_limit(self) -> int:
        return self._ml_task_service.max_concurrent_tasks

    def recover(self, session: "Session", jobs: list[JobRow]) -> list[str]:
        return []

    def run(self, job: JobRow) -> JobOutcome:
        try:
            finished = self._ml_task_service.run_task(job.reference)
        except Exception as exc:
            return JobOutcome(JobStatus.FAILED, str(exc))
        if finished is None:
            return JobOutcome(JobStatus.SUCCEEDED)
        return JobOutcome(
            _ML_STATUS_TO_JOB[finished.status],
            finished.error_summary,
        )

    def request_cancel(self, job: JobRow) -> None:
        from .ml_task_service import CancelMLTaskInput

        try:
            self._ml_task_service.cancel_ml_task(
                CancelMLTaskInput(ml_task_id=job.reference)
            )
        except InvalidStateTransitionError:
            # The job already reached a terminal state; nothing to cancel.
            return

    def capabilities(self, job: JobRow) -> JobCapabilities:
        return JobCapabilities(can_cancel=True, can_view_log=True)


__all__ = ["MLJobHandler"]
