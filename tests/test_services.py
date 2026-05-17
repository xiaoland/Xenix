from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import InvalidStateTransitionError, ValidationError
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.dataset_service import (
    DatasetService,
    ExportDatasetCopyInput,
    MaterializeManualInferenceCsvInput,
    RegisterDatasetInput,
)
from xenix.services.ml_task_service import CompleteMLTaskInput, CreateMLTaskInput, MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskType


def _build_services(monkeypatch, tmp_path: Path) -> tuple[ProjectService, DatasetService, MLTaskService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    return project_service, dataset_service, ml_task_service


def _register_dataset(
    dataset_service: DatasetService,
    project_id: str,
    dataset_path: Path,
    *,
    name: str = "Customers",
) -> object:
    return dataset_service.register_dataset(
        RegisterDatasetInput(
            project_id=project_id,
            source_path=str(dataset_path.resolve()),
            name=name,
        )
    )


def test_dataset_service_inspects_csv_summary_and_column_kinds(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
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
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "empty.csv"
    dataset_file.write_text("age,name\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        dataset_service.inspect_source_file(InspectDatasetInput(source_path=str(dataset_file.resolve())))


def test_dataset_service_materializes_manual_inference_csv_and_exports_utf8_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "predictions.csv"
    dataset_file.write_text("城市,prediction\n上海,1\n", encoding="utf-8")
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Predictions")

    materialized = dataset_service.materialize_manual_inference_csv(
        MaterializeManualInferenceCsvInput(
            feature_columns=["age", "income"],
            rows=[{"age": "30", "income": "9000"}],
        )
    )
    exported = dataset_service.export_dataset_copy(
        ExportDatasetCopyInput(
            dataset_id=dataset.id,
            destination_path=str((tmp_path / "exports" / "predictions-copy.csv").resolve()),
        )
    )

    assert materialized.exists()
    assert materialized.read_text(encoding="utf-8").splitlines() == ["age,income", "30,9000"]
    assert exported.exists()
    assert exported.read_text(encoding="utf-8") == dataset_file.read_text(encoding="utf-8")
    assert not exported.read_bytes().startswith(b"\xef\xbb\xbf")


def test_dataset_service_exports_csv_with_selected_encoding_and_xlsx(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "predictions.csv"
    dataset_file.write_text("城市,prediction\n上海,1\n苏州,0\n", encoding="utf-8")
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Predictions")

    bom_export = dataset_service.export_dataset_copy(
        ExportDatasetCopyInput(
            dataset_id=dataset.id,
            destination_path=str((tmp_path / "exports" / "predictions-bom.csv").resolve()),
            csv_encoding="utf-8-sig",
        )
    )
    xlsx_export = dataset_service.export_dataset_copy(
        ExportDatasetCopyInput(
            dataset_id=dataset.id,
            destination_path=str((tmp_path / "exports" / "predictions.xlsx").resolve()),
        )
    )

    assert bom_export.read_bytes().startswith(b"\xef\xbb\xbf")
    assert bom_export.read_text(encoding="utf-8-sig").splitlines() == [
        "城市,prediction",
        "上海,1",
        "苏州,0",
    ]
    exported_frame = pd.read_excel(xlsx_export)
    assert exported_frame.to_dict(orient="records") == [
        {"城市": "上海", "prediction": 1},
        {"城市": "苏州", "prediction": 0},
    ]


def test_ml_task_service_rejects_invalid_state_transition(monkeypatch, tmp_path: Path) -> None:
    project_service, dataset_service, ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,income,label\n30,9000,1\n41,12000,0\n", encoding="utf-8")
    dataset = _register_dataset(dataset_service, project.id, dataset_file)
    task = ml_task_service.create_ml_task(
        CreateMLTaskInput(
            project_id=project.id,
            dataset_id=dataset.id,
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
