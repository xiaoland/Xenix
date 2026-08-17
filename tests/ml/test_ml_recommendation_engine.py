from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
import pytest

from xenix.exceptions import ValidationError
from xenix.services.ml.contracts import (
    ApplyInputFile,
    ApplyModelPayload,
    ApplyTaskRequest,
    DatasetSnapshotFact,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    FitTaskRequest,
    ManualTrainingPayload,
)
from xenix.services.ml.evaluation import get_default_policy
from xenix.services.ml.models.recommendation import CollaborativeTopKRecommendationService
from xenix.services.ml.recommendation_evidence import (
    HASH_HOLDOUT_POLICY,
    LATEST_HOLDOUT_POLICY,
    RecommendationEngineConfig,
    RetainedRecommendationAnalyzer,
    fit_recommendation_engine,
    prepare_explicit_ratings,
    split_positive_holdout,
)
from xenix.services.ml.preparation import dataset_snapshot_digest
from xenix.services.ml.types import EvaluationKind


CONFIG = RecommendationEngineConfig(
    top_k=2,
    min_user_interactions=3,
    min_item_interactions=2,
    positive_rating_threshold=4.0,
)
SOURCE_DIGEST = "a" * 64


def _ratings() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    groups = [
        ("SKU-A", "SKU-B", "SKU-C"),
        ("SKU-D", "SKU-E", "SKU-F"),
        ("SKU-G", "SKU-H", "SKU-I"),
    ]
    user_number = 1
    for left, right, low_item in groups:
        for offset in range(4):
            user = f"USER-{user_number:02d}"
            left_day, right_day = ((1, 3) if offset % 2 == 0 else (3, 1))
            rows.extend(
                [
                    {
                        "user_id": user,
                        "item_id": left,
                        "rating": 5 if offset % 2 == 0 else 4,
                        "event_time": f"2026-01-{left_day:02d}T00:00:00Z",
                    },
                    {
                        "user_id": user,
                        "item_id": right,
                        "rating": 4 if offset % 2 == 0 else 5,
                        "event_time": f"2026-01-{right_day:02d}T00:00:00Z",
                    },
                    {
                        "user_id": user,
                        "item_id": low_item,
                        "rating": 5,
                        "event_time": "2026-01-01T00:00:00Z",
                    },
                    {
                        "user_id": user,
                        "item_id": "SKU-Z",
                        "rating": 1,
                        "event_time": "2026-01-02T00:00:00Z",
                    },
                ]
            )
            user_number += 1
    rows.extend(
        [
            {
                "user_id": "USER-01",
                "item_id": "SKU-A",
                "rating": 5,
                "event_time": "2026-01-01T00:00:00Z",
            },
            {
                "user_id": None,
                "item_id": "SKU-A",
                "rating": 5,
                "event_time": "2026-01-01T00:00:00Z",
            },
            {
                "user_id": "USER-X",
                "item_id": "SKU-X",
                "rating": "not-a-rating",
                "event_time": "2026-01-01T00:00:00Z",
            },
        ]
    )
    return pd.DataFrame(rows)


def _fit(*, with_time: bool = True):
    return fit_recommendation_engine(
        _ratings(),
        user_column="user_id",
        item_column="item_id",
        rating_column="rating",
        time_column="event_time" if with_time else None,
        source_dataset_snapshot_digest=SOURCE_DIGEST,
        config=CONFIG,
    )


def test_engine_builds_deterministic_same_truth_ranking_evidence() -> None:
    first = _fit()
    second = _fit()
    facts = first.facts

    assert facts.model_dump(mode="json") == second.facts.model_dump(mode="json")
    assert facts.split.policy_key == LATEST_HOLDOUT_POLICY
    assert facts.split.eligible_user_count == facts.split.holdout_interaction_count
    assert facts.split.user_overlap_count == facts.split.eligible_user_count
    assert facts.candidate.evaluated_user_count == facts.baseline.evaluated_user_count
    assert facts.candidate.ndcg_at_k is not None
    assert facts.baseline.ndcg_at_k is not None
    assert facts.candidate.ndcg_at_k > facts.baseline.ndcg_at_k
    assert facts.candidate.seen_item_violation_count == 0
    assert facts.baseline.seen_item_violation_count == 0
    assert facts.preparation.collapsed_duplicate_row_count == 1
    assert facts.preparation.dropped_missing_identity_count == 1
    assert facts.preparation.dropped_non_finite_rating_count == 1
    assert len(facts.candidate.ranking_digest) == 64
    assert len(facts.baseline.ranking_digest) == 64
    assert len(facts.evidence_digest) == 64

    serialized = json.dumps(facts.model_dump(mode="json"), sort_keys=True)
    assert "USER-01" not in serialized
    assert "SKU-A" not in serialized
    assert "item values" in serialized


def test_latest_positive_holdout_is_recomputable_and_never_silently_hashes() -> None:
    prepared = prepare_explicit_ratings(
        _ratings(),
        user_column="user_id",
        item_column="item_id",
        rating_column="rating",
        time_column="event_time",
        source_dataset_snapshot_digest=SOURCE_DIGEST,
        config=CONFIG,
    )
    _train, holdout, facts = split_positive_holdout(
        prepared.interactions,
        time_column="event_time",
        source_dataset_snapshot_digest=SOURCE_DIGEST,
        config=CONFIG,
    )

    assert facts.policy_key == LATEST_HOLDOUT_POLICY
    for row in holdout.to_dict(orient="records"):
        user_positives = prepared.interactions.loc[
            (prepared.interactions["user_id"] == row["user_id"])
            & (prepared.interactions["rating"] >= CONFIG.positive_rating_threshold)
        ]
        assert row["event_time"] == user_positives["event_time"].max()

    invalid = _ratings()
    invalid.loc[0, "event_time"] = "not-a-time"
    with pytest.raises(ValueError, match="invalid timestamps"):
        fit_recommendation_engine(
            invalid,
            user_column="user_id",
            item_column="item_id",
            rating_column="rating",
            time_column="event_time",
            source_dataset_snapshot_digest=SOURCE_DIGEST,
            config=CONFIG,
        )


def test_hash_positive_holdout_is_versioned_and_deterministic_without_time() -> None:
    dataframe = _ratings().drop(columns=["event_time"])
    first = fit_recommendation_engine(
        dataframe,
        user_column="user_id",
        item_column="item_id",
        rating_column="rating",
        time_column=None,
        source_dataset_snapshot_digest=SOURCE_DIGEST,
        config=CONFIG,
    )
    second = fit_recommendation_engine(
        dataframe,
        user_column="user_id",
        item_column="item_id",
        rating_column="rating",
        time_column=None,
        source_dataset_snapshot_digest=SOURCE_DIGEST,
        config=CONFIG,
    )

    assert first.facts.split.policy_key == HASH_HOLDOUT_POLICY
    assert first.facts.split.holdout_membership_digest == second.facts.split.holdout_membership_digest
    assert first.facts.candidate.ranking_digest == second.facts.candidate.ranking_digest


def test_retained_analyzer_excludes_seen_items_and_uses_cold_user_popularity() -> None:
    fitted = _fit()
    analyzer = fitted.final_analyzer

    for user, frame in fitted.full_recommendations.groupby("user_id", sort=True):
        items = frame.sort_values("rank")["recommended_item"].tolist()
        assert len(items) <= CONFIG.top_k
        assert len(items) == len(set(items))
        assert frame.sort_values("rank")["rank"].tolist() == list(range(1, len(items) + 1))
        assert set(items).isdisjoint(analyzer.user_seen[str(user)])

    cold = analyzer.recommend_users(["COLD-USER"])
    assert cold["recommended_item"].tolist() == list(analyzer.popularity_order[: CONFIG.top_k])
    assert set(cold["strategy"]) == {"popularity_cold_start"}
    assert fitted.facts.cold_start.cold_user_supported is True
    assert fitted.facts.cold_start.cold_item_supported is False
    assert "SKU-NEVER-SEEN" not in cold["recommended_item"].tolist()


def test_service_fit_evaluate_and_apply_core_round_trip(tmp_path: Path) -> None:
    source_path = tmp_path / "ratings.csv"
    apply_path = tmp_path / "users.csv"
    _ratings().to_csv(source_path, index=False)
    pd.DataFrame({"user_id": ["USER-01", "COLD-USER"]}).to_csv(apply_path, index=False)
    policy = get_default_policy(EvaluationKind.RANKING)
    snapshot = DatasetSnapshotFact(
        dataset_id="dataset-1",
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        source_byte_size=source_path.stat().st_size,
        schema_digest="b" * 64,
    )
    common = {
        "project_id": "project-1",
        "dataset_id": "dataset-1",
        "dataset_source_path": str(source_path),
        "evaluation_kind": EvaluationKind.RANKING,
        "train_role_bindings": [
            {"role": "user", "columns": ["user_id"]},
            {"role": "item", "columns": ["item_id"]},
            {"role": "rating", "columns": ["rating"]},
            {"role": "time", "columns": ["event_time"]},
        ],
        "evaluation_policy": policy,
        "dataset_snapshot": snapshot,
    }
    fit_result = CollaborativeTopKRecommendationService.fit(
        FitTaskRequest(
            task_id="fit-1",
            **common,
            manual_training=ManualTrainingPayload(
                model_key=CollaborativeTopKRecommendationService.key,
                params={
                    "top_k": 2,
                    "min_user_interactions": 3,
                    "min_item_interactions": 2,
                    "positive_rating_threshold": 4,
                },
            ),
        ),
        tmp_path / "fit-task",
    )

    assert Path(fit_result.model_artifact_path).is_file()
    assert Path(fit_result.final_model_artifact_path or "").is_file()
    assert Path(fit_result.holdout_artifact_path or "").is_file()
    assert Path(fit_result.export_artifact_path or "").is_file()
    assert Path(fit_result.report_artifact_path or "").is_file()
    assert fit_result.recommendation_split_facts is not None
    assert (
        fit_result.recommendation_split_facts.source_dataset_snapshot_digest
        == dataset_snapshot_digest(snapshot)
    )
    retained = joblib.load(fit_result.final_model_artifact_path)
    assert isinstance(retained, RetainedRecommendationAnalyzer)
    private_context_text = Path(fit_result.holdout_artifact_path or "").read_text(
        encoding="utf-8"
    )
    public_report_text = Path(fit_result.report_artifact_path or "").read_text(
        encoding="utf-8"
    )
    assert "USER-01" in private_context_text
    assert "SKU-A" in private_context_text
    assert "USER-01" not in public_report_text
    assert "SKU-A" not in public_report_text

    evaluation = CollaborativeTopKRecommendationService.evaluate(
        EvaluateTaskRequest(
            task_id="evaluate-1",
            **common,
            evaluate_model=EvaluateModelPayload(
                trained_model_id="trained-1",
                model_key=CollaborativeTopKRecommendationService.key,
                trained_model_artifact_path=fit_result.model_artifact_path,
                holdout_artifact_path=fit_result.holdout_artifact_path or "",
            ),
        ),
        tmp_path / "evaluate-task",
    )
    assert evaluation.evaluation is not None
    assert evaluation.baseline_evaluation is not None
    assert evaluation.comparison is not None
    assert evaluation.evaluation.primary_metric_name == "ndcg_at_k"
    assert evaluation.evaluation.details["seen_item_violation_count"] == 0
    assert evaluation.recommendation_evaluation is not None
    assert (
        evaluation.recommendation_evaluation.evidence_digest
        == json.loads(public_report_text)["evidence_digest"]
    )

    tampered_context = json.loads(private_context_text)
    tampered_context["holdout_interactions"][0]["item_id"] = "SKU-TAMPERED"
    tampered_context_path = tmp_path / "tampered-recommendation-context.json"
    tampered_context_path.write_text(json.dumps(tampered_context), encoding="utf-8")
    with pytest.raises(ValidationError, match="does not match"):
        CollaborativeTopKRecommendationService.evaluate(
            EvaluateTaskRequest(
                task_id="evaluate-tampered",
                **common,
                evaluate_model=EvaluateModelPayload(
                    trained_model_id="trained-1",
                    model_key=CollaborativeTopKRecommendationService.key,
                    trained_model_artifact_path=fit_result.model_artifact_path,
                    holdout_artifact_path=str(tampered_context_path),
                ),
            ),
            tmp_path / "evaluate-tampered-task",
        )

    apply_result = CollaborativeTopKRecommendationService.apply(
        ApplyTaskRequest(
            task_id="apply-1",
            project_id="project-1",
            dataset_id="dataset-1",
            dataset_source_path=str(source_path),
            feature_columns=["user_id"],
            apply_model=ApplyModelPayload(
                trained_model_id="trained-1",
                model_key=CollaborativeTopKRecommendationService.key,
                trained_model_artifact_path=fit_result.final_model_artifact_path or "",
            ),
            input_files=[
                ApplyInputFile(
                    absolute_path=str(apply_path),
                    file_name=apply_path.name,
                    source_kind="user_file",
                    dataset_id="apply-dataset",
                )
            ],
        ),
        tmp_path / "apply-task",
    )
    applied = pd.read_csv(apply_result.output_file_path)
    assert apply_result.source_dataset_ids == ["apply-dataset"]
    assert set(applied["user_id"]) == {"USER-01", "COLD-USER"}
    assert set(applied.loc[applied["user_id"] == "COLD-USER", "strategy"]) == {
        "popularity_cold_start"
    }
    assert set(
        applied.loc[applied["user_id"] == "USER-01", "recommended_item"]
    ).isdisjoint(retained.user_seen["USER-01"])
