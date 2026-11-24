from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..text_preparation import (
    TextPreparationQualityFacts,
    TextPreparationSpecification,
    TextVectorizationFacts,
)

_RANDOM_STATE = 42
_STABILITY_RUNS = 5
_RESAMPLE_FRACTION = 0.8
_HOLDOUT_FRACTION = 0.2
_GROUP_POLICY: Literal["business_template_connected_union.v1"] = "business_template_connected_union.v1"
_CLUSTER_QUALITY_POLICY: Literal["cosine_cluster_quality.v1"] = "cosine_cluster_quality.v1"
_CLUSTER_STABILITY_POLICY: Literal["connected_group_resample_80pct_5seed.v1"] = (
    "connected_group_resample_80pct_5seed.v1"
)
_TOPIC_SPLIT_POLICY: Literal["connected_group_hash_holdout.v1"] = "connected_group_hash_holdout.v1"
_TOPIC_QUALITY_POLICY: Literal["heldout_topic_quality.v1"] = "heldout_topic_quality.v1"
_TOPIC_STABILITY_POLICY: Literal["permutation_matched_topic_stability_5seed.v1"] = (
    "permutation_matched_topic_stability_5seed.v1"
)
_RETRIEVAL_POLICY: Literal["local_tfidf_self_excluding_top_k.v1"] = (
    "local_tfidf_self_excluding_top_k.v1"
)
_MAX_TERMS = 12


class _StrictFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SanitizedTermFact(_StrictFact):
    term: str = Field(min_length=2, max_length=48)
    weight: float = Field(ge=0.0)


class TextDiscoveryIsolationFacts(_StrictFact):
    policy_key: Literal["business_template_connected_union.v1"] = _GROUP_POLICY
    business_group_supplied: bool
    eligible_row_count: int = Field(ge=0)
    business_group_count: int = Field(ge=0)
    template_group_count: int = Field(ge=0)
    connected_group_count: int = Field(ge=0)
    near_duplicate_edge_count: int = Field(ge=0)
    partition_group_overlap_count: int = Field(default=0, ge=0)
    group_assignment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextClusterSizeFact(_StrictFact):
    cluster_label: int = Field(ge=1, le=100)
    row_count: int = Field(ge=1)
    share: float = Field(ge=0.0, le=1.0)


class TextClusterProfileFact(_StrictFact):
    cluster_label: int = Field(ge=1, le=100)
    top_terms: list[SanitizedTermFact] = Field(default_factory=list, max_length=_MAX_TERMS)


class TextClusteringQualityFacts(_StrictFact):
    policy_key: Literal["cosine_cluster_quality.v1"] = _CLUSTER_QUALITY_POLICY
    evaluated_row_count: int = Field(ge=2)
    requested_cluster_count: int = Field(ge=2, le=20)
    realized_cluster_count: int = Field(ge=1, le=20)
    cosine_silhouette: float | None = Field(default=None, ge=-1.0, le=1.0)
    degenerate_cluster_count: int = Field(ge=0)
    minimum_cluster_share: float = Field(ge=0.0, le=1.0)
    maximum_cluster_share: float = Field(ge=0.0, le=1.0)
    assignment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextClusteringStabilityFacts(_StrictFact):
    policy_key: Literal["connected_group_resample_80pct_5seed.v1"] = _CLUSTER_STABILITY_POLICY
    requested_run_count: int = Field(default=_STABILITY_RUNS, ge=1, le=_STABILITY_RUNS)
    successful_run_count: int = Field(ge=0, le=_STABILITY_RUNS)
    failed_run_count: int = Field(ge=0, le=_STABILITY_RUNS)
    sampling_fraction: float = Field(default=_RESAMPLE_FRACTION, ge=0.5, le=0.95)
    mean_adjusted_rand: float | None = Field(default=None, ge=-1.0, le=1.0)
    minimum_adjusted_rand: float | None = Field(default=None, ge=-1.0, le=1.0)
    resample_group_overlap_count: int = Field(default=0, ge=0)
    stable_label_mapping_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _run_counts_are_complete(self) -> TextClusteringStabilityFacts:
        if self.successful_run_count + self.failed_run_count != self.requested_run_count:
            raise ValueError("Clustering stability run counts must cover every requested run.")
        return self


class TextClusteringEvaluationFacts(_StrictFact):
    protocol_key: Literal["multilingual_text_clustering.v1"] = "multilingual_text_clustering.v1"
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    isolation: TextDiscoveryIsolationFacts
    vectorization: TextVectorizationFacts
    quality: TextClusteringQualityFacts
    stability: TextClusteringStabilityFacts
    sizes: list[TextClusterSizeFact] = Field(min_length=1, max_length=20)
    profiles: list[TextClusterProfileFact] = Field(min_length=1, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class TextClusteringApplyFacts(_StrictFact):
    protocol_key: Literal["multilingual_text_clustering_apply.v1"] = "multilingual_text_clustering_apply.v1"
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    vectorization: TextVectorizationFacts
    assigned_row_count: int = Field(ge=0)
    unassigned_row_count: int = Field(ge=0)
    stable_label_mapping_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextTopicSplitFacts(_StrictFact):
    policy_key: Literal["connected_group_hash_holdout.v1"] = _TOPIC_SPLIT_POLICY
    source_dataset_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligible_row_count: int = Field(ge=4)
    train_row_count: int = Field(ge=2)
    holdout_row_count: int = Field(ge=1)
    connected_group_count: int = Field(ge=2)
    train_group_count: int = Field(ge=1)
    holdout_group_count: int = Field(ge=1)
    train_membership_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_membership_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    group_overlap_count: int = Field(default=0, ge=0)


class TextTopicQualityFacts(_StrictFact):
    policy_key: Literal["heldout_topic_quality.v1"] = _TOPIC_QUALITY_POLICY
    topic_count: int = Field(ge=2, le=20)
    train_document_count: int = Field(ge=2)
    heldout_document_count: int = Field(ge=1)
    heldout_perplexity: float = Field(gt=0.0)
    mean_coherence: float = Field(ge=-1.0, le=1.0)
    term_diversity: float = Field(ge=0.0, le=1.0)
    dominant_topic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextTopicStabilityFacts(_StrictFact):
    policy_key: Literal["permutation_matched_topic_stability_5seed.v1"] = _TOPIC_STABILITY_POLICY
    requested_run_count: int = Field(default=_STABILITY_RUNS, ge=1, le=_STABILITY_RUNS)
    successful_run_count: int = Field(ge=0, le=_STABILITY_RUNS)
    failed_run_count: int = Field(ge=0, le=_STABILITY_RUNS)
    mean_matched_cosine: float | None = Field(default=None, ge=0.0, le=1.0)
    minimum_matched_cosine: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _run_counts_are_complete(self) -> TextTopicStabilityFacts:
        if self.successful_run_count + self.failed_run_count != self.requested_run_count:
            raise ValueError("Topic stability run counts must cover every requested run.")
        return self


class TextTopicPrevalenceFact(_StrictFact):
    topic_label: int = Field(ge=1, le=100)
    dominant_document_count: int = Field(ge=0)
    mean_prevalence: float = Field(ge=0.0, le=1.0)


class TextTopicProfileFact(_StrictFact):
    topic_label: int = Field(ge=1, le=100)
    top_terms: list[SanitizedTermFact] = Field(default_factory=list, max_length=_MAX_TERMS)


class TextTopicEvaluationFacts(_StrictFact):
    protocol_key: Literal["multilingual_topic_discovery.v1"] = "multilingual_topic_discovery.v1"
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    isolation: TextDiscoveryIsolationFacts
    vectorization: TextVectorizationFacts
    split: TextTopicSplitFacts
    quality: TextTopicQualityFacts
    stability: TextTopicStabilityFacts
    topic_label_identity_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    prevalence: list[TextTopicPrevalenceFact] = Field(min_length=2, max_length=20)
    profiles: list[TextTopicProfileFact] = Field(min_length=2, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class TextTopicApplyFacts(_StrictFact):
    protocol_key: Literal["multilingual_topic_discovery_apply.v1"] = "multilingual_topic_discovery_apply.v1"
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    vectorization: TextVectorizationFacts
    assigned_row_count: int = Field(ge=0)
    unassigned_row_count: int = Field(ge=0)
    topic_label_identity_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    topic_distribution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextRetrievalRankingFacts(_StrictFact):
    policy_key: Literal["binary_relevance_top_k.v1"] = "binary_relevance_top_k.v1"
    evaluated_query_count: int = Field(ge=1)
    recall_at_k: float = Field(ge=0.0, le=1.0)
    mrr_at_k: float = Field(ge=0.0, le=1.0)
    ndcg_at_k: float = Field(ge=0.0, le=1.0)


class TextRetrievalIndexDiagnosticFacts(_StrictFact):
    policy_key: Literal["local_tfidf_self_excluding_top_k.v1"] = _RETRIEVAL_POLICY
    indexed_document_count: int = Field(ge=1)
    inspected_query_count: int = Field(ge=0)
    query_with_results_count: int = Field(ge=0)
    requested_top_k: int = Field(ge=1, le=50)
    maximum_effective_top_k: int = Field(ge=0, le=50)
    result_row_count: int = Field(ge=0)
    self_match_violation_count: int = Field(default=0, ge=0)
    duplicate_match_violation_count: int = Field(default=0, ge=0)
    rank_sequence_violation_count: int = Field(default=0, ge=0)
    index_identity_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextRetrievalEvaluationFacts(_StrictFact):
    protocol_key: Literal["multilingual_local_retrieval.v1"] = "multilingual_local_retrieval.v1"
    mode: Literal["index_diagnostic", "relevance_evaluated"]
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    vectorization: TextVectorizationFacts
    diagnostics: TextRetrievalIndexDiagnosticFacts
    ranking: TextRetrievalRankingFacts | None = None
    limitations: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _ranking_requires_relevance_truth(self) -> TextRetrievalEvaluationFacts:
        if (self.mode == "relevance_evaluated") != (self.ranking is not None):
            raise ValueError("Retrieval ranking facts exist exactly when relevance truth is admitted.")
        return self


class TextRetrievalApplyFacts(_StrictFact):
    protocol_key: Literal["multilingual_local_retrieval_apply.v1"] = "multilingual_local_retrieval_apply.v1"
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    vectorization: TextVectorizationFacts
    diagnostics: TextRetrievalIndexDiagnosticFacts


@dataclass(frozen=True)
class PreparedDiscoveryCorpus:
    raw_texts: pd.Series
    prepared_texts: pd.Series
    source_positions: np.ndarray
    connected_groups: pd.Series
    preparation: TextPreparationQualityFacts
    isolation: TextDiscoveryIsolationFacts


@dataclass(frozen=True)
class TextClusterEvaluation:
    labels: np.ndarray
    facts: TextClusteringEvaluationFacts


@dataclass(frozen=True)
class TextClusterApplication:
    labels: list[int | None]
    facts: TextClusteringApplyFacts


@dataclass(frozen=True)
class TextTopicEvaluation:
    eligible_source_positions: np.ndarray
    distributions: np.ndarray
    facts: TextTopicEvaluationFacts


@dataclass(frozen=True)
class TextTopicApplication:
    distributions: list[list[float] | None]
    facts: TextTopicApplyFacts


@dataclass(frozen=True)
class RetrievalMatch:
    query_position: int
    matched_document_position: int
    rank: int
    similarity: float


@dataclass(frozen=True)
class TextRetrievalEvaluation:
    matches: tuple[RetrievalMatch, ...]
    facts: TextRetrievalEvaluationFacts


@dataclass(frozen=True)
class TextRetrievalApplication:
    matches: tuple[RetrievalMatch, ...]
    facts: TextRetrievalApplyFacts
