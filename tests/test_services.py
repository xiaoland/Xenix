import logging
from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.dataset_service import (
    DatasetService,
    ExportDatasetCopyInput,
    MaterializeManualApplyCsvInput,
    RegisterDatasetInput,
)
from xenix.services.tabular import TabularRuntimeError
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


def test_dataset_service_inspects_polars_native_column_metadata(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "events.xlsx"
    pd.DataFrame(
        [
            {
                "amount": 10.5,
                "segment": "retail",
                "active": True,
                "event_date": pd.Timestamp("2026-01-01"),
                "note": "first",
            },
            {
                "amount": None,
                "segment": "enterprise",
                "active": False,
                "event_date": pd.Timestamp("2026-01-02"),
                "note": "second",
            },
        ]
    ).to_excel(dataset_file, index=False)

    inspection = dataset_service.inspect_source_file(
        InspectDatasetInput(source_path=str(dataset_file.resolve()))
    )

    kinds = {column.name: column.kind.value for column in inspection.columns}
    nullable = {column.name: column.nullable for column in inspection.columns}
    assert kinds == {
        "amount": "numeric",
        "segment": "categorical",
        "active": "boolean",
        "event_date": "datetime",
        "note": "categorical",
    }
    assert nullable["amount"] is True
    assert nullable["segment"] is False
    assert inspection.preview_rows[0] == ["10.5", "retail", "True", "2026-01-01", "first"]


def test_dataset_service_inspects_xlsx_without_pandas_read_excel(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.xlsx"
    pd.DataFrame(
        [
            {"name": "Acme", "value": 12},
            {"name": "Contoso", "value": 18},
        ]
    ).to_excel(dataset_file, index=False)

    def fail_read_excel(*_args, **_kwargs):
        pytest.fail("xlsx inspection should use the Polars-native tabular path")

    monkeypatch.setattr("xenix.services.dataset_inspection.pd.read_excel", fail_read_excel)

    inspection = dataset_service.inspect_source_file(
        InspectDatasetInput(source_path=str(dataset_file.resolve()))
    )

    assert inspection.row_count == 2
    assert inspection.column_count == 2
    assert inspection.preview_columns == ["name", "value"]


def test_dataset_service_wraps_tabular_runtime_failure_with_structured_error(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,city\n30,Shanghai\n", encoding="utf-8")

    def fail_inspection(_path: Path):
        raise TabularRuntimeError(
            "Polars failed to read the dataset file.",
            error_details={
                "engine": "polars",
                "phase": "read",
                "package_versions": {
                    "polars": "1.42.1",
                    "polars-runtime-32": "1.41.2",
                },
            },
        )

    monkeypatch.setattr("xenix.services.dataset_service.inspect_dataset_file", fail_inspection)

    with caplog.at_level(logging.ERROR, logger="xenix.services.dataset"):
        with pytest.raises(ValidationError) as exc_info:
            dataset_service.inspect_source_file(
                InspectDatasetInput(source_path=str(dataset_file.resolve()))
            )

    assert "Dataset read failed during inspect_source_file" in caplog.text
    assert exc_info.value.error_code == "tabular_runtime_unavailable"
    assert exc_info.value.error_details["operation"] == "inspect_source_file"
    assert exc_info.value.error_details["source_path"] == str(dataset_file.resolve())
    assert exc_info.value.error_details["tabular"]["package_versions"]["polars-runtime-32"] == "1.41.2"
    assert any("pdm sync -d --clean" in hint for hint in exc_info.value.repair_hints)
    assert exc_info.value.retryable is False


def test_dataset_service_registers_dataset_without_product_project(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,city\n30,Shanghai\n", encoding="utf-8")

    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(dataset_file.resolve()),
            name="Customers",
        )
    )
    sources = dataset_service.list_source_datasets()

    assert dataset.project_id
    assert dataset.derived_from_dataset_id is None
    assert [row.id for row in sources] == [dataset.id]


def test_dataset_service_registers_xlsx_attachment_without_full_inspection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.xlsx"
    pd.DataFrame(
        [
            {"name": "Acme", "value": 12},
            {"name": "Contoso", "value": 18},
        ]
    ).to_excel(dataset_file, index=False)

    def fail_read_excel(*_args, **_kwargs):
        pytest.fail("attachment registration should not read the full xlsx dataframe")

    monkeypatch.setattr("xenix.services.dataset_inspection.pd.read_excel", fail_read_excel)

    attachment = dataset_service.register_dataset_attachment(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Customers")
    )

    assert attachment.name == "Customers"
    assert attachment.file_name == "customers.xlsx"
    assert attachment.source_format == "xlsx"
    assert attachment.row_count == 2
    assert attachment.column_count == 2
    assert attachment.preview_columns == ["name", "value"]


def test_dataset_service_discards_unreferenced_dataset(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Customers")
    )

    assert dataset_service.discard_unreferenced_dataset(dataset.id) is True

    with pytest.raises(NotFoundError):
        dataset_service.get_dataset(dataset.id)


def test_dataset_service_rejects_discard_when_dataset_is_referenced(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    source_file = tmp_path / "customers.csv"
    derived_file = tmp_path / "customers-clean.csv"
    source_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    derived_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    source = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source_file.resolve()), name="Customers")
    )
    dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(derived_file.resolve()),
            name="Customers clean",
            derived_from_dataset_id=source.id,
        )
    )

    with pytest.raises(ValidationError):
        dataset_service.discard_unreferenced_dataset(source.id)


def test_dataset_service_rejects_empty_dataset_file(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "empty.csv"
    dataset_file.write_text("age,name\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        dataset_service.inspect_source_file(InspectDatasetInput(source_path=str(dataset_file.resolve())))


def test_dataset_service_materializes_manual_apply_csv_and_exports_utf8_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    project = project_service.create_project(CreateProjectInput(name="Retail"))
    dataset_file = tmp_path / "predictions.csv"
    dataset_file.write_text("城市,prediction\n上海,1\n", encoding="utf-8")
    dataset = _register_dataset(dataset_service, project.id, dataset_file, name="Predictions")

    materialized = dataset_service.materialize_manual_apply_csv(
        MaterializeManualApplyCsvInput(
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
