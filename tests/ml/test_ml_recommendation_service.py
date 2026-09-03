from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import numpy as np
import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult
from xenix.services.ml.registry import get_model_catalog_entry, list_model_keys
from xenix.services.ml.types import ApplyMode, EvaluationKind, ModelFamily, ModelTaskKind
from xenix.services.ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus
from xenix.services.ml.trained_model_metadata import parse_trained_model_metadata


FIXTURES = FIXTURES_ROOT / "ml_recommendation"
TIMED_HISTORY = FIXTURES / "explicit_ratings_with_time_v1.csv"
HASH_HISTORY = FIXTURES / "explicit_ratings_without_time_v1.csv"
APPLY_USERS = FIXTURES / "apply_users_v1.csv"
FIXTURE_SHA256 = {
    TIMED_HISTORY.name: "0c961cb9a17a3ad2b66a9f02048036c6c7042d1b073d27dd3bd82445a0dca2b8",
    HASH_HISTORY.name: "e05d5f93ee999fe452f9e9937a3c8ca73f8c8874e5777a0424652469a0dba990",
    APPLY_USERS.name: "c1b6a7f15095f088b1340b8d8269ca2368e92bb2490723ccad24b5ea79c5318a",
}
ACTIVE_MODEL_KEY = "recommendation.collaborative_top_k"
LEGACY_MODEL_KEY = "recommendation.item_similarity"
PARAMS = {
    "top_k": 3,
    "min_user_interactions": 4,
    "min_item_interactions": 2,
    "positive_rating_threshold": 4.0,
}


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


@dataclass
class _Runtime:
    paths: Any
    storage: Any
    datasets: DatasetService
    tasks: MLTaskService
    ml: MLService
    artifacts: ArtifactService


@dataclass(frozen=True)
class _AnalyzerOracle:
    candidate_items: tuple[str, ...]
    popularity_order: tuple[str, ...]
    popularity_scores: dict[str, float]
    item_support: dict[str, int]
    user_seen: dict[str, frozenset[str]]
    user_ratings: dict[str, dict[str, float]]
    similarities: dict[tuple[str, str], float]


@dataclass(frozen=True)
class _EvaluationOracle:
    prepared: pd.DataFrame
    train: pd.DataFrame
    holdout: pd.DataFrame
    evaluation_analyzer: _AnalyzerOracle
    final_analyzer: _AnalyzerOracle
    candidate_rankings: pd.DataFrame
    baseline_rankings: pd.DataFrame
    full_rankings: pd.DataFrame
    candidate_metrics: dict[str, Any]
    baseline_metrics: dict[str, Any]
    train_digest: str
    holdout_digest: str
    shared_truth_digest: str
    preparation_digest: str
    collapsed_duplicate_row_count: int


def _runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Runtime:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    return _Runtime(
        paths=paths,
        storage=storage,
        datasets=datasets,
        tasks=tasks,
        ml=MLService(paths, storage.session_factory, datasets, tasks),
        artifacts=ArtifactService(storage.session_factory),
    )


def _wait_for_terminal(tasks: MLTaskService, task_id: str, *, timeout: float = 30.0):
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
    raise AssertionError("Recommendation analyzer did not receive an evaluation-task reference")


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


def _digest(payload: Any) -> str:
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _dataset_snapshot_digest(payload: dict[str, Any]) -> str:
    return _digest(payload)


def _pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _interaction_digest(frame: pd.DataFrame, *, time_column: str | None) -> str:
    rows: list[dict[str, Any]] = []
    for row in frame.sort_values(["user_id", "item_id"], kind="stable").to_dict(
        orient="records"
    ):
        value: dict[str, Any] = {
            "user": str(row["user_id"]),
            "item": str(row["item_id"]),
            "rating": float(row["rating"]).hex(),
        }
        if time_column is not None:
            value["time"] = pd.Timestamp(row[time_column]).isoformat()
        rows.append(value)
    return _digest(rows)


def _ranking_digest(rankings: pd.DataFrame) -> str:
    ordered = rankings.sort_values(["user_id", "rank"], kind="stable")
    return _digest(
        [
            {
                "user": str(row["user_id"]),
                "rank": int(row["rank"]),
                "item": str(row["recommended_item"]),
                "strategy": str(row["strategy"]),
                "score": float(row["score"]).hex(),
            }
            for row in ordered.to_dict(orient="records")
        ]
    )


def _holdout_hash(source_digest: str, user: str, item: str) -> str:
    return sha256(
        json.dumps(
            [source_digest, user, item],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _prepare_history(frame: pd.DataFrame, *, time_column: str | None) -> tuple[pd.DataFrame, int]:
    columns = ["user_id", "item_id", "rating"]
    if time_column is not None:
        columns.append(time_column)
    working = frame.loc[:, columns].copy()
    working["user_id"] = working["user_id"].astype("string").str.strip()
    working["item_id"] = working["item_id"].astype("string").str.strip()
    working["rating"] = pd.to_numeric(working["rating"], errors="coerce")
    if time_column is not None:
        working[time_column] = pd.to_datetime(working[time_column], utc=True)
    admitted_row_count = len(working)
    aggregations: dict[str, str] = {"rating": "mean"}
    if time_column is not None:
        aggregations[time_column] = "max"
    prepared = (
        working.groupby(["user_id", "item_id"], as_index=False, sort=True)
        .agg(aggregations)
        .sort_values(["user_id", "item_id"], kind="stable")
        .reset_index(drop=True)
    )
    return prepared, admitted_row_count - len(prepared)


def _split_history(
    prepared: pd.DataFrame,
    *,
    time_column: str | None,
    source_digest: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    provisional: list[int] = []
    for user, user_frame in prepared.groupby("user_id", sort=True):
        if len(user_frame) < PARAMS["min_user_interactions"]:
            continue
        positive = user_frame.loc[
            user_frame["rating"] >= PARAMS["positive_rating_threshold"]
        ]
        if positive.empty:
            continue
        if time_column is not None:
            positive = positive.loc[positive[time_column] == positive[time_column].max()]
        selected = min(
            positive.index,
            key=lambda index: _holdout_hash(
                source_digest,
                str(user),
                str(prepared.at[index, "item_id"]),
            ),
        )
        provisional.append(int(selected))

    provisional_train = prepared.drop(index=provisional)
    support = provisional_train.groupby("item_id")["user_id"].nunique()
    candidate_catalog = {
        str(item)
        for item, count in support.items()
        if int(count) >= PARAMS["min_item_interactions"]
    }
    selected_holdouts = [
        index
        for index in provisional
        if str(prepared.at[index, "item_id"]) in candidate_catalog
    ]
    train = prepared.drop(index=selected_holdouts).reset_index(drop=True)
    holdout = (
        prepared.loc[selected_holdouts]
        .sort_values("user_id", kind="stable")
        .reset_index(drop=True)
    )
    return train, holdout


def _build_oracle_analyzer(interactions: pd.DataFrame) -> _AnalyzerOracle:
    support = interactions.groupby("item_id")["user_id"].nunique()
    item_support = {str(item): int(count) for item, count in support.items()}
    candidate_items = tuple(
        sorted(
            item
            for item, count in item_support.items()
            if count >= PARAMS["min_item_interactions"]
        )
    )
    candidate_frame = interactions.loc[interactions["item_id"].isin(candidate_items)]
    means = candidate_frame.groupby("item_id")["rating"].mean().to_dict()
    maximum_support = max(item_support[item] for item in candidate_items)
    popularity_scores = {
        item: float(item_support[item] / maximum_support) for item in candidate_items
    }
    popularity_order = tuple(
        sorted(
            candidate_items,
            key=lambda item: (-item_support[item], -float(means[item]), item),
        )
    )
    user_seen = {
        str(user): frozenset(str(item) for item in group["item_id"])
        for user, group in interactions.groupby("user_id", sort=True)
    }
    user_ratings = {
        str(user): {
            str(row["item_id"]): float(row["rating"])
            for row in group.to_dict(orient="records")
        }
        for user, group in interactions.groupby("user_id", sort=True)
    }
    pivot = interactions.pivot_table(
        index="user_id",
        columns="item_id",
        values="rating",
        aggfunc="mean",
    )
    centered = pivot.sub(pivot.mean(axis=1), axis=0)
    similarities: dict[tuple[str, str], float] = {}
    for left_index, left in enumerate(candidate_items):
        for right in candidate_items[left_index + 1 :]:
            common = centered[left].notna() & centered[right].notna()
            common_count = int(common.sum())
            if common_count < 2:
                similarity = 0.0
            else:
                left_values = centered.loc[common, left].to_numpy(dtype=float)
                right_values = centered.loc[common, right].to_numpy(dtype=float)
                denominator = float(np.linalg.norm(left_values) * np.linalg.norm(right_values))
                cosine = (
                    float(np.dot(left_values, right_values) / denominator)
                    if denominator
                    else 0.0
                )
                similarity = max(0.0, cosine) * (common_count / (common_count + 5.0))
            similarities[_pair(left, right)] = similarity
    return _AnalyzerOracle(
        candidate_items=candidate_items,
        popularity_order=popularity_order,
        popularity_scores=popularity_scores,
        item_support=item_support,
        user_seen=user_seen,
        user_ratings=user_ratings,
        similarities=similarities,
    )


def _recommend(
    analyzer: _AnalyzerOracle,
    users: list[str],
    *,
    baseline: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for user in users:
        seen = analyzer.user_seen.get(user, frozenset())
        if baseline:
            ranked = [
                (
                    item,
                    analyzer.popularity_scores[item],
                    "popularity_baseline",
                )
                for item in analyzer.popularity_order
                if item not in seen
            ]
        else:
            is_cold = user not in analyzer.user_seen
            personalized: list[tuple[str, float, int]] = []
            if not is_cold:
                for candidate in analyzer.candidate_items:
                    if candidate in seen:
                        continue
                    numerator = 0.0
                    denominator = 0.0
                    for seen_item, rating in analyzer.user_ratings[user].items():
                        similarity = analyzer.similarities.get(
                            _pair(candidate, seen_item),
                            0.0,
                        )
                        if similarity > 0.0:
                            numerator += similarity * rating
                            denominator += abs(similarity)
                    if denominator:
                        personalized.append(
                            (
                                candidate,
                                numerator / denominator,
                                analyzer.item_support[candidate],
                            )
                        )
            if not personalized:
                strategy = "popularity_cold_start" if is_cold else "popularity_fallback"
                ranked = [
                    (
                        item,
                        analyzer.popularity_scores[item],
                        strategy,
                    )
                    for item in analyzer.popularity_order
                    if item not in seen
                ]
            else:
                personalized.sort(key=lambda value: (-value[1], -value[2], value[0]))
                ranked = [
                    (item, score, "personalized_collaborative")
                    for item, score, _support in personalized
                ]
                personalized_items = {item for item, _score, _strategy in ranked}
                ranked.extend(
                    (
                        item,
                        analyzer.popularity_scores[item],
                        "popularity_fallback",
                    )
                    for item in analyzer.popularity_order
                    if item not in seen and item not in personalized_items
                )
        for rank, (item, score, strategy) in enumerate(
            ranked[: PARAMS["top_k"]],
            start=1,
        ):
            rows.append(
                {
                    "user_id": user,
                    "rank": rank,
                    "recommended_item": item,
                    "score": float(score),
                    "strategy": strategy,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["user_id", "rank", "recommended_item", "score", "strategy"],
    )


def _ranking_metrics(
    rankings: pd.DataFrame,
    *,
    truth: dict[str, set[str]],
    analyzer: _AnalyzerOracle,
) -> dict[str, Any]:
    grouped = {
        str(user): group.sort_values("rank", kind="stable")
        for user, group in rankings.groupby("user_id", sort=True)
    }
    ndcg: list[float] = []
    recall: list[float] = []
    hit_rate: list[float] = []
    reciprocal_rank: list[float] = []
    recommended_items: set[str] = set()
    novelty: list[float] = []
    diversity: list[float] = []
    seen_violations = 0
    short_lists = 0
    for user in sorted(truth):
        items = grouped[user]["recommended_item"].astype(str).tolist()[: PARAMS["top_k"]]
        if len(items) < PARAMS["top_k"]:
            short_lists += 1
        hits = [position for position, item in enumerate(items, start=1) if item in truth[user]]
        hit_count = len(hits)
        hit_rate.append(float(bool(hits)))
        recall.append(hit_count / len(truth[user]))
        reciprocal_rank.append(1.0 / min(hits) if hits else 0.0)
        dcg = sum(1.0 / math.log2(position + 1) for position in hits)
        ideal_hits = min(len(truth[user]), PARAMS["top_k"])
        ideal_dcg = sum(
            1.0 / math.log2(position + 1)
            for position in range(1, ideal_hits + 1)
        )
        ndcg.append(dcg / ideal_dcg if ideal_dcg else 0.0)
        seen = analyzer.user_seen[user]
        seen_violations += sum(item in seen for item in items)
        recommended_items.update(items)
        novelty.extend(
            -math.log2(analyzer.item_support[item] / len(analyzer.user_seen))
            for item in items
        )
        pair_distances = [
            1.0
            - max(
                0.0,
                min(1.0, analyzer.similarities.get(_pair(left, right), 0.0)),
            )
            for left_index, left in enumerate(items)
            for right in items[left_index + 1 :]
        ]
        if pair_distances:
            diversity.append(float(np.mean(pair_distances)))
    return {
        "evaluated_user_count": len(truth),
        "recommendation_count": len(rankings),
        "short_list_user_count": short_lists,
        "ndcg_at_k": float(np.mean(ndcg)),
        "recall_at_k": float(np.mean(recall)),
        "hit_rate_at_k": float(np.mean(hit_rate)),
        "mrr_at_k": float(np.mean(reciprocal_rank)),
        "catalog_coverage_at_k": len(recommended_items) / len(analyzer.candidate_items),
        "mean_novelty_at_k": float(np.mean(novelty)),
        "mean_intra_list_diversity_at_k": float(np.mean(diversity)),
        "seen_item_violation_count": seen_violations,
        "ranking_digest": _ranking_digest(rankings),
    }


def _build_evaluation_oracle(
    frame: pd.DataFrame,
    *,
    time_column: str | None,
    source_digest: str,
) -> _EvaluationOracle:
    prepared, collapsed_duplicate_count = _prepare_history(
        frame,
        time_column=time_column,
    )
    train, holdout = _split_history(
        prepared,
        time_column=time_column,
        source_digest=source_digest,
    )
    evaluation_analyzer = _build_oracle_analyzer(train)
    final_analyzer = _build_oracle_analyzer(prepared)
    truth = {
        str(row["user_id"]): {str(row["item_id"])}
        for row in holdout.to_dict(orient="records")
    }
    users = sorted(truth)
    candidate_rankings = _recommend(evaluation_analyzer, users)
    baseline_rankings = _recommend(evaluation_analyzer, users, baseline=True)
    train_digest = _interaction_digest(train, time_column=time_column)
    holdout_digest = _interaction_digest(holdout, time_column=time_column)
    preparation_payload = {
        "policy_key": "explicit_rating_mean_duplicates.v1",
        "source_dataset_snapshot_digest": source_digest,
        "interaction_digest": _interaction_digest(prepared, time_column=time_column),
        "config": {
            "min_user_interactions": PARAMS["min_user_interactions"],
            "min_item_interactions": PARAMS["min_item_interactions"],
            "positive_rating_threshold": PARAMS["positive_rating_threshold"],
        },
    }
    return _EvaluationOracle(
        prepared=prepared,
        train=train,
        holdout=holdout,
        evaluation_analyzer=evaluation_analyzer,
        final_analyzer=final_analyzer,
        candidate_rankings=candidate_rankings,
        baseline_rankings=baseline_rankings,
        full_rankings=_recommend(final_analyzer, sorted(final_analyzer.user_seen)),
        candidate_metrics=_ranking_metrics(
            candidate_rankings,
            truth=truth,
            analyzer=evaluation_analyzer,
        ),
        baseline_metrics=_ranking_metrics(
            baseline_rankings,
            truth=truth,
            analyzer=evaluation_analyzer,
        ),
        train_digest=train_digest,
        holdout_digest=holdout_digest,
        shared_truth_digest=_digest(
            {
                "train": train_digest,
                "holdout": holdout_digest,
                "top_k": PARAMS["top_k"],
            }
        ),
        preparation_digest=_digest(preparation_payload),
        collapsed_duplicate_row_count=collapsed_duplicate_count,
    )


def _assert_metric_facts(actual: Any, expected: dict[str, Any]) -> None:
    assert actual.top_k == PARAMS["top_k"]
    for field in (
        "evaluated_user_count",
        "recommendation_count",
        "short_list_user_count",
        "seen_item_violation_count",
        "ranking_digest",
    ):
        assert getattr(actual, field) == expected[field]
    for field in (
        "ndcg_at_k",
        "recall_at_k",
        "hit_rate_at_k",
        "mrr_at_k",
        "catalog_coverage_at_k",
        "mean_novelty_at_k",
        "mean_intra_list_diversity_at_k",
    ):
        assert getattr(actual, field) == pytest.approx(expected[field], abs=1e-6)


def _assert_ranking_frame(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    columns = ["user_id", "rank", "recommended_item", "score", "strategy"]
    actual_ordered = actual.loc[:, columns].sort_values(["user_id", "rank"]).reset_index(drop=True)
    expected_ordered = expected.loc[:, columns].sort_values(["user_id", "rank"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        actual_ordered.drop(columns="score"),
        expected_ordered.drop(columns="score"),
        check_dtype=False,
    )
    assert actual_ordered["score"].to_numpy() == pytest.approx(
        expected_ordered["score"].to_numpy(),
        abs=1e-12,
    )
    for _user, group in actual_ordered.groupby("user_id", sort=False):
        assert group["rank"].tolist() == list(range(1, len(group) + 1))
        assert group["recommended_item"].is_unique
        assert len(group) <= PARAMS["top_k"]


def _exercise_ranking_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    history_path: Path,
    time_column: str | None,
    expected_policy: str,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        training_dataset = _register(runtime.datasets, history_path)
        apply_dataset = _register(
            runtime.datasets,
            APPLY_USERS,
            project_id=training_dataset.project_id,
        )
        training_digest_before = sha256(
            Path(training_dataset.source_path).read_bytes()
        ).hexdigest()
        apply_digest_before = sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest()
        roles = [
            {"role": "user", "columns": ["user_id"]},
            {"role": "item", "columns": ["item_id"]},
            {"role": "rating", "columns": ["rating"]},
        ]
        if time_column is not None:
            roles.append({"role": "time", "columns": [time_column]})
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=roles,
            )
        )
        assert binding.dataset_snapshot_payload is not None
        assert binding.dataset_snapshot_payload["source_sha256"] == training_digest_before
        expected_snapshot_digest = _dataset_snapshot_digest(
            binding.dataset_snapshot_payload
        )
        fit_task = runtime.ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=binding.id,
                run_name=f"Recommendation {expected_policy}",
                model_key=ACTIVE_MODEL_KEY,
                params=PARAMS,
            )
        )
        completed_fit = _wait_for_terminal(runtime.tasks, fit_task.id)
        assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
        fit_payload = completed_fit.result_payload or {}
        assert fit_payload["training_scopes"] == {
            "evaluation_model": "per_user_holdout_training_interactions",
            "apply_model": "all_admitted_interactions",
        }

        trained_model = runtime.ml.get_trained_model_by_ml_task(fit_task.id)
        assert trained_model is not None
        evaluation_task_id = _wait_for_evaluation_id(runtime.ml, trained_model.id)
        completed_evaluation = _wait_for_terminal(runtime.tasks, evaluation_task_id)
        assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, completed_evaluation.error_summary
        evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)
        facts = evaluation.recommendation_evaluation
        assert facts is not None
        assert evaluation.evaluation_kind is EvaluationKind.RANKING
        assert evaluation.evaluation is not None
        assert evaluation.baseline_evaluation is not None
        assert evaluation.comparison is not None
        assert evaluation.comparison.primary_metric_name == "ndcg_at_k"
        assert evaluation.evaluation.primary_metric_name == "ndcg_at_k"
        assert evaluation.baseline_evaluation.primary_metric_name == "ndcg_at_k"

        source_digest = facts.split.source_dataset_snapshot_digest
        assert source_digest == expected_snapshot_digest
        raw_history = pd.read_csv(history_path)
        oracle = _build_evaluation_oracle(
            raw_history,
            time_column=time_column,
            source_digest=source_digest,
        )
        assert facts.split.policy_key == expected_policy
        assert facts.split.eligible_user_count == len(oracle.holdout)
        assert facts.split.train_interaction_count == len(oracle.train)
        assert facts.split.holdout_interaction_count == len(oracle.holdout)
        assert facts.split.train_user_count == oracle.train["user_id"].nunique()
        assert facts.split.holdout_user_count == oracle.holdout["user_id"].nunique()
        assert facts.split.user_overlap_count == facts.split.holdout_user_count
        assert facts.split.train_membership_digest == oracle.train_digest
        assert facts.split.holdout_membership_digest == oracle.holdout_digest
        assert facts.split.shared_truth_digest == oracle.shared_truth_digest

        preparation = facts.preparation
        assert preparation.policy_key == "explicit_rating_mean_duplicates.v1"
        assert preparation.source_row_count == len(raw_history)
        assert preparation.admitted_interaction_count == len(oracle.prepared)
        assert preparation.collapsed_duplicate_row_count == (
            oracle.collapsed_duplicate_row_count
        ) == 1
        assert preparation.dropped_missing_identity_count == 0
        assert preparation.dropped_non_finite_rating_count == 0
        assert preparation.user_count == oracle.prepared["user_id"].nunique()
        assert preparation.item_count == oracle.prepared["item_id"].nunique()
        assert preparation.candidate_item_count == len(
            oracle.evaluation_analyzer.candidate_items
        )
        assert preparation.time_column_present is (time_column is not None)
        assert preparation.preparation_digest == oracle.preparation_digest
        _assert_metric_facts(facts.candidate, oracle.candidate_metrics)
        _assert_metric_facts(facts.baseline, oracle.baseline_metrics)
        assert facts.candidate.seen_item_violation_count == 0
        assert facts.baseline.seen_item_violation_count == 0
        assert evaluation.evaluation.details["ranking_digest"] == facts.candidate.ranking_digest
        assert evaluation.baseline_evaluation.details["ranking_digest"] == facts.baseline.ranking_digest
        assert len(facts.evidence_digest) == 64
        fit_facts = fit_payload["result_summary"]["recommendation_evaluation"]
        assert fit_facts["evidence_digest"] == facts.evidence_digest
        assert fit_payload["recommendation_split_facts"] == facts.split.model_dump(
            mode="json"
        )
        assert fit_payload["recommendation_preparation_facts"] == (
            facts.preparation.model_dump(mode="json")
        )
        serialized_facts = facts.model_dump_json()
        assert "u01" not in serialized_facts
        assert "item_a" not in serialized_facts

        fit_dataset = runtime.datasets.get_dataset(fit_payload["result_dataset_id"])
        assert fit_dataset.derived_from_dataset_id == training_dataset.id
        assert fit_dataset.ml_task_id == completed_fit.id
        fit_frame = pd.read_parquet(fit_dataset.source_path)
        assert fit_frame.columns.tolist() == [
            "user_id",
            "rank",
            "recommended_item",
            "score",
            "strategy",
        ]
        _assert_ranking_frame(fit_frame, oracle.full_rankings)
        for user, seen in oracle.final_analyzer.user_seen.items():
            recommended = set(
                fit_frame.loc[fit_frame["user_id"] == user, "recommended_item"].astype(str)
            )
            assert recommended.isdisjoint(seen)
        assert "item_i" not in set(fit_frame["recommended_item"])

        fit_artifacts = runtime.tasks.list_ml_task_artifacts(completed_fit.id)
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
        for artifact in (training_report, export_artifact):
            assert artifact.ready_to_open is True
            assert artifact.artifact_id
            resolved = runtime.artifacts.resolve_uri(build_artifact_uri(artifact.artifact_id))
            assert resolved.exists is True

        evaluation_report = next(
            artifact
            for artifact in runtime.tasks.list_ml_task_artifacts(evaluation_task_id)
            if artifact.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT
        )
        assert evaluation_report.ready_to_open is True
        assert evaluation_report.artifact_id
        assert runtime.artifacts.resolve_uri(
            build_artifact_uri(evaluation_report.artifact_id)
        ).exists is True

        refreshed_model = runtime.ml.get_trained_model(trained_model.id)
        assert refreshed_model is not None
        metadata = parse_trained_model_metadata(refreshed_model.metadata_payload)
        assert metadata is not None
        assert metadata.model_family == "recommendation"
        assert metadata.model_task_kind == "recommender"
        assert metadata.evaluation_kind == "ranking"
        assert metadata.supports_evaluation is True
        assert metadata.supports_apply is True
        assert metadata.apply_mode == "rows"
        assert metadata.training_params == PARAMS
        assert metadata.evaluation_model_training_scope == (
            "per_user_holdout_training_interactions"
        )
        assert metadata.apply_model_training_scope == "all_admitted_interactions"
        assert metadata.evaluation_ml_task_id == evaluation_task_id
        assert metadata.evaluation_facts_authority == "ml_task_result"

        apply_task = runtime.ml.apply(
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
        completed_apply = _wait_for_terminal(runtime.tasks, apply_task.id)
        assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
        apply_payload = completed_apply.result_payload or {}
        assert apply_payload["source_dataset_ids"] == [apply_dataset.id]
        assert apply_payload["source_artifact_ids"] == []
        result_dataset = runtime.datasets.get_dataset(apply_payload["result_dataset_id"])
        assert result_dataset.derived_from_dataset_id == apply_dataset.id
        assert result_dataset.ml_task_id == apply_task.id
        apply_frame = pd.read_parquet(result_dataset.source_path)
        assert apply_frame.columns.tolist() == [
            "source_file",
            "input_row_number",
            "user_id",
            "rank",
            "recommended_item",
            "score",
            "strategy",
        ]
        expected_apply = _recommend(
            oracle.final_analyzer,
            pd.read_csv(APPLY_USERS)["user_id"].astype(str).tolist(),
        )
        _assert_ranking_frame(apply_frame, expected_apply)
        assert set(apply_frame.loc[apply_frame["user_id"] == "u01", "strategy"]) == {
            "personalized_collaborative"
        }
        assert set(apply_frame.loc[apply_frame["user_id"] == "u09", "strategy"]) == {
            "popularity_fallback"
        }
        assert set(apply_frame.loc[apply_frame["user_id"] == "u99", "strategy"]) == {
            "popularity_cold_start"
        }
        known_seen = oracle.final_analyzer.user_seen["u01"]
        known_items = set(
            apply_frame.loc[apply_frame["user_id"] == "u01", "recommended_item"]
        )
        assert known_items.isdisjoint(known_seen)
        assert "item_i" not in set(apply_frame["recommended_item"])

        apply_artifact = next(
            artifact
            for artifact in runtime.tasks.list_ml_task_artifacts(apply_task.id)
            if artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT
        )
        assert apply_artifact.ready_to_open is True
        assert apply_artifact.artifact_id
        resolved_apply = runtime.artifacts.resolve_uri(
            build_artifact_uri(apply_artifact.artifact_id)
        )
        assert resolved_apply.exists is True
        assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
        assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
        assert resolved_apply.metadata_payload["result_dataset_id"] == result_dataset.id

        assert sha256(Path(training_dataset.source_path).read_bytes()).hexdigest() == (
            training_digest_before
        )
        assert sha256(Path(apply_dataset.source_path).read_bytes()).hexdigest() == apply_digest_before
        assert sha256(history_path.read_bytes()).hexdigest() == FIXTURE_SHA256[history_path.name]
        assert sha256(APPLY_USERS.read_bytes()).hexdigest() == FIXTURE_SHA256[APPLY_USERS.name]
    finally:
        runtime.storage.engine.dispose()


def test_latest_positive_recommendation_lifecycle_and_independent_metrics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timed = pd.read_csv(TIMED_HISTORY)
    untimed = pd.read_csv(HASH_HISTORY)
    pd.testing.assert_frame_equal(
        timed.drop(columns="event_time"),
        untimed,
        check_dtype=False,
    )
    _exercise_ranking_lifecycle(
        monkeypatch,
        tmp_path,
        history_path=TIMED_HISTORY,
        time_column="event_time",
        expected_policy="latest_positive_per_user.v1",
    )


def test_hash_positive_twin_replays_the_same_public_ranking_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exercise_ranking_lifecycle(
        monkeypatch,
        tmp_path,
        history_path=HASH_HISTORY,
        time_column=None,
        expected_policy="deterministic_hash_positive_per_user.v1",
    )


def test_active_personalized_key_preserves_legacy_item_similarity_semantics() -> None:
    assert {ACTIVE_MODEL_KEY, LEGACY_MODEL_KEY}.issubset(set(list_model_keys()))
    active = get_model_catalog_entry(ACTIVE_MODEL_KEY)
    legacy = get_model_catalog_entry(LEGACY_MODEL_KEY)

    assert active.model_family is ModelFamily.RECOMMENDATION
    assert active.model_task_kind is ModelTaskKind.RECOMMENDER
    assert active.evaluation_kind is EvaluationKind.RANKING
    assert active.supports_evaluation is True
    assert active.apply_mode is ApplyMode.ROWS
    assert [role.name for role in active.train_role_schema.roles] == [
        "user",
        "item",
        "rating",
        "time",
    ]
    assert [role.name for role in active.apply_role_schema.roles] == ["user"]

    assert legacy.model_family is ModelFamily.RECOMMENDATION
    assert legacy.model_task_kind is ModelTaskKind.RECOMMENDER
    assert legacy.evaluation_kind is EvaluationKind.SUMMARY
    assert legacy.supports_evaluation is False
    assert legacy.apply_mode is ApplyMode.ROWS
    assert [role.name for role in legacy.apply_role_schema.roles] == ["item"]
    assert set(legacy.param_schema["properties"]) == {
        "min_ratings_base",
        "min_ratings_candidate",
        "similarity_threshold",
        "top_k",
    }
