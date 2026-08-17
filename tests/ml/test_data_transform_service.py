from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.data_transform import (
    DataQueryInput,
    DataQueryTransformService,
    DatasetSqlBinding,
)


def _make_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> DataQueryTransformService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    return DataQueryTransformService(paths)


def _binding(source_path: Path) -> DatasetSqlBinding:
    return DatasetSqlBinding(
        alias="input",
        dataset_id="dataset-1",
        source_path=str(source_path.resolve()),
    )


def test_parquet_binding_queries_numeric_column(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    service = _make_service(monkeypatch, tmp_path)
    source = tmp_path / "nums.parquet"
    pd.DataFrame({"value": [1, 2]}).to_parquet(source)

    result = service.query(
        DataQueryInput(
            bindings=[_binding(source)],
            sql="SELECT SUM(value) AS total FROM input",
            limit=1,
        )
    )

    assert result.rows[0]["total"] == 3
    assert result.total_row_count == 1
    assert result.returned_row_count == 1


def test_xlsx_binding_queries_row_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    service = _make_service(monkeypatch, tmp_path)
    source = tmp_path / "rows.xlsx"
    pd.DataFrame({"label": ["a", "b"]}).to_excel(source, index=False)

    result = service.query(
        DataQueryInput(
            bindings=[_binding(source)],
            sql="SELECT COUNT(*) AS n FROM input",
            limit=1,
        )
    )

    assert result.rows[0]["n"] == 2


def test_csv_binding_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    service = _make_service(monkeypatch, tmp_path)
    source = tmp_path / "nums.csv"
    source.write_text("value\n1\n2\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="bindings support"):
        service.query(
            DataQueryInput(
                bindings=[_binding(source)],
                sql="SELECT SUM(value) AS total FROM input",
                limit=1,
            )
        )
