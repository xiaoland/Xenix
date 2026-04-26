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
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus, MLTaskType
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
        "regression.bayesian_ridge",
        "regression.gradient_boosting",
    ]
    assert initial_snapshot.can_proceed_to_inference is False
    assert len(all_tasks) in {5, 6}
    assert [task.task_type for task in all_tasks].count(MLTaskType.EVALUATE) >= 2
    assert sum(1 for task in all_tasks if task.status is MLTaskStatus.SUCCEEDED) >= 4
    assert terminal_snapshot.is_terminal is True
    assert terminal_snapshot.can_proceed_to_inference is True
    assert sum(1 for step in terminal_snapshot.step_snapshots if step.status is ScenarioTrainingStepStatus.SUCCEEDED) >= 2
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


def test_start_training_run_uses_selected_steps_when_provided(
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
    template_service = ScenarioTemplateService()
    template = template_service.get_template("sales_demand_forecast.v1")
    scenario_project = workflow_service.ensure_scenario_project()

    dataset_file = tmp_path / "selected-demand.csv"
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
    dataset = _register_dataset(dataset_service, scenario_project.id, dataset_file, name="Selected Demand")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=scenario_project.id,
            name="Selected Model Run",
            source_dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )

    selected_steps = [template.training_plan[0]]
    run = workflow_service.start_training_run(
        StartScenarioTrainingRunInput(
            template_key=template.key,
            work_item_id=work_item.id,
            selected_steps=selected_steps,
        )
    )
    terminal_snapshot = _wait_for_terminal_run(workflow_service, run)
    root_tasks = [ml_service.get_task_details(task_id).task for task_id in run.root_task_ids]

    assert len(run.root_task_ids) == 1
    assert len(run.steps) == 1
    assert root_tasks[0].task_type is MLTaskType.FIT
    assert _extract_model_key(root_tasks[0]) == "regression.linear"
    assert len(terminal_snapshot.step_snapshots) == 1
    assert terminal_snapshot.step_snapshots[0].model_key == "regression.linear"


def test_clustering_training_run_finishes_without_inference_gate(
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

    dataset_file = tmp_path / "segments.csv"
    dataset_file.write_text(
        "spend,visits,segment\n"
        "100,1,A\n"
        "110,1,A\n"
        "120,2,A\n"
        "420,9,C\n"
        "430,8,C\n"
        "440,9,C\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, scenario_project.id, dataset_file, name="Segments")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=scenario_project.id,
            name="Segmentation Run",
            source_dataset_id=dataset.id,
            feature_columns=["spend", "visits", "segment"],
            target_columns=[],
        )
    )

    run = workflow_service.start_training_run(
        StartScenarioTrainingRunInput(
            template_key="customer_segmentation_clustering.v1",
            work_item_id=work_item.id,
        )
    )
    initial_snapshot = workflow_service.get_training_run_snapshot(run)
    root_tasks = [ml_service.get_task_details(task_id).task for task_id in run.root_task_ids]
    terminal_snapshot = _wait_for_terminal_run(workflow_service, run)
    all_tasks = ml_service.list_work_item_tasks(work_item.id)

    assert [task.task_type for task in root_tasks] == [
        MLTaskType.FIT,
        MLTaskType.FIT,
    ]
    assert [_extract_model_key(task) for task in root_tasks] == [
        "clustering.kmeans",
        "clustering.dbscan",
    ]
    assert initial_snapshot.can_proceed_to_inference is False
    assert len(all_tasks) == 2
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in all_tasks)
    assert terminal_snapshot.is_terminal is True
    assert terminal_snapshot.can_proceed_to_inference is False
    assert terminal_snapshot.best_trained_model_id is None
    assert all(step.status is ScenarioTrainingStepStatus.SUCCEEDED for step in terminal_snapshot.step_snapshots)
    assert all(step.evaluate_task_id is None for step in terminal_snapshot.step_snapshots)
    assert all(isinstance(step.result_summary.get("cluster_count"), int) for step in terminal_snapshot.step_snapshots)


def test_anomaly_training_run_finishes_without_inference_gate(
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

    dataset_file = tmp_path / "anomaly-run.csv"
    dataset_file.write_text(
        "amount,count,region\n"
        "10,1,North\n"
        "11,1,North\n"
        "12,1,North\n"
        "13,2,North\n"
        "14,2,North\n"
        "15,2,North\n"
        "120,20,South\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, scenario_project.id, dataset_file, name="Anomaly Run")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=scenario_project.id,
            name="Anomaly Run",
            source_dataset_id=dataset.id,
            feature_columns=["amount", "count", "region"],
            target_columns=[],
        )
    )

    run = workflow_service.start_training_run(
        StartScenarioTrainingRunInput(
            template_key="anomaly_detection.v1",
            work_item_id=work_item.id,
        )
    )
    terminal_snapshot = _wait_for_terminal_run(workflow_service, run)
    root_tasks = [ml_service.get_task_details(task_id).task for task_id in run.root_task_ids]
    all_tasks = ml_service.list_work_item_tasks(work_item.id)

    assert [task.task_type for task in root_tasks] == [
        MLTaskType.FIT,
        MLTaskType.FIT,
    ]
    assert [_extract_model_key(task) for task in root_tasks] == [
        "anomaly.isolation_forest",
        "anomaly.local_outlier_factor",
    ]
    assert terminal_snapshot.is_terminal is True
    assert terminal_snapshot.can_proceed_to_inference is False
    assert len(all_tasks) == 2
    assert all(step.evaluate_task_id is None for step in terminal_snapshot.step_snapshots)
    assert all(isinstance(step.result_summary.get("anomaly_count"), int) for step in terminal_snapshot.step_snapshots)
    for task_id in run.root_task_ids:
        details = ml_service.get_task_details(task_id)
        export_artifacts = [
            artifact for artifact in details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
        ]
        assert len(export_artifacts) == 1
        assert Path(export_artifacts[0].absolute_path).name == "anomaly_scores.csv"


def test_key_driver_training_run_exports_reports_without_inference_gate(
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

    dataset_file = tmp_path / "drivers.csv"
    dataset_file.write_text(
        "price,discount,region,revenue\n"
        "10,1,North,120\n"
        "11,1,North,130\n"
        "12,2,North,150\n"
        "20,1,South,190\n"
        "21,2,South,215\n"
        "22,2,South,230\n"
        "30,3,West,330\n"
        "31,3,West,340\n"
        "32,4,West,365\n"
        "33,4,West,380\n",
        encoding="utf-8",
    )
    dataset = _register_dataset(dataset_service, scenario_project.id, dataset_file, name="Drivers")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=scenario_project.id,
            name="Driver Run",
            source_dataset_id=dataset.id,
            feature_columns=["price", "discount", "region"],
            target_columns=["revenue"],
        )
    )

    run = workflow_service.start_training_run(
        StartScenarioTrainingRunInput(
            template_key="key_driver_analysis.v1",
            work_item_id=work_item.id,
        )
    )
    terminal_snapshot = _wait_for_terminal_run(workflow_service, run)
    root_tasks = [ml_service.get_task_details(task_id).task for task_id in run.root_task_ids]
    all_tasks = ml_service.list_work_item_tasks(work_item.id)

    assert [task.task_type for task in root_tasks] == [
        MLTaskType.FIT,
        MLTaskType.FIT,
    ]
    assert [_extract_model_key(task) for task in root_tasks] == [
        "regression.gradient_boosting",
        "regression.lasso",
    ]
    assert terminal_snapshot.is_terminal is True
    assert terminal_snapshot.can_proceed_to_inference is False
    assert [task.task_type for task in all_tasks].count(MLTaskType.EVALUATE) == 2
    assert all(step.evaluate_task_id is not None for step in terminal_snapshot.step_snapshots)
    assert all(step.result_summary.get("key_driver_report") is True for step in terminal_snapshot.step_snapshots)
    for task_id in run.root_task_ids:
        details = ml_service.get_task_details(task_id)
        export_artifacts = [
            artifact for artifact in details.artifacts if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
        ]
        assert len(export_artifacts) == 1
        assert Path(export_artifacts[0].absolute_path).name == "key_drivers.csv"
