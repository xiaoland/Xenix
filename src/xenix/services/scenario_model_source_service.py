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
    created_at: datetime
    is_best_for_work_item: bool
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)


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
                    options.append(
                        CompatibleTrainedModelOption(
                            trained_model_id=trained_model.id,
                            work_item_id=work_item.id,
                            work_item_name=work_item.name,
                            model_key=trained_model.model_key,
                            model_display_name=catalog.display_name,
                            created_at=normalize_datetime_to_utc(trained_model.created_at),
                            is_best_for_work_item=work_item.best_trained_model_id == trained_model.id,
                            feature_columns=list(work_item.feature_columns),
                            target_columns=list(work_item.target_columns),
                        )
                    )

        return sorted(options, key=lambda option: option.created_at, reverse=True)
