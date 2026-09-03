from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from .digests import sha256_json


STABILITY_PROTOCOL = "subsample_80pct_5seed_ari.v1"
STABILITY_SEEDS = (104729, 130363, 155921, 181081, 205019)
NULL_PROTOCOL = "permuted_labels_preserve_sizes.v1"
NULL_SEEDS = tuple(3109 + index * 7919 for index in range(16))
EVIDENCE_PROTOCOL = "clustering_trustworthiness.v1"


class ClusteringMetricUnavailableReason(StrEnum):
    NO_EVALUATED_ROWS = "no_evaluated_rows"
    FEWER_THAN_TWO_CLUSTERS = "fewer_than_two_clusters"
    CLUSTER_PER_EVALUATED_ROW = "cluster_per_evaluated_row"
    INSUFFICIENT_STABILITY_OVERLAP = "insufficient_stability_overlap"


class ProfileValueSuppressionReason(StrEnum):
    HIGH_CARDINALITY_IDENTIFIER_LIKE = "high_cardinality_identifier_like"


class _Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClusteringQualityFacts(_Fact):
    silhouette: float | None = None
    calinski_harabasz: float | None = None
    davies_bouldin: float | None = None
    evaluated_row_count: int = Field(ge=0)
    noise_row_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    unavailable_reason: ClusteringMetricUnavailableReason | None = None


class ClusteringStabilityFacts(_Fact):
    protocol: str = STABILITY_PROTOCOL
    sample_fraction: float = Field(gt=0.0, le=1.0)
    seeds: list[int]
    run_count: int = Field(ge=0)
    comparison_count: int = Field(ge=0)
    mean_adjusted_rand_index: float | None = None
    minimum_adjusted_rand_index: float | None = None
    unavailable_reason: ClusteringMetricUnavailableReason | None = None
    digest: str


class ClusteringNullBaselineFacts(_Fact):
    protocol: str = NULL_PROTOCOL
    run_count: int = Field(ge=0)
    median_silhouette: float | None = None
    candidate_margin: float | None = None
    unavailable_reason: ClusteringMetricUnavailableReason | None = None
    digest: str


class ClusterSizeFact(_Fact):
    cluster_id: int
    row_count: int = Field(ge=0)
    proportion: float = Field(ge=0.0, le=1.0)
    is_noise: bool
    minimum_segment_warning: bool


class NumericClusterProfileFact(_Fact):
    feature: str
    non_missing_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


class CategoricalClusterProfileFact(_Fact):
    feature: str
    non_missing_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    top_value: str | None = None
    top_value_share: float | None = Field(default=None, ge=0.0, le=1.0)
    value_suppressed: bool = False
    suppression_reason: ProfileValueSuppressionReason | None = None


class ClusterProfileFact(_Fact):
    cluster_id: int
    row_count: int = Field(ge=0)
    numeric: list[NumericClusterProfileFact]
    categorical: list[CategoricalClusterProfileFact]


class ClusterLabelMapEntry(_Fact):
    raw_label: int
    display_label: int
    is_noise: bool


class ClusterLabelMapFacts(_Fact):
    protocol: str = "sorted_raw_labels_noise_minus_one.v1"
    entries: list[ClusterLabelMapEntry]
    digest: str


class ClusteringEvaluationFacts(_Fact):
    protocol: str = EVIDENCE_PROTOCOL
    quality: ClusteringQualityFacts
    stability: ClusteringStabilityFacts
    null_baseline: ClusteringNullBaselineFacts
    sizes: list[ClusterSizeFact]
    profiles: list[ClusterProfileFact]
    label_map: ClusterLabelMapFacts
    assignment_digest: str
    limitations: list[str]
    evidence_digest: str


def build_stable_label_mapping(raw_labels: Sequence[int] | np.ndarray) -> dict[int, int]:
    """Build the persisted raw-to-display map for one retained analyzer.

    Display labels are deliberately only stable inside a retained analyzer.  The
    ordering does not claim that display cluster 1 has the same meaning across
    separate fits.
    """

    labels = np.asarray(raw_labels, dtype=np.int64)
    distinct = sorted(int(value) for value in np.unique(labels))
    mapping: dict[int, int] = {}
    next_display = 1
    for raw_label in distinct:
        if raw_label == -1:
            mapping[raw_label] = -1
        else:
            mapping[raw_label] = next_display
            next_display += 1
    return mapping


def apply_label_mapping(
    raw_labels: Sequence[int] | np.ndarray,
    mapping: dict[int, int],
) -> np.ndarray:
    labels = np.asarray(raw_labels, dtype=np.int64)
    unknown = sorted(set(int(value) for value in np.unique(labels)) - set(mapping))
    if unknown:
        raise ValueError(
            "Predicted cluster labels were not present in the retained label map: "
            f"{unknown}."
        )
    return np.asarray([mapping[int(value)] for value in labels], dtype=np.int64)


def label_map_facts(mapping: dict[int, int]) -> ClusterLabelMapFacts:
    entries = [
        ClusterLabelMapEntry(
            raw_label=raw_label,
            display_label=display_label,
            is_noise=raw_label == -1,
        )
        for raw_label, display_label in sorted(mapping.items())
    ]
    return ClusterLabelMapFacts(entries=entries, digest=_digest([entry.model_dump() for entry in entries]))


def build_clustering_evidence(
    *,
    raw_features: pd.DataFrame,
    transformed_features: Any,
    display_labels: Sequence[int] | np.ndarray,
    label_mapping: dict[int, int],
    estimator_factory: Callable[[int], Any],
    stability_seeds: Sequence[int] = STABILITY_SEEDS,
    stability_sample_fraction: float = 0.8,
    null_seeds: Sequence[int] = NULL_SEEDS,
    minimum_segment_proportion: float = 0.05,
    max_profile_features: int = 20,
) -> ClusteringEvaluationFacts:
    """Recompute bounded clustering trust evidence from assignments and features."""

    labels = np.asarray(display_labels, dtype=np.int64)
    matrix = _as_dense_finite_matrix(transformed_features)
    if len(raw_features) != len(labels) or matrix.shape[0] != len(labels):
        raise ValueError("Raw features, transformed features, and labels must align by row.")

    quality = compute_quality(matrix, labels)
    stability = compute_stability(
        matrix,
        estimator_factory,
        seeds=stability_seeds,
        sample_fraction=stability_sample_fraction,
    )
    null_baseline = compute_null_baseline(matrix, labels, quality, seeds=null_seeds)
    sizes = compute_cluster_sizes(
        labels,
        minimum_segment_proportion=minimum_segment_proportion,
    )
    profiles, limitations = compute_original_scale_profiles(
        raw_features,
        labels,
        max_features=max_profile_features,
    )
    limitations.append(
        "Stability refits the model on five 80% subsamples in the retained prepared "
        "feature space; preprocessing is held fixed."
    )
    label_map = label_map_facts(label_mapping)
    assignment_digest = _digest([int(value) for value in labels])
    payload = {
        "protocol": EVIDENCE_PROTOCOL,
        "quality": quality.model_dump(mode="json"),
        "stability": stability.model_dump(mode="json"),
        "null_baseline": null_baseline.model_dump(mode="json"),
        "sizes": [fact.model_dump(mode="json") for fact in sizes],
        "profiles": [fact.model_dump(mode="json") for fact in profiles],
        "label_map": label_map.model_dump(mode="json"),
        "assignment_digest": assignment_digest,
        "limitations": limitations,
    }
    return ClusteringEvaluationFacts(
        quality=quality,
        stability=stability,
        null_baseline=null_baseline,
        sizes=sizes,
        profiles=profiles,
        label_map=label_map,
        assignment_digest=assignment_digest,
        limitations=limitations,
        evidence_digest=_digest(payload),
    )


def compute_quality(
    transformed_features: Any,
    display_labels: Sequence[int] | np.ndarray,
) -> ClusteringQualityFacts:
    matrix = _as_dense_finite_matrix(transformed_features)
    labels = np.asarray(display_labels, dtype=np.int64)
    evaluated_mask = labels != -1
    evaluated_matrix = matrix[evaluated_mask]
    evaluated_labels = labels[evaluated_mask]
    noise_count = int((~evaluated_mask).sum())
    cluster_count = int(len(np.unique(evaluated_labels)))
    evaluated_count = int(len(evaluated_labels))
    reason = _metric_unavailable_reason(evaluated_count, cluster_count)
    if reason is not None:
        return ClusteringQualityFacts(
            evaluated_row_count=evaluated_count,
            noise_row_count=noise_count,
            cluster_count=cluster_count,
            unavailable_reason=reason,
        )
    return ClusteringQualityFacts(
        silhouette=float(silhouette_score(evaluated_matrix, evaluated_labels)),
        calinski_harabasz=float(
            calinski_harabasz_score(evaluated_matrix, evaluated_labels)
        ),
        davies_bouldin=float(davies_bouldin_score(evaluated_matrix, evaluated_labels)),
        evaluated_row_count=evaluated_count,
        noise_row_count=noise_count,
        cluster_count=cluster_count,
    )


def compute_stability(
    transformed_features: Any,
    estimator_factory: Callable[[int], Any],
    *,
    seeds: Sequence[int] = STABILITY_SEEDS,
    sample_fraction: float = 0.8,
) -> ClusteringStabilityFacts:
    matrix = _as_dense_finite_matrix(transformed_features)
    row_count = matrix.shape[0]
    sample_size = min(row_count, max(2, int(np.floor(row_count * sample_fraction))))
    runs: list[tuple[np.ndarray, np.ndarray]] = []
    run_digests: list[dict[str, Any]] = []
    for seed in seeds:
        random = np.random.default_rng(seed)
        indices = np.sort(random.choice(row_count, size=sample_size, replace=False))
        estimator = estimator_factory(int(seed))
        labels = np.asarray(estimator.fit_predict(matrix[indices]), dtype=np.int64)
        runs.append((indices, labels))
        run_digests.append(
            {
                "seed": int(seed),
                "indices": _digest([int(value) for value in indices]),
                "labels": _digest([int(value) for value in labels]),
            }
        )

    agreements: list[float] = []
    for left_index in range(len(runs)):
        left_rows, left_labels = runs[left_index]
        for right_index in range(left_index + 1, len(runs)):
            right_rows, right_labels = runs[right_index]
            common, left_positions, right_positions = np.intersect1d(
                left_rows,
                right_rows,
                assume_unique=True,
                return_indices=True,
            )
            if len(common) < 2:
                continue
            agreements.append(
                float(
                    adjusted_rand_score(
                        left_labels[left_positions],
                        right_labels[right_positions],
                    )
                )
            )

    digest = _digest(
        {
            "protocol": STABILITY_PROTOCOL,
            "sample_fraction": sample_fraction,
            "runs": run_digests,
            "agreements": agreements,
        }
    )
    if not agreements:
        return ClusteringStabilityFacts(
            sample_fraction=sample_fraction,
            seeds=[int(seed) for seed in seeds],
            run_count=len(runs),
            comparison_count=0,
            unavailable_reason=(
                ClusteringMetricUnavailableReason.INSUFFICIENT_STABILITY_OVERLAP
            ),
            digest=digest,
        )
    return ClusteringStabilityFacts(
        sample_fraction=sample_fraction,
        seeds=[int(seed) for seed in seeds],
        run_count=len(runs),
        comparison_count=len(agreements),
        mean_adjusted_rand_index=float(np.mean(agreements)),
        minimum_adjusted_rand_index=float(np.min(agreements)),
        digest=digest,
    )


def compute_null_baseline(
    transformed_features: Any,
    display_labels: Sequence[int] | np.ndarray,
    quality: ClusteringQualityFacts | None = None,
    *,
    seeds: Sequence[int] = NULL_SEEDS,
) -> ClusteringNullBaselineFacts:
    matrix = _as_dense_finite_matrix(transformed_features)
    labels = np.asarray(display_labels, dtype=np.int64)
    candidate = quality or compute_quality(matrix, labels)
    if candidate.silhouette is None:
        return ClusteringNullBaselineFacts(
            run_count=0,
            unavailable_reason=candidate.unavailable_reason,
            digest=_digest({"protocol": NULL_PROTOCOL, "reason": candidate.unavailable_reason}),
        )

    scores: list[float] = []
    for seed in seeds:
        permuted = np.random.default_rng(seed).permutation(labels)
        permuted_quality = compute_quality(matrix, permuted)
        if permuted_quality.silhouette is not None:
            scores.append(permuted_quality.silhouette)
    if not scores:
        return ClusteringNullBaselineFacts(
            run_count=0,
            unavailable_reason=ClusteringMetricUnavailableReason.FEWER_THAN_TWO_CLUSTERS,
            digest=_digest({"protocol": NULL_PROTOCOL, "scores": []}),
        )
    median = float(np.median(scores))
    return ClusteringNullBaselineFacts(
        run_count=len(scores),
        median_silhouette=median,
        candidate_margin=float(candidate.silhouette - median),
        digest=_digest({"protocol": NULL_PROTOCOL, "seeds": list(seeds), "scores": scores}),
    )


def compute_cluster_sizes(
    display_labels: Sequence[int] | np.ndarray,
    *,
    minimum_segment_proportion: float = 0.05,
) -> list[ClusterSizeFact]:
    labels = np.asarray(display_labels, dtype=np.int64)
    row_count = len(labels)
    facts: list[ClusterSizeFact] = []
    for cluster_id in sorted(int(value) for value in np.unique(labels)):
        count = int((labels == cluster_id).sum())
        proportion = count / row_count if row_count else 0.0
        facts.append(
            ClusterSizeFact(
                cluster_id=cluster_id,
                row_count=count,
                proportion=proportion,
                is_noise=cluster_id == -1,
                minimum_segment_warning=(
                    cluster_id != -1 and proportion < minimum_segment_proportion
                ),
            )
        )
    return facts


def compute_original_scale_profiles(
    raw_features: pd.DataFrame,
    display_labels: Sequence[int] | np.ndarray,
    *,
    max_features: int = 20,
) -> tuple[list[ClusterProfileFact], list[str]]:
    if max_features < 1:
        raise ValueError("max_features must be positive.")
    labels = np.asarray(display_labels, dtype=np.int64)
    if len(raw_features) != len(labels):
        raise ValueError("Raw features and labels must align by row.")
    selected_columns = list(raw_features.columns[:max_features])
    suppressed_categorical_features = {
        column
        for column in selected_columns
        if _is_identifier_like_categorical(raw_features[column])
    }
    limitations = [
        "Profiles are descriptive aggregates and do not establish external or causal validity.",
        "Display labels are stable only inside this retained analyzer, not across separate fits.",
    ]
    if len(raw_features.columns) > max_features:
        limitations.append(
            f"Profiles are bounded to the first {max_features} selected feature columns."
        )
    if suppressed_categorical_features:
        limitations.append(
            "Top values are suppressed for high-cardinality identifier-like categorical "
            "features: "
            + ", ".join(str(column) for column in sorted(suppressed_categorical_features))
            + "."
        )

    profiles: list[ClusterProfileFact] = []
    for cluster_id in sorted(int(value) for value in np.unique(labels)):
        cluster_frame = raw_features.loc[labels == cluster_id, selected_columns]
        numeric: list[NumericClusterProfileFact] = []
        categorical: list[CategoricalClusterProfileFact] = []
        for column in selected_columns:
            series = cluster_frame[column]
            missing_count = int(series.isna().sum())
            non_missing = series.dropna()
            if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(
                series.dtype
            ):
                numeric.append(
                    NumericClusterProfileFact(
                        feature=str(column),
                        non_missing_count=int(len(non_missing)),
                        missing_count=missing_count,
                        median=_optional_float(non_missing.median()),
                        q1=_optional_float(non_missing.quantile(0.25)),
                        q3=_optional_float(non_missing.quantile(0.75)),
                    )
                )
            else:
                value_counts = non_missing.astype(str).value_counts(dropna=False)
                value_suppressed = column in suppressed_categorical_features
                top_value = (
                    None
                    if value_suppressed or value_counts.empty
                    else str(value_counts.index[0])
                )
                top_share = None
                if not value_suppressed and len(non_missing):
                    top_share = float(value_counts.iloc[0] / len(non_missing))
                categorical.append(
                    CategoricalClusterProfileFact(
                        feature=str(column),
                        non_missing_count=int(len(non_missing)),
                        missing_count=missing_count,
                        distinct_count=int(non_missing.nunique()),
                        top_value=top_value,
                        top_value_share=top_share,
                        value_suppressed=value_suppressed,
                        suppression_reason=(
                            ProfileValueSuppressionReason.HIGH_CARDINALITY_IDENTIFIER_LIKE
                            if value_suppressed
                            else None
                        ),
                    )
                )
        profiles.append(
            ClusterProfileFact(
                cluster_id=cluster_id,
                row_count=int(len(cluster_frame)),
                numeric=numeric,
                categorical=categorical,
            )
        )
    return profiles, limitations


def _is_identifier_like_categorical(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(
        series.dtype
    ):
        return False
    non_missing = series.dropna()
    if len(non_missing) == 0:
        return False
    distinct_count = int(non_missing.nunique())
    return distinct_count > 20 and distinct_count / len(non_missing) > 0.5


def _metric_unavailable_reason(
    evaluated_count: int,
    cluster_count: int,
) -> ClusteringMetricUnavailableReason | None:
    if evaluated_count == 0:
        return ClusteringMetricUnavailableReason.NO_EVALUATED_ROWS
    if cluster_count < 2:
        return ClusteringMetricUnavailableReason.FEWER_THAN_TWO_CLUSTERS
    if cluster_count >= evaluated_count:
        return ClusteringMetricUnavailableReason.CLUSTER_PER_EVALUATED_ROW
    return None


def _as_dense_finite_matrix(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError("Transformed features must be a two-dimensional matrix.")
    if not np.isfinite(matrix).all():
        raise ValueError("Transformed features must contain only finite values.")
    return matrix


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _digest(payload: Any) -> str:
    return sha256_json(payload, default=str)
