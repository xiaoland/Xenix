from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import InvalidStateTransitionError, ValidationError
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_task_service import CompleteMLTaskInput, CreateMLTaskInput, MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskType
from xenix.services.work_item_service import (
    AttachDatasetSelectionInput,
    CreateWorkItemInput,
    WorkItemService,
)


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ProjectService, WorkItemService, DatasetService, MLTaskService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory)
    dataset_service = DatasetService(context.session_factory)
    ml_task_service = MLTaskService(context.session_factory, paths)
    return project_service, work_item_service, dataset_service, ml_task_service


def test_dataset_service_inspects_csv_summary_and_column_kinds(monkeypatch, tmp_path: Path) -> None:
    _project_service, _work_item_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text(
        "age,city,active\n30,Shanghai,True\n41,Suzhou,False\n",
        encoding="utf-8",
    )

    inspection = dataset_service.inspect_source_file(
        InspectDatasetInput(source_path=str(dataset_file.resolve()))
    )

    assert inspection.file_name == "customers.csv"
    assert inspection.row_count == 2
    assert inspection.column_count == 3
    assert [column.name for column in inspection.columns] == ["age", "city", "active"]
    assert inspection.columns[0].kind.value == "numeric"


def test_dataset_service_rejects_empty_dataset_file(monkeypatch, tmp_path: Path) -> None:
    _project_service, _work_item_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "empty.csv"
    dataset_file.write_text("age,name\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        dataset_service.inspect_source_file(InspectDatasetInput(source_path=str(dataset_file.resolve())))


def test_work_item_service_persists_dataset_feature_and_target_selection(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(project_id=project.id, name="Churn")
    )

    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,income,label\n30,9000,1\n41,12000,0\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            project_id=project.id,
            source_path=str(dataset_file.resolve()),
            name="Customers",
        )
    )

    updated = work_item_service.attach_dataset_selection(
        AttachDatasetSelectionInput(
            work_item_id=work_item.id,
            dataset_id=dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
    )

    assert updated.dataset_id == dataset.id
    assert updated.feature_columns == ["age", "income"]
    assert updated.target_columns == ["label"]


def test_work_item_service_rejects_overlapping_feature_and_target_columns(monkeypatch, tmp_path: Path) -> None:
    project_service, work_item_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    work_item = work_item_service.create_work_item(
        CreateWorkItemInput(project_id=project.id, name="Churn")
    )

    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,income,label\n30,9000,1\n41,12000,0\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            project_id=project.id,
            source_path=str(dataset_file.resolve()),
            name="Customers",
        )
    )

    with pytest.raises(ValidationError):
        work_item_service.attach_dataset_selection(
            AttachDatasetSelectionInput(
                work_item_id=work_item.id,
                dataset_id=dataset.id,
                feature_columns=["age", "label"],
                target_columns=["label"],
            )
        )


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
