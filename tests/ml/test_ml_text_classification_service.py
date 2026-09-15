from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from time import monotonic, sleep
import unicodedata
from typing import Any, Iterable

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


FIXTURE_ROOT = FIXTURES_ROOT / "ml_text_classification"
TRAINING_FIXTURE = FIXTURE_ROOT / "bilingual_raw_training_v1.csv"
APPLY_FIXTURE = FIXTURE_ROOT / "bilingual_raw_apply_v1.csv"
CUSTOM_DICTIONARY_FIXTURE = FIXTURE_ROOT / "custom_dictionary_v1.csv"
STOPWORDS_FIXTURE = FIXTURE_ROOT / "stopwords_v1.csv"
NEAR_DUPLICATE_RECORD_PAIRS = (
    ("p01-02", "p02-02"),
    ("p03-02", "p04-02"),
    ("p05-02", "p06-02"),
    ("s01-02", "s02-02"),
    ("s03-02", "s04-02"),
    ("s05-02", "s06-02"),
)
ACTIVE_MODEL_KEY = "text.classification.multilingual_logistic_regression_tfidf"
PARAMS_TEMPLATE = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 5000,
    "minimum_document_frequency": 1,
    "class_weight": "balanced",
}



@dataclass(frozen=True)
class _ClassificationMetrics:
    accuracy: float
    balanced_accuracy: float
    precision_macro: float
    precision_weighted: float
    recall_macro: float
    recall_weighted: float
    f1_macro: float
    f1_weighted: float


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


class _DisjointSet:
    def __init__(self, values: Iterable[str]) -> None:
        self._parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        self._parent[max(left_root, right_root)] = min(left_root, right_root)


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


def _normalized_exact_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", normalized).strip()












def _exact_template_components(frame: pd.DataFrame) -> dict[str, str]:
    """Fixture oracle: union business groups and non-empty exact text duplicates."""

    record_ids = frame["record_id"].astype(str).tolist()
    disjoint_set = _DisjointSet(record_ids)
    for _group, rows in frame.groupby("business_group", sort=True):
        members = rows["record_id"].astype(str).tolist()
        for member in members[1:]:
            disjoint_set.union(members[0], member)

    duplicate_buckets: dict[str, list[str]] = defaultdict(list)
    for row in frame.to_dict(orient="records"):
        key = _normalized_exact_text(row["message"])
        if key:
            duplicate_buckets[key].append(str(row["record_id"]))
    for members in duplicate_buckets.values():
        for member in members[1:]:
            disjoint_set.union(members[0], member)
    return {record_id: disjoint_set.find(record_id) for record_id in record_ids}








def _component_overlap_count(
    components: dict[str, str],
    *,
    train_record_ids: Iterable[str],
    holdout_record_ids: Iterable[str],
) -> int:
    train_components = {components[value] for value in train_record_ids}
    holdout_components = {components[value] for value in holdout_record_ids}
    return len(train_components & holdout_components)












def _classification_metrics(
    truth: Iterable[str],
    predictions: Iterable[str],
) -> _ClassificationMetrics:
    truth_values = [str(value) for value in truth]
    predicted_values = [str(value) for value in predictions]
    if not truth_values or len(truth_values) != len(predicted_values):
        raise ValueError("Classification oracle requires equal, non-empty vectors.")

    labels = sorted(set(truth_values) | set(predicted_values))
    support = Counter(truth_values)
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    for label in labels:
        true_positive = sum(
            actual == label and predicted == label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        false_positive = sum(
            actual != label and predicted == label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        false_negative = sum(
            actual == label and predicted != label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        precision[label] = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall[label] = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1[label] = (
            2.0 * precision[label] * recall[label] / (precision[label] + recall[label])
            if precision[label] + recall[label]
            else 0.0
        )

    row_count = len(truth_values)
    accuracy = sum(
        actual == predicted
        for actual, predicted in zip(truth_values, predicted_values, strict=True)
    ) / row_count

    def macro(values: dict[str, float]) -> float:
        return sum(values.values()) / len(labels)

    def weighted(values: dict[str, float]) -> float:
        return sum(values[label] * support[label] for label in labels) / row_count

    return _ClassificationMetrics(
        accuracy=accuracy,
        balanced_accuracy=macro(recall),
        precision_macro=macro(precision),
        precision_weighted=weighted(precision),
        recall_macro=macro(recall),
        recall_weighted=weighted(recall),
        f1_macro=macro(f1),
        f1_weighted=weighted(f1),
    )


def _most_frequent_dummy_predictions(
    training_truth: Iterable[str],
    *,
    holdout_row_count: int,
) -> list[str]:
    counts = Counter(str(value) for value in training_truth)
    if not counts or holdout_row_count < 1:
        raise ValueError("Dummy oracle requires training labels and a positive holdout size.")
    winner = min(counts, key=lambda label: (-counts[label], label))
    return [winner] * holdout_row_count


def _generic_prediction_digest(predictions: Iterable[str]) -> str:
    payload = [
        {"type": "str", "value": str(value)}
        for value in predictions
    ]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()




def test_clean_room_bilingual_fixtures_exercise_leakage_and_apply_edges() -> None:
    training = pd.read_csv(TRAINING_FIXTURE, keep_default_na=False)
    assert training.columns.tolist() == [
        "record_id",
        "business_group",
        "message",
        "label",
    ]
    assert len(training) == 48
    assert training["record_id"].is_unique
    assert training["business_group"].nunique() == 12
    assert training.groupby("business_group")["label"].nunique().eq(1).all()
    assert training.groupby("business_group").size().eq(4).all()
    assert training["label"].value_counts().to_dict() == {
        "priority": 24,
        "standard": 24,
    }
    assert training["message"].map(_normalized_exact_text).eq("").sum() == 2

    components = _exact_template_components(training)
    component_members: dict[str, list[str]] = defaultdict(list)
    for record_id, component in components.items():
        component_members[component].append(record_id)
    assert sorted(len(members) for members in component_members.values()) == [16] * 3
    assert all(
        training.loc[training["record_id"].isin(members), "label"].nunique() == 2
        for members in component_members.values()
    )
    assert _component_overlap_count(
        components,
        train_record_ids=["p01-01", "p02-02"],
        holdout_record_ids=["p01-03", "p02-04"],
    ) == 1
    assert _component_overlap_count(
        components,
        train_record_ids=["p01-01", "s02-01"],
        holdout_record_ids=["p03-01", "s04-01"],
    ) == 0

    indexed = training.set_index("record_id")
    for left, right in NEAR_DUPLICATE_RECORD_PAIRS:
        assert indexed.at[left, "business_group"] != indexed.at[right, "business_group"]
        assert indexed.at[left, "label"] == indexed.at[right, "label"]
        assert indexed.at[left, "message"] != indexed.at[right, "message"]

    custom_terms = pd.read_csv(CUSTOM_DICTIONARY_FIXTURE)["term"].astype(str).tolist()
    stopwords = pd.read_csv(STOPWORDS_FIXTURE)["term"].astype(str).tolist()
    corpus = "\n".join(training["message"].astype(str))
    apply = pd.read_csv(APPLY_FIXTURE, keep_default_na=False)
    apply_corpus = "\n".join(apply["message"].astype(str))
    assert len(custom_terms) == 4
    assert all(term in f"{corpus}\n{apply_corpus}" for term in custom_terms)
    assert len(stopwords) == 5
    assert all(term.casefold() in corpus.casefold() for term in stopwords)
    assert apply.columns.tolist() == ["request_id", "message"]
    assert len(apply) == 6
    assert apply["message"].map(_normalized_exact_text).eq("").sum() == 2
    assert "QuantumFoam" in apply_corpus
    assert "龙鳞协议" in apply_corpus


def test_independent_classification_and_dummy_oracles_are_deterministic() -> None:
    truth = ["priority", "priority", "standard", "standard"]
    predictions = ["priority", "standard", "standard", "standard"]
    metrics = _classification_metrics(truth, predictions)
    assert metrics.accuracy == pytest.approx(0.75)
    assert metrics.balanced_accuracy == pytest.approx(0.75)
    assert metrics.precision_macro == pytest.approx(5.0 / 6.0)
    assert metrics.precision_weighted == pytest.approx(5.0 / 6.0)
    assert metrics.recall_macro == pytest.approx(0.75)
    assert metrics.recall_weighted == pytest.approx(0.75)
    assert metrics.f1_macro == pytest.approx(11.0 / 15.0)
    assert metrics.f1_weighted == pytest.approx(11.0 / 15.0)

    dummy = _most_frequent_dummy_predictions(
        ["standard", "priority", "standard", "priority"],
        holdout_row_count=4,
    )
    assert dummy == ["priority"] * 4
    digest = _generic_prediction_digest(predictions)
    assert len(digest) == 64
    assert digest == _generic_prediction_digest(predictions)
    assert digest != _generic_prediction_digest(list(reversed(predictions)))
    assert math.isfinite(metrics.f1_weighted)


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
