from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


EVALUATION_PROTOCOL = "recommendation_ranking.v1"
PREPARATION_POLICY = "explicit_rating_mean_duplicates.v1"
LATEST_HOLDOUT_POLICY = "latest_positive_per_user.v1"
HASH_HOLDOUT_POLICY = "deterministic_hash_positive_per_user.v1"
COLLABORATIVE_POLICY = "item_neighborhood_explicit_rating.v1"
POPULARITY_POLICY = "global_popularity_unseen.v1"


class RankingMetricUnavailableReason(StrEnum):
    NO_ELIGIBLE_USERS = "no_eligible_users"
    NO_CANDIDATE_ITEMS = "no_candidate_items"
    FEWER_THAN_TWO_RECOMMENDATIONS = "fewer_than_two_recommendations"


class _Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecommendationSplitFacts(_Fact):
    schema_version: int = 1
    policy_key: str
    source_dataset_snapshot_digest: str
    eligible_user_count: int = Field(ge=0)
    train_interaction_count: int = Field(ge=0)
    holdout_interaction_count: int = Field(ge=0)
    train_user_count: int = Field(ge=0)
    holdout_user_count: int = Field(ge=0)
    user_overlap_count: int = Field(ge=0)
    train_membership_digest: str
    holdout_membership_digest: str
    shared_truth_digest: str
    evaluation_scope: str = "per_user_positive_holdout"


class RecommendationPreparationFacts(_Fact):
    schema_version: int = 1
    policy_key: str = PREPARATION_POLICY
    source_row_count: int = Field(ge=0)
    admitted_interaction_count: int = Field(ge=0)
    dropped_missing_identity_count: int = Field(ge=0)
    dropped_non_finite_rating_count: int = Field(ge=0)
    collapsed_duplicate_row_count: int = Field(ge=0)
    user_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    positive_interaction_count: int = Field(ge=0)
    candidate_item_count: int = Field(ge=0)
    min_user_interactions: int = Field(ge=2)
    min_item_interactions: int = Field(ge=1)
    positive_rating_threshold: float
    time_column_present: bool
    preparation_digest: str


class RecommendationRankingMetrics(_Fact):
    policy_key: str
    top_k: int = Field(ge=1, le=50)
    evaluated_user_count: int = Field(ge=0)
    recommendation_count: int = Field(ge=0)
    short_list_user_count: int = Field(ge=0)
    ndcg_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    hit_rate_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    mrr_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    catalog_coverage_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_novelty_at_k: float | None = Field(default=None, ge=0.0)
    mean_intra_list_diversity_at_k: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    diversity_unavailable_reason: RankingMetricUnavailableReason | None = None
    seen_item_violation_count: int = Field(ge=0)
    ranking_digest: str


class RecommendationColdStartFacts(_Fact):
    policy_key: str = POPULARITY_POLICY
    known_user_strategy: str = COLLABORATIVE_POLICY
    cold_user_strategy: str = POPULARITY_POLICY
    cold_user_supported: bool = True
    cold_item_supported: bool = False
    limitations: list[str]


class RecommendationEvaluationFacts(_Fact):
    protocol: str = EVALUATION_PROTOCOL
    split: RecommendationSplitFacts
    preparation: RecommendationPreparationFacts
    candidate: RecommendationRankingMetrics
    baseline: RecommendationRankingMetrics
    cold_start: RecommendationColdStartFacts
    evidence_digest: str
    limitations: list[str]


class RecommendationHoldoutInteraction(_Fact):
    user_id: str
    item_id: str
    rating: float
    event_time: str | None = None


class RecommendationEvaluationContext(_Fact):
    context_key: str = "xenix.recommendation_evaluation_context.v1"
    split: RecommendationSplitFacts
    preparation: RecommendationPreparationFacts
    holdout_interactions: list[RecommendationHoldoutInteraction] = Field(min_length=1)


@dataclass(frozen=True)
class RecommendationEngineConfig:
    top_k: int
    min_user_interactions: int
    min_item_interactions: int
    positive_rating_threshold: float


@dataclass
class RetainedRecommendationAnalyzer:
    user_column: str
    item_column: str
    rating_column: str
    time_column: str | None
    config: RecommendationEngineConfig
    interactions: pd.DataFrame
    candidate_items: tuple[str, ...]
    popularity_order: tuple[str, ...]
    popularity_scores: dict[str, float]
    item_support: dict[str, int]
    user_seen: dict[str, frozenset[str]]
    user_ratings: dict[str, dict[str, float]]
    item_similarity: dict[tuple[str, str], float]

    def recommend_users(self, users: list[Any]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for raw_user in users:
            user = _normalize_identity(raw_user)
            if user is None:
                continue
            rows.extend(self._recommend_user(user))
        return pd.DataFrame(
            rows,
            columns=["user_id", "rank", "recommended_item", "score", "strategy"],
        )

    def _recommend_user(self, user: str) -> list[dict[str, Any]]:
        seen = self.user_seen.get(user, frozenset())
        is_cold = user not in self.user_seen
        personalized: list[tuple[str, float, int]] = []
        if not is_cold:
            ratings = self.user_ratings[user]
            for candidate in self.candidate_items:
                if candidate in seen:
                    continue
                numerator = 0.0
                denominator = 0.0
                for seen_item, rating in ratings.items():
                    similarity = self.item_similarity.get(
                        _item_pair(candidate, seen_item),
                        0.0,
                    )
                    if similarity <= 0.0:
                        continue
                    numerator += similarity * rating
                    denominator += abs(similarity)
                if denominator > 0.0:
                    personalized.append(
                        (
                            candidate,
                            numerator / denominator,
                            self.item_support[candidate],
                        )
                    )
        if not personalized:
            strategy = "popularity_cold_start" if is_cold else "popularity_fallback"
            ranked = [
                (
                    item,
                    self.popularity_scores[item],
                    strategy,
                )
                for item in self.popularity_order
                if item not in seen
            ]
        else:
            personalized.sort(key=lambda value: (-value[1], -value[2], value[0]))
            ranked = [
                (item, score, "personalized_collaborative")
                for item, score, _support in personalized
            ]
            scored_items = {item for item, _score, _strategy in ranked}
            ranked.extend(
                (
                    item,
                    self.popularity_scores[item],
                    "popularity_fallback",
                )
                for item in self.popularity_order
                if item not in seen and item not in scored_items
            )
        return [
            {
                "user_id": user,
                "rank": rank,
                "recommended_item": item,
                "score": float(score),
                "strategy": strategy,
            }
            for rank, (item, score, strategy) in enumerate(
                ranked[: self.config.top_k],
                start=1,
            )
        ]


@dataclass(frozen=True)
class RecommendationFitEvidence:
    evaluation_analyzer: RetainedRecommendationAnalyzer
    final_analyzer: RetainedRecommendationAnalyzer
    full_recommendations: pd.DataFrame
    evaluation_context: RecommendationEvaluationContext
    facts: RecommendationEvaluationFacts


@dataclass(frozen=True)
class _PreparedInteractions:
    interactions: pd.DataFrame
    facts_seed: dict[str, Any]


def fit_recommendation_engine(
    dataframe: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    time_column: str | None,
    source_dataset_snapshot_digest: str,
    config: RecommendationEngineConfig,
) -> RecommendationFitEvidence:
    prepared = prepare_explicit_ratings(
        dataframe,
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        time_column=time_column,
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        config=config,
    )
    train, holdout, split = split_positive_holdout(
        prepared.interactions,
        time_column=time_column,
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        config=config,
    )
    evaluation_analyzer = build_retained_analyzer(
        train,
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        time_column=time_column,
        config=config,
    )
    preparation = _finalize_preparation_facts(
        prepared.facts_seed,
        interactions=prepared.interactions,
        candidate_item_count=len(evaluation_analyzer.candidate_items),
        config=config,
        time_column_present=time_column is not None,
    )
    context = RecommendationEvaluationContext(
        split=split,
        preparation=preparation,
        holdout_interactions=[
            RecommendationHoldoutInteraction(
                user_id=str(row[user_column]),
                item_id=str(row[item_column]),
                rating=float(row[rating_column]),
                event_time=(
                    pd.Timestamp(row[time_column]).isoformat()
                    if time_column is not None
                    else None
                ),
            )
            for row in holdout.to_dict(orient="records")
        ],
    )
    facts = recompute_recommendation_evaluation(evaluation_analyzer, context)
    final_analyzer = build_retained_analyzer(
        prepared.interactions,
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        time_column=time_column,
        config=config,
    )
    full_recommendations = final_analyzer.recommend_users(sorted(final_analyzer.user_seen))
    return RecommendationFitEvidence(
        evaluation_analyzer=evaluation_analyzer,
        final_analyzer=final_analyzer,
        full_recommendations=full_recommendations,
        evaluation_context=context,
        facts=facts,
    )


def recompute_recommendation_evaluation(
    analyzer: RetainedRecommendationAnalyzer,
    context: RecommendationEvaluationContext,
) -> RecommendationEvaluationFacts:
    holdout = _holdout_frame(analyzer, context)
    recomputed_split = _build_split_facts(
        analyzer.interactions,
        holdout,
        user_column=analyzer.user_column,
        item_column=analyzer.item_column,
        rating_column=analyzer.rating_column,
        time_column=analyzer.time_column,
        policy_key=context.split.policy_key,
        source_dataset_snapshot_digest=context.split.source_dataset_snapshot_digest,
        config=analyzer.config,
    )
    if recomputed_split != context.split:
        raise ValueError(
            "Recommendation evaluation context does not match the retained evaluation analyzer."
        )
    if context.preparation.candidate_item_count != len(analyzer.candidate_items):
        raise ValueError(
            "Recommendation preparation facts do not match the retained candidate catalog."
        )
    truth = {
        str(row[analyzer.user_column]): {str(row[analyzer.item_column])}
        for row in holdout.to_dict(orient="records")
    }
    evaluation_users = sorted(truth)
    candidate_metrics = evaluate_rankings(
        analyzer.recommend_users(evaluation_users),
        truth=truth,
        analyzer=analyzer,
        policy_key=COLLABORATIVE_POLICY,
        top_k=analyzer.config.top_k,
    )
    baseline_metrics = evaluate_rankings(
        popularity_recommendations(
            analyzer,
            evaluation_users,
            top_k=analyzer.config.top_k,
        ),
        truth=truth,
        analyzer=analyzer,
        policy_key=POPULARITY_POLICY,
        top_k=analyzer.config.top_k,
    )
    cold_start = RecommendationColdStartFacts(
        limitations=[
            "Cold users receive deterministic popularity recommendations.",
            "Items absent from the retained training catalog cannot be recommended.",
            "Offline ranking evidence does not establish online causal uplift.",
        ]
    )
    limitations = [
        "Evaluation uses one admitted positive held-out item per eligible user.",
        "User and item values remain in local result datasets and are absent from evaluation facts.",
        "Offline ranking quality does not establish online causal uplift.",
    ]
    evidence_payload = {
        "protocol": EVALUATION_PROTOCOL,
        "split": recomputed_split.model_dump(mode="json"),
        "preparation": context.preparation.model_dump(mode="json"),
        "candidate": candidate_metrics.model_dump(mode="json"),
        "baseline": baseline_metrics.model_dump(mode="json"),
        "cold_start": cold_start.model_dump(mode="json"),
        "limitations": limitations,
    }
    return RecommendationEvaluationFacts(
        split=recomputed_split,
        preparation=context.preparation,
        candidate=candidate_metrics,
        baseline=baseline_metrics,
        cold_start=cold_start,
        evidence_digest=_digest(evidence_payload),
        limitations=limitations,
    )


def prepare_explicit_ratings(
    dataframe: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    time_column: str | None,
    source_dataset_snapshot_digest: str,
    config: RecommendationEngineConfig,
) -> _PreparedInteractions:
    columns = [user_column, item_column, rating_column]
    if time_column is not None:
        columns.append(time_column)
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Recommendation columns are missing: {', '.join(missing)}.")

    source_row_count = len(dataframe)
    working = dataframe.loc[:, columns].copy()
    normalized_users = working[user_column].map(_normalize_identity)
    normalized_items = working[item_column].map(_normalize_identity)
    missing_identity = normalized_users.isna() | normalized_items.isna()
    numeric_ratings = pd.to_numeric(working[rating_column], errors="coerce")
    non_finite_rating = ~np.isfinite(numeric_ratings.to_numpy(dtype=float, na_value=np.nan))
    admitted_mask = ~missing_identity & ~non_finite_rating
    dropped_missing_identity_count = int(missing_identity.sum())
    dropped_non_finite_rating_count = int((~missing_identity & non_finite_rating).sum())
    working = working.loc[admitted_mask].copy()
    working[user_column] = normalized_users.loc[admitted_mask].astype(str)
    working[item_column] = normalized_items.loc[admitted_mask].astype(str)
    working[rating_column] = numeric_ratings.loc[admitted_mask].astype(float)
    if working.empty:
        raise ValueError("Recommendation training requires valid explicit ratings.")

    if time_column is not None:
        parsed_time = pd.to_datetime(
            working[time_column],
            format="mixed",
            errors="coerce",
            utc=True,
        )
        if parsed_time.isna().any():
            raise ValueError(
                "The declared recommendation time column contains missing or invalid timestamps."
            )
        working[time_column] = parsed_time

    group_columns = [user_column, item_column]
    deduplicated_count = int(working.groupby(group_columns, sort=False).ngroups)
    collapsed_duplicate_row_count = len(working) - deduplicated_count
    aggregations: dict[str, Any] = {rating_column: "mean"}
    if time_column is not None:
        aggregations[time_column] = "max"
    working = working.groupby(group_columns, as_index=False, sort=True).agg(aggregations)
    working = working.sort_values(group_columns, kind="stable").reset_index(drop=True)
    if int((working[rating_column] >= config.positive_rating_threshold).sum()) == 0:
        raise ValueError("No rating meets the configured positive-rating threshold.")

    return _PreparedInteractions(
        interactions=working,
        facts_seed={
            "source_row_count": source_row_count,
            "dropped_missing_identity_count": dropped_missing_identity_count,
            "dropped_non_finite_rating_count": dropped_non_finite_rating_count,
            "collapsed_duplicate_row_count": collapsed_duplicate_row_count,
            "source_dataset_snapshot_digest": source_dataset_snapshot_digest,
            "user_column": user_column,
            "item_column": item_column,
            "rating_column": rating_column,
        },
    )


def split_positive_holdout(
    interactions: pd.DataFrame,
    *,
    time_column: str | None,
    source_dataset_snapshot_digest: str,
    config: RecommendationEngineConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, RecommendationSplitFacts]:
    user_column, item_column, rating_column = interactions.columns[:3]
    provisional_indices: list[int] = []
    for user, user_frame in interactions.groupby(user_column, sort=True):
        if len(user_frame) < config.min_user_interactions:
            continue
        positive = user_frame.loc[
            user_frame[rating_column] >= config.positive_rating_threshold
        ]
        if positive.empty:
            continue
        if time_column is not None:
            latest_time = positive[time_column].max()
            candidates = positive.loc[positive[time_column] == latest_time]
            selected = min(
                candidates.index,
                key=lambda index: _holdout_hash(
                    source_dataset_snapshot_digest,
                    str(user),
                    str(interactions.at[index, item_column]),
                ),
            )
        else:
            selected = min(
                positive.index,
                key=lambda index: _holdout_hash(
                    source_dataset_snapshot_digest,
                    str(user),
                    str(interactions.at[index, item_column]),
                ),
            )
        provisional_indices.append(int(selected))

    if not provisional_indices:
        raise ValueError("Recommendation evaluation requires at least one eligible user holdout.")
    provisional_train = interactions.drop(index=provisional_indices)
    provisional_support = provisional_train.groupby(item_column)[user_column].nunique()
    catalog = {
        str(item)
        for item, support in provisional_support.items()
        if int(support) >= config.min_item_interactions
    }
    holdout_indices = [
        index
        for index in provisional_indices
        if str(interactions.at[index, item_column]) in catalog
    ]
    if not holdout_indices:
        raise ValueError(
            "Recommendation evaluation has no held-out positive item in the training-side catalog."
        )
    train = interactions.drop(index=holdout_indices).reset_index(drop=True)
    holdout = interactions.loc[holdout_indices].sort_values(user_column).reset_index(drop=True)
    split_policy = LATEST_HOLDOUT_POLICY if time_column is not None else HASH_HOLDOUT_POLICY
    facts = _build_split_facts(
        train,
        holdout,
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        time_column=time_column,
        policy_key=split_policy,
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        config=config,
    )
    return train, holdout, facts


def _build_split_facts(
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    time_column: str | None,
    policy_key: str,
    source_dataset_snapshot_digest: str,
    config: RecommendationEngineConfig,
) -> RecommendationSplitFacts:
    eligible_users = set(holdout[user_column].astype(str))
    train_users = set(train[user_column].astype(str))
    train_digest = _interaction_digest(
        train,
        user_column,
        item_column,
        rating_column,
        time_column,
    )
    holdout_digest = _interaction_digest(
        holdout,
        user_column,
        item_column,
        rating_column,
        time_column,
    )
    return RecommendationSplitFacts(
        policy_key=policy_key,
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        eligible_user_count=len(eligible_users),
        train_interaction_count=len(train),
        holdout_interaction_count=len(holdout),
        train_user_count=len(train_users),
        holdout_user_count=len(eligible_users),
        user_overlap_count=len(eligible_users & train_users),
        train_membership_digest=train_digest,
        holdout_membership_digest=holdout_digest,
        shared_truth_digest=_digest(
            {
                "train": train_digest,
                "holdout": holdout_digest,
                "top_k": config.top_k,
            }
        ),
    )


def _holdout_frame(
    analyzer: RetainedRecommendationAnalyzer,
    context: RecommendationEvaluationContext,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for interaction in context.holdout_interactions:
        row: dict[str, Any] = {
            analyzer.user_column: interaction.user_id,
            analyzer.item_column: interaction.item_id,
            analyzer.rating_column: interaction.rating,
        }
        if analyzer.time_column is not None:
            if interaction.event_time is None:
                raise ValueError("Timed recommendation holdout is missing an event timestamp.")
            row[analyzer.time_column] = pd.Timestamp(interaction.event_time)
        elif interaction.event_time is not None:
            raise ValueError("Untimed recommendation holdout unexpectedly contains an event timestamp.")
        rows.append(row)
    return pd.DataFrame(rows)


def build_retained_analyzer(
    interactions: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    time_column: str | None,
    config: RecommendationEngineConfig,
) -> RetainedRecommendationAnalyzer:
    support_series = interactions.groupby(item_column)[user_column].nunique()
    item_support = {str(item): int(support) for item, support in support_series.items()}
    candidate_items = tuple(
        sorted(
            item
            for item, support in item_support.items()
            if support >= config.min_item_interactions
        )
    )
    if not candidate_items:
        raise ValueError("No item meets the configured recommendation support threshold.")
    candidate_set = set(candidate_items)
    candidate_frame = interactions.loc[interactions[item_column].isin(candidate_set)]
    mean_ratings = candidate_frame.groupby(item_column)[rating_column].mean().to_dict()
    maximum_support = max(item_support[item] for item in candidate_items)
    popularity_scores = {
        item: float(item_support[item] / maximum_support) for item in candidate_items
    }
    popularity_order = tuple(
        sorted(
            candidate_items,
            key=lambda item: (
                -item_support[item],
                -float(mean_ratings[item]),
                item,
            ),
        )
    )
    user_seen = {
        str(user): frozenset(str(item) for item in frame[item_column])
        for user, frame in interactions.groupby(user_column, sort=True)
    }
    user_ratings = {
        str(user): {
            str(row[item_column]): float(row[rating_column])
            for row in frame.to_dict(orient="records")
        }
        for user, frame in interactions.groupby(user_column, sort=True)
    }
    item_similarity = _build_item_similarity(
        interactions,
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        candidate_items=candidate_items,
    )
    return RetainedRecommendationAnalyzer(
        user_column=user_column,
        item_column=item_column,
        rating_column=rating_column,
        time_column=time_column,
        config=config,
        interactions=interactions.copy(),
        candidate_items=candidate_items,
        popularity_order=popularity_order,
        popularity_scores=popularity_scores,
        item_support=item_support,
        user_seen=user_seen,
        user_ratings=user_ratings,
        item_similarity=item_similarity,
    )


def popularity_recommendations(
    analyzer: RetainedRecommendationAnalyzer,
    users: list[str],
    *,
    top_k: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for user in users:
        seen = analyzer.user_seen.get(user, frozenset())
        ranked = [item for item in analyzer.popularity_order if item not in seen][:top_k]
        rows.extend(
            {
                "user_id": user,
                "rank": rank,
                "recommended_item": item,
                "score": analyzer.popularity_scores[item],
                "strategy": "popularity_baseline",
            }
            for rank, item in enumerate(ranked, start=1)
        )
    return pd.DataFrame(
        rows,
        columns=["user_id", "rank", "recommended_item", "score", "strategy"],
    )


def evaluate_rankings(
    rankings: pd.DataFrame,
    *,
    truth: dict[str, set[str]],
    analyzer: RetainedRecommendationAnalyzer,
    policy_key: str,
    top_k: int,
) -> RecommendationRankingMetrics:
    by_user = {
        str(user): frame.sort_values("rank", kind="stable")
        for user, frame in rankings.groupby("user_id", sort=True)
    }
    ndcg_values: list[float] = []
    recall_values: list[float] = []
    hit_values: list[float] = []
    reciprocal_ranks: list[float] = []
    recommended_items: set[str] = set()
    novelty_values: list[float] = []
    diversity_values: list[float] = []
    seen_violations = 0
    short_lists = 0
    total_users = max(1, len(analyzer.user_seen))
    for user in sorted(truth):
        frame = by_user.get(user)
        items = (
            [str(value) for value in frame["recommended_item"].tolist()[:top_k]]
            if frame is not None
            else []
        )
        if len(items) < top_k:
            short_lists += 1
        relevant = truth[user]
        hit_positions = [index + 1 for index, item in enumerate(items) if item in relevant]
        hit_count = len(hit_positions)
        hit_values.append(float(bool(hit_count)))
        recall_values.append(hit_count / len(relevant))
        reciprocal_ranks.append(1.0 / min(hit_positions) if hit_positions else 0.0)
        dcg = sum(1.0 / math.log2(position + 1) for position in hit_positions)
        ideal_hits = min(len(relevant), top_k)
        ideal_dcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))
        ndcg_values.append(dcg / ideal_dcg if ideal_dcg else 0.0)
        seen = analyzer.user_seen.get(user, frozenset())
        seen_violations += sum(item in seen for item in items)
        recommended_items.update(items)
        novelty_values.extend(
            -math.log2(max(1, analyzer.item_support[item]) / total_users)
            for item in items
        )
        if len(items) >= 2:
            distances = [
                1.0 - max(0.0, min(1.0, analyzer.item_similarity.get(_item_pair(left, right), 0.0)))
                for left_index, left in enumerate(items)
                for right in items[left_index + 1 :]
            ]
            if distances:
                diversity_values.append(float(np.mean(distances)))

    evaluated_user_count = len(truth)
    unavailable = (
        RankingMetricUnavailableReason.NO_ELIGIBLE_USERS
        if evaluated_user_count == 0
        else None
    )
    diversity_reason = (
        None
        if diversity_values
        else RankingMetricUnavailableReason.FEWER_THAN_TWO_RECOMMENDATIONS
    )
    return RecommendationRankingMetrics(
        policy_key=policy_key,
        top_k=top_k,
        evaluated_user_count=evaluated_user_count,
        recommendation_count=len(rankings),
        short_list_user_count=short_lists,
        ndcg_at_k=(float(np.mean(ndcg_values)) if unavailable is None else None),
        recall_at_k=(float(np.mean(recall_values)) if unavailable is None else None),
        hit_rate_at_k=(float(np.mean(hit_values)) if unavailable is None else None),
        mrr_at_k=(float(np.mean(reciprocal_ranks)) if unavailable is None else None),
        catalog_coverage_at_k=(
            len(recommended_items) / len(analyzer.candidate_items)
            if analyzer.candidate_items
            else None
        ),
        mean_novelty_at_k=(float(np.mean(novelty_values)) if novelty_values else None),
        mean_intra_list_diversity_at_k=(
            float(np.mean(diversity_values)) if diversity_values else None
        ),
        diversity_unavailable_reason=diversity_reason,
        seen_item_violation_count=seen_violations,
        ranking_digest=_ranking_digest(rankings),
    )


def _build_item_similarity(
    interactions: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    candidate_items: tuple[str, ...],
) -> dict[tuple[str, str], float]:
    pivot = interactions.pivot_table(
        index=user_column,
        columns=item_column,
        values=rating_column,
        aggfunc="mean",
    )
    centered = pivot.sub(pivot.mean(axis=1), axis=0)
    similarity: dict[tuple[str, str], float] = {}
    for left_index, left in enumerate(candidate_items):
        if left not in centered.columns:
            continue
        left_values = centered[left]
        for right in candidate_items[left_index + 1 :]:
            if right not in centered.columns:
                continue
            right_values = centered[right]
            common = left_values.notna() & right_values.notna()
            common_count = int(common.sum())
            if common_count < 2:
                value = 0.0
            else:
                left_common = left_values[common].to_numpy(dtype=float)
                right_common = right_values[common].to_numpy(dtype=float)
                denominator = float(np.linalg.norm(left_common) * np.linalg.norm(right_common))
                cosine = float(np.dot(left_common, right_common) / denominator) if denominator else 0.0
                value = max(0.0, cosine) * (common_count / (common_count + 5.0))
            similarity[_item_pair(left, right)] = value
    return similarity


def _finalize_preparation_facts(
    seed: dict[str, Any],
    *,
    interactions: pd.DataFrame,
    candidate_item_count: int,
    config: RecommendationEngineConfig,
    time_column_present: bool,
) -> RecommendationPreparationFacts:
    user_column = str(seed["user_column"])
    item_column = str(seed["item_column"])
    rating_column = str(seed["rating_column"])
    payload = {
        "policy_key": PREPARATION_POLICY,
        "source_dataset_snapshot_digest": seed["source_dataset_snapshot_digest"],
        "interaction_digest": _interaction_digest(
            interactions,
            user_column,
            item_column,
            rating_column,
            interactions.columns[3] if time_column_present else None,
        ),
        "config": {
            "min_user_interactions": config.min_user_interactions,
            "min_item_interactions": config.min_item_interactions,
            "positive_rating_threshold": config.positive_rating_threshold,
        },
    }
    return RecommendationPreparationFacts(
        source_row_count=int(seed["source_row_count"]),
        admitted_interaction_count=len(interactions),
        dropped_missing_identity_count=int(seed["dropped_missing_identity_count"]),
        dropped_non_finite_rating_count=int(seed["dropped_non_finite_rating_count"]),
        collapsed_duplicate_row_count=int(seed["collapsed_duplicate_row_count"]),
        user_count=int(interactions[user_column].nunique()),
        item_count=int(interactions[item_column].nunique()),
        positive_interaction_count=int(
            (interactions[rating_column] >= config.positive_rating_threshold).sum()
        ),
        candidate_item_count=candidate_item_count,
        min_user_interactions=config.min_user_interactions,
        min_item_interactions=config.min_item_interactions,
        positive_rating_threshold=config.positive_rating_threshold,
        time_column_present=time_column_present,
        preparation_digest=_digest(payload),
    )


def _interaction_digest(
    dataframe: pd.DataFrame,
    user_column: str,
    item_column: str,
    rating_column: str,
    time_column: str | None,
) -> str:
    values = []
    ordered = dataframe.sort_values([user_column, item_column], kind="stable")
    for row in ordered.to_dict(orient="records"):
        value: dict[str, Any] = {
            "user": str(row[user_column]),
            "item": str(row[item_column]),
            "rating": float(row[rating_column]).hex(),
        }
        if time_column is not None:
            value["time"] = pd.Timestamp(row[time_column]).isoformat()
        values.append(value)
    return _digest(values)


def _ranking_digest(rankings: pd.DataFrame) -> str:
    if rankings.empty:
        return _digest([])
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


def _normalize_identity(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    normalized = str(value).strip()
    return normalized or None


def _item_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _holdout_hash(source_digest: str, user: str, item: str) -> str:
    return hashlib.sha256(
        json.dumps(
            [source_digest, user, item],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
