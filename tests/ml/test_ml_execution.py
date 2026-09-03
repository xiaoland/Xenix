from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import polars as pl
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult
from xenix.services.ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    DatasetColumnBindingRow,
    MLTaskArtifactKind,
    MLTaskStatus,
)
from xenix.services.ml.trained_model_metadata import parse_trained_model_metadata

_FIXTURE_ROOT = FIXTURES_ROOT / "ml_foundation"
_TRAIN_FIXTURE = _FIXTURE_ROOT / "grouped_lifecycle_v1.csv"
_APPLY_FIXTURE = _FIXTURE_ROOT / "grouped_lifecycle_apply_v1.csv"
_TRAIN_FIXTURE_SHA256 = "5efcb0cfbd31860c312a37c124fe522ef3465dc64ef0ef36e31fbcb7f47339e2"
_APPLY_FIXTURE_SHA256 = "d9e0a09706c197ad79bbf0c09ea0fb41de4f67e6cfad60a69dd2eaa7435bd40c"


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


def _services(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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
    return storage, datasets, tasks, ml


def _wait_for_terminal(tasks: MLTaskService, task_id: str, timeout: float = 20.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        task = tasks.get_ml_task(task_id)
        if task.status in {
            MLTaskStatus.SUCCEEDED,
            MLTaskStatus.FAILED,
            MLTaskStatus.CANCELLED,
        }:
            return task
        sleep(0.02)
    raise AssertionError(f"ML task {task_id} did not finish within {timeout} seconds")


def _wait_for_evaluation_id(ml: MLService, trained_model_id: str, timeout: float = 20.0) -> str:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        trained_model = ml.get_trained_model(trained_model_id)
        metadata = parse_trained_model_metadata(
            trained_model.metadata_payload if trained_model is not None else None
        )
        if metadata is not None and metadata.evaluation_ml_task_id:
            assert metadata.evaluation_facts_authority == "ml_task_result"
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("The trained analyzer never received its direct evaluation-task reference")


def _register_grouped_training_dataset(datasets: DatasetService):
    dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(_TRAIN_FIXTURE.resolve()),
            name="Grouped customer lifecycle",
        )
    )
    return dataset


def _create_grouped_binding(ml: MLService, dataset_id: str):
    return ml.create_column_binding(
        CreateColumnBindingInput(
            dataset_id=dataset_id,
            model_key="classification.logistic_regression",
            role_bindings=[
                {
                    "role": "feature",
                    "columns": [
                        "orders_30d",
                        "avg_response_hours",
                        "support_tickets",
                        "plan_tier",
                    ],
                },
                {"role": "target", "columns": ["will_churn"]},
                {"role": "group", "columns": ["customer_id"]},
            ],
        )
    )


def test_grouped_training_evaluation_and_apply_preserve_truthful_facts_and_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert sha256(_TRAIN_FIXTURE.read_bytes()).hexdigest() == _TRAIN_FIXTURE_SHA256
    assert sha256(_APPLY_FIXTURE.read_bytes()).hexdigest() == _APPLY_FIXTURE_SHA256
    storage, datasets, tasks, ml = _services(monkeypatch, tmp_path)
    training_dataset = _register_grouped_training_dataset(datasets)
    apply_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(_APPLY_FIXTURE.resolve()),
            project_id=training_dataset.project_id,
            name="New customer scoring batch",
        )
    )
    training_source_before = sha256(Path(training_dataset.source_path).read_bytes()).hexdigest()
    apply_source_before = sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest()

    binding = _create_grouped_binding(ml, training_dataset.id)
    assert binding.schema_version == 2
    assert binding.dataset_snapshot_payload is not None
    assert binding.dataset_snapshot_payload["dataset_id"] == training_dataset.id

    fit_task = ml.fit_with_evaluate(
        FitWithEvaluateInput(
            binding_id=binding.id,
            run_name="Grouped churn risk",
            model_key="classification.logistic_regression",
        )
    )
    completed_fit = _wait_for_terminal(tasks, fit_task.id)
    assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
    fit_payload = completed_fit.result_payload or {}
    assert fit_payload["split_facts"]["realized_strategy"] == "group_hash_holdout.v1"
    assert fit_payload["split_facts"]["group_overlap_count"] == 0
    assert fit_payload["split_facts"]["eligible_group_count"] == 18
    assert fit_payload["preparation_facts"]["fit_scope"] == "outer_train_split"
    assert fit_payload["preparation_facts"]["fit_row_count"] == fit_payload["split_facts"]["train_row_count"]
    assert fit_payload["preparation_facts"]["unknown_category_handling"] == "ignore"

    trained_model = ml.get_trained_model_by_ml_task(fit_task.id)
    assert trained_model is not None
    evaluation_task_id = _wait_for_evaluation_id(ml, trained_model.id)
    completed_evaluation = _wait_for_terminal(tasks, evaluation_task_id)
    assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, completed_evaluation.error_summary
    evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)
    assert evaluation.split_facts.group_overlap_count == 0
    assert evaluation.split_facts.train_membership_digest == fit_payload["split_facts"]["train_membership_digest"]
    assert evaluation.preparation_facts.output_schema_digest == fit_payload["preparation_facts"]["output_schema_digest"]
    assert evaluation.comparison.primary_metric_name == evaluation.evaluation.primary_metric_name
    assert evaluation.baseline_evaluation.primary_metric_name == evaluation.evaluation.primary_metric_name
    assert evaluation.comparison.verdict.value in {"candidate_better", "baseline_better", "tied"}
    evaluation_artifacts = tasks.list_ml_task_artifacts(evaluation_task_id)
    report = next(
        artifact
        for artifact in evaluation_artifacts
        if artifact.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT
    )
    assert report.ready_to_open
    assert Path(report.absolute_path).is_file()

    apply_task = ml.apply(
        ApplyWithFilesInput(
            trained_model_id=trained_model.id,
            input_sources=[
                ApplySourceInput(
                    source_path=apply_dataset.source_path,
                    dataset_id=apply_dataset.id,
                )
            ],
        )
    )
    completed_apply = _wait_for_terminal(tasks, apply_task.id)
    assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
    apply_payload = completed_apply.result_payload or {}
    assert apply_payload["source_dataset_ids"] == [apply_dataset.id]
    assert apply_payload["source_artifact_ids"] == []
    assert apply_payload["row_count"] == 6
    result_dataset = datasets.get_dataset(apply_payload["result_dataset_id"])
    assert result_dataset.derived_from_dataset_id == apply_dataset.id
    assert result_dataset.derived_from_dataset_id != training_dataset.id
    result_inspection = datasets.inspect_source_file(
        InspectDatasetInput(source_path=result_dataset.source_path)
    )
    assert result_inspection.row_count == 6
    assert result_inspection.preview_columns[-1] == "prediction"
    apply_artifact = next(
        artifact
        for artifact in tasks.list_ml_task_artifacts(apply_task.id)
        if artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT
    )
    assert apply_artifact.ready_to_open

    assert sha256(Path(training_dataset.source_path).read_bytes()).hexdigest() == training_source_before
    assert sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest() == apply_source_before
    assert sha256(_TRAIN_FIXTURE.read_bytes()).hexdigest() == _TRAIN_FIXTURE_SHA256
    assert sha256(_APPLY_FIXTURE.read_bytes()).hexdigest() == _APPLY_FIXTURE_SHA256
    storage.engine.dispose()


def test_training_rejects_changed_dataset_bytes_and_legacy_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    storage, datasets, _tasks, ml = _services(monkeypatch, tmp_path)
    dataset = _register_grouped_training_dataset(datasets)
    binding = _create_grouped_binding(ml, dataset.id)

    frame = pl.read_parquet(dataset.source_path)
    frame = frame.with_columns(
        pl.when(pl.col("event_id") == "E001-01")
        .then(pl.lit(99))
        .otherwise(pl.col("orders_30d"))
        .alias("orders_30d")
    )
    frame.write_parquet(dataset.source_path)
    with pytest.raises(ValidationError, match="contents changed"):
        ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=binding.id,
                model_key="classification.logistic_regression",
            )
        )

    fresh_dataset = _register_grouped_training_dataset(datasets)
    with storage.session_factory() as session:
        legacy = DatasetColumnBindingRow(
            dataset_id=fresh_dataset.id,
            role_bindings=[
                {"role": "feature", "columns": ["orders_30d"]},
                {"role": "target", "columns": ["will_churn"]},
            ],
            model_key="classification.logistic_regression",
            model_family="supervised",
            model_task_kind="predictor",
            schema_version=1,
        )
        session.add(legacy)
        session.commit()
        session.refresh(legacy)
        legacy_id = legacy.id
    with pytest.raises(ValidationError, match="predates immutable Dataset identity"):
        ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=legacy_id,
                model_key="classification.logistic_regression",
            )
        )
    storage.engine.dispose()
