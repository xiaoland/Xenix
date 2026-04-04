import time
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import ProjectService
from xenix.services.scenario_template_service import ScenarioTemplateService
from xenix.services.scenario_workflow_service import (
    SCENARIO_PROJECT_DESCRIPTION,
    SCENARIO_PROJECT_NAME,
    PrepareScenarioWorkItemInput,
    ScenarioTrainingStepStatus,
    ScenarioWorkflowService,
    StartScenarioTrainingRunInput,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskStatus, MLTaskType
from xenix.services.work_item_service import CreateWorkItemInput, WorkItemService


def _build_services(
    monkeypatch,
    tmp_path: Path,
) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService, MLService, ScenarioWorkflowService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    workflow_service = ScenarioWorkflowService(
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        template_service=ScenarioTemplateService(),
    )
    return project_service, work_item_service, dataset_service, ml_task_service, ml_service, workflow_service


def _register_dataset(
    dataset_service: DatasetService,
    project_id: str,
    dataset_path: Path,
    *,
    name: str,
) -> object:
    return dataset_service.register_dataset(
        RegisterDatasetInput(project_id=project_id, source_path=str(dataset_path.resolve()), name=name)
    )


def _wait_for_terminal_run(
    workflow_service: ScenarioWorkflowService,
    run,
    *,
    timeout_seconds: float = 60.0,
):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        snapshot = workflow_service.get_training_run_snapshot(run)
        if snapshot.is_terminal:
            return snapshot
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for the scenario training run to reach a terminal state.")


def _extract_model_key(task) -> str:
    payload = task.request_payload
    if isinstance(payload.get("manual_training"), dict):
        return str(payload["manual_training"].get("model_key", ""))
    if isinstance(payload.get("hyperparameter_tuning"), dict):
        return str(payload["hyperparameter_tuning"].get("model_key", ""))
    return ""


def test_ensure_scenario_project_is_created_once_and_reused(monkeypatch, tmp_path: Path) -> None:
    project_service, _work_item_service, _dataset_service, _ml_task_service, _ml_service, workflow_service = (
        _build_services(monkeypatch, tmp_path)
    )

    first = workflow_service.ensure_scenario_project()
    second = workflow_service.ensure_scenario_project()
    all_projects = project_service.list_projects()

    assert first.id == second.id
    assert first.name == SCENARIO_PROJECT_NAME
    assert first.description == SCENARIO_PROJECT_DESCRIPTION
    assert [project.name for project in all_projects] == [SCENARIO_PROJECT_NAME]


def test_start_training_run_submits_root_tasks_in_template_order_and_enables_proceed_on_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        _project_service,
        work_item_service,
        dataset_service,
        _ml_task_service,
        ml_service,
        workflow_service,
    ) = _build_services(monkeypatch, tmp_path)
    scenario_project = workflow_service.ensure_scenario_project()

    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, scenario_project.id, dataset_file, name="Demand")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=scenario_project.id,
            name="Demand Run",
            source_dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )

    run = workflow_service.start_training_run(
        StartScenarioTrainingRunInput(
            template_key="sales_demand_forecast.v1",
            work_item_id=work_item.id,
        )
    )
    initial_snapshot = workflow_service.get_training_run_snapshot(run)
    root_tasks = [ml_service.get_task_details(task_id).task for task_id in run.root_task_ids]
    terminal_snapshot = _wait_for_terminal_run(workflow_service, run)
    all_tasks = ml_service.list_work_item_tasks(work_item.id)
    work_item_after = work_item_service.get_work_item(work_item.id)

    assert [task.task_type for task in root_tasks] == [
        MLTaskType.FIT,
        MLTaskType.HYPERPARAMETER_TUNING,
        MLTaskType.HYPERPARAMETER_TUNING,
    ]
    assert [_extract_model_key(task) for task in root_tasks] == [
        "regression.linear",
        "regression.ridge",
        "regression.random_forest",
    ]
    assert initial_snapshot.can_proceed_to_inference is False
    assert len(all_tasks) == 6
    assert [task.task_type for task in all_tasks].count(MLTaskType.EVALUATE) == 3
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in all_tasks)
    assert terminal_snapshot.is_terminal is True
    assert terminal_snapshot.can_proceed_to_inference is True
    assert all(
        step.status is ScenarioTrainingStepStatus.SUCCEEDED for step in terminal_snapshot.step_snapshots
    )
    assert work_item_after.best_trained_model_id == terminal_snapshot.best_trained_model_id


def test_prepare_work_item_creates_dataset_and_managed_work_item_in_hidden_scenario_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        project_service,
        work_item_service,
        _dataset_service,
        _ml_task_service,
        _ml_service,
        workflow_service,
    ) = _build_services(monkeypatch, tmp_path)

    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n",
        encoding="utf-8",
    )

    prepared = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )
    scenario_project = project_service.list_projects()[0]
    work_item = work_item_service.get_work_item(prepared.work_item_id)

    assert scenario_project.name == SCENARIO_PROJECT_NAME
    assert prepared.project_id == scenario_project.id
    assert work_item.project_id == scenario_project.id
    assert work_item.dataset_id == prepared.dataset_id
    assert prepared.feature_columns == ["feature_a", "feature_b"]
    assert prepared.target_columns == ["target"]
