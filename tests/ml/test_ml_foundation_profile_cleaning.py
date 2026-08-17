from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import polars as pl

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.analysis_profile import AnalysisProfileService, ProfileDatasetInput
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ArtifactKind


FIXTURE_PATH = FIXTURES_ROOT / "ml_foundation" / "profile_cleaning_v1.csv"
FIXTURE_SHA256 = "b9db883e5fa16b49896ca8647d428cba51a43cecc68b41546c8e7b152de61161"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xtt_metadata(value: str, key: str) -> str:
    prefix = f"{key}: "
    return next(line.removeprefix(prefix) for line in value.splitlines() if line.startswith(prefix))


def _xtt_json_metadata(value: str, key: str):
    return json.loads(_xtt_metadata(value, key))


def test_clean_room_profile_and_whole_dataset_cleaning_workflow(
    monkeypatch,
    tmp_path: Path,
) -> None:
    assert _sha256(FIXTURE_PATH) == FIXTURE_SHA256
    source_bytes_hash = _sha256(FIXTURE_PATH)

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(context.session_factory, paths)
    artifacts = ArtifactService(context.session_factory)
    source_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(FIXTURE_PATH.resolve()),
            name="Support quality clean-room",
        )
    )
    materialized_source_hash = _sha256(Path(source_dataset.source_path))
    profile_service = AnalysisProfileService(datasets)

    source_profile = profile_service.profile_dataset(
        ProfileDatasetInput(dataset_id=source_dataset.id)
    )

    assert source_profile.scope == "whole_dataset"
    assert source_profile.basic.model_dump() == {
        "row_count": 10,
        "column_count": 7,
        "exact_duplicate_row_count": 1,
    }
    source_fields = {field.name: field for field in source_profile.fields}
    assert source_fields["ticket_id"].logical_type == "identifier"
    assert source_fields["opened_on"].logical_type == "datetime"
    assert source_fields["region"].logical_type == "categorical_text"
    assert source_fields["revenue"].missing_count == 1
    assert source_fields["region"].missing_count == 1
    assert source_fields["converted"].logical_type == "binary"
    assert next(
        summary for summary in source_profile.numeric_summaries if summary.field_name == "revenue"
    ).maximum == 5000

    inline_worker = InlinePreprocessingWorkerRunner()
    tools = AgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=DataCleaningService(paths, worker_runner=inline_worker),
        data_transform_service=Mock(),
        ml_service=Mock(),
        artifact_service=artifacts,
        preprocessing_worker_runner=inline_worker,
    )
    clean_outcome = tools.execute(
        "data.clean",
        {
            "dataset_id": source_dataset.id,
            "name": "Support quality cleaned",
            "operations": [
                {"operation": "duplicate.exact_rows", "params": {"keep": "first"}},
                {
                    "operation": "duplicate.key_columns",
                    "params": {"column_indexes": [0], "keep": "first"},
                },
                {
                    "operation": "missing.fill_median",
                    "params": {"column_indexes": [3]},
                },
                {
                    "operation": "missing.fill_mode",
                    "params": {"column_indexes": [2]},
                },
                {
                    "operation": "validation.max",
                    "params": {
                        "column_index": 4,
                        "value": 1,
                        "action": "drop_rows",
                        "name": "discount_rate_at_most_one",
                    },
                },
            ],
        },
        ToolExecutionContext(
            thread_id="foundation-profile-cleaning",
            dataset_ids=(source_dataset.id,),
        ),
    )

    assert isinstance(clean_outcome.value, str)
    assert "Whole-Dataset cleaned result created" in clean_outcome.value
    assert "not holdout-safe learned model preparation" in clean_outcome.value
    assert "cleaned rows and schema preview are omitted" in clean_outcome.value
    assert "local follow-up tools" not in clean_outcome.value
    assert "shape:" not in clean_outcome.value
    assert "schema:" not in clean_outcome.value
    assert "\ndata:" not in clean_outcome.value
    assert "\nrecords:" not in clean_outcome.value
    assert "preview_rows" not in clean_outcome.value
    assert "T-001" not in clean_outcome.value
    assert "2025-01-01" not in clean_outcome.value
    assert len(clean_outcome.value) < 4_096
    assert _xtt_metadata(clean_outcome.value, "source_dataset_id") == source_dataset.id
    operation_effects = _xtt_json_metadata(clean_outcome.value, "operation_effects")
    assert operation_effects[2] == {
        "operation": "missing.fill_median",
        "column": "revenue",
        "cells_filled": 1,
        "resolved_fill_value": 135.0,
    }
    assert operation_effects[3] == {
        "operation": "missing.fill_mode",
        "column": "region",
        "cells_filled": 1,
        "resolved_fill_value": "North",
    }
    assert _xtt_json_metadata(clean_outcome.value, "validation_effects") == [
        {
            "name": "discount_rate_at_most_one",
            "column": "discount_rate",
            "operation": "validation.max",
            "action": "drop_rows",
            "violations": 1,
            "rows_removed": 1,
        }
    ]
    derived_dataset_id = _xtt_metadata(clean_outcome.value, "dataset_id")
    artifact_id = _xtt_metadata(clean_outcome.value, "artifact_id")
    derived_dataset = datasets.get_dataset(derived_dataset_id)
    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert [dataset.id for dataset in datasets.list_derived_datasets(source_dataset.id)] == [
        derived_dataset_id
    ]

    opened_result = artifacts.resolve_uri(build_artifact_uri(artifact_id))
    assert opened_result.artifact_id == artifact_id
    assert opened_result.kind is ArtifactKind.DATASET
    assert opened_result.exists is True
    assert opened_result.ready_to_open is True
    assert opened_result.metadata_payload["dataset_id"] == derived_dataset_id

    cleaned = pl.read_parquet(derived_dataset.source_path).sort("ticket_id")
    assert cleaned.columns == [
        "ticket_id",
        "opened_on",
        "region",
        "revenue",
        "discount_rate",
        "satisfaction",
        "converted",
    ]
    assert cleaned.height == 7
    assert cleaned["ticket_id"].to_list() == [
        "T-001",
        "T-002",
        "T-003",
        "T-004",
        "T-005",
        "T-007",
        "T-008",
    ]
    cleaned_by_id = {row["ticket_id"]: row for row in cleaned.to_dicts()}
    assert cleaned_by_id["T-003"]["revenue"] == 135
    assert cleaned_by_id["T-004"]["region"] == "North"
    assert cleaned_by_id["T-005"]["revenue"] == 5000
    assert "T-006" not in cleaned_by_id

    derived_profile = profile_service.profile_dataset(
        ProfileDatasetInput(dataset_id=derived_dataset_id)
    )
    assert derived_profile.basic.row_count == 7
    assert derived_profile.basic.exact_duplicate_row_count == 0
    derived_fields = {field.name: field for field in derived_profile.fields}
    assert derived_fields["revenue"].missing_count == 0
    assert derived_fields["region"].missing_count == 0
    assert next(
        summary for summary in derived_profile.numeric_summaries if summary.field_name == "revenue"
    ).maximum == 5000

    assert _sha256(FIXTURE_PATH) == source_bytes_hash
    assert _sha256(Path(source_dataset.source_path)) == materialized_source_hash
