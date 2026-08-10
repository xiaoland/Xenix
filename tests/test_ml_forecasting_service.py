from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult
from xenix.services.ml.registry import get_model_catalog_entry, list_model_keys
from xenix.services.ml.types import ApplyMode, EvaluationKind, ModelFamily, ModelTaskKind
from xenix.services.ml_service import (
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus
from xenix.services.trained_model_metadata import parse_trained_model_metadata

FIXTURE = Path(__file__).parent / "fixtures" / "ml_cf_service" / "weekly_panel_v1.csv"
FIXTURE_SHA256 = "37f02afd4419c6cc379865b129a6b30762b35ce950cc44946953bc505d43e50c"


class _InlineWorkerRunner:
    max_dispatch_threads = 1

    def run(
        self,
        entrypoint: Any,
        task_dir: Path,
        *,
        cancel_requested: Any | None = None,
    ) -> int:
        if cancel_requested is not None and cancel_requested():
            return -15
        entrypoint(str(task_dir))
        return 0


def _wait_for_terminal(tasks: MLTaskService, task_id: str, *, timeout: float = 30.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        task = tasks.get_ml_task(task_id)
        if task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
            return task
        sleep(0.02)
    raise AssertionError(f"ML task {task_id} did not finish within {timeout} seconds")


def _wait_for_evaluation_id(ml: MLService, trained_model_id: str, *, timeout: float = 30.0) -> str:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        model = ml.get_trained_model(trained_model_id)
        metadata = parse_trained_model_metadata(model.metadata_payload if model is not None else None)
        if metadata is not None and metadata.evaluation_ml_task_id:
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("Forecast model did not receive an authoritative Evaluate task reference")


def test_holt_winters_public_lifecycle_preserves_temporal_evidence_and_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    ml = MLService(paths, storage.session_factory, datasets, tasks)
    artifacts = ArtifactService(storage.session_factory)

    training_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(FIXTURE.resolve()),
            name="Aligned weekly regional demand",
        )
    )
    source_before = sha256(Path(training_dataset.source_path).read_bytes()).hexdigest()
    binding = ml.create_column_binding(
        CreateColumnBindingInput(
            dataset_id=training_dataset.id,
            model_key="forecasting.holt_winters",
            role_bindings=[
                {"role": "time", "columns": ["week"]},
                {"role": "target", "columns": ["orders"]},
                {"role": "group", "columns": ["region"]},
            ],
        )
    )
    fit_params = {
        "horizon": 4,
        "seasonal_period": 4,
        "frequency": "weekly",
        "interval_level": 0.8,
        "rolling_windows": 3,
        "damped_trend": False,
    }
    fit_task = ml.fit_with_evaluate(
        FitWithEvaluateInput(
            binding_id=binding.id,
            run_name="Weekly demand forecast",
            model_key="forecasting.holt_winters",
            params=fit_params,
        )
    )
    completed_fit = _wait_for_terminal(tasks, fit_task.id)
    assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
    fit_payload = completed_fit.result_payload or {}
    assert fit_payload["forecast_split_facts"]["group_count"] == 2
    assert fit_payload["forecast_split_facts"]["rolling_windows"] == 3
    assert fit_payload["forecast_split_facts"]["future_overlap_count"] == 0
    assert fit_payload["forecast_preparation_facts"]["frequency"] == "weekly"
    assert fit_payload["training_scopes"] == {
        "evaluation_model": "chronological_training_prefixes",
        "apply_model": "all_observed_history",
    }

    trained_model = ml.get_trained_model_by_ml_task(fit_task.id)
    assert trained_model is not None
    evaluation_task_id = _wait_for_evaluation_id(ml, trained_model.id)
    completed_evaluation = _wait_for_terminal(tasks, evaluation_task_id)
    assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, completed_evaluation.error_summary
    evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)
    assert evaluation.evaluation_kind is EvaluationKind.FORECASTING
    assert evaluation.forecast_evaluation is not None
    assert evaluation.forecast_evaluation.split.fold_identity_digest == fit_payload["forecast_split_facts"][
        "fold_identity_digest"
    ]
    assert evaluation.forecast_evaluation.preparation.preparation_digest == fit_payload[
        "forecast_preparation_facts"
    ]["preparation_digest"]
    assert evaluation.comparison.primary_metric_name == "mae"
    assert evaluation.evaluation.primary_metric_name == "mae"
    assert evaluation.baseline_evaluation.primary_metric_name == "mae"
    assert evaluation.forecast_evaluation.intervals.coverage_guaranteed is False

    evaluation_artifact = next(
        artifact
        for artifact in tasks.list_ml_task_artifacts(evaluation_task_id)
        if artifact.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT
    )
    assert evaluation_artifact.ready_to_open is True
    assert evaluation_artifact.artifact_id is not None
    resolved_evaluation_artifact = artifacts.resolve_uri(
        build_artifact_uri(evaluation_artifact.artifact_id)
    )
    assert resolved_evaluation_artifact.exists is True
    assert resolved_evaluation_artifact.ready_to_open is True
    assert resolved_evaluation_artifact.metadata_payload["ml_task_id"] == evaluation_task_id

    refreshed_model = ml.get_trained_model(trained_model.id)
    assert refreshed_model is not None
    metadata = parse_trained_model_metadata(refreshed_model.metadata_payload)
    assert metadata is not None
    assert metadata.model_family == "forecasting"
    assert metadata.model_task_kind == "forecaster"
    assert metadata.evaluation_kind == "forecasting"
    assert metadata.supports_evaluation is True
    assert metadata.supports_apply is True
    assert metadata.apply_mode == "future_horizon"
    assert metadata.forecast_options == {
        "horizon": 4,
        "seasonal_period": 4,
        "frequency": "weekly",
        "interval_level": 0.8,
        "rolling_windows": 3,
    }
    assert metadata.evaluation_model_training_scope == "chronological_training_prefixes"
    assert metadata.apply_model_training_scope == "all_observed_history"
    assert metadata.evaluation_ml_task_id == evaluation_task_id
    assert metadata.evaluation_facts_authority == "ml_task_result"
    assert metadata.evaluation_primary_metric_name == evaluation.evaluation.primary_metric_name
    assert metadata.training_params == fit_params

    apply_task = ml.apply(
        ApplyWithFilesInput(
            trained_model_id=trained_model.id,
            horizon=4,
        )
    )
    completed_apply = _wait_for_terminal(tasks, apply_task.id)
    assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
    apply_payload = completed_apply.result_payload or {}
    assert apply_payload["source_dataset_ids"] == [training_dataset.id]
    assert apply_payload["source_artifact_ids"] == []
    assert apply_payload["row_count"] == 8
    assert apply_payload["input_file_count"] == 0
    assert apply_payload["prediction_column_name"] == "forecast"

    result_dataset = datasets.get_dataset(apply_payload["result_dataset_id"])
    assert result_dataset.derived_from_dataset_id == training_dataset.id
    assert result_dataset.ml_task_id == apply_task.id
    result_inspection = datasets.inspect_source_file(
        InspectDatasetInput(source_path=result_dataset.source_path)
    )
    assert result_inspection.row_count == 8
    result_frame = pd.read_parquet(result_dataset.source_path)
    assert result_frame.columns.tolist() == [
        "region",
        "forecast_time",
        "forecast",
        "lower_bound",
        "upper_bound",
        "model_key",
        "interval_method",
        "interval_level",
        "horizon",
    ]
    assert result_frame[["region", "forecast_time"]].duplicated().sum() == 0
    assert result_frame["region"].tolist() == ["north"] * 4 + ["south"] * 4
    assert result_frame.groupby("region", sort=False)["forecast_time"].apply(list).map(
        lambda values: values == sorted(values)
    ).all()
    assert (result_frame["lower_bound"] <= result_frame["forecast"]).all()
    assert (result_frame["forecast"] <= result_frame["upper_bound"]).all()

    apply_artifact = next(
        artifact
        for artifact in tasks.list_ml_task_artifacts(apply_task.id)
        if artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT
    )
    assert apply_artifact.artifact_id is not None
    resolved_apply_artifact = artifacts.resolve_uri(build_artifact_uri(apply_artifact.artifact_id))
    assert resolved_apply_artifact.exists is True
    assert resolved_apply_artifact.metadata_payload["training_dataset_id"] == training_dataset.id
    assert resolved_apply_artifact.metadata_payload["source_dataset_ids"] == [training_dataset.id]
    assert resolved_apply_artifact.metadata_payload["result_dataset_id"] == result_dataset.id

    forecast_keys = {
        "forecasting.seasonal_naive",
        "forecasting.holt_winters",
        "forecasting.sarima",
    }
    assert forecast_keys.issubset(set(list_model_keys()))
    for model_key in forecast_keys:
        catalog = get_model_catalog_entry(model_key)
        assert catalog.model_family is ModelFamily.FORECASTING
        assert catalog.model_task_kind is ModelTaskKind.FORECASTER
        assert catalog.evaluation_kind is EvaluationKind.FORECASTING
        assert catalog.apply_mode is ApplyMode.FUTURE_HORIZON
        assert catalog.supports_evaluation is True
        assert catalog.supports_apply is True

    assert sha256(Path(training_dataset.source_path).read_bytes()).hexdigest() == source_before
    assert sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    storage.engine.dispose()
