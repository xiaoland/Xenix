import logging
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from xenix.services.artifact_service import ArtifactService
from xenix.services.dataset_export_service import DatasetExportService
from xenix.services.dataset_inspection import InspectDatasetInput, load_dataframe
from xenix.services.dataset_service import (
    DatasetService,
    ExportDatasetCopyInput,
    MaterializeManualApplyCsvInput,
    RegisterDatasetInput,
)
from xenix.services.tabular import TabularRuntimeError
from xenix.services.link_router import LinkRouter
from xenix.services.ml_task_service import CompleteMLTaskInput, CreateMLTaskInput, MLTaskService
from xenix.services.project_service import CreateProjectInput, ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import DatasetSourceFormat, MLTaskType


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


def _rewrite_xlsx_dimension(path: Path, dimension_ref: str) -> None:
    replacement_path = path.with_suffix(".rewritten.xlsx")
    with ZipFile(path, "r") as source, ZipFile(replacement_path, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = content.decode("utf-8")
                text = re.sub(r'<dimension ref="[^"]+"\s*/>', f'<dimension ref="{dimension_ref}"/>', text, count=1)
                content = text.encode("utf-8")
            target.writestr(item, content)
    replacement_path.replace(path)


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


def test_dataset_service_registers_xlsx_attachment_with_stale_dimension_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "stale-dimensions.xlsx"
    pd.DataFrame(
        [
            {"name": "Acme", "value": 12},
            {"name": "Contoso", "value": 18},
        ]
    ).to_excel(dataset_file, index=False)
    _rewrite_xlsx_dimension(dataset_file, "A1")

    attachment = dataset_service.register_dataset_attachment(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Customers")
    )

    assert attachment.name == "Customers"
    assert attachment.file_name == "stale-dimensions.xlsx"
    assert attachment.source_format == "xlsx"
    assert attachment.row_count == 2
    assert attachment.column_count == 2
    assert attachment.preview_columns == ["name", "value"]


def test_dataset_service_registers_workbook_sheets_as_app_owned_parquet_datasets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "sales.xlsx"
    with pd.ExcelWriter(dataset_file) as writer:
        pd.DataFrame([{"region": "north", "amount": 10}, {"region": "south", "amount": 5}]).to_excel(
            writer,
            sheet_name="April",
            index=False,
        )
        pd.DataFrame([{"region": "east", "amount": 7}]).to_excel(
            writer,
            sheet_name="May",
            index=False,
        )

    attachment = dataset_service.register_dataset_attachment(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Sales")
    )

    assert attachment.file_name == "sales.xlsx"
    assert attachment.source_format == "xlsx"
    assert [item.name for item in attachment.datasets] == ["Sales - April", "Sales - May"]
    assert [item.row_count for item in attachment.datasets] == [2, 1]

    first = dataset_service.get_dataset(attachment.datasets[0].dataset_id)
    second = dataset_service.get_dataset(attachment.datasets[1].dataset_id)
    assert first.source_format is DatasetSourceFormat.PARQUET
    assert second.source_format is DatasetSourceFormat.PARQUET
    assert Path(first.source_path).suffix == ".parquet"
    assert Path(second.source_path).suffix == ".parquet"
    assert first.import_id == second.import_id
    assert first.workbook_id == second.workbook_id
    assert [first.sheet_name, second.sheet_name] == ["April", "May"]
    assert [first.sheet_index, second.sheet_index] == [0, 1]
    assert load_dataframe(Path(first.source_path), first.source_format).to_dict(orient="records") == [
        {"region": "north", "amount": 10},
        {"region": "south", "amount": 5},
    ]


def test_dataset_service_discards_unreferenced_dataset(monkeypatch, tmp_path: Path) -> None:
    _project_service, dataset_service, _ml_task_service = _build_services(monkeypatch, tmp_path)
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Customers")
    )
    materialized_path = Path(dataset.source_path)

    assert dataset_service.discard_unreferenced_dataset(dataset.id) is True

    with pytest.raises(NotFoundError):
        dataset_service.get_dataset(dataset.id)
    assert not materialized_path.exists()


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

    def fail_pandas_export(*_args, **_kwargs):
        raise AssertionError("Dataset export should use Polars, not Pandas.")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_pandas_export)
    monkeypatch.setattr(pd.DataFrame, "to_excel", fail_pandas_export)

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
    gbk_export = dataset_service.export_dataset_copy(
        ExportDatasetCopyInput(
            dataset_id=dataset.id,
            destination_path=str((tmp_path / "exports" / "predictions-gbk.csv").resolve()),
            csv_encoding="gbk",
        )
    )

    assert bom_export.read_bytes().startswith(b"\xef\xbb\xbf")
    assert bom_export.read_text(encoding="utf-8-sig").splitlines() == [
        "城市,prediction",
        "上海,1",
        "苏州,0",
    ]
    assert gbk_export.read_text(encoding="gbk").splitlines() == [
        "城市,prediction",
        "上海,1",
        "苏州,0",
    ]
    exported_frame = pd.read_excel(xlsx_export)
    assert exported_frame.to_dict(orient="records") == [
        {"城市": "上海", "prediction": 1},
        {"城市": "苏州", "prediction": 0},
    ]


def test_dataset_export_service_materializes_workbook_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    artifact_service = ArtifactService(context.session_factory)
    export_service = DatasetExportService(
        paths=paths,
        dataset_service=dataset_service,
        artifact_service=artifact_service,
    )
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("name,value\nAcme,12\nContoso,18\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(dataset_file.resolve()), name="Customers")
    )

    artifact = export_service.materialize_dataset_export_artifact(dataset.id)

    assert artifact.dataset_id == dataset.id
    assert artifact.export_format == "xlsx"
    assert Path(artifact.absolute_path).suffix == ".xlsx"
    assert Path(artifact.absolute_path).exists()
    resolved = artifact_service.resolve_uri(f"artifact://{artifact.artifact_id}")
    assert resolved.metadata_payload["dataset_export"] == {
        "dataset_id": dataset.id,
        "format": "xlsx",
        "source_path": dataset.source_path,
    }
    assert pd.read_excel(artifact.absolute_path).to_dict(orient="records") == [
        {"name": "Acme", "value": 12},
        {"name": "Contoso", "value": 18},
    ]


def test_link_router_rejects_dataset_scheme(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    artifact_service = ArtifactService(context.session_factory)
    router = LinkRouter(artifact_service=artifact_service)

    with pytest.raises(ValidationError, match="Dataset URI scheme is not supported"):
        router.activate("dataset:" + "//dataset-1")


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
