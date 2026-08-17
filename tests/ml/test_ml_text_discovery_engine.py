from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from xenix.services.data_tokenization_contracts import TextPreparationInput
from xenix.services.ml.text_discovery import (
    MultilingualTextClusterer,
    MultilingualTextRetriever,
    MultilingualTopicDiscoverer,
    TextRetrievalEvaluationFacts,
    prepare_discovery_corpus,
)
from xenix.services.ml.text_preparation import build_text_preparer
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
from xenix.services.ml.models.text_analysis import (
    MultilingualTextClusteringService,
    MultilingualTextSimilarityService,
    MultilingualTextTopicModelingService,
)
from xenix.services.ml.types import EvaluationKind


FIXTURE = FIXTURES_ROOT / "ml_rt_service" / "text_discovery" / "bilingual_feedback.csv"
SNAPSHOT_DIGEST = "7" * 64


def _prepared():
    frame = pd.read_csv(FIXTURE)
    preparer = build_text_preparer(
        TextPreparationInput(
            tokenizer_profile="multilingual_business_v1",
            phrase_mode="unigram_bigram",
            custom_dictionary_resources=[],
            stopword_resources=[],
        )
    )
    prepared = prepare_discovery_corpus(
        frame,
        text_column="text",
        business_group_column="business_group",
        preparer=preparer,
        minimum_rows=12,
    )
    return frame, preparer, prepared


def test_clustering_has_recomputable_cosine_group_stability_and_safe_stable_labels() -> None:
    _, preparer, prepared = _prepared()
    first = MultilingualTextClusterer(
        preparer=preparer,
        n_clusters=3,
        max_features=2000,
        displayed_term_count=5,
    ).fit(prepared)
    second = MultilingualTextClusterer(
        preparer=preparer,
        n_clusters=3,
        max_features=2000,
        displayed_term_count=5,
    ).fit(prepared)

    first_evaluation = first.evaluate(prepared)
    second_evaluation = second.evaluate(prepared)

    assert first_evaluation.facts == second_evaluation.facts
    assert first_evaluation.facts.quality.realized_cluster_count == 3
    assert first_evaluation.facts.quality.cosine_silhouette is not None
    assert sum(item.row_count for item in first_evaluation.facts.sizes) == len(prepared.raw_texts)
    assert first_evaluation.facts.stability.requested_run_count == 5
    assert first_evaluation.facts.stability.resample_group_overlap_count == 0
    assert first_evaluation.facts.stability.successful_run_count >= 4
    assert {item.cluster_label for item in first_evaluation.facts.profiles} == {1, 2, 3}
    projection = json.dumps(first_evaluation.facts.model_dump(mode="json"), ensure_ascii=False)
    assert "http" not in projection
    assert "@" not in projection
    assert "food-01" not in projection

    applied = first.apply(pd.Series(["牛肉面汤底浓郁", "friendly patient staff", "全新未知词汇"]))
    assert applied.facts.assigned_row_count == 3
    assert applied.facts.stable_label_mapping_digest == first_evaluation.facts.stability.stable_label_mapping_digest
    assert applied.labels[0] in {1, 2, 3}
    assert applied.labels[1] in {1, 2, 3}


def test_topic_evaluation_is_group_safe_heldout_and_permutation_matched() -> None:
    _, preparer, prepared = _prepared()
    first = MultilingualTopicDiscoverer(
        preparer=preparer,
        topic_count=3,
        max_features=2000,
        displayed_term_count=5,
    )
    first_result = first.fit_evaluation(prepared, source_dataset_snapshot_digest=SNAPSHOT_DIGEST)
    second = MultilingualTopicDiscoverer(
        preparer=preparer,
        topic_count=3,
        max_features=2000,
        displayed_term_count=5,
    )
    second_result = second.fit_evaluation(prepared, source_dataset_snapshot_digest=SNAPSHOT_DIGEST)

    facts = first_result.facts
    assert facts == second_result.facts
    assert facts.split.group_overlap_count == 0
    assert facts.isolation.partition_group_overlap_count == 0
    assert facts.quality.heldout_perplexity > 0
    assert -1 <= facts.quality.mean_coherence <= 1
    assert 0 < facts.quality.term_diversity <= 1
    assert facts.stability.successful_run_count == 5
    assert facts.stability.mean_matched_cosine is not None
    assert sum(item.dominant_document_count for item in facts.prevalence) == facts.split.holdout_row_count
    assert sum(item.mean_prevalence for item in facts.prevalence) == pytest.approx(1.0)
    assert first_result.distributions.shape == (facts.split.holdout_row_count, 3)

    full = MultilingualTopicDiscoverer(
        preparer=preparer,
        topic_count=3,
        max_features=2000,
        displayed_term_count=5,
    ).fit_all(prepared, evaluation_reference=first)
    full_application = full.apply(prepared.raw_texts)
    assert full.label_identity_digest == facts.topic_label_identity_digest
    assert full_application.facts.topic_label_identity_digest == facts.topic_label_identity_digest
    assert full.vectorizer.get_feature_names_out().tolist() == first.vectorizer.get_feature_names_out().tolist()
    assert {row.index(max(row)) + 1 for row in full_application.distributions if row is not None} <= {1, 2, 3}


def test_retrieval_truth_gates_metrics_and_preserves_self_excluding_unique_top_k() -> None:
    frame, preparer, prepared = _prepared()
    retriever = MultilingualTextRetriever(
        preparer=preparer,
        max_features=2000,
        top_k=4,
        minimum_similarity=0.01,
    ).fit(
        prepared,
        document_ids=frame["document_id"],
        relevance_groups=frame["relevance_group"],
    )
    result = retriever.evaluate(prepared)

    assert result.facts.mode == "relevance_evaluated"
    assert result.facts.ranking is not None
    assert 0 <= result.facts.ranking.recall_at_k <= 1
    assert result.facts.diagnostics.self_match_violation_count == 0
    assert result.facts.diagnostics.duplicate_match_violation_count == 0
    assert result.facts.diagnostics.rank_sequence_violation_count == 0
    for query in range(len(frame.index)):
        matches = [item for item in result.matches if item.query_position == query]
        assert len(matches) <= 4
        assert len({item.matched_document_position for item in matches}) == len(matches)
        assert all(item.matched_document_position != query for item in matches)

    diagnostic_only = MultilingualTextRetriever(
        preparer=preparer,
        max_features=2000,
        top_k=4,
        minimum_similarity=0.01,
    ).fit(prepared, document_ids=frame["document_id"], relevance_groups=None).evaluate(prepared)
    assert diagnostic_only.facts.mode == "index_diagnostic"
    assert diagnostic_only.facts.ranking is None
    assert "recall_at_k" not in diagnostic_only.facts.model_dump_json(exclude_none=True)


def test_retrieval_fact_rejects_relevance_claim_without_ranking_truth() -> None:
    _, preparer, prepared = _prepared()
    diagnostic = MultilingualTextRetriever(
        preparer=preparer,
        max_features=2000,
        top_k=3,
        minimum_similarity=0.0,
    ).fit(prepared, document_ids=None, relevance_groups=None).evaluate(prepared)
    payload = diagnostic.facts.model_dump(mode="json")
    payload["mode"] = "relevance_evaluated"

    with pytest.raises(ValueError, match="exactly when relevance truth"):
        TextRetrievalEvaluationFacts.model_validate(payload)


def test_active_service_adapters_fit_evaluate_apply_and_materialize_local_tables(tmp_path: Path) -> None:
    snapshot = DatasetSnapshotFact(
        dataset_id="text-discovery-source",
        source_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        source_byte_size=FIXTURE.stat().st_size,
        schema_digest="8" * 64,
    )
    preparation = TextPreparationInput(
        tokenizer_profile="multilingual_business_v1",
        phrase_mode="unigram_bigram",
    )
    cases = [
        (
            MultilingualTextClusteringService,
            EvaluationKind.TEXT_CLUSTERING,
            [{"role": "text", "columns": ["text"]}, {"role": "group", "columns": ["business_group"]}],
            {"n_clusters": 3, "displayed_term_count": 5, "phrase_mode": "unigram_bigram"},
        ),
        (
            MultilingualTextTopicModelingService,
            EvaluationKind.TOPIC_MODELING,
            [{"role": "text", "columns": ["text"]}, {"role": "group", "columns": ["business_group"]}],
            {"topic_count": 3, "displayed_term_count": 5, "phrase_mode": "unigram_bigram"},
        ),
        (
            MultilingualTextSimilarityService,
            EvaluationKind.RETRIEVAL,
            [
                {"role": "text", "columns": ["text"]},
                {"role": "document_id", "columns": ["document_id"]},
                {"role": "relevance_group", "columns": ["relevance_group"]},
            ],
            {"top_k": 3, "minimum_similarity": 0.01, "phrase_mode": "unigram_bigram"},
        ),
    ]

    for service, evaluation_kind, role_bindings, params in cases:
        common = {
            "project_id": "project",
            "dataset_id": "text-discovery-source",
            "dataset_source_path": str(FIXTURE.resolve()),
            "evaluation_kind": evaluation_kind,
            "train_role_bindings": role_bindings,
            "evaluation_policy": get_default_policy(evaluation_kind),
            "dataset_snapshot": snapshot,
            "text_preparation": preparation,
        }
        fit = service.fit(
            FitTaskRequest(
                task_id=f"fit-{service.key}",
                **common,
                manual_training=ManualTrainingPayload(model_key=service.key, params=params),
            ),
            tmp_path / service.key / "fit",
        )
        evaluated = service.evaluate(
            EvaluateTaskRequest(
                task_id=f"evaluate-{service.key}",
                **common,
                evaluate_model=EvaluateModelPayload(
                    trained_model_id=f"trained-{service.key}",
                    model_key=service.key,
                    trained_model_artifact_path=fit.model_artifact_path,
                    holdout_artifact_path=str(fit.holdout_artifact_path),
                ),
            ),
            tmp_path / service.key / "evaluate",
        )
        applied = service.apply(
            ApplyTaskRequest(
                task_id=f"apply-{service.key}",
                project_id="project",
                dataset_id="text-discovery-source",
                dataset_source_path=str(FIXTURE.resolve()),
                feature_columns=["text"],
                apply_model=ApplyModelPayload(
                    trained_model_id=f"trained-{service.key}",
                    model_key=service.key,
                    trained_model_artifact_path=str(fit.final_model_artifact_path),
                ),
                input_files=[
                    ApplyInputFile(
                        absolute_path=str(FIXTURE.resolve()),
                        file_name=FIXTURE.name,
                        source_kind="dataset",
                        dataset_id="text-discovery-source",
                    )
                ],
            ),
            tmp_path / service.key / "apply",
        )

        training_table = pd.read_csv(str(fit.export_artifact_path))
        apply_table = pd.read_csv(applied.output_file_path)
        assert fit.report_artifact_path is not None
        assert evaluated.model_key == service.key
        assert applied.source_dataset_ids == ["text-discovery-source"]
        assert "text" in apply_table.columns
        if evaluation_kind is EvaluationKind.TEXT_CLUSTERING:
            assert "text" in training_table.columns
            assert "cluster_label" in training_table.columns
            assert "cluster_label" in apply_table.columns
            assert evaluated.text_clustering_evaluation == fit.text_clustering_evaluation
            assert applied.text_clustering_apply_facts is not None
        elif evaluation_kind is EvaluationKind.TOPIC_MODELING:
            assert "text" in training_table.columns
            assert {"dominant_topic", "topic_score", "topic_1_share", "topic_2_share", "topic_3_share"} <= set(
                training_table.columns
            )
            assert {"dominant_topic", "topic_score", "topic_1_share", "topic_2_share", "topic_3_share"} <= set(
                apply_table.columns
            )
            assert evaluated.text_topic_evaluation == fit.text_topic_evaluation
            assert applied.text_topic_apply_facts is not None
            assert (
                applied.text_topic_apply_facts.topic_label_identity_digest
                == fit.text_topic_evaluation.topic_label_identity_digest
            )
        else:
            assert {"query_document_id", "query_text", "matched_document_id", "matched_text", "rank", "similarity"} <= set(
                training_table.columns
            )
            assert {"text", "matched_document_id", "matched_text", "rank", "similarity"} <= set(
                apply_table.columns
            )
            assert evaluated.text_retrieval_evaluation == fit.text_retrieval_evaluation
            assert applied.text_retrieval_apply_facts is not None
            assert applied.text_retrieval_apply_facts.diagnostics.self_match_violation_count == 0
