from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

import hashlib
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from xenix.services.data_cleaning import (
    CleanDatasetInput,
    CleanOperation,
    DataCleaningService,
)
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.exceptions import ValidationError


FIXTURE_ROOT = FIXTURES_ROOT / "ml_foundation"
RAW_FIXTURE = FIXTURE_ROOT / "ordered_validation_raw_v1.csv"
EXPECTED_FIXTURE = FIXTURE_ROOT / "ordered_validation_expected_v1.csv"
RAW_SHA256 = "8665e1c600fc0c3e7e649af6b65b13dc2c03e0d588d4a0770819d89a26e970e5"
EXPECTED_SHA256 = "7e29274c0e6057e3aae83fc04500877f0dc2932fca4423207ab838ab841e767d"


def test_spawned_cleaning_preserves_source_and_matches_inline_feature_preparation(app_paths, tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("Region,Amount\n North ,1\nSouth,2\nNorth,3\nSouth,100\n", encoding="utf-8")
    original = source.read_bytes()
    request = CleanDatasetInput(
        source_path=str(source),
        name="Prepared features",
        operations=[
            CleanOperation(operation="schema.normalize_column_names"),
            CleanOperation(operation="text.trim", params={"column_names": ["region"]}),
            CleanOperation(operation="outlier.clip_iqr", params={"column_names": ["amount"]}),
            CleanOperation(operation="encoding.one_hot", params={"column_names": ["region"]}),
            CleanOperation(operation="scaling.minmax", params={"column_names": ["amount"]}),
        ],
    )
    spawned = DataCleaningService(app_paths).clean_dataset(request)
    inline = DataCleaningService(app_paths, worker_runner=InlinePreprocessingWorkerRunner()).clean_dataset(request)
    actual = pd.read_parquet(spawned.output_path)
    assert_frame_equal(actual, pd.read_parquet(inline.output_path))
    assert spawned.report == inline.report
    assert actual["region_north"].tolist() == [1, 0, 1, 0]
    assert actual["region_south"].tolist() == [0, 1, 0, 1]
    assert actual["amount"].min() == 0 and actual["amount"].max() == 1
    assert actual["amount"].iloc[1] == pytest.approx(1 / 64.5)
    assert source.read_bytes() == original


def test_column_shape_change_rejects_stale_indexes_without_publishing_partial_output(app_paths, tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("region,amount\nNorth,1\nSouth,2\n", encoding="utf-8")
    service = DataCleaningService(app_paths, worker_runner=InlinePreprocessingWorkerRunner())
    with pytest.raises(ValidationError, match="after 'encoding.one_hot'"):
        service.clean_dataset(
            CleanDatasetInput(
                source_path=str(source),
                name="Invalid plan",
                operations=[
                    CleanOperation(operation="encoding.one_hot", params={"column_names": ["region"]}),
                    CleanOperation(operation="scaling.minmax", params={"column_indexes": [1]}),
                ],
            )
        )
    assert not list(app_paths.artifacts.rglob("*.parquet"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialized_source(storage, app_paths) -> tuple[Path, DataCleaningService]:
    datasets = DatasetService(storage.session_factory, app_paths)
    source_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(RAW_FIXTURE.resolve()),
            name="Ordered validation source",
        )
    )
    service = DataCleaningService(
        app_paths,
        worker_runner=InlinePreprocessingWorkerRunner(),
    )
    return Path(source_dataset.source_path), service


def test_ordered_validation_preserves_nullable_rows_for_later_imputation(
    storage,
    app_paths,
) -> None:
    assert _sha256(RAW_FIXTURE) == RAW_SHA256
    assert _sha256(EXPECTED_FIXTURE) == EXPECTED_SHA256
    source_hash = _sha256(RAW_FIXTURE)
    source_path, service = _materialized_source(storage, app_paths)
    materialized_source_hash = _sha256(source_path)

    result = service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source_path),
            name="Ordered validation service oracle",
            operations=[
                CleanOperation(
                    operation="duplicate.exact_rows",
                    params={"keep": "first"},
                ),
                CleanOperation(
                    operation="validation.non_negative",
                    params={
                        "column_name": "unit_count",
                        "action": "drop_rows",
                        "name": "unit_count_non_negative",
                    },
                ),
                CleanOperation(
                    operation="text.trim",
                    params={"column_names": ["status"]},
                ),
                CleanOperation(
                    operation="text.lowercase",
                    params={"column_names": ["status"]},
                ),
                CleanOperation(
                    operation="missing.fill_median",
                    params={"column_names": ["unit_count"]},
                ),
            ],
        )
    )

    actual = pd.read_parquet(result.output_path).sort_values("batch_id").reset_index(drop=True)
    expected = pd.read_csv(EXPECTED_FIXTURE).sort_values("batch_id").reset_index(drop=True)
    assert_frame_equal(actual, expected, check_dtype=False)

    assert result.report["row_count_before"] == 10
    assert result.report["row_count_after"] == 7
    assert result.report["rows_removed"] == 3
    assert result.report["operations"][0] == {
        "operation": "duplicate.exact_rows",
        "rows_removed": 1,
    }
    assert result.report["validation_rules"] == [
        {
            "name": "unit_count_non_negative",
            "column": "unit_count",
            "operation": "validation.non_negative",
            "action": "drop_rows",
            "violations": 2,
            "rows_removed": 2,
        }
    ]
    assert next(
        operation for operation in result.report["operations"] if operation["operation"] == "missing.fill_median"
    ) == {
        "operation": "missing.fill_median",
        "column": "unit_count",
        "cells_filled": 2,
        "resolved_fill_value": 22,
    }
    assert _sha256(RAW_FIXTURE) == source_hash
    assert _sha256(source_path) == materialized_source_hash


@pytest.mark.parametrize(
    ("operation", "params", "expected_batch_ids", "violations"),
    [
        (
            "validation.non_negative",
            {},
            [
                "BATCH-201",
                "BATCH-202",
                "BATCH-203",
                "BATCH-205",
                "BATCH-206",
                "BATCH-207",
                "BATCH-208",
                "BATCH-208",
            ],
            2,
        ),
        (
            "validation.min",
            {"value": 10},
            [
                "BATCH-202",
                "BATCH-203",
                "BATCH-205",
                "BATCH-206",
                "BATCH-207",
                "BATCH-208",
                "BATCH-208",
            ],
            3,
        ),
        (
            "validation.max",
            {"value": 35},
            [
                "BATCH-201",
                "BATCH-202",
                "BATCH-203",
                "BATCH-204",
                "BATCH-205",
                "BATCH-206",
                "BATCH-207",
                "BATCH-209",
            ],
            2,
        ),
    ],
)
def test_numeric_comparison_validation_preserves_missing_values(
    storage,
    app_paths,
    operation: str,
    params: dict[str, int],
    expected_batch_ids: list[str],
    violations: int,
) -> None:
    source_path, service = _materialized_source(storage, app_paths)
    result = service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source_path),
            name="Nullable comparison control",
            operations=[
                CleanOperation(
                    operation=operation,
                    params={"column_name": "unit_count", "action": "drop_rows", **params},
                )
            ],
        )
    )

    actual = pd.read_parquet(result.output_path)
    assert sorted(actual["batch_id"].tolist()) == expected_batch_ids
    assert int(actual["unit_count"].isna().sum()) == 2
    assert result.report["validation_rules"][0]["violations"] == violations
    assert result.report["validation_rules"][0]["rows_removed"] == violations


def test_validation_report_only_and_explicit_not_null_have_distinct_row_semantics(
    storage,
    app_paths,
) -> None:
    source_path, service = _materialized_source(storage, app_paths)
    report_only = service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source_path),
            name="Validation report only control",
            operations=[
                CleanOperation(
                    operation="validation.non_negative",
                    params={"column_name": "unit_count", "action": "report_only"},
                )
            ],
        )
    )
    explicit_not_null = service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source_path),
            name="Explicit not-null control",
            operations=[
                CleanOperation(
                    operation="validation.not_null",
                    params={"column_name": "unit_count", "action": "drop_rows"},
                )
            ],
        )
    )

    report_only_frame = pd.read_parquet(report_only.output_path)
    not_null_frame = pd.read_parquet(explicit_not_null.output_path)
    assert len(report_only_frame.index) == 10
    assert report_only.report["validation_rules"] == [
        {
            "name": "validation.non_negative",
            "column": "unit_count",
            "operation": "validation.non_negative",
            "action": "report_only",
            "violations": 2,
        }
    ]
    assert len(not_null_frame.index) == 8
    assert int(not_null_frame["unit_count"].isna().sum()) == 0
    assert explicit_not_null.report["validation_rules"][0]["violations"] == 2
    assert explicit_not_null.report["validation_rules"][0]["rows_removed"] == 2


def test_operation_order_changes_the_imputation_authority_set(
    storage,
    app_paths,
) -> None:
    source_path, service = _materialized_source(storage, app_paths)
    result = service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source_path),
            name="Fill before validation order witness",
            operations=[
                CleanOperation(
                    operation="duplicate.exact_rows",
                    params={"keep": "first"},
                ),
                CleanOperation(
                    operation="missing.fill_median",
                    params={"column_names": ["unit_count"]},
                ),
                CleanOperation(
                    operation="validation.non_negative",
                    params={"column_name": "unit_count", "action": "drop_rows"},
                ),
            ],
        )
    )

    actual = pd.read_parquet(result.output_path).set_index("batch_id")
    assert len(actual.index) == 7
    assert actual.loc["BATCH-202", "unit_count"] == 14
    assert actual.loc["BATCH-207", "unit_count"] == 14
    assert next(
        operation for operation in result.report["operations"] if operation["operation"] == "missing.fill_median"
    ) == {
        "operation": "missing.fill_median",
        "column": "unit_count",
        "cells_filled": 2,
        "resolved_fill_value": 14,
    }
    assert result.report["validation_rules"][0]["violations"] == 2
    assert result.report["rows_removed"] == 3
