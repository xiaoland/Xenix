from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field

from ..config import AppPaths
from ..exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from .storage.layout import ml_task_root
from .storage.models import MLTaskArtifactKind, MLTaskArtifactRow, MLTaskRow, MLTaskStatus, MLTaskType
from .storage.repositories import DatasetRepository, MLTaskRepository, ProjectRepository, WorkItemRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


ALLOWED_TRANSITIONS: dict[MLTaskStatus, set[MLTaskStatus]] = {
    MLTaskStatus.PENDING: {MLTaskStatus.RUNNING, MLTaskStatus.CANCELLED},
    MLTaskStatus.RUNNING: {
        MLTaskStatus.SUCCEEDED,
        MLTaskStatus.FAILED,
        MLTaskStatus.CANCELLED,
    },
}


class CreateMLTaskInput(SQLModel):
    project_id: str
    work_item_id: str
    dataset_id: str | None = None
    task_type: MLTaskType
    request_payload: dict[str, Any] = Field(default_factory=dict)


class StartMLTaskInput(SQLModel):
    ml_task_id: str


class MLTaskArtifactInput(SQLModel):
    artifact_kind: MLTaskArtifactKind
    absolute_path: str
    ready_to_open: bool = True


class CompleteMLTaskInput(SQLModel):
    ml_task_id: str
    result_payload: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[MLTaskArtifactInput] = Field(default_factory=list)


class FailMLTaskInput(SQLModel):
    ml_task_id: str
    error_summary: str


class CancelMLTaskInput(SQLModel):
    ml_task_id: str


class MLTaskService:
    def __init__(self, session_factory: sessionmaker, paths: AppPaths) -> None:
        self._session_factory = session_factory
        self._paths = paths
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()
        self._datasets = DatasetRepository()
        self._ml_tasks = MLTaskRepository()

    def create_ml_task(self, input_data: CreateMLTaskInput) -> MLTaskRow:
        if not isinstance(input_data.request_payload, Mapping):
            raise ValidationError("ML task request payload must be a dictionary.")

        now = _utc_now()
        row = MLTaskRow(
            project_id=input_data.project_id,
            work_item_id=input_data.work_item_id,
            dataset_id=input_data.dataset_id,
            task_type=input_data.task_type,
            status=MLTaskStatus.PENDING,
            request_payload=dict(input_data.request_payload),
            created_at=now,
            updated_at=now,
        )

        with self._session_factory() as session:
            project = self._projects.get(session, input_data.project_id)
            if project is None:
                raise NotFoundError(f"Project '{input_data.project_id}' was not found.")

            work_item = self._work_items.get(session, input_data.work_item_id)
            if work_item is None:
                raise NotFoundError(f"Work item '{input_data.work_item_id}' was not found.")
            if work_item.project_id != project.id:
                raise ValidationError("ML task work item does not belong to the provided project.")

            if input_data.dataset_id is not None:
                dataset = self._datasets.get(session, input_data.dataset_id)
                if dataset is None:
                    raise NotFoundError(f"Dataset '{input_data.dataset_id}' was not found.")
                if dataset.project_id != project.id:
                    raise ValidationError("ML task dataset does not belong to the provided project.")

            self._ml_tasks.create(session, row)
            session.commit()
            return row

    def start_ml_task(self, input_data: StartMLTaskInput) -> MLTaskRow:
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, input_data.ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{input_data.ml_task_id}' was not found.")

            self._require_transition(row.status, MLTaskStatus.RUNNING)
            now = _utc_now()
            updated = self._ml_tasks.update_status(
                session,
                row.id,
                row.status,
                MLTaskStatus.RUNNING,
                now,
            )
            session.commit()

        ml_task_root(self._paths, input_data.ml_task_id).mkdir(parents=True, exist_ok=True)
        return updated

    def complete_ml_task(self, input_data: CompleteMLTaskInput) -> MLTaskRow:
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, input_data.ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{input_data.ml_task_id}' was not found.")

            self._require_transition(row.status, MLTaskStatus.SUCCEEDED)

            artifacts: list[MLTaskArtifactRow] = []
            for artifact in input_data.artifacts:
                artifact_path = Path(artifact.absolute_path)
                if not artifact_path.exists():
                    raise ValidationError(f"ML task artifact '{artifact_path}' does not exist.")
                artifacts.append(
                    MLTaskArtifactRow(
                        ml_task_id=row.id,
                        artifact_kind=artifact.artifact_kind,
                        absolute_path=str(artifact_path),
                        ready_to_open=artifact.ready_to_open,
                        created_at=_utc_now(),
                    )
                )

            completed = self._ml_tasks.complete(
                session,
                row.id,
                dict(input_data.result_payload),
                _utc_now(),
                artifacts,
            )
            session.commit()
            return completed

    def fail_ml_task(self, input_data: FailMLTaskInput) -> MLTaskRow:
        error_summary = input_data.error_summary.strip()
        if not error_summary:
            raise ValidationError("ML task failure summary cannot be empty.")

        with self._session_factory() as session:
            row = self._ml_tasks.get(session, input_data.ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{input_data.ml_task_id}' was not found.")

            self._require_transition(row.status, MLTaskStatus.FAILED)
            failed = self._ml_tasks.fail(session, row.id, error_summary, _utc_now())
            session.commit()
            return failed

    def cancel_ml_task(self, input_data: CancelMLTaskInput) -> MLTaskRow:
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, input_data.ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{input_data.ml_task_id}' was not found.")

            self._require_transition(row.status, MLTaskStatus.CANCELLED)
            cancelled = self._ml_tasks.cancel(session, row.id, _utc_now())
            session.commit()
            return cancelled

    def list_ml_tasks(self, work_item_id: str) -> list[MLTaskRow]:
        with self._session_factory() as session:
            return self._ml_tasks.list_by_work_item(session, work_item_id)

    def get_ml_task(self, ml_task_id: str) -> MLTaskRow:
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{ml_task_id}' was not found.")
            return row

    def _require_transition(self, current: MLTaskStatus, target: MLTaskStatus) -> None:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"ML task transition from '{current.value}' to '{target.value}' is not allowed."
            )
