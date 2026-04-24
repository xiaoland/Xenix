from __future__ import annotations

from datetime import datetime

from pydantic import Field
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..datetime_utils import normalize_datetime_to_utc
from .ml.registry import get_model_catalog_entry
from .scenario_template_service import ScenarioTemplateService
from .scenario_workflow_service import SCENARIO_PROJECT_NAME
from .storage.repositories import ProjectRepository, TrainedModelRepository, WorkItemRepository
from .trained_model_metadata import parse_trained_model_metadata


class ListCompatibleTrainedModelsInput(SQLModel):
    template_key: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)


class CompatibleTrainedModelOption(SQLModel):
    trained_model_id: str
    work_item_id: str
    work_item_name: str
    model_key: str
    model_display_name: str
    saved_name: str | None = None
    artifact_file_name: str | None = None
    created_at: datetime
    is_best_for_work_item: bool
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    source_dataset_name: str | None = None
    source_dataset_file_name: str | None = None
    dataset_row_count: int | None = None
    dataset_column_count: int | None = None
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)
    save_note: str | None = None
    evaluation_primary_metric_name: str | None = None
    evaluation_primary_metric_value: float | None = None
    evaluation_metrics: dict[str, float] = Field(default_factory=dict)


class ScenarioModelSourceService:
    def __init__(
        self,
        session_factory: sessionmaker,
        template_service: ScenarioTemplateService,
    ) -> None:
        self._session_factory = session_factory
        self._template_service = template_service
        self._projects = ProjectRepository()
        self._work_items = WorkItemRepository()
        self._trained_models = TrainedModelRepository()

    def list_compatible_trained_models(
        self,
        input_data: ListCompatibleTrainedModelsInput,
    ) -> list[CompatibleTrainedModelOption]:
        template = self._template_service.get_template(input_data.template_key)
        if not template.training_plan:
            return []

        feature_columns = [column.strip() for column in input_data.feature_columns if column.strip()]
        target_columns = [column.strip() for column in input_data.target_columns if column.strip()]
        expected_problem_kind = get_model_catalog_entry(template.training_plan[0].model_key).problem_kind

        options: list[CompatibleTrainedModelOption] = []
        with self._session_factory() as session:
            scenario_project = next(
                (project for project in self._projects.list_all(session) if project.name == SCENARIO_PROJECT_NAME),
                None,
            )
            if scenario_project is None:
                return []

            for work_item in self._work_items.list_by_project(session, scenario_project.id):
                if work_item.feature_columns != feature_columns or work_item.target_columns != target_columns:
                    continue

                for trained_model in self._trained_models.list_by_work_item(session, work_item.id):
                    if trained_model.problem_kind != expected_problem_kind:
                        continue
                    catalog = get_model_catalog_entry(trained_model.model_key)
                    metadata = parse_trained_model_metadata(trained_model.metadata_payload)
                    options.append(
                        CompatibleTrainedModelOption(
                            trained_model_id=trained_model.id,
                            work_item_id=work_item.id,
                            work_item_name=work_item.name,
                            model_key=trained_model.model_key,
                            model_display_name=(
                                metadata.model_display_name if metadata is not None else catalog.display_name
                            ),
                            saved_name=metadata.saved_name if metadata is not None else None,
                            artifact_file_name=metadata.artifact_file_name if metadata is not None else None,
                            created_at=normalize_datetime_to_utc(trained_model.created_at),
                            is_best_for_work_item=work_item.best_trained_model_id == trained_model.id,
                            feature_columns=list(work_item.feature_columns),
                            target_columns=list(work_item.target_columns),
                            source_dataset_name=metadata.source_dataset_name if metadata is not None else None,
                            source_dataset_file_name=(
                                metadata.source_dataset_file_name if metadata is not None else None
                            ),
                            dataset_row_count=metadata.dataset_row_count if metadata is not None else None,
                            dataset_column_count=metadata.dataset_column_count if metadata is not None else None,
                            preview_columns=list(metadata.preview_columns) if metadata is not None else [],
                            preview_rows=[list(row) for row in metadata.preview_rows] if metadata is not None else [],
                            save_note=metadata.save_note if metadata is not None else None,
                            evaluation_primary_metric_name=(
                                metadata.evaluation_primary_metric_name if metadata is not None else None
                            ),
                            evaluation_primary_metric_value=(
                                metadata.evaluation_primary_metric_value if metadata is not None else None
                            ),
                            evaluation_metrics=dict(metadata.evaluation_metrics) if metadata is not None else {},
                        )
                    )

        return sorted(options, key=lambda option: option.created_at, reverse=True)
