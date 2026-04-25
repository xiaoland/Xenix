from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field
from sqlmodel import SQLModel

from ..exceptions import ValidationError
from .dataset_inspection import InspectDatasetInput
from .dataset_service import DatasetService, RegisterDatasetInput
from .ml_service import FitWithEvaluateInput, MLService, TuneWithEvaluateInput
from .project_service import CreateProjectInput, ProjectService
from .scenario_template_service import (
    ScenarioTemplateService,
    ScenarioTrainingOperation,
    ScenarioTrainingPlanStep,
)
from .ml.registry import get_model_catalog_entry
from .storage.models import MLTaskRow, MLTaskStatus, MLTaskType, ProjectRow
from .work_item_service import CreateWorkItemInput, WorkItemService

SCENARIO_PROJECT_NAME = "Xenix Scenarios"
SCENARIO_PROJECT_DESCRIPTION = "Application-managed hidden project for scenario mode."


class ScenarioTrainingStepStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StartScenarioTrainingRunInput(SQLModel):
    template_key: str
    work_item_id: str
    selected_steps: list[ScenarioTrainingPlanStep] = Field(default_factory=list)


class PrepareScenarioWorkItemInput(SQLModel):
    template_key: str
    source_path: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    dataset_name: str | None = None
    work_item_name: str | None = None


class ScenarioWorkItemPreparationResult(SQLModel):
    template_key: str
    project_id: str
    work_item_id: str
    dataset_id: str
    feature_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)


class ScenarioTrainingRun(SQLModel):
    template_key: str
    work_item_id: str
    steps: list[ScenarioTrainingPlanStep] = Field(default_factory=list)
    root_task_ids: list[str] = Field(default_factory=list)


class ScenarioTrainingStepSnapshot(SQLModel):
    step_key: str
    operation: ScenarioTrainingOperation
    model_key: str
    model_display_name: str
    root_task_id: str
    root_status: MLTaskStatus
    evaluate_task_id: str | None = None
    evaluate_status: MLTaskStatus | None = None
    trained_model_id: str | None = None
    training_params: dict[str, Any] = Field(default_factory=dict)
    best_params: dict[str, Any] = Field(default_factory=dict)
    evaluation_metrics: dict[str, float] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    primary_metric_name: str | None = None
    primary_metric_value: float | None = None
    candidate_count: int | None = None
    status: ScenarioTrainingStepStatus
    failure_summary: str | None = None


class ScenarioTrainingRunSnapshot(SQLModel):
    template_key: str
    work_item_id: str
    step_snapshots: list[ScenarioTrainingStepSnapshot] = Field(default_factory=list)
    best_trained_model_id: str | None = None
    is_terminal: bool
    can_proceed_to_inference: bool


class ScenarioWorkflowService:
    def __init__(
        self,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        ml_service: MLService,
        template_service: ScenarioTemplateService,
    ) -> None:
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._template_service = template_service

    def ensure_scenario_project(self) -> ProjectRow:
        for project in self._project_service.list_projects():
            if project.name == SCENARIO_PROJECT_NAME:
                return project
        return self._project_service.create_project(
            CreateProjectInput(
                name=SCENARIO_PROJECT_NAME,
                description=SCENARIO_PROJECT_DESCRIPTION,
            )
        )

    def prepare_work_item(self, input_data: PrepareScenarioWorkItemInput) -> ScenarioWorkItemPreparationResult:
        template = self._template_service.get_template(input_data.template_key)
        scenario_project = self.ensure_scenario_project()
        source_path = Path(input_data.source_path).expanduser()
        if not source_path.is_absolute():
            raise ValidationError("Dataset source path must be absolute.")

        inspection = self._dataset_service.inspect_source_file(
            InspectDatasetInput(source_path=str(source_path.resolve()))
        )
        feature_columns = [column.strip() for column in input_data.feature_columns if column.strip()]
        target_columns = [column.strip() for column in input_data.target_columns if column.strip()]
        if len(feature_columns) < template.min_feature_columns:
            raise ValidationError(
                f"Select at least {template.min_feature_columns} input columns for '{template.display_name}'."
            )
        if len(target_columns) != template.required_target_count:
            raise ValidationError(
                f"Select exactly {template.required_target_count} prediction target column for '{template.display_name}'."
            )
        if set(feature_columns) & set(target_columns):
            raise ValidationError("Input columns and prediction target cannot overlap.")

        available_columns = {column.name for column in inspection.columns}
        if not set(feature_columns).issubset(available_columns):
            raise ValidationError("Selected input columns are invalid for the dataset file.")
        if not set(target_columns).issubset(available_columns):
            raise ValidationError("Selected prediction target is invalid for the dataset file.")

        dataset_name = input_data.dataset_name.strip() if input_data.dataset_name else source_path.stem
        work_item_name = input_data.work_item_name.strip() if input_data.work_item_name else source_path.stem
        source_dataset = self._dataset_service.register_dataset(
            RegisterDatasetInput(
                project_id=scenario_project.id,
                source_path=str(source_path.resolve()),
                name=dataset_name,
            )
        )
        work_item = self._work_item_service.create_work_item(
            CreateWorkItemInput(
                project_id=scenario_project.id,
                name=work_item_name,
                source_dataset_id=source_dataset.id,
                feature_columns=feature_columns,
                target_columns=target_columns,
            )
        )
        return ScenarioWorkItemPreparationResult(
            template_key=template.key,
            project_id=scenario_project.id,
            work_item_id=work_item.id,
            dataset_id=work_item.dataset_id,
            feature_columns=feature_columns,
            target_columns=target_columns,
        )

    def start_training_run(self, input_data: StartScenarioTrainingRunInput) -> ScenarioTrainingRun:
        self._work_item_service.get_work_item(input_data.work_item_id)
        template = self._template_service.get_template(input_data.template_key)
        steps = input_data.selected_steps or template.training_plan

        root_task_ids: list[str] = []
        for step in steps:
            created = self._submit_plan_step(input_data.work_item_id, step)
            root_task_ids.append(created.id)

        return ScenarioTrainingRun(
            template_key=template.key,
            work_item_id=input_data.work_item_id,
            steps=steps,
            root_task_ids=root_task_ids,
        )

    def get_training_run_snapshot(self, run: ScenarioTrainingRun) -> ScenarioTrainingRunSnapshot:
        template = self._template_service.get_template(run.template_key)
        work_item = self._work_item_service.get_work_item(run.work_item_id)
        tasks_by_id = {task.id: task for task in self._ml_service.list_work_item_tasks(run.work_item_id)}
        run_steps = run.steps or template.training_plan

        step_snapshots: list[ScenarioTrainingStepSnapshot] = []
        for step, root_task_id in zip(run_steps, run.root_task_ids, strict=True):
            root_task = tasks_by_id[root_task_id]
            evaluate_task = self._find_follow_up_evaluate(run.work_item_id, root_task_id)
            step_snapshots.append(self._build_step_snapshot(step, root_task, evaluate_task))

        is_terminal = all(
            snapshot.status in {ScenarioTrainingStepStatus.SUCCEEDED, ScenarioTrainingStepStatus.FAILED}
            for snapshot in step_snapshots
        )
        can_proceed = template.supervised_required and is_terminal and work_item.best_trained_model_id is not None
        return ScenarioTrainingRunSnapshot(
            template_key=run.template_key,
            work_item_id=run.work_item_id,
            step_snapshots=step_snapshots,
            best_trained_model_id=work_item.best_trained_model_id,
            is_terminal=is_terminal,
            can_proceed_to_inference=can_proceed,
        )

    def _submit_plan_step(self, work_item_id: str, step: ScenarioTrainingPlanStep) -> MLTaskRow:
        if step.operation is ScenarioTrainingOperation.FIT:
            return self._ml_service.fit_with_evaluate(
                FitWithEvaluateInput(
                    work_item_id=work_item_id,
                    model_key=step.model_key,
                    params=step.params,
                )
            )
        return self._ml_service.tune_with_evaluate(
            TuneWithEvaluateInput(
                work_item_id=work_item_id,
                model_key=step.model_key,
                param_grid=step.param_grid,
            )
        )

    def _find_follow_up_evaluate(self, work_item_id: str, root_task_id: str) -> MLTaskRow | None:
        for task in self._ml_service.list_work_item_tasks(work_item_id):
            if task.task_type is not MLTaskType.EVALUATE:
                continue
            evaluate_model = (task.request_payload or {}).get("evaluate_model", {})
            if evaluate_model.get("source_ml_task_id") == root_task_id:
                return task
        return None

    def _build_step_snapshot(
        self,
        step: ScenarioTrainingPlanStep,
        root_task: MLTaskRow,
        evaluate_task: MLTaskRow | None,
    ) -> ScenarioTrainingStepSnapshot:
        catalog = get_model_catalog_entry(step.model_key)
        if root_task.status in {MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
            return ScenarioTrainingStepSnapshot(
                step_key=step.step_key,
                operation=step.operation,
                model_key=step.model_key,
                model_display_name=catalog.display_name,
                root_task_id=root_task.id,
                root_status=root_task.status,
                trained_model_id=_extract_trained_model_id(root_task),
                training_params=_extract_training_params(root_task),
                best_params=_extract_best_params(root_task),
                result_summary=_extract_result_summary(root_task),
                candidate_count=_extract_candidate_count(root_task),
                status=ScenarioTrainingStepStatus.FAILED,
                failure_summary=root_task.error_summary,
            )

        if root_task.status is MLTaskStatus.SUCCEEDED and evaluate_task is None and not catalog.requires_target:
            return ScenarioTrainingStepSnapshot(
                step_key=step.step_key,
                operation=step.operation,
                model_key=step.model_key,
                model_display_name=catalog.display_name,
                root_task_id=root_task.id,
                root_status=root_task.status,
                trained_model_id=_extract_trained_model_id(root_task),
                training_params=_extract_training_params(root_task),
                best_params=_extract_best_params(root_task),
                result_summary=_extract_result_summary(root_task),
                candidate_count=_extract_candidate_count(root_task),
                status=ScenarioTrainingStepStatus.SUCCEEDED,
            )

        if root_task.status in {MLTaskStatus.PENDING, MLTaskStatus.RUNNING} or evaluate_task is None:
            return ScenarioTrainingStepSnapshot(
                step_key=step.step_key,
                operation=step.operation,
                model_key=step.model_key,
                model_display_name=catalog.display_name,
                root_task_id=root_task.id,
                root_status=root_task.status,
                trained_model_id=_extract_trained_model_id(root_task),
                training_params=_extract_training_params(root_task),
                best_params=_extract_best_params(root_task),
                result_summary=_extract_result_summary(root_task),
                candidate_count=_extract_candidate_count(root_task),
                status=ScenarioTrainingStepStatus.RUNNING,
            )

        if evaluate_task.status in {MLTaskStatus.PENDING, MLTaskStatus.RUNNING}:
            return ScenarioTrainingStepSnapshot(
                step_key=step.step_key,
                operation=step.operation,
                model_key=step.model_key,
                model_display_name=catalog.display_name,
                root_task_id=root_task.id,
                root_status=root_task.status,
                evaluate_task_id=evaluate_task.id,
                evaluate_status=evaluate_task.status,
                trained_model_id=_extract_trained_model_id(root_task),
                training_params=_extract_training_params(root_task),
                best_params=_extract_best_params(root_task),
                result_summary=_extract_result_summary(root_task),
                candidate_count=_extract_candidate_count(root_task),
                status=ScenarioTrainingStepStatus.RUNNING,
            )

        if evaluate_task.status is MLTaskStatus.SUCCEEDED:
            primary_metric_name, primary_metric_value, evaluation_metrics = _extract_evaluation_metrics(evaluate_task)
            return ScenarioTrainingStepSnapshot(
                step_key=step.step_key,
                operation=step.operation,
                model_key=step.model_key,
                model_display_name=catalog.display_name,
                root_task_id=root_task.id,
                root_status=root_task.status,
                evaluate_task_id=evaluate_task.id,
                evaluate_status=evaluate_task.status,
                trained_model_id=_extract_trained_model_id(root_task),
                training_params=_extract_training_params(root_task),
                best_params=_extract_best_params(root_task),
                evaluation_metrics=evaluation_metrics,
                result_summary=_extract_result_summary(root_task),
                primary_metric_name=primary_metric_name,
                primary_metric_value=primary_metric_value,
                candidate_count=_extract_candidate_count(root_task),
                status=ScenarioTrainingStepStatus.SUCCEEDED,
            )

        primary_metric_name, primary_metric_value, evaluation_metrics = _extract_evaluation_metrics(evaluate_task)
        return ScenarioTrainingStepSnapshot(
            step_key=step.step_key,
            operation=step.operation,
            model_key=step.model_key,
            model_display_name=catalog.display_name,
            root_task_id=root_task.id,
            root_status=root_task.status,
            evaluate_task_id=evaluate_task.id,
            evaluate_status=evaluate_task.status,
            trained_model_id=_extract_trained_model_id(root_task),
            training_params=_extract_training_params(root_task),
            best_params=_extract_best_params(root_task),
            evaluation_metrics=evaluation_metrics,
            result_summary=_extract_result_summary(root_task),
            primary_metric_name=primary_metric_name,
            primary_metric_value=primary_metric_value,
            candidate_count=_extract_candidate_count(root_task),
            status=ScenarioTrainingStepStatus.FAILED,
            failure_summary=evaluate_task.error_summary,
        )


def _extract_trained_model_id(task: MLTaskRow) -> str | None:
    result_payload = task.result_payload or {}
    trained_model_id = result_payload.get("trained_model_id")
    return str(trained_model_id) if isinstance(trained_model_id, str) and trained_model_id else None


def _extract_training_params(task: MLTaskRow) -> dict[str, Any]:
    result_payload = task.result_payload or {}
    params = result_payload.get("params")
    if isinstance(params, dict):
        return dict(params)
    return {}


def _extract_best_params(task: MLTaskRow) -> dict[str, Any]:
    result_payload = task.result_payload or {}
    best_params = result_payload.get("best_params")
    if isinstance(best_params, dict):
        return dict(best_params)
    return {}


def _extract_candidate_count(task: MLTaskRow) -> int | None:
    result_payload = task.result_payload or {}
    tuning_summary = result_payload.get("tuning_summary")
    if not isinstance(tuning_summary, dict):
        return None
    cv_summary = tuning_summary.get("cv_summary")
    if not isinstance(cv_summary, dict):
        return None
    candidate_count = cv_summary.get("candidate_count")
    return int(candidate_count) if isinstance(candidate_count, int) else None


def _extract_result_summary(task: MLTaskRow) -> dict[str, Any]:
    result_payload = task.result_payload or {}
    result_summary = result_payload.get("result_summary")
    if isinstance(result_summary, dict):
        return dict(result_summary)
    return {}


def _extract_evaluation_metrics(task: MLTaskRow) -> tuple[str | None, float | None, dict[str, float]]:
    result_payload = task.result_payload or {}
    evaluation = result_payload.get("evaluation")
    if not isinstance(evaluation, dict):
        return None, None, {}

    primary_metric_name = evaluation.get("primary_metric_name")
    primary_metric_value = evaluation.get("primary_metric_value")
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}

    normalized_metrics: dict[str, float] = {}
    for key, value in metrics.items():
        if isinstance(key, str) and isinstance(value, (int, float)):
            normalized_metrics[key] = float(value)

    resolved_primary_name = str(primary_metric_name) if isinstance(primary_metric_name, str) else None
    resolved_primary_value = float(primary_metric_value) if isinstance(primary_metric_value, (int, float)) else None
    return resolved_primary_name, resolved_primary_value, normalized_metrics
