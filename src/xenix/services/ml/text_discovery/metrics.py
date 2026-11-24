from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

from ....exceptions import ValidationError
from ..digests import sha256_json
from ..text_preparation import PreparedTextCorpus
from .facts import (
    _HOLDOUT_FRACTION,
    _RANDOM_STATE,
    _RESAMPLE_FRACTION,
    _STABILITY_RUNS,
    _TOPIC_SPLIT_POLICY,
    RetrievalMatch,
    SanitizedTermFact,
    TextClusterProfileFact,
    TextClusteringStabilityFacts,
    TextRetrievalRankingFacts,
    TextTopicProfileFact,
    TextTopicSplitFacts,
    TextTopicStabilityFacts,
)

_URL_OR_EMAIL_RE = re.compile(r"(?i)(?:https?://|www\.|\b[^\s@]+@[^\s@]+\.[^\s@]+\b)")
_LONG_NUMBER_RE = re.compile(r"\d{5,}")
_OPAQUE_IDENTIFIER_RE = re.compile(r"(?i)^(?:[a-z]*\d[a-z\d_-]{5,}|[a-f\d]{12,}|\w+[_-]\w+[_-]\w+)$")


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
