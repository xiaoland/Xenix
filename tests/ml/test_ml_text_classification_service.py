from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import joblib
import pandas as pd
import pytest


from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult, FitTaskResult
from xenix.services.ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus, ProjectRow
from xenix.services.ml.trained_model_metadata import parse_trained_model_metadata

pytestmark = pytest.mark.slow


FIXTURE_ROOT = FIXTURES_ROOT / "ml_text_classification"
TRAINING_FIXTURE = FIXTURE_ROOT / "bilingual_raw_training_v1.csv"
APPLY_FIXTURE = FIXTURE_ROOT / "bilingual_raw_apply_v1.csv"
CUSTOM_DICTIONARY_FIXTURE = FIXTURE_ROOT / "custom_dictionary_v1.csv"
STOPWORDS_FIXTURE = FIXTURE_ROOT / "stopwords_v1.csv"
ACTIVE_MODEL_KEY = "text.classification.multilingual_logistic_regression_tfidf"
PARAMS_TEMPLATE = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 5000,
    "minimum_document_frequency": 1,
    "class_weight": "balanced",
}


@dataclass
class _Runtime:
    storage: Any
    datasets: DatasetService
    tasks: MLTaskService
    ml: MLService
    artifacts: ArtifactService


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


class _TamperingInlineWorkerRunner(_InlineWorkerRunner):
    target_path: Path | None = None

    def run(
        self,
        entrypoint: Any,
        task_dir: Path,
        *,
        cancel_requested: Any | None = None,
    ) -> int:
        if self.target_path is not None:
            self.target_path.write_text("term\ntampered-after-staging\n", encoding="utf-8")
            self.target_path = None
        return super().run(
            entrypoint,
            task_dir,
            cancel_requested=cancel_requested,
        )


def _runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    worker_runner: Any | None = None,
) -> _Runtime:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=worker_runner or _InlineWorkerRunner(),
    )
    return _Runtime(
        storage=storage,
        datasets=datasets,
        tasks=tasks,
        ml=MLService(paths, storage.session_factory, datasets, tasks),
        artifacts=ArtifactService(storage.session_factory),
    )


def _register(
    datasets: DatasetService,
    source: Path,
    *,
    project_id: str | None = None,
):
    return datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            project_id=project_id,
            name=source.stem,
        )
    )


def _wait_for_terminal(
    tasks: MLTaskService,
    task_id: str,
    *,
    timeout: float = 30.0,
):
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


def _wait_for_evaluation_id(
    ml: MLService,
    trained_model_id: str,
    *,
    timeout: float = 30.0,
) -> str:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        model = ml.get_trained_model(trained_model_id)
        metadata = parse_trained_model_metadata(
            model.metadata_payload if model is not None else None
        )
        if metadata is not None and metadata.evaluation_ml_task_id:
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("Text classifier did not receive an evaluation task reference")


def _fixture_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_multilingual_text_classification_real_lifecycle_is_leakage_safe_and_public(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        apply_dataset = _register(runtime.datasets, APPLY_FIXTURE, project_id=training_dataset.project_id)
        custom = _register(runtime.datasets, CUSTOM_DICTIONARY_FIXTURE, project_id=training_dataset.project_id)
        stopwords = _register(runtime.datasets, STOPWORDS_FIXTURE, project_id=training_dataset.project_id)
        sources = {Path(d.source_path): _fixture_digest(Path(d.source_path))
                   for d in (training_dataset, apply_dataset, custom, stopwords)}
        binding = runtime.ml.create_column_binding(CreateColumnBindingInput(
            dataset_id=training_dataset.id, model_key=ACTIVE_MODEL_KEY,
            role_bindings=[{"role": "text", "columns": ["message"]},
                           {"role": "target", "columns": ["label"]},
                           {"role": "group", "columns": ["business_group"]}],
        ))
        params = {**PARAMS_TEMPLATE, "custom_dictionary_dataset_ids": [custom.id],
                  "stopword_dataset_ids": [stopwords.id]}
        fit_task = runtime.ml.fit_with_evaluate(FitWithEvaluateInput(
            binding_id=binding.id, run_name="Bilingual classification", model_key=ACTIVE_MODEL_KEY, params=params,
        ))
        completed_fit = _wait_for_terminal(runtime.tasks, fit_task.id)
        assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
        fit = FitTaskResult.model_validate(completed_fit.result_payload)
        assert fit.training_scopes is not None
        assert fit.training_scopes.evaluation_model == "out_of_fold_partitions"
        assert fit.training_scopes.apply_model == "all_eligible_rows"
        assert fit.text_preparation_specification is not None
        trained_model = runtime.ml.get_trained_model_by_ml_task(fit_task.id)
        assert trained_model is not None
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        assert metadata is not None
        assert metadata.evaluation_model_training_scope == "out_of_fold_partitions"
        evaluation_id = _wait_for_evaluation_id(runtime.ml, trained_model.id)
        completed_evaluation = _wait_for_terminal(runtime.tasks, evaluation_id)
        assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, completed_evaluation.error_summary
        evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)
        assert evaluation.evaluation is not None
        assert evaluation.baseline_evaluation is not None
        assert evaluation.cross_validation is not None
        assert evaluation.cross_validation["status"] == "complete"
        assert evaluation.cross_validation["evaluated_row_count"] == evaluation.cross_validation["eligible_row_count"]
        assert all(fold["group_overlap_count"] == 0 for fold in evaluation.cross_validation["folds"])
        evaluation_report = next(a for a in runtime.tasks.list_ml_task_artifacts(evaluation_id)
                                 if a.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT)
        assert runtime.artifacts.resolve_uri(build_artifact_uri(evaluation_report.artifact_id)).exists
        apply_task = runtime.ml.apply(ApplyWithFilesInput(
            trained_model_id=trained_model.id,
            input_sources=[ApplySourceInput(source_path=apply_dataset.source_path, dataset_id=apply_dataset.id)],
        ))
        completed_apply = _wait_for_terminal(runtime.tasks, apply_task.id)
        assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
        payload = completed_apply.result_payload or {}
        assert payload["text_classification_apply_facts"]["specification"] == fit.text_preparation_specification.model_dump(mode="json")
        result_dataset = runtime.datasets.get_dataset(payload["result_dataset_id"])
        assert result_dataset.derived_from_dataset_id == apply_dataset.id
        result = pd.read_parquet(result_dataset.source_path)
        source = pd.read_parquet(apply_dataset.source_path)
        assert result["message"].fillna("").tolist() == source["message"].fillna("").tolist()
        retained = joblib.load(fit.final_model_artifact_path)
        assert result.prediction.tolist() == retained.predict(source.message).tolist()
        assert result.prediction_score.to_numpy() == pytest.approx(retained.predict_proba(source.message).max(axis=1))
        assert (result.prediction_evidence == "no_known_features").any()
        artifact = next(a for a in runtime.tasks.list_ml_task_artifacts(apply_task.id)
                        if a.artifact_kind is MLTaskArtifactKind.APPLY_RESULT)
        resolved = runtime.artifacts.resolve_uri(build_artifact_uri(artifact.artifact_id))
        assert resolved.exists
        assert resolved.metadata_payload["training_dataset_id"] == training_dataset.id
        assert resolved.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
        assert all(_fixture_digest(path) == digest for path, digest in sources.items())
    finally:
        runtime.storage.engine.dispose()



def test_text_resources_reject_cross_project_dataset_references(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        with runtime.storage.session_factory() as session:
            other_project = ProjectRow(name="Independent text resource project")
            session.add(other_project)
            session.commit()
            session.refresh(other_project)
        cross_project_resource = _register(
            runtime.datasets,
            CUSTOM_DICTIONARY_FIXTURE,
            project_id=other_project.id,
        )
        assert cross_project_resource.project_id != training_dataset.project_id
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["label"]},
                    {"role": "group", "columns": ["business_group"]},
                ],
            )
        )
        with pytest.raises(
            ValidationError,
            match="resources must belong to the training project",
        ):
            runtime.ml.fit_with_evaluate(
                FitWithEvaluateInput(
                    binding_id=binding.id,
                    model_key=ACTIVE_MODEL_KEY,
                    params={
                        **PARAMS_TEMPLATE,
                        "custom_dictionary_dataset_ids": [cross_project_resource.id],
                        "stopword_dataset_ids": [],
                    },
                )
            )
    finally:
        runtime.storage.engine.dispose()


def test_text_resource_integrity_fails_closed_after_staging_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _TamperingInlineWorkerRunner()
    runtime = _runtime(monkeypatch, tmp_path, worker_runner=runner)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        mutable_terms = tmp_path / "mutable_terms.csv"
        mutable_terms.write_text("term\n星云工单\n", encoding="utf-8")
        resource_dataset = _register(
            runtime.datasets,
            mutable_terms,
            project_id=training_dataset.project_id,
        )
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["label"]},
                    {"role": "group", "columns": ["business_group"]},
                ],
            )
        )
        runner.target_path = Path(resource_dataset.source_path)
        fit_task = runtime.ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=binding.id,
                model_key=ACTIVE_MODEL_KEY,
                params={
                    **PARAMS_TEMPLATE,
                    "custom_dictionary_dataset_ids": [resource_dataset.id],
                    "stopword_dataset_ids": [],
                },
            )
        )
        failed = _wait_for_terminal(runtime.tasks, fit_task.id)
        assert failed.status is MLTaskStatus.FAILED
        assert "SHA-256 integrity check" in str(failed.error_summary)
    finally:
        runtime.storage.engine.dispose()
