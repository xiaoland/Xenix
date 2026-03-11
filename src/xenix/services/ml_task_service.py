from __future__ import annotations

import json
import queue
import shutil
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel

from ..config import AppPaths
from ..exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from .ml.contracts import EvaluateTaskResult, FitTaskResult, HyperparameterTuningTaskResult, TaskLogEntry
from .ml.contracts import InferenceTaskResult
from .ml.execution import MLWorkerRunner
from .ml.operations import run_evaluate_task, run_fit_task, run_hyperparameter_tuning_task, run_inference_task
from .storage.layout import (
    canonical_inference_dir,
    canonical_model_dir,
    ml_task_root,
    task_input_dir,
    task_logs_path,
    task_output_dir,
    task_models_dir,
    task_request_path,
    task_result_path,
)
from .storage.models import (
    DatasetRow,
    DatasetSourceFormat,
    MLTaskArtifactKind,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    TrainedModelRow,
)
from .storage.repositories import (
    DatasetRepository,
    MLTaskRepository,
    ProjectRepository,
    TrainedModelRepository,
    WorkItemRepository,
)


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
    def __init__(
        self,
        session_factory: sessionmaker,
        paths: AppPaths,
        worker_runner: MLWorkerRunner | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._paths = paths
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()
        self._datasets = DatasetRepository()
        self._ml_tasks = MLTaskRepository()
        self._trained_models = TrainedModelRepository()
        self._worker_runner = worker_runner or MLWorkerRunner()
        self._queue: queue.Queue[str] = queue.Queue()
        self._callbacks: list[Callable[[MLTaskRow], None]] = []
        self._dispatcher_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._submitted_ids: set[str] = set()

    def register_completion_listener(self, callback: Callable[[MLTaskRow], None]) -> None:
        self._callbacks.append(callback)

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

    def submit_ml_task(self, ml_task_id: str) -> None:
        task = self.get_ml_task(ml_task_id)
        if task.status is not MLTaskStatus.PENDING:
            raise InvalidStateTransitionError(
                f"ML task '{ml_task_id}' must be pending before it can be submitted."
            )

        root = ml_task_root(self._paths, ml_task_id)
        root.mkdir(parents=True, exist_ok=True)
        task_input_dir(self._paths, ml_task_id).mkdir(parents=True, exist_ok=True)
        task_output_dir(self._paths, ml_task_id).mkdir(parents=True, exist_ok=True)
        task_models_dir(self._paths, ml_task_id).mkdir(parents=True, exist_ok=True)
        task_request_path(self._paths, ml_task_id).write_text(
            json.dumps(task.request_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

        with self._lock:
            if ml_task_id in self._submitted_ids:
                return
            self._submitted_ids.add(ml_task_id)
            self._queue.put(ml_task_id)
            self._ensure_dispatcher_locked()

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
            completed = self._complete_row(session, row, input_data.result_payload, input_data.artifacts)
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

    def list_ml_task_artifacts(self, ml_task_id: str) -> list[MLTaskArtifactRow]:
        with self._session_factory() as session:
            return self._ml_tasks.list_artifacts(session, ml_task_id)

    def read_task_logs(self, ml_task_id: str) -> list[TaskLogEntry]:
        path = task_logs_path(self._paths, ml_task_id)
        if not path.exists():
            return []
        return [
            TaskLogEntry.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _ensure_dispatcher_locked(self) -> None:
        if self._dispatcher_thread is not None and self._dispatcher_thread.is_alive():
            return
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop,
            name="xenix-ml-dispatcher",
            daemon=True,
        )
        self._dispatcher_thread.start()

    def _dispatch_loop(self) -> None:
        while True:
            ml_task_id = self._queue.get()
            try:
                finished_task = self._run_task(ml_task_id)
                if finished_task is not None:
                    self._notify_callbacks(finished_task)
            finally:
                with self._lock:
                    self._submitted_ids.discard(ml_task_id)
                self._queue.task_done()

    def _run_task(self, ml_task_id: str) -> MLTaskRow | None:
        task = self.get_ml_task(ml_task_id)
        if task.status is not MLTaskStatus.PENDING:
            return task

        try:
            running_task = self.start_ml_task(StartMLTaskInput(ml_task_id=ml_task_id))
            return_code = self._worker_runner.run(
                self._resolve_entrypoint(running_task.task_type),
                ml_task_root(self._paths, ml_task_id),
            )
            if return_code == 0:
                return self._finalize_success(ml_task_id)
            return self._finalize_failure(ml_task_id, return_code)
        except Exception as exc:
            current = self.get_ml_task(ml_task_id)
            if current.status is MLTaskStatus.RUNNING:
                return self.fail_ml_task(
                    FailMLTaskInput(ml_task_id=ml_task_id, error_summary=str(exc))
                )
            return current

    def _resolve_entrypoint(self, task_type: MLTaskType) -> Callable[[str], None]:
        if task_type is MLTaskType.FIT:
            return run_fit_task
        if task_type is MLTaskType.HYPERPARAMETER_TUNING:
            return run_hyperparameter_tuning_task
        if task_type is MLTaskType.EVALUATE:
            return run_evaluate_task
        if task_type is MLTaskType.INFERENCE:
            return run_inference_task
        raise ValidationError(f"ML task type '{task_type.value}' is not executable in this workflow.")

    def _finalize_success(self, ml_task_id: str) -> MLTaskRow:
        with self._session_factory() as session:
            row = self._ml_tasks.get(session, ml_task_id)
            if row is None:
                raise NotFoundError(f"ML task '{ml_task_id}' was not found.")
            if row.task_type is MLTaskType.FIT:
                result_payload, artifacts = self._finalize_fit_task(session, row)
            elif row.task_type is MLTaskType.HYPERPARAMETER_TUNING:
                result_payload, artifacts = self._finalize_tuning_task(session, row)
            elif row.task_type is MLTaskType.EVALUATE:
                result_payload, artifacts = self._finalize_evaluate_task(row)
            elif row.task_type is MLTaskType.INFERENCE:
                result_payload, artifacts = self._finalize_inference_task(session, row)
            else:
                raise ValidationError(f"ML task type '{row.task_type.value}' cannot be finalized.")

            completed = self._complete_row(session, row, result_payload, artifacts)
            session.commit()
            return completed

    def _finalize_fit_task(
        self,
        session: Any,
        row: MLTaskRow,
    ) -> tuple[dict[str, Any], list[MLTaskArtifactInput]]:
        result = FitTaskResult.model_validate_json(task_result_path(self._paths, row.id).read_text(encoding="utf-8"))
        if result.error_summary:
            raise ValidationError(result.error_summary)
        model_path = Path(result.model_artifact_path)
        holdout_path = Path(result.holdout_artifact_path)
        self._require_existing_path(model_path)
        self._require_existing_path(holdout_path)
        canonical_path = self._copy_canonical_model(row.work_item_id, row.id, result.model_key, model_path)
        trained_model = self._trained_models.create(
            session,
            TrainedModelRow(
                work_item_id=row.work_item_id,
                ml_task_id=row.id,
                model_key=result.model_key,
                problem_kind=result.problem_kind,
                artifact_path=str(canonical_path),
            ),
        )
        payload = result.model_dump(mode="json")
        payload["trained_model_id"] = trained_model.id
        payload["canonical_model_artifact_path"] = str(canonical_path)
        artifacts = [
            MLTaskArtifactInput(artifact_kind=MLTaskArtifactKind.MODEL, absolute_path=str(canonical_path)),
            MLTaskArtifactInput(
                artifact_kind=MLTaskArtifactKind.HOLDOUT_DATA,
                absolute_path=str(holdout_path),
                ready_to_open=False,
            ),
        ]
        return payload, artifacts

    def _finalize_tuning_task(
        self,
        session: Any,
        row: MLTaskRow,
    ) -> tuple[dict[str, Any], list[MLTaskArtifactInput]]:
        result = HyperparameterTuningTaskResult.model_validate_json(
            task_result_path(self._paths, row.id).read_text(encoding="utf-8")
        )
        if result.error_summary:
            raise ValidationError(result.error_summary)
        model_path = Path(result.model_artifact_path)
        holdout_path = Path(result.holdout_artifact_path)
        self._require_existing_path(model_path)
        self._require_existing_path(holdout_path)
        canonical_path = self._copy_canonical_model(row.work_item_id, row.id, result.model_key, model_path)
        trained_model = self._trained_models.create(
            session,
            TrainedModelRow(
                work_item_id=row.work_item_id,
                ml_task_id=row.id,
                model_key=result.model_key,
                problem_kind=result.problem_kind,
                artifact_path=str(canonical_path),
            ),
        )
        payload = result.model_dump(mode="json")
        payload["trained_model_id"] = trained_model.id
        payload["canonical_model_artifact_path"] = str(canonical_path)
        artifacts = [
            MLTaskArtifactInput(artifact_kind=MLTaskArtifactKind.MODEL, absolute_path=str(canonical_path)),
            MLTaskArtifactInput(
                artifact_kind=MLTaskArtifactKind.HOLDOUT_DATA,
                absolute_path=str(holdout_path),
                ready_to_open=False,
            ),
        ]
        return payload, artifacts

    def _finalize_evaluate_task(self, row: MLTaskRow) -> tuple[dict[str, Any], list[MLTaskArtifactInput]]:
        result = EvaluateTaskResult.model_validate_json(
            task_result_path(self._paths, row.id).read_text(encoding="utf-8")
        )
        if result.error_summary:
            raise ValidationError(result.error_summary)
        return result.model_dump(mode="json"), []

    def _finalize_inference_task(
        self,
        session: Any,
        row: MLTaskRow,
    ) -> tuple[dict[str, Any], list[MLTaskArtifactInput]]:
        result = InferenceTaskResult.model_validate_json(
            task_result_path(self._paths, row.id).read_text(encoding="utf-8")
        )
        if result.error_summary:
            raise ValidationError(result.error_summary)

        output_path = Path(result.output_file_path)
        self._require_existing_path(output_path)
        canonical_path = self._copy_canonical_inference_output(row.work_item_id, row.id, output_path)
        work_item = self._work_items.get(session, row.work_item_id)
        if work_item is None:
            raise NotFoundError(f"Work item '{row.work_item_id}' was not found.")
        dataset_row = DatasetRow(
            project_id=row.project_id,
            name=f"{work_item.name} predictions",
            source_path=str(canonical_path),
            source_format=DatasetSourceFormat.CSV,
            copied_from=None,
            copied_at=None,
            ml_task_id=row.id,
        )
        self._datasets.create(session, dataset_row)
        payload = result.model_dump(mode="json")
        payload["canonical_output_path"] = str(canonical_path)
        payload["result_dataset_id"] = dataset_row.id
        payload["row_count"] = result.summary.row_count
        payload["input_file_count"] = result.summary.input_file_count
        payload["prediction_column_name"] = result.summary.prediction_column_name
        artifacts = [
            MLTaskArtifactInput(
                artifact_kind=MLTaskArtifactKind.INFERENCE_RESULT,
                absolute_path=str(canonical_path),
                ready_to_open=True,
            )
        ]
        return payload, artifacts

    def _finalize_failure(self, ml_task_id: str, return_code: int) -> MLTaskRow:
        result_path = task_result_path(self._paths, ml_task_id)
        error_summary = f"Worker process exited with code {return_code}."
        if result_path.exists():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                if isinstance(payload.get("error_summary"), str) and payload["error_summary"].strip():
                    error_summary = payload["error_summary"].strip()
            except json.JSONDecodeError:
                pass
        return self.fail_ml_task(FailMLTaskInput(ml_task_id=ml_task_id, error_summary=error_summary))

    def _complete_row(
        self,
        session: Any,
        row: MLTaskRow,
        result_payload: Mapping[str, Any],
        artifacts: list[MLTaskArtifactInput],
    ) -> MLTaskRow:
        persisted_artifacts: list[MLTaskArtifactRow] = []
        for artifact in artifacts:
            artifact_path = Path(artifact.absolute_path)
            self._require_existing_path(artifact_path)
            persisted_artifacts.append(
                MLTaskArtifactRow(
                    ml_task_id=row.id,
                    artifact_kind=artifact.artifact_kind,
                    absolute_path=str(artifact_path),
                    ready_to_open=artifact.ready_to_open,
                    created_at=_utc_now(),
                )
            )

        return self._ml_tasks.complete(
            session,
            row.id,
            dict(result_payload),
            _utc_now(),
            persisted_artifacts,
        )

    def _copy_canonical_model(
        self,
        work_item_id: str,
        ml_task_id: str,
        model_key: str,
        source_path: Path,
    ) -> Path:
        destination_dir = canonical_model_dir(self._paths, work_item_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / f"{ml_task_id}-{model_key.replace('.', '_')}.joblib"
        shutil.copy2(source_path, destination_path)
        return destination_path

    def _copy_canonical_inference_output(
        self,
        work_item_id: str,
        ml_task_id: str,
        source_path: Path,
    ) -> Path:
        destination_dir = canonical_inference_dir(self._paths, work_item_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / f"{ml_task_id}-predictions.csv"
        shutil.copy2(source_path, destination_path)
        return destination_path

    def _notify_callbacks(self, task: MLTaskRow) -> None:
        for callback in list(self._callbacks):
            try:
                callback(task)
            except Exception:
                continue

    def _require_existing_path(self, path: Path) -> None:
        if not path.exists():
            raise ValidationError(f"ML task artifact '{path}' does not exist.")

    def _require_transition(self, current: MLTaskStatus, target: MLTaskStatus) -> None:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"ML task transition from '{current.value}' to '{target.value}' is not allowed."
            )
