from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import InvalidStateTransitionError
from xenix.services.dataset_service import DatasetService, MaterializeDatasetCopyInput, RegisterDatasetInput
from xenix.services.ml_task_service import CompleteMLTaskInput, CreateMLTaskInput, MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskType
from xenix.services.work_item_service import CreateWorkItemInput, WorkItemService


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    return project_service, work_item_service, dataset_service, ml_task_service


def test_dataset_service_materializes_and_cleans_temp_copy(monkeypatch, tmp_path: Path) -> None:
    project_service, _work_item_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))

    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("id,name\n1,Alice\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            project_id=project.id,
            source_path=str(dataset_file.resolve()),
            name="Customers",
        )
    )

    with dataset_service.materialize_read_copy(
        MaterializeDatasetCopyInput(dataset_id=dataset.id, owner_id="task-1")
    ) as materialized:
        assert materialized.copied_path.exists()
        assert materialized.copied_path.read_text(encoding="utf-8") == dataset_file.read_text(encoding="utf-8")

    assert not materialized.copied_path.exists()
    assert not materialized.copied_path.parent.exists()


def test_ml_task_service_rejects_invalid_state_transition(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, _dataset_service, ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(project_id=project.id, name="Churn")
    )
    task = ml_task_service.create_ml_task(
        CreateMLTaskInput(
            project_id=project.id,
            work_item_id=work_item.id,
            task_type=MLTaskType.FIT,
            request_payload={"model": "regression.ridge"},
        )
    )

    with pytest.raises(InvalidStateTransitionError):
        ml_task_service.complete_ml_task(
            CompleteMLTaskInput(
                ml_task_id=task.id,
                result_payload={"score": 0.91},
            )
        )
