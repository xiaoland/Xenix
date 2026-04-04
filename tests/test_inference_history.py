import time
from datetime import timedelta
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.inference_history_service import (
    InferenceHistoryFilter,
    InferenceHistoryService,
    InferenceHistorySortDirection,
)
from xenix.services.ml_service import FitWithEvaluateInput, InferWithFilesInput, MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskStatus
from xenix.services.work_item_service import CreateWorkItemInput, WorkItemService


def _build_services(
    monkeypatch,
    tmp_path: Path,
) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService, MLService, InferenceHistoryService]:
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
    history_service = InferenceHistoryService(context.session_factory)
    return project_service, work_item_service, dataset_service, ml_task_service, ml_service, history_service


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


def _wait_for_terminal_tasks(
    ml_service: MLService,
    work_item_id: str,
    *,
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


def test_inference_history_lists_only_persisted_inference_results_sorted_by_finished_time(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        project_service,
        work_item_service,
        dataset_service,
        _ml_task_service,
        ml_service,
        history_service,
    ) = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))

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
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Demand")
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(
            project_id=project.id,
            name="Demand Run",
            source_dataset_id=dataset.id,
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )

    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=work_item.id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=2)

    first_input = tmp_path / "infer-a.csv"
    first_input.write_text("feature_a,feature_b\n11,9\n12,10\n", encoding="utf-8")
    first_task = ml_service.infer(
        InferWithFilesInput(
            work_item_id=work_item.id,
            input_files=[str(first_input.resolve())],
        )
    )
    _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=3)
    first_details = ml_service.get_task_details(first_task.id)

    time.sleep(0.2)

    second_input = tmp_path / "infer-b.csv"
    second_input.write_text("feature_a,feature_b\n13,11\n14,12\n", encoding="utf-8")
    second_task = ml_service.infer(
        InferWithFilesInput(
            work_item_id=work_item.id,
            input_files=[str(second_input.resolve())],
        )
    )
    _wait_for_terminal_tasks(ml_service, work_item.id, expected_count=4)
    second_details = ml_service.get_task_details(second_task.id)

    desc_rows = history_service.list_results(
        InferenceHistoryFilter(sort_direction=InferenceHistorySortDirection.DESC)
    )
    asc_rows = history_service.list_results(
        InferenceHistoryFilter(sort_direction=InferenceHistorySortDirection.ASC)
    )
    filtered_rows = history_service.list_results(
        InferenceHistoryFilter(
            start_time=first_details.task.finished_at + timedelta(milliseconds=1),
            sort_direction=InferenceHistorySortDirection.ASC,
        )
    )

    assert [row.inference_task_id for row in desc_rows] == [second_task.id, first_task.id]
    assert [row.inference_task_id for row in asc_rows] == [first_task.id, second_task.id]
    assert [row.inference_task_id for row in filtered_rows] == [second_task.id]
    assert all(row.work_item_name == "Demand Run" for row in desc_rows)
    assert all(row.result_dataset_id for row in desc_rows)
    assert all(row.result_path for row in desc_rows)
    assert all(row.model_key == "regression.linear" for row in desc_rows)
    assert all(row.row_count == 2 for row in desc_rows)
