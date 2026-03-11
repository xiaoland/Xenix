import time
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import (
    BulkTuneWithEvaluateInput,
    BulkTuningSelection,
    FitWithEvaluateInput,
    MLService,
    TuneWithEvaluateInput,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskStatus, MLTaskType
from xenix.services.work_item_service import (
    AttachDatasetSelectionInput,
    CreateWorkItemInput,
    WorkItemService,
)


def _build_services(
    monkeypatch,
    tmp_path: Path,
) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService, MLService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory)
    dataset_service = DatasetService(context.session_factory)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    return project_service, work_item_service, dataset_service, ml_task_service, ml_service


def _wait_for_terminal_tasks(
    ml_service: MLService,
    work_item_id: str,
    expected_count: int,
    timeout_seconds: float = 60.0,
) -> list:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        tasks = ml_service.list_work_item_tasks(work_item_id)
        if len(tasks) >= expected_count and all(
            task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}
            for task in tasks
        ):
            return tasks
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for ML tasks to complete.")


def test_fit_with_evaluate_runs_in_background_and_persists_best_model(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(CreateWorkItemInput(project_id=project.id, name="Demand"))
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
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(project_id=project.id, source_path=str(dataset_file.resolve()), name="Demand")
    )
    work_item_service.attach_dataset_selection(
        AttachDatasetSelectionInput(
            work_item_id=work_item.id,
            dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )

    fit_task = ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)
    trained_models = ml_service.list_trained_models(work_item.id)
    work_item_after = work_item_service.get_work_item(work_item.id)
    fit_details = ml_service.get_task_details(fit_task.id)

    assert len(tasks) == 2
    assert {task.task_type for task in tasks} == {MLTaskType.FIT, MLTaskType.EVALUATE}
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(trained_models) == 1
    assert work_item_after.best_trained_model_id == trained_models[0].id
    assert len(fit_details.artifacts) == 2
    assert any(log.level == "INFO" for log in fit_details.logs)


def test_bulk_tuning_creates_one_tuning_task_per_model_and_follow_up_evaluations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(CreateWorkItemInput(project_id=project.id, name="Churn"))
    dataset_file = tmp_path / "churn.csv"
    dataset_file.write_text(
        "age,tenure,segment,label\n"
        "22,1,A,0\n"
        "25,2,A,0\n"
        "29,3,B,1\n"
        "31,4,B,1\n"
        "34,5,C,1\n"
        "36,6,C,1\n"
        "39,1,A,0\n"
        "42,2,B,0\n"
        "45,3,C,1\n"
        "48,4,A,1\n"
        "51,5,B,1\n"
        "54,6,C,1\n",
        encoding="utf-8",
    )
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(project_id=project.id, source_path=str(dataset_file.resolve()), name="Churn")
    )
    work_item_service.attach_dataset_selection(
        AttachDatasetSelectionInput(
            work_item_id=work_item.id,
            dataset_id=dataset.id,
            feature_columns=["age", "tenure", "segment"],
            target_columns=["label"],
        )
    )

    created = ml_service.bulk_tune_with_evaluate(
        BulkTuneWithEvaluateInput(
            work_item_id=work_item.id,
            selections=[
                BulkTuningSelection(
                    model_key="classification.logistic_regression",
                    param_grid={"C": [0.1, 1.0], "max_iter": [500, 1000]},
                ),
                BulkTuningSelection(
                    model_key="classification.random_forest",
                    param_grid={
                        "n_estimators": [50, 100],
                        "max_depth": [0, 5],
                        "max_features": ["all", "sqrt"],
                    },
                ),
            ],
        )
    )

    tasks = _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=4)

    assert len(created) == 2
    assert len(tasks) == 4
    assert [task.task_type for task in tasks].count(MLTaskType.HYPERPARAMETER_TUNING) == 2
    assert [task.task_type for task in tasks].count(MLTaskType.EVALUATE) == 2
    assert all(task.status is MLTaskStatus.SUCCEEDED for task in tasks)
    assert len(ml_service.list_trained_models(work_item.id)) == 2


def test_tuning_rejects_empty_param_grid_sequences_before_worker(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service, ml_service = _build_services(
        monkeypatch, tmp_path
    )
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(CreateWorkItemInput(project_id=project.id, name="Churn"))
    dataset_file = tmp_path / "churn.csv"
    dataset_file.write_text(
        "age,tenure,segment,label\n"
        "22,1,A,0\n"
        "25,2,A,0\n"
        "29,3,B,1\n"
        "31,4,B,1\n"
        "34,5,C,1\n"
        "36,6,C,1\n",
        encoding="utf-8",
    )
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(project_id=project.id, source_path=str(dataset_file.resolve()), name="Churn")
    )
    work_item_service.attach_dataset_selection(
        AttachDatasetSelectionInput(
            work_item_id=work_item.id,
            dataset_id=dataset.id,
            feature_columns=["age", "tenure", "segment"],
            target_columns=["label"],
        )
    )

    with pytest.raises(ValidationError):
        ml_service.tune_with_evaluate(
            TuneWithEvaluateInput(
                work_item_id=work_item.id,
                model_key="classification.random_forest",
                param_grid={"n_estimators": [], "max_depth": [3], "max_features": ["sqrt"]},
            )
        )
