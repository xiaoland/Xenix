from __future__ import annotations

from pathlib import Path

import pandas as pd

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import DatasetImportRow


def _dataset_service(monkeypatch, tmp_path: Path) -> tuple[DatasetService, object]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return DatasetService(context.session_factory, paths), context


def test_source_presentation_uses_import_provenance_not_materialized_path(monkeypatch, tmp_path: Path) -> None:
    service, _context = _dataset_service(monkeypatch, tmp_path)
    source = tmp_path / "customers.csv"
    source.write_text("name\nAda\n", encoding="utf-8")

    dataset = service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Customers")
    )
    presentation = service.resolve_dataset_source_presentation(dataset.id)

    assert presentation is not None
    assert presentation.dataset_id == dataset.id
    assert presentation.source_group_id
    assert presentation.file_name == source.name
    assert presentation.open_path == str(source.resolve())
    assert presentation.is_openable is True
    assert presentation.open_path != dataset.source_path


def test_source_presentation_keeps_label_when_original_file_is_missing(monkeypatch, tmp_path: Path) -> None:
    service, _context = _dataset_service(monkeypatch, tmp_path)
    source = tmp_path / "customers.csv"
    source.write_text("name\nAda\n", encoding="utf-8")
    dataset = service.register_dataset(RegisterDatasetInput(source_path=str(source.resolve())))
    source.unlink()

    presentation = service.resolve_dataset_source_presentation(dataset.id)

    assert presentation is not None
    assert presentation.file_name == source.name
    assert presentation.open_path is None
    assert presentation.is_openable is False


def test_source_presentation_groups_workbook_sheets_by_import(monkeypatch, tmp_path: Path) -> None:
    service, _context = _dataset_service(monkeypatch, tmp_path)
    source = tmp_path / "sales.xlsx"
    with pd.ExcelWriter(source) as writer:
        pd.DataFrame({"value": [1]}).to_excel(writer, sheet_name="North", index=False)
        pd.DataFrame({"value": [2]}).to_excel(writer, sheet_name="South", index=False)

    attachment = service.register_dataset_attachment(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    presentations = [
        service.resolve_dataset_source_presentation(item.dataset_id)
        for item in attachment.datasets
    ]

    assert len(presentations) == 2
    assert all(item is not None for item in presentations)
    assert {item.source_group_id for item in presentations if item is not None} == {
        presentations[0].source_group_id  # type: ignore[union-attr]
    }


def test_source_presentation_is_soft_for_missing_dataset_or_import(monkeypatch, tmp_path: Path) -> None:
    service, context = _dataset_service(monkeypatch, tmp_path)
    assert service.resolve_dataset_source_presentation("missing") is None

    source = tmp_path / "customers.csv"
    source.write_text("name\nAda\n", encoding="utf-8")
    dataset = service.register_dataset(RegisterDatasetInput(source_path=str(source.resolve())))
    with context.session_factory() as session:
        row = session.get(type(dataset), dataset.id)
        assert row is not None
        row.import_id = None
        session.add(row)
        session.commit()

    assert service.resolve_dataset_source_presentation(dataset.id) is None


def test_source_presentation_fails_closed_for_relative_legacy_source_path(monkeypatch, tmp_path: Path) -> None:
    service, context = _dataset_service(monkeypatch, tmp_path)
    source = tmp_path / "customers.csv"
    source.write_text("name\nAda\n", encoding="utf-8")
    dataset = service.register_dataset(RegisterDatasetInput(source_path=str(source.resolve())))
    monkeypatch.chdir(tmp_path)
    with context.session_factory() as session:
        imported = session.get(DatasetImportRow, dataset.import_id)
        assert imported is not None
        imported.original_path = source.name
        session.add(imported)
        session.commit()

    presentation = service.resolve_dataset_source_presentation(dataset.id)

    assert presentation is not None
    assert presentation.file_name == source.name
    assert presentation.open_path is None
    assert presentation.is_openable is False
