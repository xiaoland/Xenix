from __future__ import annotations

import math

import pandas as pd

from .ml.recommendation_evidence import (
    RecommendationEngineConfig,
    fit_recommendation_engine,
    recompute_recommendation_evaluation,
)


def run_recommendation_packaged_smoke() -> None:
    """Exercise retained ranking, evaluation, and cold-start paths in the frozen app."""

    items = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")
    rows: list[dict[str, object]] = []
    for user_index in range(8):
        for offset in range(4):
            item = items[(user_index + offset) % len(items)]
            rows.append(
                {
                    "account": f"account-{user_index + 1}",
                    "product": item,
                    "rating": 4.0 + float((user_index + offset) % 2),
                    "event_time": pd.Timestamp("2026-01-01")
                    + pd.Timedelta(days=(user_index * 5) + offset),
                }
            )

    fitted = fit_recommendation_engine(
        pd.DataFrame(rows),
        user_column="account",
        item_column="product",
        rating_column="rating",
        time_column="event_time",
        source_dataset_snapshot_digest="packaged-recommendation-smoke",
        config=RecommendationEngineConfig(
            top_k=2,
            min_user_interactions=3,
            min_item_interactions=2,
            positive_rating_threshold=4.0,
        ),
    )
    recomputed = recompute_recommendation_evaluation(
        fitted.evaluation_analyzer,
        fitted.evaluation_context,
    )
    known_user = "account-1"
    requested = fitted.final_analyzer.recommend_users([known_user, "new-account"])
    known_rows = requested.loc[requested["user_id"] == known_user]
    cold_rows = requested.loc[requested["user_id"] == "new-account"]
    known_seen = fitted.final_analyzer.user_seen[known_user]
    metric_values = (
        recomputed.candidate.ndcg_at_k,
        recomputed.candidate.recall_at_k,
        recomputed.baseline.ndcg_at_k,
        recomputed.baseline.recall_at_k,
    )
    if (
        recomputed != fitted.facts
        or any(value is None or not math.isfinite(value) for value in metric_values)
        or recomputed.candidate.seen_item_violation_count != 0
        or len(known_rows.index) != 2
        or len(cold_rows.index) != 2
        or any(item in known_seen for item in known_rows["recommended_item"])
        or set(cold_rows["strategy"]) != {"popularity_cold_start"}
    ):
        raise RuntimeError("Packaged recommendation smoke failed.")
