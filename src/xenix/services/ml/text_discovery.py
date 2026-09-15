from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Literal, Sequence, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.optimize import linear_sum_assignment
from scipy.sparse import csr_matrix
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

from ...exceptions import ValidationError
from .digests import prediction_digest, sha256_json
from .text_preparation import (
    PreparedTextCorpus,
    TextPreparationQualityFacts,
    TextPreparationSpecification,
    TextPreparer,
    TextVectorizationFacts,
    build_text_vectorization_facts,
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

_URL_OR_EMAIL_RE = re.compile(r"(?i)(?:https?://|www\.|\b[^\s@]+@[^\s@]+\.[^\s@]+\b)")
_LONG_NUMBER_RE = re.compile(r"\d{5,}")
_OPAQUE_IDENTIFIER_RE = re.compile(r"(?i)^(?:[a-z]*\d[a-z\d_-]{5,}|[a-f\d]{12,}|\w+[_-]\w+[_-]\w+)$")


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


def prepare_discovery_corpus(
    dataframe: pd.DataFrame,
    *,
    text_column: str,
    business_group_column: str | None,
    preparer: TextPreparer,
    minimum_rows: int,
) -> PreparedDiscoveryCorpus:
    required = [text_column]
    if business_group_column is not None:
        required.append(business_group_column)
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValidationError(f"Text discovery columns are missing: {', '.join(missing)}.")
    if len(set(required)) != len(required):
        raise ValidationError("Text and optional business group columns must be distinct.")
    corpus = preparer.prepare_series(dataframe[text_column])
    eligible_mask = corpus.prepared_texts.ne("")
    source_positions = np.flatnonzero(eligible_mask.to_numpy(dtype=bool))
    if len(source_positions) < minimum_rows:
        raise ValidationError(f"Text discovery requires at least {minimum_rows} non-empty prepared rows.")
    eligible_corpus = _subset_corpus(corpus, source_positions)
    business_values = (
        dataframe.loc[eligible_mask, business_group_column].reset_index(drop=True)
        if business_group_column is not None
        else pd.Series([None] * len(source_positions), dtype="object")
    )
    connected, template_count, near_edges, business_count = _connected_discovery_groups(
        eligible_corpus,
        business_values,
    )
    preparation = corpus.quality_facts.model_copy(update={"eligible_row_count": len(source_positions)})
    isolation = TextDiscoveryIsolationFacts(
        business_group_supplied=business_group_column is not None,
        eligible_row_count=len(source_positions),
        business_group_count=business_count,
        template_group_count=template_count,
        connected_group_count=int(connected.nunique(dropna=False)),
        near_duplicate_edge_count=near_edges,
        group_assignment_digest=_digest_values(connected.astype(str).tolist()),
    )
    return PreparedDiscoveryCorpus(
        raw_texts=dataframe.loc[eligible_mask, text_column].astype("string").fillna("").reset_index(drop=True),
        prepared_texts=corpus.prepared_texts.loc[eligible_mask].reset_index(drop=True),
        source_positions=source_positions,
        connected_groups=connected,
        preparation=preparation,
        isolation=isolation,
    )


class MultilingualTextClusterer:
    def __init__(
        self,
        *,
        preparer: TextPreparer,
        n_clusters: int,
        max_features: int,
        displayed_term_count: int,
    ) -> None:
        self.preparer = preparer
        self.n_clusters = n_clusters
        self.max_features = max_features
        self.displayed_term_count = displayed_term_count

    def fit(self, prepared: PreparedDiscoveryCorpus) -> MultilingualTextClusterer:
        if len(prepared.prepared_texts.index) <= self.n_clusters:
            raise ValidationError("Text clustering requires more eligible rows than requested clusters.")
        self.vectorizer = _tfidf(self.max_features, self.preparer.ngram_max)
        try:
            matrix = self.vectorizer.fit_transform(prepared.prepared_texts.tolist())
        except ValueError as exc:
            raise ValidationError(f"Text clustering could not fit a TF-IDF vocabulary: {exc}") from exc
        self.model = KMeans(n_clusters=self.n_clusters, n_init=10, max_iter=300, random_state=_RANDOM_STATE)
        raw_labels = self.model.fit_predict(matrix)
        self.raw_to_stable_label = _stable_component_labels(
            self.model.cluster_centers_, self.vectorizer.get_feature_names_out()
        )
        self.fit_vectorization = build_text_vectorization_facts(
            self.vectorizer, prepared.prepared_texts, fit_row_count=len(prepared.prepared_texts.index)
        )
        self.text_column: str | None = None
        self.group_column: str | None = None
        self._fit_assignment_digest = prediction_digest(_map_labels(raw_labels, self.raw_to_stable_label))
        return self

    def evaluate(self, prepared: PreparedDiscoveryCorpus) -> TextClusterEvaluation:
        matrix = self.vectorizer.transform(prepared.prepared_texts.tolist())
        raw_labels = np.asarray(self.model.predict(matrix), dtype=int)
        labels = _map_labels(raw_labels, self.raw_to_stable_label)
        counts = {int(label): int(np.sum(labels == label)) for label in sorted(set(labels.tolist()))}
        sizes = [
            TextClusterSizeFact(cluster_label=label, row_count=count, share=count / len(labels))
            for label, count in counts.items()
        ]
        silhouette = _safe_cosine_silhouette(matrix, labels)
        shares = [fact.share for fact in sizes]
        quality = TextClusteringQualityFacts(
            evaluated_row_count=len(labels),
            requested_cluster_count=self.n_clusters,
            realized_cluster_count=len(counts),
            cosine_silhouette=silhouette,
            degenerate_cluster_count=sum(fact.row_count < 2 or fact.share < 0.02 for fact in sizes),
            minimum_cluster_share=min(shares),
            maximum_cluster_share=max(shares),
            assignment_digest=prediction_digest(labels),
        )
        profiles = cast(
            list[TextClusterProfileFact],
            _component_profiles(
            self.model.cluster_centers_,
            self.vectorizer.get_feature_names_out(),
            self.raw_to_stable_label,
            self.displayed_term_count,
                profile_type="cluster",
            ),
        )
        stability = _cluster_stability(
            matrix,
            prepared.connected_groups,
            base_labels=labels,
            n_clusters=self.n_clusters,
            mapping_digest=_json_digest(self.raw_to_stable_label),
        )
        limitations: list[str] = ["Clusters are exploratory structure, not observed business truth."]
        if quality.degenerate_cluster_count:
            limitations.append("One or more clusters are very small or singleton clusters.")
        if any(len(profile.top_terms) < self.displayed_term_count for profile in profiles):
            limitations.append("Unsafe or identifier-like cluster terms were suppressed.")
        return TextClusterEvaluation(
            labels=labels,
            facts=TextClusteringEvaluationFacts(
                specification=self.preparer.specification,
                preparation=prepared.preparation,
                isolation=prepared.isolation,
                vectorization=build_text_vectorization_facts(
                    self.vectorizer,
                    prepared.prepared_texts,
                    fit_row_count=self.fit_vectorization.fit_row_count,
                ),
                quality=quality,
                stability=stability,
                sizes=sizes,
                profiles=profiles,
                limitations=limitations,
            ),
        )

    def apply(self, texts: pd.Series) -> TextClusterApplication:
        corpus = self.preparer.prepare_series(_as_text_series(texts))
        eligible = corpus.prepared_texts.ne("")
        labels: list[int | None] = [None] * len(corpus.prepared_texts.index)
        if eligible.any():
            raw = self.model.predict(self.vectorizer.transform(corpus.prepared_texts.loc[eligible].tolist()))
            stable = _map_labels(np.asarray(raw, dtype=int), self.raw_to_stable_label)
            for position, value in zip(np.flatnonzero(eligible.to_numpy(dtype=bool)), stable, strict=True):
                labels[int(position)] = int(value)
        facts = TextClusteringApplyFacts(
            specification=self.preparer.specification,
            preparation=corpus.quality_facts,
            vectorization=build_text_vectorization_facts(
                self.vectorizer, corpus.prepared_texts, fit_row_count=self.fit_vectorization.fit_row_count
            ),
            assigned_row_count=sum(value is not None for value in labels),
            unassigned_row_count=sum(value is None for value in labels),
            stable_label_mapping_digest=_json_digest(self.raw_to_stable_label),
            assignment_digest=prediction_digest(labels),
        )
        return TextClusterApplication(labels=labels, facts=facts)


class MultilingualTopicDiscoverer:
    def __init__(
        self,
        *,
        preparer: TextPreparer,
        topic_count: int,
        max_features: int,
        displayed_term_count: int,
    ) -> None:
        self.preparer = preparer
        self.topic_count = topic_count
        self.max_features = max_features
        self.displayed_term_count = displayed_term_count
        self.label_identity_digest: str = ""

    def fit_evaluation(
        self,
        prepared: PreparedDiscoveryCorpus,
        *,
        source_dataset_snapshot_digest: str,
    ) -> TextTopicEvaluation:
        train, holdout, split = _topic_group_holdout(
            prepared.connected_groups,
            source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        )
        self.vectorizer = _counts(self.max_features, self.preparer.ngram_max)
        try:
            train_matrix = self.vectorizer.fit_transform(prepared.prepared_texts.iloc[train].tolist())
        except ValueError as exc:
            raise ValidationError(f"Topic discovery could not fit a training-only vocabulary: {exc}") from exc
        self.model = LatentDirichletAllocation(
            n_components=self.topic_count,
            max_iter=30,
            learning_method="batch",
            random_state=_RANDOM_STATE,
        )
        self.model.fit(train_matrix)
        self.raw_to_stable_label = _stable_component_labels(
            self.model.components_, self.vectorizer.get_feature_names_out()
        )
        self.fit_vectorization = build_text_vectorization_facts(
            self.vectorizer,
            prepared.prepared_texts.iloc[train].reset_index(drop=True),
            fit_row_count=len(train),
        )
        self.text_column: str | None = None
        self.group_column: str | None = None
        return self._evaluation(prepared, train=train, holdout=holdout, split=split)

    def fit_all(
        self,
        prepared: PreparedDiscoveryCorpus,
        *,
        evaluation_reference: MultilingualTopicDiscoverer,
    ) -> MultilingualTopicDiscoverer:
        self.vectorizer = evaluation_reference.vectorizer
        matrix = self.vectorizer.transform(prepared.prepared_texts.tolist())
        self.model = LatentDirichletAllocation(
            n_components=self.topic_count,
            max_iter=30,
            learning_method="batch",
            random_state=_RANDOM_STATE,
        )
        self.model.fit(matrix)
        similarity = cosine_similarity(
            _row_normalize(evaluation_reference.model.components_),
            _row_normalize(self.model.components_),
        )
        evaluation_rows, full_columns = linear_sum_assignment(-similarity)
        self.raw_to_stable_label = {
            int(full_raw): evaluation_reference.raw_to_stable_label[int(evaluation_raw)]
            for evaluation_raw, full_raw in zip(evaluation_rows, full_columns, strict=True)
        }
        self.label_identity_digest = evaluation_reference.label_identity_digest
        self.fit_vectorization = build_text_vectorization_facts(
            self.vectorizer,
            prepared.prepared_texts,
            fit_row_count=evaluation_reference.fit_vectorization.fit_row_count,
        )
        return self

    def recompute_evaluation(
        self,
        prepared: PreparedDiscoveryCorpus,
        *,
        source_dataset_snapshot_digest: str,
    ) -> TextTopicEvaluation:
        train, holdout, split = _topic_group_holdout(
            prepared.connected_groups,
            source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        )
        return self._evaluation(prepared, train=train, holdout=holdout, split=split)

    def _evaluation(
        self,
        prepared: PreparedDiscoveryCorpus,
        *,
        train: np.ndarray,
        holdout: np.ndarray,
        split: TextTopicSplitFacts,
    ) -> TextTopicEvaluation:
        train_matrix = self.vectorizer.transform(prepared.prepared_texts.iloc[train].tolist())
        holdout_matrix = self.vectorizer.transform(prepared.prepared_texts.iloc[holdout].tolist())
        distributions = np.asarray(self.model.transform(holdout_matrix), dtype=float)
        stable_distributions = _stable_distribution_columns(distributions, self.raw_to_stable_label)
        dominant = stable_distributions.argmax(axis=1) + 1
        profiles = cast(
            list[TextTopicProfileFact],
            _component_profiles(
            self.model.components_,
            self.vectorizer.get_feature_names_out(),
            self.raw_to_stable_label,
            self.displayed_term_count,
                profile_type="topic",
            ),
        )
        self.label_identity_digest = _topic_profile_identity_digest(profiles)
        top_indexes = _top_feature_indexes(self.model.components_, self.displayed_term_count)
        quality = TextTopicQualityFacts(
            topic_count=self.topic_count,
            train_document_count=len(train),
            heldout_document_count=len(holdout),
            heldout_perplexity=float(self.model.perplexity(holdout_matrix)),
            mean_coherence=_mean_umass_coherence(train_matrix, top_indexes),
            term_diversity=_term_diversity(top_indexes),
            dominant_topic_digest=prediction_digest(dominant),
        )
        prevalence = [
            TextTopicPrevalenceFact(
                topic_label=label,
                dominant_document_count=int(np.sum(dominant == label)),
                mean_prevalence=float(stable_distributions[:, label - 1].mean()),
            )
            for label in range(1, self.topic_count + 1)
        ]
        stability = _topic_stability(train_matrix, self.model.components_, self.topic_count)
        isolation = prepared.isolation.model_copy(update={"partition_group_overlap_count": split.group_overlap_count})
        limitations = ["Topics are exploratory structure, not observed business truth."]
        if any(len(profile.top_terms) < self.displayed_term_count for profile in profiles):
            limitations.append("Unsafe or identifier-like topic terms were suppressed.")
        return TextTopicEvaluation(
            eligible_source_positions=prepared.source_positions[holdout],
            distributions=stable_distributions,
            facts=TextTopicEvaluationFacts(
                specification=self.preparer.specification,
                preparation=prepared.preparation,
                isolation=isolation,
                vectorization=build_text_vectorization_facts(
                    self.vectorizer,
                    prepared.prepared_texts.iloc[holdout].reset_index(drop=True),
                    fit_row_count=self.fit_vectorization.fit_row_count,
                ),
                split=split,
                quality=quality,
                stability=stability,
                topic_label_identity_digest=self.label_identity_digest,
                prevalence=prevalence,
                profiles=profiles,
                limitations=limitations,
            ),
        )

    def apply(self, texts: pd.Series) -> TextTopicApplication:
        corpus = self.preparer.prepare_series(_as_text_series(texts))
        eligible = corpus.prepared_texts.ne("")
        rows: list[list[float] | None] = [None] * len(corpus.prepared_texts.index)
        if eligible.any():
            matrix = self.vectorizer.transform(corpus.prepared_texts.loc[eligible].tolist())
            stable = _stable_distribution_columns(self.model.transform(matrix), self.raw_to_stable_label)
            for position, values in zip(np.flatnonzero(eligible.to_numpy(dtype=bool)), stable, strict=True):
                rows[int(position)] = [float(value) for value in values]
        facts = TextTopicApplyFacts(
            specification=self.preparer.specification,
            preparation=corpus.quality_facts,
            vectorization=build_text_vectorization_facts(
                self.vectorizer, corpus.prepared_texts, fit_row_count=self.fit_vectorization.fit_row_count
            ),
            assigned_row_count=sum(value is not None for value in rows),
            unassigned_row_count=sum(value is None for value in rows),
            topic_label_identity_digest=self.label_identity_digest,
            topic_distribution_digest=prediction_digest(rows),
        )
        return TextTopicApplication(distributions=rows, facts=facts)


class MultilingualTextRetriever:
    def __init__(
        self,
        *,
        preparer: TextPreparer,
        max_features: int,
        top_k: int,
        minimum_similarity: float,
    ) -> None:
        self.preparer = preparer
        self.max_features = max_features
        self.top_k = top_k
        self.minimum_similarity = minimum_similarity

    def fit(
        self,
        prepared: PreparedDiscoveryCorpus,
        *,
        document_ids: pd.Series | None,
        relevance_groups: pd.Series | None,
    ) -> MultilingualTextRetriever:
        count = len(prepared.prepared_texts.index)
        if document_ids is None:
            ids = pd.Series([f"row-{position + 1}" for position in prepared.source_positions], dtype="string")
            self.document_id_supplied = False
        else:
            ids = _validate_identity_series(document_ids, "document_id", count)
            self.document_id_supplied = True
        if ids.duplicated().any():
            raise ValidationError("Retrieval document IDs must be unique among eligible rows.")
        if relevance_groups is None:
            groups = None
        else:
            groups = _validate_identity_series(relevance_groups, "relevance_group", count)
            if groups.nunique(dropna=False) < 1:
                raise ValidationError("Retrieval relevance truth must contain at least one non-empty group.")
        self.vectorizer = _tfidf(self.max_features, self.preparer.ngram_max)
        try:
            self.matrix = csr_matrix(self.vectorizer.fit_transform(prepared.prepared_texts.tolist()))
        except ValueError as exc:
            raise ValidationError(f"Text retrieval could not fit a TF-IDF vocabulary: {exc}") from exc
        self.document_ids: tuple[str, ...] = tuple(str(value) for value in ids.tolist())
        self.document_texts: tuple[str, ...] = tuple(str(value) for value in prepared.raw_texts.tolist())
        self.document_identity_hashes = tuple(_sha256(value) for value in self.document_ids)
        self.relevance_group_hashes = (
            tuple(_sha256(value) for value in groups.astype(str).tolist()) if groups is not None else None
        )
        self.fit_vectorization = build_text_vectorization_facts(
            self.vectorizer, prepared.prepared_texts, fit_row_count=count
        )
        self.text_column: str | None = None
        self.document_id_column: str | None = None
        self.relevance_group_column: str | None = None
        return self

    def evaluate(self, prepared: PreparedDiscoveryCorpus) -> TextRetrievalEvaluation:
        if len(prepared.prepared_texts.index) != len(self.document_ids):
            raise ValidationError("Retrieval evaluation source membership no longer matches the retained index.")
        matches = self._rank(
            self.matrix,
            query_identity_hashes=self.document_identity_hashes,
            exclude_known_self=True,
        )
        diagnostics = self._diagnostics(
            matches,
            query_count=len(self.document_ids),
            query_identity_hashes=self.document_identity_hashes,
        )
        ranking = _ranking_facts(matches, self.relevance_group_hashes, self.top_k)
        mode: Literal["index_diagnostic", "relevance_evaluated"] = (
            "relevance_evaluated" if ranking is not None else "index_diagnostic"
        )
        limitations = [] if ranking is not None else [
            "No relevance-group truth was admitted; semantic relevance metrics are intentionally absent."
        ]
        return TextRetrievalEvaluation(
            matches=matches,
            facts=TextRetrievalEvaluationFacts(
                mode=mode,
                specification=self.preparer.specification,
                preparation=prepared.preparation,
                vectorization=build_text_vectorization_facts(
                    self.vectorizer,
                    prepared.prepared_texts,
                    fit_row_count=self.fit_vectorization.fit_row_count,
                ),
                diagnostics=diagnostics,
                ranking=ranking,
                limitations=limitations,
            ),
        )

    def apply(self, texts: pd.Series, *, document_ids: pd.Series | None = None) -> TextRetrievalApplication:
        corpus = self.preparer.prepare_series(_as_text_series(texts))
        eligible = corpus.prepared_texts.ne("")
        eligible_texts = corpus.prepared_texts.loc[eligible].reset_index(drop=True)
        query_matrix = self.vectorizer.transform(eligible_texts.tolist())
        query_hashes: tuple[str, ...] | None = None
        if document_ids is not None:
            normalized = _validate_identity_series(document_ids, "document_id", len(corpus.prepared_texts.index))
            query_hashes = tuple(_sha256(value) for value in normalized.loc[eligible].astype(str).tolist())
        eligible_matches = self._rank(
            query_matrix,
            query_identity_hashes=query_hashes,
            exclude_known_self=query_hashes is not None,
        )
        positions = np.flatnonzero(eligible.to_numpy(dtype=bool)).tolist()
        matches = tuple(
            RetrievalMatch(
                query_position=int(positions[item.query_position]),
                matched_document_position=item.matched_document_position,
                rank=item.rank,
                similarity=item.similarity,
            )
            for item in eligible_matches
        )
        facts = TextRetrievalApplyFacts(
            specification=self.preparer.specification,
            preparation=corpus.quality_facts,
            vectorization=build_text_vectorization_facts(
                self.vectorizer, corpus.prepared_texts, fit_row_count=self.fit_vectorization.fit_row_count
            ),
            diagnostics=self._diagnostics(
                matches,
                query_count=len(corpus.prepared_texts.index),
                query_identity_hashes=query_hashes,
            ),
        )
        return TextRetrievalApplication(matches=matches, facts=facts)

    def matched_document_id(self, position: int) -> str:
        return self.document_ids[position]

    def matched_document_text(self, position: int) -> str:
        return self.document_texts[position]

    def _rank(
        self,
        query_matrix: Any,
        *,
        query_identity_hashes: Sequence[str] | None,
        exclude_known_self: bool,
    ) -> tuple[RetrievalMatch, ...]:
        similarities = cosine_similarity(query_matrix, self.matrix)
        matches: list[RetrievalMatch] = []
        for query_position, row in enumerate(np.asarray(similarities)):
            ordered = sorted(
                range(len(self.document_ids)),
                key=lambda position: (-float(row[position]), self.document_identity_hashes[position]),
            )
            rank = 0
            for document_position in ordered:
                if (
                    exclude_known_self
                    and query_identity_hashes is not None
                    and query_identity_hashes[query_position] == self.document_identity_hashes[document_position]
                ):
                    continue
                similarity = float(row[document_position])
                if similarity < self.minimum_similarity:
                    continue
                rank += 1
                matches.append(
                    RetrievalMatch(
                        query_position=query_position,
                        matched_document_position=document_position,
                        rank=rank,
                        similarity=similarity,
                    )
                )
                if rank >= self.top_k:
                    break
        return tuple(matches)

    def _diagnostics(
        self,
        matches: Sequence[RetrievalMatch],
        *,
        query_count: int,
        query_identity_hashes: Sequence[str] | None,
    ) -> TextRetrievalIndexDiagnosticFacts:
        grouped: dict[int, list[RetrievalMatch]] = {}
        for match in matches:
            grouped.setdefault(match.query_position, []).append(match)
        duplicate_violations = sum(
            len(items) - len({item.matched_document_position for item in items}) for items in grouped.values()
        )
        rank_violations = sum(
            [item.rank for item in items] != list(range(1, len(items) + 1)) for items in grouped.values()
        )
        self_violations = sum(
            query_identity_hashes is not None
            and item.query_position < len(query_identity_hashes)
            and query_identity_hashes[item.query_position]
            == self.document_identity_hashes[item.matched_document_position]
            for item in matches
        )
        safe_rows = [
            [item.query_position, item.matched_document_position, item.rank, round(item.similarity, 12)]
            for item in matches
        ]
        return TextRetrievalIndexDiagnosticFacts(
            indexed_document_count=len(self.document_ids),
            inspected_query_count=query_count,
            query_with_results_count=len(grouped),
            requested_top_k=self.top_k,
            maximum_effective_top_k=max((len(items) for items in grouped.values()), default=0),
            result_row_count=len(matches),
            self_match_violation_count=self_violations,
            duplicate_match_violation_count=duplicate_violations,
            rank_sequence_violation_count=rank_violations,
            index_identity_digest=_digest_values(self.document_identity_hashes),
            result_digest=_json_digest(safe_rows),
        )


def _subset_corpus(corpus: PreparedTextCorpus, positions: np.ndarray) -> PreparedTextCorpus:
    return PreparedTextCorpus(
        token_rows=[corpus.token_rows[int(position)] for position in positions],
        prepared_texts=corpus.prepared_texts.iloc[positions].reset_index(drop=True),
        normalized_texts=corpus.normalized_texts.iloc[positions].reset_index(drop=True),
        exact_fingerprints=corpus.exact_fingerprints.iloc[positions].reset_index(drop=True),
        template_fingerprints=corpus.template_fingerprints.iloc[positions].reset_index(drop=True),
        token_sets=tuple(corpus.token_sets[int(position)] for position in positions),
        quality_facts=corpus.quality_facts,
    )


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> bool:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return False
        first, second = sorted((left_root, right_root))
        self.parent[second] = first
        return True


def _connected_discovery_groups(
    corpus: PreparedTextCorpus,
    business_values: pd.Series,
) -> tuple[pd.Series, int, int, int]:
    union = _UnionFind(len(corpus.prepared_texts.index))
    first_by_template: dict[str, int] = {}
    for position, fingerprint in enumerate(corpus.template_fingerprints.astype(str).tolist()):
        union.union(first_by_template.setdefault(fingerprint, position), position)
    inverted: dict[str, list[int]] = {}
    near_edges = 0
    for position, tokens in enumerate(corpus.token_sets):
        candidates: set[int] = set()
        for token in tokens:
            candidates.update(inverted.get(token, []))
        for candidate in sorted(candidates):
            if _jaccard(tokens, corpus.token_sets[candidate]) >= 0.8:
                near_edges += int(union.union(candidate, position))
        for token in tokens:
            inverted.setdefault(token, []).append(position)
    business_hashes: list[str] = []
    first_by_business: dict[str, int] = {}
    for position, value in enumerate(business_values.tolist()):
        key = "" if pd.isna(value) else _sha256(str(value))
        business_hashes.append(key)
        if key:
            union.union(first_by_business.setdefault(key, position), position)
    roots = [union.find(position) for position in range(len(corpus.prepared_texts.index))]
    root_payloads: dict[int, list[int]] = {}
    for position, root in enumerate(roots):
        root_payloads.setdefault(root, []).append(position)
    root_keys = {
        root: f"connected-{_digest_values([str(position) for position in members])[:24]}"
        for root, members in root_payloads.items()
    }
    template_count = int(corpus.template_fingerprints.nunique(dropna=False))
    return (
        pd.Series([root_keys[root] for root in roots], dtype="string"),
        template_count,
        near_edges,
        len({key for key in business_hashes if key}),
    )


def _topic_group_holdout(
    groups: pd.Series,
    *,
    source_dataset_snapshot_digest: str,
) -> tuple[np.ndarray, np.ndarray, TextTopicSplitFacts]:
    unique = sorted(groups.astype(str).unique().tolist())
    if len(unique) < 2:
        raise ValidationError("Topic discovery requires at least two connected groups for train/heldout evidence.")
    scored = sorted(
        unique,
        key=lambda group: _sha256(f"{source_dataset_snapshot_digest}:{group}:{_TOPIC_SPLIT_POLICY}"),
    )
    holdout_count = min(len(unique) - 1, max(1, int(math.ceil(len(unique) * _HOLDOUT_FRACTION))))
    holdout_groups = set(scored[:holdout_count])
    holdout = np.flatnonzero(groups.astype(str).isin(holdout_groups).to_numpy(dtype=bool))
    train = np.flatnonzero(~groups.astype(str).isin(holdout_groups).to_numpy(dtype=bool))
    if len(train) < 2 or not len(holdout):
        raise ValidationError("Topic discovery could not realize a non-empty group-safe train/heldout split.")
    train_group_values = set(groups.iloc[train].astype(str).tolist())
    holdout_group_values = set(groups.iloc[holdout].astype(str).tolist())
    split = TextTopicSplitFacts(
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
        eligible_row_count=len(groups.index),
        train_row_count=len(train),
        holdout_row_count=len(holdout),
        connected_group_count=len(unique),
        train_group_count=len(train_group_values),
        holdout_group_count=len(holdout_group_values),
        train_membership_digest=_digest_values([str(value) for value in train.tolist()]),
        holdout_membership_digest=_digest_values([str(value) for value in holdout.tolist()]),
        group_overlap_count=len(train_group_values & holdout_group_values),
    )
    return train, holdout, split


def _cluster_stability(
    matrix: Any,
    groups: pd.Series,
    *,
    base_labels: np.ndarray,
    n_clusters: int,
    mapping_digest: str,
) -> TextClusteringStabilityFacts:
    unique_groups = sorted(groups.astype(str).unique().tolist())
    scores: list[float] = []
    failures = 0
    for offset in range(_STABILITY_RUNS):
        rng = np.random.default_rng(_RANDOM_STATE + offset + 1)
        sample_count = min(len(unique_groups), max(1, int(math.ceil(len(unique_groups) * _RESAMPLE_FRACTION))))
        selected = set(rng.choice(unique_groups, size=sample_count, replace=False).tolist())
        positions = np.flatnonzero(groups.astype(str).isin(selected).to_numpy(dtype=bool))
        if len(positions) <= n_clusters:
            failures += 1
            continue
        try:
            model = KMeans(
                n_clusters=n_clusters,
                n_init=10,
                max_iter=300,
                random_state=_RANDOM_STATE + offset + 1,
            ).fit(matrix[positions])
            scores.append(float(adjusted_rand_score(base_labels, model.predict(matrix))))
        except ValueError:
            failures += 1
    return TextClusteringStabilityFacts(
        successful_run_count=len(scores),
        failed_run_count=failures,
        mean_adjusted_rand=float(np.mean(scores)) if scores else None,
        minimum_adjusted_rand=float(np.min(scores)) if scores else None,
        stable_label_mapping_digest=mapping_digest,
    )


def _topic_stability(matrix: Any, base_components: np.ndarray, topic_count: int) -> TextTopicStabilityFacts:
    scores: list[float] = []
    failures = 0
    base = _row_normalize(base_components)
    for offset in range(_STABILITY_RUNS):
        try:
            model = LatentDirichletAllocation(
                n_components=topic_count,
                max_iter=30,
                learning_method="batch",
                random_state=_RANDOM_STATE + offset + 1,
            ).fit(matrix)
            similarity = cosine_similarity(base, _row_normalize(model.components_))
            rows, columns = linear_sum_assignment(-similarity)
            scores.append(float(np.mean(similarity[rows, columns])))
        except ValueError:
            failures += 1
    return TextTopicStabilityFacts(
        successful_run_count=len(scores),
        failed_run_count=failures,
        mean_matched_cosine=float(np.mean(scores)) if scores else None,
        minimum_matched_cosine=float(np.min(scores)) if scores else None,
    )


def _ranking_facts(
    matches: Sequence[RetrievalMatch],
    relevance_groups: Sequence[str] | None,
    top_k: int,
) -> TextRetrievalRankingFacts | None:
    if relevance_groups is None:
        return None
    by_query: dict[int, list[RetrievalMatch]] = {}
    for match in matches:
        by_query.setdefault(match.query_position, []).append(match)
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    for query_position, query_group in enumerate(relevance_groups):
        relevant = {
            position
            for position, group in enumerate(relevance_groups)
            if position != query_position and group == query_group
        }
        if not relevant:
            continue
        ranked = sorted(by_query.get(query_position, []), key=lambda item: item.rank)
        hits = [int(item.matched_document_position in relevant) for item in ranked[:top_k]]
        recalls.append(sum(hits) / len(relevant))
        reciprocal_ranks.append(next((1.0 / rank for rank, hit in enumerate(hits, start=1) if hit), 0.0))
        dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits, start=1))
        ideal_hits = min(len(relevant), top_k)
        ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcgs.append(dcg / ideal if ideal else 0.0)
    if not recalls:
        raise ValidationError("Admitted retrieval relevance truth has no query with another relevant document.")
    return TextRetrievalRankingFacts(
        evaluated_query_count=len(recalls),
        recall_at_k=float(np.mean(recalls)),
        mrr_at_k=float(np.mean(reciprocal_ranks)),
        ndcg_at_k=float(np.mean(ndcgs)),
    )


def _component_profiles(
    components: np.ndarray,
    feature_names: Sequence[Any],
    mapping: dict[int, int],
    displayed_term_count: int,
    *,
    profile_type: Literal["cluster", "topic"],
) -> list[TextClusterProfileFact] | list[TextTopicProfileFact]:
    features = [str(value) for value in feature_names]
    profiles: list[Any] = []
    for raw_label, stable_label in sorted(mapping.items(), key=lambda item: item[1]):
        terms: list[SanitizedTermFact] = []
        for index in np.argsort(components[raw_label])[::-1]:
            term = features[int(index)]
            if not _safe_display_term(term):
                continue
            terms.append(SanitizedTermFact(term=term, weight=float(components[raw_label, int(index)])))
            if len(terms) >= displayed_term_count:
                break
        if profile_type == "cluster":
            profiles.append(TextClusterProfileFact(cluster_label=stable_label, top_terms=terms))
        else:
            profiles.append(TextTopicProfileFact(topic_label=stable_label, top_terms=terms))
    return profiles


def _stable_component_labels(components: np.ndarray, feature_names: Sequence[Any]) -> dict[int, int]:
    features = [str(value) for value in feature_names]
    keys: list[tuple[tuple[str, ...], str, int]] = []
    for raw_label, row in enumerate(components):
        safe_terms = tuple(
            features[int(index)]
            for index in np.argsort(row)[::-1]
            if _safe_display_term(features[int(index)])
        )[:5]
        centroid_digest = _sha256(np.asarray(row, dtype=np.float64).round(12).tobytes().hex())
        keys.append((safe_terms, centroid_digest, raw_label))
    return {raw_label: stable for stable, (_, _, raw_label) in enumerate(sorted(keys), start=1)}


def _topic_profile_identity_digest(profiles: Sequence[TextTopicProfileFact]) -> str:
    return _json_digest(
        [
            {
                "topic_label": profile.topic_label,
                "terms": [term.term for term in profile.top_terms],
            }
            for profile in profiles
        ]
    )


def _stable_distribution_columns(distributions: np.ndarray, mapping: dict[int, int]) -> np.ndarray:
    result = np.zeros_like(np.asarray(distributions, dtype=float))
    for raw, stable in mapping.items():
        result[:, stable - 1] = distributions[:, raw]
    return result


def _map_labels(labels: np.ndarray, mapping: dict[int, int]) -> np.ndarray:
    return np.asarray([mapping[int(value)] for value in labels], dtype=int)


def _safe_cosine_silhouette(matrix: Any, labels: np.ndarray) -> float | None:
    unique = np.unique(labels)
    if len(unique) < 2 or len(unique) >= len(labels):
        return None
    return float(silhouette_score(matrix, labels, metric="cosine"))


def _mean_umass_coherence(matrix: Any, top_indexes: list[list[int]]) -> float:
    binary = (matrix > 0).astype(np.int8).tocsc()
    values: list[float] = []
    for indexes in top_indexes:
        for left_position in range(1, len(indexes)):
            left = indexes[left_position]
            for right_position in range(left_position):
                right = indexes[right_position]
                right_count = int(binary[:, right].sum())
                both_count = int(binary[:, left].multiply(binary[:, right]).sum())
                values.append(math.log((both_count + 1) / max(1, right_count)))
    if not values:
        return 0.0
    raw = float(np.mean(values))
    return float(max(-1.0, min(1.0, math.tanh(raw))))


def _top_feature_indexes(components: np.ndarray, count: int) -> list[list[int]]:
    return [[int(value) for value in np.argsort(row)[::-1][:count]] for row in components]


def _term_diversity(indexes: list[list[int]]) -> float:
    flattened = [value for row in indexes for value in row]
    return len(set(flattened)) / len(flattened) if flattened else 0.0


def _safe_display_term(term: str) -> bool:
    value = term.strip()
    if len(value) < 2 or len(value) > 48:
        return False
    if value in {"<url>", "<email>", "<number>"}:
        return False
    if _URL_OR_EMAIL_RE.search(value) or _LONG_NUMBER_RE.search(value) or _OPAQUE_IDENTIFIER_RE.fullmatch(value):
        return False
    return any(character.isalpha() or "\u3400" <= character <= "\u9fff" for character in value)


def _validate_identity_series(values: pd.Series, role: str, expected_count: int) -> pd.Series:
    result = values.astype("string").fillna("").reset_index(drop=True)
    if len(result.index) != expected_count:
        raise ValidationError(f"Retrieval {role} values must align with eligible text rows.")
    if result.eq("").any():
        raise ValidationError(f"Retrieval {role} values cannot be empty for eligible text rows.")
    return result


def _tfidf(max_features: int, ngram_max: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        max_features=max_features,
        ngram_range=(1, ngram_max),
    )


def _counts(max_features: int, ngram_max: int) -> CountVectorizer:
    return CountVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        max_features=max_features,
        ngram_range=(1, ngram_max),
    )


def _row_normalize(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    totals = array.sum(axis=1, keepdims=True)
    return array / np.where(totals == 0.0, 1.0, totals)


def _as_text_series(values: pd.Series) -> pd.Series:
    return values.astype("string").fillna("").reset_index(drop=True)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_digest(value: Any) -> str:
    return sha256_json(value, allow_nan=False)


def _digest_values(values: Sequence[str]) -> str:
    return _json_digest(list(values))
