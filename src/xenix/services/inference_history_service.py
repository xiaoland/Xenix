from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session, select

from .storage.models import MLTaskRow, MLTaskStatus, MLTaskType, WorkItemRow


class InferenceHistorySortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class InferenceHistoryFilter(SQLModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    sort_direction: InferenceHistorySortDirection = InferenceHistorySortDirection.DESC


class InferenceHistoryRow(SQLModel):
    inference_task_id: str
    finished_at: datetime
    work_item_id: str
    work_item_name: str | None = None
    model_key: str | None = None
    row_count: int | None = None
    result_dataset_id: str
    result_path: str
    scenario_template_name: str | None = None


class InferenceHistoryService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def list_results(self, filter: InferenceHistoryFilter) -> list[InferenceHistoryRow]:
        with self._session_factory() as session:
            tasks = self._list_candidate_tasks(session, filter)
            rows: list[InferenceHistoryRow] = []
            for task, work_item_name in tasks:
                row = self._build_row(task, work_item_name)
                if row is not None:
                    rows.append(row)
            return rows

    def _list_candidate_tasks(
        self,
        session: Session,
        filter: InferenceHistoryFilter,
    ) -> list[tuple[MLTaskRow, str | None]]:
        statement = (
            select(MLTaskRow, WorkItemRow.name)
            .select_from(MLTaskRow)
            .join(WorkItemRow, WorkItemRow.id == MLTaskRow.work_item_id, isouter=True)
            .where(
                MLTaskRow.task_type == MLTaskType.INFERENCE,
                MLTaskRow.status == MLTaskStatus.SUCCEEDED,
                MLTaskRow.finished_at.is_not(None),
            )
        )
        if filter.start_time is not None:
            statement = statement.where(MLTaskRow.finished_at >= filter.start_time)
        if filter.end_time is not None:
            statement = statement.where(MLTaskRow.finished_at <= filter.end_time)

        order_by = MLTaskRow.finished_at.asc()
        if filter.sort_direction is InferenceHistorySortDirection.DESC:
            order_by = MLTaskRow.finished_at.desc()
        statement = statement.order_by(order_by)
        return list(session.exec(statement))

    def _build_row(self, task: MLTaskRow, work_item_name: str | None) -> InferenceHistoryRow | None:
        finished_at = task.finished_at
        payload = task.result_payload or {}
        result_dataset_id = payload.get("result_dataset_id")
        result_path = payload.get("canonical_output_path")
        if not isinstance(finished_at, datetime):
            return None
        if not isinstance(result_dataset_id, str) or not result_dataset_id:
            return None
        if not isinstance(result_path, str) or not result_path:
            return None

        workflow_context = payload.get("workflow_context", {})
        scenario_template_name = None
        if isinstance(workflow_context, dict):
            template_name = workflow_context.get("scenario_template_name")
            if isinstance(template_name, str) and template_name:
                scenario_template_name = template_name

        model_key = payload.get("model_key")
        row_count = payload.get("row_count")
        return InferenceHistoryRow(
            inference_task_id=task.id,
            finished_at=finished_at,
            work_item_id=task.work_item_id,
            work_item_name=work_item_name,
            model_key=model_key if isinstance(model_key, str) else None,
            row_count=row_count if isinstance(row_count, int) else None,
            result_dataset_id=result_dataset_id,
            result_path=result_path,
            scenario_template_name=scenario_template_name,
        )
