from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.sparse import csr_matrix
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity

from ....exceptions import ValidationError
from ..digests import prediction_digest
from ..text_preparation import (
    TextPreparer,
    build_text_vectorization_facts,
)
from .facts import (
    _RANDOM_STATE,
    PreparedDiscoveryCorpus,
    RetrievalMatch,
    TextClusterApplication,
    TextClusterEvaluation,
    TextClusterProfileFact,
    TextClusterSizeFact,
    TextClusteringApplyFacts,
    TextClusteringEvaluationFacts,
    TextClusteringQualityFacts,
    TextDiscoveryIsolationFacts,
    TextRetrievalApplication,
    TextRetrievalApplyFacts,
    TextRetrievalEvaluation,
    TextRetrievalEvaluationFacts,
    TextRetrievalIndexDiagnosticFacts,
    TextTopicApplication,
    TextTopicApplyFacts,
    TextTopicEvaluation,
    TextTopicEvaluationFacts,
    TextTopicPrevalenceFact,
    TextTopicProfileFact,
    TextTopicQualityFacts,
    TextTopicSplitFacts,
)
from .metrics import (
    _as_text_series,
    _cluster_stability,
    _component_profiles,
    _connected_discovery_groups,
    _counts,
    _digest_values,
    _json_digest,
    _map_labels,
    _mean_umass_coherence,
    _ranking_facts,
    _row_normalize,
    _safe_cosine_silhouette,
    _sha256,
    _stable_component_labels,
    _stable_distribution_columns,
    _subset_corpus,
    _term_diversity,
    _tfidf,
    _top_feature_indexes,
    _topic_group_holdout,
    _topic_profile_identity_digest,
    _topic_stability,
    _validate_identity_series,
)


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
