from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import polars as pl
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
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
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus, MLTaskType
from xenix.services.trained_model_metadata import parse_trained_model_metadata


FIXTURES = Path(__file__).parent / "fixtures" / "ml_cf_service"
TRAIN_PATH = FIXTURES / "segment_train.csv"
APPLY_PATH = FIXTURES / "segment_apply.csv"
TRAIN_SHA256 = "29f04b70690660525437d05bc39716947bac792151d511934ce879c431deffb7"
APPLY_SHA256 = "582f80327ac6858a6f4880889472f85cdf7cae3be0607028e5b9087da0700043"
FEATURES = ["visits_90d", "avg_order_value", "return_rate", "channel"]


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
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("The clustering analyzer never received its evaluation-task reference")


def _register_dataset(datasets: DatasetService, source: Path, *, project_id: str | None = None):
    return datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            project_id=project_id,
            name=source.stem,
        )
    )


def _binding(ml: MLService, dataset_id: str, model_key: str):
    return ml.create_column_binding(
        CreateColumnBindingInput(
            dataset_id=dataset_id,
            model_key=model_key,
            role_bindings=[{"role": "feature", "columns": FEATURES}],
        )
    )


def _fit(
    ml: MLService,
    tasks: MLTaskService,
    *,
    binding_id: str,
    model_key: str,
    params: dict[str, Any],
):
    task = ml.fit_with_evaluate(
        FitWithEvaluateInput(
            binding_id=binding_id,
            run_name="Clustering trustworthiness acceptance",
            model_key=model_key,
            params=params,
        )
    )
    completed = _wait_for_terminal(tasks, task.id)
    assert completed.status is MLTaskStatus.SUCCEEDED, completed.error_summary
    return completed


def test_kmeans_service_fit_evaluate_assignment_and_apply_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert sha256(TRAIN_PATH.read_bytes()).hexdigest() == TRAIN_SHA256
    assert sha256(APPLY_PATH.read_bytes()).hexdigest() == APPLY_SHA256
    storage, datasets, tasks, ml = _services(monkeypatch, tmp_path)
    training_dataset = _register_dataset(datasets, TRAIN_PATH)
    apply_dataset = _register_dataset(
        datasets,
        APPLY_PATH,
        project_id=training_dataset.project_id,
    )
    training_source_digest = sha256(Path(training_dataset.source_path).read_bytes()).hexdigest()
    apply_source_digest = sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest()

    binding = _binding(ml, training_dataset.id, "clustering.kmeans")
    completed_fit = _fit(
        ml,
        tasks,
        binding_id=binding.id,
        model_key="clustering.kmeans",
        params={"n_clusters": 3, "n_init": 20, "max_iter": 300, "random_state": 42},
    )
    fit_payload = completed_fit.result_payload or {}
    assignment_dataset = datasets.get_dataset(fit_payload["result_dataset_id"])
    assert assignment_dataset.derived_from_dataset_id == training_dataset.id
    assert assignment_dataset.ml_task_id == completed_fit.id
    assignment_frame = pl.read_parquet(assignment_dataset.source_path)
    assert assignment_frame.height == 78
    assert assignment_frame.columns[-1] == "cluster_id"
    assert assignment_frame["cluster_id"].n_unique() == 3

    fit_artifacts = tasks.list_ml_task_artifacts(completed_fit.id)
    training_report = next(
        artifact
        for artifact in fit_artifacts
        if artifact.artifact_kind is MLTaskArtifactKind.TRAINING_REPORT
    )
    export_artifact = next(
        artifact
        for artifact in fit_artifacts
        if artifact.artifact_kind is MLTaskArtifactKind.EXPORT_FILE
    )
    assert training_report.ready_to_open is True
    assert training_report.artifact_id
    assert export_artifact.artifact_id
    assert Path(training_report.absolute_path).is_file()

    trained_model = ml.get_trained_model_by_ml_task(completed_fit.id)
    assert trained_model is not None
    evaluation_task_id = _wait_for_evaluation_id(ml, trained_model.id)
    completed_evaluation = _wait_for_terminal(tasks, evaluation_task_id)
    assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, completed_evaluation.error_summary
    evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)
    assert evaluation.clustering_evaluation is not None
    assert evaluation.clustering_evaluation.quality.cluster_count == 3
    assert evaluation.clustering_evaluation.stability.run_count == 5
    assert evaluation.clustering_evaluation.null_baseline.run_count == 16
    assert evaluation.evaluation is not None
    assert evaluation.baseline_evaluation is not None
    assert evaluation.comparison is not None
    evaluation_report = next(
        artifact
        for artifact in tasks.list_ml_task_artifacts(evaluation_task_id)
        if artifact.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT
    )
    assert evaluation_report.ready_to_open is True
    assert evaluation_report.artifact_id
    assert Path(evaluation_report.absolute_path).is_file()

    training_apply = ml.apply(
        ApplyWithFilesInput(
            trained_model_id=trained_model.id,
            input_sources=[
                ApplySourceInput(
                    source_path=training_dataset.source_path,
                    dataset_id=training_dataset.id,
                )
            ],
        )
    )
    completed_training_apply = _wait_for_terminal(tasks, training_apply.id)
    assert completed_training_apply.status is MLTaskStatus.SUCCEEDED, completed_training_apply.error_summary
    training_apply_payload = completed_training_apply.result_payload or {}
    replay_dataset = datasets.get_dataset(training_apply_payload["result_dataset_id"])
    replay_frame = pl.read_parquet(replay_dataset.source_path)
    assert replay_dataset.derived_from_dataset_id == training_dataset.id
    assert replay_frame["cluster_id"].to_list() == assignment_frame["cluster_id"].to_list()

    unseen_apply = ml.apply(
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
    completed_unseen_apply = _wait_for_terminal(tasks, unseen_apply.id)
    assert completed_unseen_apply.status is MLTaskStatus.SUCCEEDED, completed_unseen_apply.error_summary
    unseen_payload = completed_unseen_apply.result_payload or {}
    assert unseen_payload["source_dataset_ids"] == [apply_dataset.id]
    assert unseen_payload["source_artifact_ids"] == []
    unseen_result = datasets.get_dataset(unseen_payload["result_dataset_id"])
    assert unseen_result.derived_from_dataset_id == apply_dataset.id
    unseen_frame = pl.read_parquet(unseen_result.source_path)
    assert unseen_frame.height == 9
    assert unseen_frame.columns[-1] == "cluster_id"
    assert "marketplace" in pl.read_parquet(apply_dataset.source_path)["channel"].to_list()

    assert sha256(Path(training_dataset.source_path).read_bytes()).hexdigest() == training_source_digest
    assert sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest() == apply_source_digest
    assert sha256(TRAIN_PATH.read_bytes()).hexdigest() == TRAIN_SHA256
    assert sha256(APPLY_PATH.read_bytes()).hexdigest() == APPLY_SHA256
    storage.engine.dispose()


def test_dbscan_apply_is_rejected_by_ml_service_admission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    storage, datasets, tasks, ml = _services(monkeypatch, tmp_path)
    training_dataset = _register_dataset(datasets, TRAIN_PATH)
    binding = _binding(ml, training_dataset.id, "clustering.dbscan")
    completed_fit = _fit(
        ml,
        tasks,
        binding_id=binding.id,
        model_key="clustering.dbscan",
        params={"eps": 1.2, "min_samples": 4},
    )
    trained_model = ml.get_trained_model_by_ml_task(completed_fit.id)
    assert trained_model is not None
    apply_task_ids_before = {
        task.id
        for task in tasks.list_dataset_ml_tasks(training_dataset.id)
        if task.task_type is MLTaskType.APPLY
    }

    with pytest.raises(ValidationError, match="does not support apply"):
        ml.apply(
            ApplyWithFilesInput(
                trained_model_id=trained_model.id,
                input_sources=[
                    ApplySourceInput(
                        source_path=training_dataset.source_path,
                        dataset_id=training_dataset.id,
                    )
                ],
            )
        )

    apply_task_ids_after = {
        task.id
        for task in tasks.list_dataset_ml_tasks(training_dataset.id)
        if task.task_type is MLTaskType.APPLY
    }
    assert apply_task_ids_after == apply_task_ids_before
    storage.engine.dispose()
