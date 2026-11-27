from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import Field, PositiveInt, field_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .....exceptions import ValidationError
from ....data_tokenization_contracts import TextProcessingOptions
from ....storage.models import ProblemKind
from ...contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    TrainingScopeFacts,
)
from ...dataset_loader import load_dataset, load_holdout_frame
from ...digests import prediction_digest as evaluation_prediction_digest
from ...evaluation import (
    build_dummy_baseline_metrics,
    build_evaluation_comparison,
    build_metric_snapshot,
)
from ...preparation import (
    build_text_preparation_facts,
    prepare_supervised_split,
    read_evaluation_context,
)
from ...text_classification_evaluation import read_cross_validation, write_cross_validation
from ...text_preparation import (
    PreparedTextClassificationData,
    PreparedTextCorpus,
    TextClassificationApplyFacts,
    TextClassificationEvaluationFacts,
    TextPreparer,
    build_text_leakage_facts,
    build_text_preparer,
    build_text_vectorization_facts,
)
from ...types import (
    ColumnRoleKind,
    ModelFamily,
    ModelResultContract,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)
from .._text_helpers import (
    _as_text_series,
    _multilingual_artifact_paths,
    _multilingual_result_summary,
    _prepare_multilingual_request_data,
    _read_multilingual_holdout_context,
    _require_zero_text_leakage,
    _save_multilingual_holdout,
    _single_role_column,
    _single_role_column_from_artifact,
    _text_preparation_input,
    _verify_recomputed_text_context,
    _write_apply_output,
)

_TEXT_RANDOM_STATE = 42


class MultilingualTextClassificationParams(TextProcessingOptions):
    stopword_policy: Literal["none", "business"] = Field(default="none", description="None retains meaning-bearing words; business enables the built-in stopword list.")
    minimum_token_length: int = Field(default=1, ge=1, le=20, description="1 retains Chinese single-character words, including negation and actions.")
    preparation_profile: Literal["multilingual_business_v1"] = "multilingual_business_v1"
    phrase_mode: Literal["unigram", "unigram_bigram"] = "unigram"
    max_features: int = Field(default=5000, ge=200, le=50000)
    minimum_document_frequency: int = Field(default=1, ge=1, le=20)
    class_weight: Literal["balanced", "none"] = "balanced"
    custom_dictionary_dataset_ids: list[PositiveInt] = Field(default_factory=list, max_length=4)
    stopword_dataset_ids: list[PositiveInt] = Field(default_factory=list, max_length=4)

    @field_validator("custom_dictionary_dataset_ids", "stopword_dataset_ids")
    @classmethod
    def _resource_dataset_ids_must_be_unique(cls, values: list[int]) -> list[int]:
        if len(set(values)) != len(values):
            raise ValueError("Text preparation Dataset IDs cannot contain duplicates.")
        return values


class MultilingualTextClassifier:
    """Retained raw-text classifier whose TF-IDF vocabulary is fitted inside each training partition."""

    def __init__(
        self,
        *,
        preparer: TextPreparer,
        max_features: int = 5000,
        minimum_document_frequency: int = 1,
        class_weight: Literal["balanced", "none"] = "balanced",
    ) -> None:
        self.preparer = preparer
        self.max_features = max_features
        self.minimum_document_frequency = minimum_document_frequency
        self.class_weight = class_weight
        self.text_column: str | None = None

    def fit(self, texts: pd.Series, labels: pd.Series) -> MultilingualTextClassifier:
        corpus = self.preparer.prepare_series(_as_text_series(texts))
        if corpus.prepared_texts.eq("").any():
            raise ValidationError("Text classifier training rows must remain non-empty after retained preparation.")
        if getattr(self.preparer.specification, "text_strategy", "words") == "characters":
            self.vectorizer = TfidfVectorizer(
                analyzer="char", lowercase=False, max_features=self.max_features,
                min_df=self.minimum_document_frequency,
                ngram_range=(2, self.preparer.specification.character_ngram_max),
            )
        else:
            self.vectorizer = TfidfVectorizer(
                tokenizer=str.split, preprocessor=None, token_pattern=None, lowercase=False,
                max_features=self.max_features, min_df=self.minimum_document_frequency,
                ngram_range=(1, self.preparer.ngram_max),
            )
        try:
            matrix = self.vectorizer.fit_transform(corpus.prepared_texts.tolist())
        except ValueError as exc:
            raise ValidationError(f"Text classification could not fit a TF-IDF vocabulary: {exc}") from exc
        self.model = LogisticRegression(
            class_weight=None if self.class_weight == "none" else self.class_weight,
            max_iter=500,
            random_state=_TEXT_RANDOM_STATE,
        )
        self.model.fit(matrix, labels.reset_index(drop=True))
        self.fit_preparation_facts = corpus.quality_facts
        self.fit_vectorization_facts = build_text_vectorization_facts(
            self.vectorizer,
            corpus.prepared_texts,
            fit_row_count=len(corpus.prepared_texts.index),
        )
        return self

    def prepare(self, texts: pd.Series) -> PreparedTextCorpus:
        return self.preparer.prepare_series(_as_text_series(texts))

    def predict(self, texts: pd.Series) -> np.ndarray:
        corpus = self.prepare(texts)
        return np.asarray(self.model.predict(self.vectorizer.transform(corpus.prepared_texts.tolist())))

    def predict_proba(self, texts: pd.Series) -> np.ndarray:
        corpus = self.prepare(texts)
        return np.asarray(self.model.predict_proba(self.vectorizer.transform(corpus.prepared_texts.tolist())))

    def feature_coverage(self, texts: pd.Series) -> pd.DataFrame:
        """Row-level evidence; an empty vector remains an observable prediction, not a rejected call."""
        corpus = self.prepare(texts)
        analyzer = self.vectorizer.build_analyzer()
        counts = []
        for text in corpus.prepared_texts:
            features = analyzer(text)
            known = sum(feature in self.vectorizer.vocabulary_ for feature in features)
            counts.append({
                "known_feature_count": known,
                "feature_coverage": known / len(features) if features else 0.0,
                "prediction_evidence": "no_known_features" if not known else "known_features",
            })
        return pd.DataFrame(counts)

    @property
    def classes_(self) -> np.ndarray:
        return np.asarray(self.model.classes_)


class MultilingualTextClassificationService(ModelServiceBase):
    key = "text.classification.multilingual_logistic_regression_tfidf"
    uses_automatic_groups = True
    display_name = "Multilingual Raw Text Classification"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Text classification"
    guidance = (
        "Predicts a label directly from bilingual raw text with retained preparation and business/template-safe evaluation."
    )
    recommendation_tier = 10
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.PREDICTOR
    params_model = MultilingualTextClassificationParams
    param_grid_model = None
    supports_hyperparameter_tuning = False
    result_contract = ModelResultContract(
        train_result_kinds=["model", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw business text prepared inside the retained analyzer.",
            ),
            ModelRoleDefinition(
                name="target",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Target label column to predict.",
            ),
            ModelRoleDefinition(
                name="group",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional business entity joined with service-owned template groups before splitting.",
            ),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw text prepared with the exact retained training specification.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextClassificationParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        prepared = _prepare_multilingual_request_data(request, preparer)
        if request.evaluation_policy.split_strategy == "group_kfold.v1":
            return cls._fit_cross_validation(request, task_dir, params, preparer, prepared)
        split = prepare_supervised_split(
            prepared.raw_texts,
            prepared.labels,
            request,
            groups=prepared.connected_groups,
        )
        leakage = build_text_leakage_facts(
            prepared,
            train_positions=split.train_positions,
            holdout_positions=split.holdout_positions,
        )
        _require_zero_text_leakage(leakage)

        estimator = cls._build_estimator(preparer, params)
        text_column = _single_role_column(request.train_role_bindings, "text")
        estimator.text_column = text_column
        estimator.fit(split.train_features, split.train_target)
        generic_preparation = build_text_preparation_facts(estimator, fit_row_count=len(split.train_target.index))
        final_estimator = cls._build_estimator(preparer, params)
        final_estimator.text_column = text_column
        final_estimator.fit(prepared.raw_texts, prepared.labels)

        model_path, final_model_path, holdout_path = _multilingual_artifact_paths(cls.key, task_dir)
        joblib.dump(estimator, model_path)
        joblib.dump(final_estimator, final_model_path)
        _save_multilingual_holdout(
            split.holdout_features,
            split.holdout_target,
            split.train_target,
            text_column=text_column,
            target_column=_single_role_column(request.train_role_bindings, "target"),
            split_facts=split.split_facts,
            preparation_facts=generic_preparation,
            text_preparation_facts=prepared.preparation_facts,
            text_leakage_facts=leakage,
            text_vectorization_facts=estimator.fit_vectorization_facts,
            path=holdout_path,
        )
        payload: dict[str, Any] = {
            "task_id": request.task_id,
            "evaluation_kind": request.evaluation_kind,
            "evaluation_policy": request.evaluation_policy,
            "model_key": cls.key,
            "params": params.model_dump(mode="json"),
            "model_artifact_path": str(model_path),
            "final_model_artifact_path": str(final_model_path),
            "holdout_artifact_path": str(holdout_path),
            "split_facts": split.split_facts,
            "preparation_facts": generic_preparation,
            "training_scopes": TrainingScopeFacts(
                evaluation_model="holdout_train_split",
                apply_model="all_eligible_rows",
            ),
            "text_preparation_specification": prepared.specification,
            "text_preparation_facts": prepared.preparation_facts,
            "text_leakage_facts": leakage,
            "text_vectorization_facts": estimator.fit_vectorization_facts,
            "result_summary": _multilingual_result_summary(prepared, split, estimator.fit_vectorization_facts),
        }
        return FitTaskResult.model_validate(payload)

    @classmethod
    def _fit_cross_validation(
        cls, request: FitTaskRequest, task_dir: Path,
        params: MultilingualTextClassificationParams, preparer: TextPreparer,
        prepared: PreparedTextClassificationData,
    ) -> FitTaskResult:
        model_path, final_path, evidence_path = _multilingual_artifact_paths(cls.key, task_dir)
        write_cross_validation(
            prepared, build_estimator=lambda: cls._build_estimator(preparer, params),
            policy=request.evaluation_policy, source_sha256=request.dataset_snapshot.source_sha256,
            path=evidence_path,
        )
        final = cls._build_estimator(preparer, params)
        final.text_column = _single_role_column(request.train_role_bindings, "text")
        final.fit(prepared.raw_texts, prepared.labels)
        joblib.dump(final, model_path)
        joblib.dump(final, final_path)
        return FitTaskResult(
            task_id=request.task_id, evaluation_kind=request.evaluation_kind, evaluation_policy=request.evaluation_policy,
            model_key=cls.key, params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path), final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            training_scopes=TrainingScopeFacts(evaluation_model="out_of_fold_partitions", apply_model="all_eligible_rows"),
            text_preparation_specification=prepared.specification,
            text_preparation_facts=prepared.preparation_facts,
            text_vectorization_facts=final.fit_vectorization_facts,
            result_summary={"class_count": int(prepared.labels.nunique()),
                "apply_row_count": len(prepared.labels), "text_strategy": preparer.specification.text_strategy},
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        del request, task_dir
        raise ValidationError(
            "Multilingual text classification v1 does not admit hyperparameter tuning with staged resources."
        )

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        del task_dir
        if request.evaluation_policy.split_strategy == "group_kfold.v1":
            return EvaluateTaskResult(
                task_id=request.task_id, evaluation_kind=request.evaluation_kind, evaluation_policy=request.evaluation_policy,
                trained_model_id=request.evaluate_model.trained_model_id, model_key=cls.key,
                **read_cross_validation(Path(request.evaluate_model.holdout_artifact_path), request.evaluation_policy),
            )
        estimator = joblib.load(request.evaluate_model.trained_model_artifact_path)
        if not isinstance(estimator, MultilingualTextClassifier):
            raise ValidationError("The evaluation artifact is not a retained multilingual text classifier.")
        holdout = load_holdout_frame(Path(request.evaluate_model.holdout_artifact_path))
        baseline_target, stored_split, generic_preparation = read_evaluation_context(holdout)
        stored_text_facts = _read_multilingual_holdout_context(holdout)
        prepared = _prepare_multilingual_request_data(request, estimator.preparer)
        split = prepare_supervised_split(
            prepared.raw_texts,
            prepared.labels,
            request,
            groups=prepared.connected_groups,
        )
        leakage = build_text_leakage_facts(
            prepared,
            train_positions=split.train_positions,
            holdout_positions=split.holdout_positions,
        )
        _require_zero_text_leakage(leakage)
        train_corpus = estimator.prepare(split.train_features)
        recomputed_fit_vectorization = build_text_vectorization_facts(
            estimator.vectorizer,
            train_corpus.prepared_texts,
            fit_row_count=len(split.train_target.index),
        )
        _verify_recomputed_text_context(
            holdout,
            split.holdout_features,
            split.holdout_target,
            text_column=_single_role_column(request.train_role_bindings, "text"),
            target_column=_single_role_column(request.train_role_bindings, "target"),
            stored_split=stored_split,
            recomputed_split=split.split_facts,
            stored_text_facts=stored_text_facts,
            recomputed_preparation=prepared.preparation_facts,
            recomputed_leakage=leakage,
            recomputed_fit_vectorization=recomputed_fit_vectorization,
        )
        predictions = estimator.predict(split.holdout_features)
        probabilities = estimator.predict_proba(split.holdout_features)
        metrics = build_metric_snapshot(
            request.evaluation_kind,
            split.holdout_target,
            predictions,
            y_proba=probabilities,
            classes=estimator.classes_,
        )
        baseline_metrics = build_dummy_baseline_metrics(
            request.evaluation_kind,
            baseline_target,
            split.holdout_target,
        )
        holdout_corpus = estimator.prepare(split.holdout_features)
        vectorization = build_text_vectorization_facts(
            estimator.vectorizer,
            holdout_corpus.prepared_texts,
            fit_row_count=estimator.fit_vectorization_facts.fit_row_count,
        )
        text_evaluation = TextClassificationEvaluationFacts(
            specification=estimator.preparer.specification,
            preparation=prepared.preparation_facts,
            leakage=leakage,
            vectorization=vectorization,
            prediction_digest=evaluation_prediction_digest(predictions.tolist()),
        )
        payload: dict[str, Any] = {
            "task_id": request.task_id,
            "evaluation_kind": request.evaluation_kind,
            "evaluation_policy": request.evaluation_policy,
            "trained_model_id": request.evaluate_model.trained_model_id,
            "model_key": cls.key,
            "evaluation": metrics,
            "baseline_evaluation": baseline_metrics,
            "comparison": build_evaluation_comparison(request.evaluation_policy, metrics, baseline_metrics),
            "split_facts": split.split_facts,
            "preparation_facts": generic_preparation,
            "text_classification_evaluation": text_evaluation,
        }
        return EvaluateTaskResult.model_validate(payload)

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        estimator = joblib.load(request.apply_model.trained_model_artifact_path)
        if not isinstance(estimator, MultilingualTextClassifier):
            raise ValidationError("The apply artifact is not a retained multilingual text classifier.")
        text_column = _single_role_column_from_artifact(estimator, request.feature_columns)
        result_frames: list[pd.DataFrame] = []
        inspected_texts: list[pd.Series] = []
        inspected_coverage: list[pd.DataFrame] = []
        all_predictions: list[Any] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if text_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
            texts = _as_text_series(dataframe[text_column])
            predictions = estimator.predict(texts)
            probabilities = estimator.predict_proba(texts)
            result_frame = dataframe.copy()
            result_frame["prediction"] = predictions
            result_frame["prediction_score"] = probabilities.max(axis=1).astype(float)
            coverage = estimator.feature_coverage(texts)
            inspected_coverage.append(coverage)
            for column in coverage:
                result_frame[column] = coverage[column].to_numpy()
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)
            inspected_texts.append(texts)
            all_predictions.extend(predictions.tolist())
        output_path = _write_apply_output(task_dir, "multilingual_text_classification_predictions.csv", result_frames)
        combined_texts = pd.concat(inspected_texts, ignore_index=True)
        corpus = estimator.prepare(combined_texts)
        vectorization = build_text_vectorization_facts(
            estimator.vectorizer,
            corpus.prepared_texts,
            fit_row_count=estimator.fit_vectorization_facts.fit_row_count,
        )
        apply_facts = TextClassificationApplyFacts(
            feature_coverage={
                "text_strategy": getattr(estimator.preparer.specification, "text_strategy", "words"),
                "no_known_features_row_count": int(sum((frame.known_feature_count == 0).sum() for frame in inspected_coverage)),
                "mean_feature_coverage": float(pd.concat(inspected_coverage).feature_coverage.mean()),
                "interpretation": "Coverage counts recognized feature occurrences, not correctness. prediction_score is uncalibrated maximum class probability; zero-feature rows are bias-only predictions.",
            },
            specification=estimator.preparer.specification,
            preparation=corpus.quality_facts,
            vectorization=vectorization,
            prediction_digest=evaluation_prediction_digest(all_predictions),
        )
        payload: dict[str, Any] = {
            "task_id": request.task_id,
            "trained_model_id": request.apply_model.trained_model_id,
            "model_key": cls.key,
            "output_file_path": str(output_path),
            "summary": ApplySummary(
                row_count=sum(len(frame.index) for frame in result_frames),
                input_file_count=len(request.input_files),
                prediction_column_name="prediction",
            ),
            "source_dataset_ids": [item.dataset_id for item in request.input_files if item.dataset_id],
            "source_artifact_ids": [item.artifact_id for item in request.input_files if item.artifact_id],
            "text_classification_apply_facts": apply_facts,
        }
        return ApplyTaskResult.model_validate(payload)

    @classmethod
    def _build_estimator(
        cls,
        preparer: TextPreparer,
        params: MultilingualTextClassificationParams,
    ) -> MultilingualTextClassifier:
        return MultilingualTextClassifier(
            preparer=preparer,
            max_features=params.max_features,
            minimum_document_frequency=params.minimum_document_frequency,
            class_weight=params.class_weight,
        )
