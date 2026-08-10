from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from xenix.exceptions import ValidationError
from xenix.services.data_tokenization_contracts import StagedTextResourceInput, TextPreparationInput
from xenix.services.ml.models.text_analysis import (
    MultilingualTextClassificationService,
    MultilingualTextClassificationParams,
    MultilingualTextClassifier,
    TokenizedTextClassificationService,
)
from xenix.services.ml.contracts import (
    ApplyInputFile,
    ApplyModelPayload,
    ApplyTaskRequest,
    DatasetSnapshotFact,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluationPolicySnapshot,
    FitTaskRequest,
    ManualTrainingPayload,
    MetricDirection,
)
from xenix.services.ml.evaluation import prediction_digest
from xenix.services.ml.types import EvaluationKind
from xenix.services.ml.text_preparation import (
    build_text_leakage_facts,
    build_text_preparer,
    build_text_vectorization_facts,
    prepare_text_classification_data,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ml_rt_service" / "text_classification"


def _resource(name: str, dataset_id: str) -> StagedTextResourceInput:
    path = FIXTURE_ROOT / name
    return StagedTextResourceInput(
        dataset_id=dataset_id,
        absolute_path=str(path.resolve()),
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def _preparation_input() -> TextPreparationInput:
    return TextPreparationInput(
        tokenizer_profile="multilingual_business_v1",
        phrase_mode="unigram_bigram",
        custom_dictionary_resources=[_resource("custom_dictionary.csv", "dictionary-dataset")],
        stopword_resources=[_resource("stopwords.csv", "stopword-dataset")],
    )


def _prepared():
    frame = pd.read_csv(FIXTURE_ROOT / "bilingual_training.csv")
    preparer = build_text_preparer(_preparation_input())
    return preparer, prepare_text_classification_data(
        frame,
        text_column="message",
        target_column="label",
        business_group_column="account",
        preparer=preparer,
    )


def test_business_and_template_groups_form_one_privacy_safe_connected_union() -> None:
    preparer, prepared = _prepared()
    unique_groups = prepared.connected_groups.drop_duplicates().tolist()
    holdout_mask = prepared.connected_groups.eq(unique_groups[-1]).to_numpy(dtype=bool)
    holdout_positions = holdout_mask.nonzero()[0]
    train_positions = (~holdout_mask).nonzero()[0]

    facts = build_text_leakage_facts(
        prepared,
        train_positions=train_positions,
        holdout_positions=holdout_positions,
    )
    serialized = json.dumps(
        {
            "preparation": prepared.preparation_facts.model_dump(mode="json"),
            "leakage": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    assert prepared.preparation_facts.source_row_count == 16
    assert prepared.preparation_facts.eligible_row_count == 16
    assert facts.business_group_count == 8
    assert facts.connected_group_count < facts.business_group_count
    assert facts.train_business_group_overlap_count == 0
    assert facts.train_template_group_overlap_count == 0
    assert facts.train_connected_group_overlap_count == 0
    assert "acct-a" not in serialized
    assert "诺华臻享" not in serialized
    assert "NovaCare" not in serialized
    assert "arrived quickly" not in serialized
    specification = preparer.specification.model_dump(mode="json")
    assert specification["custom_dictionary_references"] == [
        {
            "dataset_id": "dictionary-dataset",
            "source_sha256": _resource("custom_dictionary.csv", "dictionary-dataset").source_sha256,
            "term_count": 2,
        }
    ]
    assert specification["stopword_references"][0]["dataset_id"] == "stopword-dataset"
    assert "absolute_path" not in json.dumps(specification, sort_keys=True)


def test_naive_row_partition_is_detected_as_template_and_business_leakage() -> None:
    _preparer, prepared = _prepared()
    train_positions = [0, 3, 4, 7, 8, 11, 12, 15]
    holdout_positions = [1, 2, 5, 6, 9, 10, 13, 14]

    facts = build_text_leakage_facts(
        prepared,
        train_positions=train_positions,
        holdout_positions=holdout_positions,
    )

    assert facts.train_business_group_overlap_count == 8
    assert facts.train_template_group_overlap_count > 0
    assert facts.train_connected_group_overlap_count > 0


def test_classifier_fits_vocabulary_on_training_groups_only_and_retains_apply_preparation() -> None:
    preparer, prepared = _prepared()
    unique_groups = prepared.connected_groups.drop_duplicates().tolist()
    holdout_mask = prepared.connected_groups.eq(unique_groups[-1]).to_numpy(dtype=bool)
    train_positions = (~holdout_mask).nonzero()[0]
    holdout_positions = holdout_mask.nonzero()[0]
    classifier = MultilingualTextClassifier(
        preparer=preparer,
        max_features=5000,
        minimum_document_frequency=1,
        class_weight="balanced",
    )

    classifier.fit(
        prepared.raw_texts.iloc[train_positions].reset_index(drop=True),
        prepared.labels.iloc[train_positions].reset_index(drop=True),
    )
    holdout_texts = prepared.raw_texts.iloc[holdout_positions].reset_index(drop=True)
    predictions = classifier.predict(holdout_texts)
    repeat_predictions = classifier.predict(holdout_texts)
    holdout_corpus = classifier.prepare(holdout_texts)
    vectorization = build_text_vectorization_facts(
        classifier.vectorizer,
        holdout_corpus.prepared_texts,
        fit_row_count=len(train_positions),
    )

    assert "rudely" not in classifier.vectorizer.vocabulary_
    assert vectorization.fit_row_count == len(train_positions)
    assert predictions.tolist() == repeat_predictions.tolist()
    assert prediction_digest(predictions) == prediction_digest(repeat_predictions)
    assert classifier.preparer.specification == preparer.specification
    assert classifier.fit_vectorization_facts.fit_row_count == len(train_positions)


def test_raw_apply_reports_empty_and_oov_rows_without_changing_the_retained_spec() -> None:
    preparer, prepared = _prepared()
    classifier = MultilingualTextClassifier(preparer=preparer)
    classifier.fit(prepared.raw_texts, prepared.labels)
    apply_frame = pd.read_csv(FIXTURE_ROOT / "bilingual_apply.csv", keep_default_na=False)
    before_digest = classifier.preparer.specification.specification_digest

    predictions = classifier.predict(apply_frame["message"])
    corpus = classifier.prepare(apply_frame["message"])
    vectorization = build_text_vectorization_facts(
        classifier.vectorizer,
        corpus.prepared_texts,
        fit_row_count=len(prepared.labels.index),
    )

    assert len(predictions) == 4
    assert corpus.quality_facts.empty_after_preparation_row_count == 1
    assert vectorization.out_of_vocabulary_row_count >= 1
    assert classifier.preparer.specification.specification_digest == before_digest


def test_active_and_legacy_keys_have_distinct_persisted_semantics() -> None:
    assert MultilingualTextClassificationService.key == "text.classification.multilingual_logistic_regression_tfidf"
    assert TokenizedTextClassificationService.key == "text.classification.logistic_regression_tfidf"
    assert MultilingualTextClassificationService.key != TokenizedTextClassificationService.key
    assert MultilingualTextClassificationService.supports_hyperparameter_tuning is False
    assert MultilingualTextClassificationService.result_contract is not None
    assert MultilingualTextClassificationService.result_contract.train_result_kinds == ["model", "metrics", "report"]


def test_active_params_expose_only_bounded_registered_resource_ids() -> None:
    params = MultilingualTextClassificationParams(
        custom_dictionary_dataset_ids=["dictionary-dataset"],
        stopword_dataset_ids=["stopword-dataset"],
    )
    serialized = params.model_dump(mode="json")

    assert serialized["custom_dictionary_dataset_ids"] == ["dictionary-dataset"]
    assert serialized["stopword_dataset_ids"] == ["stopword-dataset"]
    assert "path" not in json.dumps(serialized, sort_keys=True)
    with pytest.raises(ValueError, match="at most 4 items"):
        MultilingualTextClassificationParams(custom_dictionary_dataset_ids=[f"dataset-{index}" for index in range(5)])


def test_active_adapter_fit_and_evaluate_recompute_the_private_grouped_truth(tmp_path: Path) -> None:
    source = FIXTURE_ROOT / "bilingual_training.csv"
    snapshot = DatasetSnapshotFact(
        dataset_id="training-dataset",
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_byte_size=source.stat().st_size,
        schema_digest="1" * 64,
    )
    policy = EvaluationPolicySnapshot(
        policy_key="classification.grouped.v1",
        evaluation_kind=EvaluationKind.CLASSIFICATION,
        primary_metric_name="balanced_accuracy",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=["f1_macro"],
        split_strategy="group_hash_holdout.v1",
        test_size=0.25,
        cv_folds=2,
        random_state=42,
    )
    common = {
        "project_id": "project",
        "dataset_id": "training-dataset",
        "dataset_source_path": str(source.resolve()),
        "evaluation_kind": EvaluationKind.CLASSIFICATION,
        "train_role_bindings": [
            {"role": "text", "columns": ["message"]},
            {"role": "target", "columns": ["label"]},
            {"role": "group", "columns": ["account"]},
        ],
        "evaluation_policy": policy,
        "dataset_snapshot": snapshot,
        "text_preparation": _preparation_input(),
    }
    fit_request = FitTaskRequest(
        task_id="fit-task",
        **common,
        manual_training=ManualTrainingPayload(
            model_key=MultilingualTextClassificationService.key,
            params={
                "phrase_mode": "unigram_bigram",
                "custom_dictionary_dataset_ids": ["dictionary-dataset"],
                "stopword_dataset_ids": ["stopword-dataset"],
            },
        ),
    )

    mismatched_request = fit_request.model_copy(
        update={
            "text_preparation": TextPreparationInput(
                tokenizer_profile="multilingual_business_v1",
                phrase_mode="unigram_bigram",
            )
        }
    )
    with pytest.raises(ValidationError, match="Dataset IDs do not match"):
        MultilingualTextClassificationService.fit(mismatched_request, tmp_path / "mismatch")
    fit_result = MultilingualTextClassificationService.fit(fit_request, tmp_path / "fit")
    evaluate_request = EvaluateTaskRequest(
        task_id="evaluate-task",
        **common,
        evaluate_model=EvaluateModelPayload(
            trained_model_id="trained-model",
            model_key=fit_result.model_key,
            trained_model_artifact_path=fit_result.model_artifact_path,
            holdout_artifact_path=str(fit_result.holdout_artifact_path),
        ),
    )
    evaluation = MultilingualTextClassificationService.evaluate(evaluate_request, tmp_path / "evaluate")
    apply_request = ApplyTaskRequest(
        task_id="apply-task",
        project_id="project",
        dataset_id="apply-dataset",
        dataset_source_path=str((FIXTURE_ROOT / "bilingual_apply.csv").resolve()),
        feature_columns=["message"],
        apply_model=ApplyModelPayload(
            trained_model_id="trained-model",
            model_key=fit_result.model_key,
            trained_model_artifact_path=str(fit_result.final_model_artifact_path),
        ),
        input_files=[
            ApplyInputFile(
                absolute_path=str((FIXTURE_ROOT / "bilingual_apply.csv").resolve()),
                file_name="bilingual_apply.csv",
                source_kind="dataset",
                dataset_id="apply-dataset",
            )
        ],
    )
    apply_result = MultilingualTextClassificationService.apply(apply_request, tmp_path / "apply")

    assert fit_result.split_facts is not None
    assert fit_result.split_facts.group_overlap_count == 0
    assert fit_result.training_scopes is not None
    assert fit_result.training_scopes.evaluation_model == "holdout_train_split"
    assert fit_result.training_scopes.apply_model == "all_eligible_rows"
    assert fit_result.text_preparation_specification is not None
    assert fit_result.text_preparation_facts is not None
    assert fit_result.text_leakage_facts is not None
    assert fit_result.text_vectorization_facts is not None
    assert evaluation.split_facts == fit_result.split_facts
    assert evaluation.evaluation is not None
    assert evaluation.baseline_evaluation is not None
    assert evaluation.comparison is not None
    assert evaluation.text_classification_evaluation is not None
    assert evaluation.text_classification_evaluation.specification == fit_result.text_preparation_specification
    assert evaluation.text_classification_evaluation.leakage.train_connected_group_overlap_count == 0
    assert apply_result.source_dataset_ids == ["apply-dataset"]
    assert apply_result.text_classification_apply_facts is not None
    assert apply_result.text_classification_apply_facts.specification == fit_result.text_preparation_specification
    assert apply_result.text_classification_apply_facts.preparation.empty_after_preparation_row_count == 1


def test_raw_classifier_rejects_training_rows_that_become_empty() -> None:
    preparer = build_text_preparer(_preparation_input())
    classifier = MultilingualTextClassifier(preparer=preparer)

    with pytest.raises(ValidationError, match="remain non-empty"):
        classifier.fit(pd.Series(["service", "客服"]), pd.Series(["yes", "no"]))
