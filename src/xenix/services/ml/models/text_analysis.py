from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Protocol

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from sklearn.base import clone
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import GridSearchCV

from ....exceptions import ValidationError
from ...data_tokenization_contracts import TextPreparationInput
from ...storage.models import ProblemKind
from ..contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    CandidateMetrics,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    PreparationFacts,
    SplitFacts,
    TrainingScopeFacts,
    TuningSummary,
)
from ..dataset_loader import load_dataset, load_holdout_frame
from ..digests import prediction_digest as evaluation_prediction_digest
from ..evaluation import (
    build_dummy_baseline_metrics,
    build_evaluation_comparison,
    build_metric_snapshot,
    scoring_name_for_policy,
)
from ..preparation import (
    PreparedSupervisedSplit,
    attach_evaluation_context,
    build_group_aware_cv,
    build_text_preparation_facts,
    dataset_snapshot_digest,
    prepare_supervised_split,
    read_evaluation_context,
)
from ..text_discovery import (
    MultilingualTextClusterer,
    MultilingualTextRetriever,
    MultilingualTopicDiscoverer,
    TextClusteringEvaluationFacts,
    TextRetrievalEvaluationFacts,
    TextTopicEvaluationFacts,
    prepare_discovery_corpus,
)
from ..text_preparation import (
    PreparedTextClassificationData,
    PreparedTextCorpus,
    TextClassificationApplyFacts,
    TextClassificationEvaluationFacts,
    TextLeakageFacts,
    TextPreparationQualityFacts,
    TextPreparer,
    TextVectorizationFacts,
    build_text_leakage_facts,
    build_text_preparer,
    build_text_vectorization_facts,
    prepare_text_classification_data,
)
from ..types import (
    ColumnRoleKind,
    EvaluationKind,
    ModelFamily,
    ModelResultContract,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)

_TEXT_RANDOM_STATE = 42
_TEXT_EVALUATION_CONTEXT_KEY = "xenix.text_classification_context.v1"


class MultilingualTextClassificationParams(BaseModel):
    preparation_profile: Literal["multilingual_business_v1"] = "multilingual_business_v1"
    phrase_mode: Literal["unigram", "unigram_bigram"] = "unigram"
    max_features: int = Field(default=5000, ge=200, le=50000)
    minimum_document_frequency: int = Field(default=1, ge=1, le=20)
    class_weight: Literal["balanced", "none"] = "balanced"
    custom_dictionary_dataset_ids: list[str] = Field(default_factory=list, max_length=4)
    stopword_dataset_ids: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("custom_dictionary_dataset_ids", "stopword_dataset_ids")
    @classmethod
    def _resource_dataset_ids_must_be_bounded_references(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 128 for value in values):
            raise ValueError("Text preparation Dataset IDs must contain 1 to 128 non-whitespace characters.")
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
        self.vectorizer = TfidfVectorizer(
            tokenizer=str.split,
            preprocessor=None,
            token_pattern=None,
            lowercase=False,
            max_features=self.max_features,
            min_df=self.minimum_document_frequency,
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

    @property
    def classes_(self) -> np.ndarray:
        return np.asarray(self.model.classes_)


class TokenizedTextClassificationParams(BaseModel):
    max_features: int = Field(default=3000, ge=200, le=50000)
    ngram_max: int = Field(default=1, ge=1, le=2)
    c: float = Field(default=1.0, gt=0.0, le=100.0)
    max_iter: int = Field(default=500, ge=100, le=5000)


class TokenizedTextClassificationParamGrid(BaseModel):
    max_features: list[int] = Field(default=[2000, 5000])
    ngram_max: list[int] = Field(default=[1, 2])
    c: list[float] = Field(default=[0.5, 1.0, 2.0])


class TokenizedTextClusteringParams(BaseModel):
    n_clusters: int = Field(default=4, ge=2, le=20)
    max_features: int = Field(default=3000, ge=200, le=50000)
    ngram_max: int = Field(default=1, ge=1, le=2)
    max_iter: int = Field(default=300, ge=50, le=2000)


class TokenizedTextTopicModelingParams(BaseModel):
    topic_count: int = Field(default=4, ge=2, le=20)
    max_features: int = Field(default=3000, ge=200, le=50000)
    max_iter: int = Field(default=20, ge=5, le=200)
    top_terms_per_topic: int = Field(default=8, ge=3, le=20)


class TokenizedTextSimilarityParams(BaseModel):
    max_features: int = Field(default=3000, ge=200, le=50000)
    ngram_max: int = Field(default=1, ge=1, le=2)
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0.1, ge=0.0, le=1.0)


class _TextDiscoveryParams(Protocol):
    @property
    def preparation_profile(self) -> str: ...

    @property
    def phrase_mode(self) -> str: ...

    @property
    def custom_dictionary_dataset_ids(self) -> list[str]: ...

    @property
    def stopword_dataset_ids(self) -> list[str]: ...


class _MultilingualDiscoveryParamsBase(BaseModel):
    preparation_profile: Literal["multilingual_business_v1"] = "multilingual_business_v1"
    phrase_mode: Literal["unigram", "unigram_bigram"] = "unigram"
    max_features: int = Field(default=5000, ge=200, le=50000)
    custom_dictionary_dataset_ids: list[str] = Field(default_factory=list, max_length=4)
    stopword_dataset_ids: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("custom_dictionary_dataset_ids", "stopword_dataset_ids")
    @classmethod
    def _resource_ids_are_bounded_and_unique(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 128 for value in values):
            raise ValueError("Text preparation Dataset IDs must contain 1 to 128 non-whitespace characters.")
        if len(values) != len(set(values)):
            raise ValueError("Text preparation Dataset IDs cannot contain duplicates.")
        return values


class MultilingualTextClusteringParams(_MultilingualDiscoveryParamsBase):
    n_clusters: int = Field(default=4, ge=2, le=20)
    displayed_term_count: int = Field(default=8, ge=3, le=12)


class MultilingualTextTopicModelingParams(_MultilingualDiscoveryParamsBase):
    topic_count: int = Field(default=4, ge=2, le=20)
    displayed_term_count: int = Field(default=8, ge=3, le=12)


class MultilingualTextRetrievalParams(_MultilingualDiscoveryParamsBase):
    top_k: int = Field(default=5, ge=1, le=50)
    minimum_similarity: float = Field(default=0.1, ge=0.0, le=1.0)


class MultilingualTextClassificationService(ModelServiceBase):
    key = "text.classification.multilingual_logistic_regression_tfidf"
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
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        del request, task_dir
        raise ValidationError(
            "Multilingual text classification v1 does not admit hyperparameter tuning with staged resources."
        )

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        del task_dir
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


class TokenizedTextClassificationService(ModelServiceBase):
    key = "text.classification.logistic_regression_tfidf"
    display_name = "Tokenized Text Classification"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Text classification"
    guidance = "Predicts one label from a tokenized Chinese text column using TF-IDF and logistic regression."
    recommendation_tier = 25
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.PREDICTOR
    params_model = TokenizedTextClassificationParams
    param_grid_model = TokenizedTextClassificationParamGrid
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Pre-tokenized text column, typically token_text from data.tokenize.",
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
                description=(
                    "Optional business entity whose rows must remain together across evaluation partitions."
                ),
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
                description="Pre-tokenized text column used for prediction.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = cls.validate_params(request.manual_training.params)
        text_column = _single_role_column(request.train_role_bindings, "text")
        target_column = _single_role_column(request.train_role_bindings, "target")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        texts, labels, groups = _prepare_supervised_text(
            dataframe,
            text_column=text_column,
            target_column=target_column,
            group_column=group_column,
        )
        prepared = _text_train_test_split(texts, labels, request, groups=groups)
        train_texts = prepared.train_features
        holdout_texts = prepared.holdout_features
        train_labels = prepared.train_target
        holdout_labels = prepared.holdout_target

        estimator = cls._build_estimator(params)
        estimator.text_column = text_column
        estimator.fit(train_texts, train_labels)
        preparation_facts = build_text_preparation_facts(estimator, fit_row_count=len(train_texts.index))
        final_estimator = cls._build_estimator(params)
        final_estimator.text_column = text_column
        final_estimator.fit(texts, labels)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        final_model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}-final.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        joblib.dump(final_estimator, final_model_artifact_path)
        _save_text_holdout(
            holdout_texts,
            holdout_labels,
            train_labels,
            text_column=text_column,
            target_column=target_column,
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            path=holdout_artifact_path,
        )

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(final_model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            result_summary={
                "class_count": int(labels.nunique(dropna=True)),
                "train_row_count": int(len(train_texts.index)),
                "holdout_row_count": int(len(holdout_texts.index)),
                "evaluation_model_training_scope": "holdout_train_split",
                "apply_model_training_scope": "all_eligible_rows",
                "text_column": text_column,
                "target_column": target_column,
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        grid = cls.validate_param_grid(request.hyperparameter_tuning.param_grid)
        text_column = _single_role_column(request.train_role_bindings, "text")
        target_column = _single_role_column(request.train_role_bindings, "target")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        texts, labels, groups = _prepare_supervised_text(
            dataframe,
            text_column=text_column,
            target_column=target_column,
            group_column=group_column,
        )
        prepared = _text_train_test_split(texts, labels, request, groups=groups)
        train_texts = prepared.train_features
        holdout_texts = prepared.holdout_features
        train_labels = prepared.train_target
        holdout_labels = prepared.holdout_target

        cv, fit_groups = build_group_aware_cv(
            request.evaluation_policy,
            request.evaluation_kind,
            train_labels,
            prepared.train_groups,
        )

        search = GridSearchCV(
            estimator=cls._build_estimator(),
            param_grid={
                "vectorizer__max_features": grid.max_features,
                "vectorizer__ngram_range": [(1, int(value)) for value in grid.ngram_max],
                "model__C": grid.c,
            },
            cv=cv,
            scoring=scoring_name_for_policy(request.evaluation_policy),
            n_jobs=1,
        )
        search.fit(train_texts, train_labels, groups=fit_groups)
        estimator = search.best_estimator_
        estimator.text_column = text_column
        preparation_facts = build_text_preparation_facts(estimator, fit_row_count=len(train_texts.index))
        final_estimator = clone(search.best_estimator_)
        final_estimator.text_column = text_column
        final_estimator.fit(texts, labels)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        final_model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}-final.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        joblib.dump(final_estimator, final_model_artifact_path)
        _save_text_holdout(
            holdout_texts,
            holdout_labels,
            train_labels,
            text_column=text_column,
            target_column=target_column,
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            path=holdout_artifact_path,
        )

        return HyperparameterTuningTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            best_params=_serialize_search_best_params(search.best_params_),
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(final_model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            result_summary={
                "class_count": int(labels.nunique(dropna=True)),
                "train_row_count": int(len(train_texts.index)),
                "holdout_row_count": int(len(holdout_texts.index)),
                "evaluation_model_training_scope": "holdout_train_split",
                "apply_model_training_scope": "all_eligible_rows",
                "text_column": text_column,
                "target_column": target_column,
            },
            tuning_summary=TuningSummary(
                best_params=_serialize_search_best_params(search.best_params_),
                cv_summary={
                    "best_score": float(search.best_score_),
                    "candidate_count": len(search.cv_results_["params"]),
                },
            ),
        )

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        estimator = joblib.load(request.evaluate_model.trained_model_artifact_path)
        holdout = load_holdout_frame(Path(request.evaluate_model.holdout_artifact_path))
        baseline_training_target, split_facts, preparation_facts = read_evaluation_context(holdout)
        text_column = _single_role_column(request.train_role_bindings, "text")
        target_column = _single_role_column(request.train_role_bindings, "target")
        texts = _normalize_token_text_series(holdout[text_column])
        labels = holdout[target_column].copy()
        predictions = estimator.predict(texts)
        probabilities = estimator.predict_proba(texts) if hasattr(estimator, "predict_proba") else None
        classes = getattr(estimator, "classes_", None)
        metrics = build_metric_snapshot(
            request.evaluation_kind,
            labels,
            predictions,
            y_proba=probabilities,
            classes=classes,
        )
        baseline_metrics = build_dummy_baseline_metrics(
            request.evaluation_kind,
            baseline_training_target,
            labels,
        )
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=metrics,
            baseline_evaluation=baseline_metrics,
            comparison=build_evaluation_comparison(request.evaluation_policy, metrics, baseline_metrics),
            split_facts=split_facts,
            preparation_facts=preparation_facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        estimator = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _single_role_column_from_artifact(estimator, request.feature_columns)
        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if text_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
            texts = _normalize_token_text_series(dataframe[text_column])
            predictions = estimator.predict(texts)
            result_frame = dataframe.copy()
            result_frame["prediction"] = predictions
            if hasattr(estimator, "predict_proba"):
                scores = estimator.predict_proba(texts).max(axis=1)
                result_frame["prediction_score"] = [float(score) for score in scores]
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_path = _write_apply_output(task_dir, "text_classification_predictions.csv", result_frames)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=int(sum(len(frame.index) for frame in result_frames)),
                input_file_count=len(request.input_files),
                prediction_column_name="prediction",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
        )

    @classmethod
    def _build_estimator(cls, params: TokenizedTextClassificationParams | None = None):
        typed = TokenizedTextClassificationParams.model_validate(params or {})
        vectorizer = TfidfVectorizer(
            tokenizer=str.split,
            preprocessor=None,
            token_pattern=None,
            lowercase=False,
            max_features=typed.max_features,
            ngram_range=(1, typed.ngram_max),
        )
        model = LogisticRegression(
            C=typed.c,
            max_iter=typed.max_iter,
            random_state=_TEXT_RANDOM_STATE,
        )
        estimator = _TextVectorizerClassifier(vectorizer=vectorizer, model=model)
        estimator.text_column = None
        return estimator


class MultilingualTextClusteringService(ModelServiceBase):
    key = "text.clustering.multilingual_kmeans_tfidf"
    display_name = "Multilingual Raw Text Clustering"
    problem_kind = ProblemKind.CLUSTERING
    evaluation_kind = EvaluationKind.TEXT_CLUSTERING
    family = "Text clustering"
    guidance = "Explores bilingual raw text structure with retained preparation and recomputable cosine evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.TEXT_ANALYZER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextClusteringParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw business text prepared inside the retained clusterer.",
            ),
            ModelRoleDefinition(
                name="group",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional business entity joined with template groups for stability resampling.",
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
                description="Raw text transformed by the exact retained preparation specification.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextClusteringParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=group_column,
            preparer=preparer,
            minimum_rows=max(4, params.n_clusters + 1),
        )
        analyzer = MultilingualTextClusterer(
            preparer=preparer,
            n_clusters=params.n_clusters,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        ).fit(prepared)
        analyzer.text_column = text_column
        analyzer.group_column = group_column
        evaluation = analyzer.evaluate(prepared)
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(analyzer, model_path)
        joblib.dump(analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, dataset_snapshot_digest(request.dataset_snapshot))
        _write_json_report(report_path, evaluation.facts)
        cluster_output = dataframe.copy()
        cluster_output["cluster_label"] = pd.NA
        cluster_output.iloc[
            prepared.source_positions,
            cluster_output.columns.get_loc("cluster_label"),
        ] = evaluation.labels.tolist()
        cluster_output.to_csv(export_path, index=False)
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="all_eligible_rows",
                apply_model="all_eligible_rows",
            ),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_clustering_evaluation=evaluation.facts,
            result_summary=_cluster_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTextClusterer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=analyzer.group_column,
            preparer=analyzer.preparer,
            minimum_rows=max(4, analyzer.n_clusters + 1),
        )
        facts = analyzer.evaluate(prepared).facts
        _verify_discovery_evidence(
            Path(request.evaluate_model.holdout_artifact_path),
            facts,
            dataset_snapshot_digest(request.dataset_snapshot),
        )
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_cluster_candidate_metrics(facts),
            text_clustering_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTextClusterer = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        application = analyzer.apply(texts)
        output = pd.concat(frames, ignore_index=True)
        if len(frames) > 1:
            output["source_file"] = [item["source_file"] for item in locations]
        output["cluster_label"] = application.labels
        output_path = task_dir / "output" / "text_cluster_assignments.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output.index),
                input_file_count=len(frames),
                prediction_column_name="cluster_label",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_clustering_apply_facts=application.facts,
        )


class MultilingualTextTopicModelingService(ModelServiceBase):
    key = "text.topic_modeling.multilingual_lda"
    display_name = "Multilingual Raw Text Topic Discovery"
    problem_kind = ProblemKind.TOPIC_MODELING
    evaluation_kind = EvaluationKind.TOPIC_MODELING
    family = "Topic modeling"
    guidance = "Explores bilingual raw text topics with group-safe heldout and permutation-matched stability evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.TEXT_ANALYZER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextTopicModelingParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw business text prepared inside the retained topic analyzer.",
            ),
            ModelRoleDefinition(
                name="group",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional business entity joined with template groups for heldout isolation.",
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
                description="Raw text transformed by the exact retained topic preparation specification.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextTopicModelingParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=group_column,
            preparer=preparer,
            minimum_rows=max(8, params.topic_count + 2),
        )
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        evaluation_analyzer = MultilingualTopicDiscoverer(
            preparer=preparer,
            topic_count=params.topic_count,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        )
        evaluation = evaluation_analyzer.fit_evaluation(
            prepared,
            source_dataset_snapshot_digest=snapshot_digest,
        )
        evaluation_analyzer.text_column = text_column
        evaluation_analyzer.group_column = group_column
        final_analyzer = MultilingualTopicDiscoverer(
            preparer=preparer,
            topic_count=params.topic_count,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        ).fit_all(prepared, evaluation_reference=evaluation_analyzer)
        final_analyzer.text_column = text_column
        final_analyzer.group_column = group_column
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(evaluation_analyzer, model_path)
        joblib.dump(final_analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, snapshot_digest)
        _write_json_report(report_path, evaluation.facts)
        full_application = final_analyzer.apply(prepared.raw_texts)
        _append_topic_outputs(dataframe, prepared.source_positions, full_application.distributions).to_csv(
            export_path,
            index=False,
        )
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="connected_group_train_split",
                apply_model="all_eligible_rows",
            ),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_topic_evaluation=evaluation.facts,
            result_summary=_topic_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTopicDiscoverer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=analyzer.group_column,
            preparer=analyzer.preparer,
            minimum_rows=max(8, analyzer.topic_count + 2),
        )
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        facts = analyzer.recompute_evaluation(
            prepared,
            source_dataset_snapshot_digest=snapshot_digest,
        ).facts
        _verify_discovery_evidence(Path(request.evaluate_model.holdout_artifact_path), facts, snapshot_digest)
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_topic_candidate_metrics(facts),
            text_topic_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTopicDiscoverer = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        application = analyzer.apply(texts)
        output = _append_topic_outputs(
            pd.concat(frames, ignore_index=True),
            np.arange(len(locations), dtype=int),
            application.distributions,
        )
        if len(frames) > 1:
            output["source_file"] = [item["source_file"] for item in locations]
        output_path = task_dir / "output" / "text_topic_distributions.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output.index),
                input_file_count=len(frames),
                prediction_column_name="dominant_topic",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_topic_apply_facts=application.facts,
        )


class MultilingualTextSimilarityService(ModelServiceBase):
    key = "text.similarity.multilingual_tfidf_cosine"
    display_name = "Multilingual Local Text Retrieval"
    problem_kind = ProblemKind.RETRIEVAL
    evaluation_kind = EvaluationKind.RETRIEVAL
    family = "Similarity retrieval"
    guidance = "Builds a retained local raw-text index with self-excluding Top-K and truth-gated ranking evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.RETRIEVER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextRetrievalParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(name="text", kind=ColumnRoleKind.SINGLE_COLUMN, required=True),
            ModelRoleDefinition(name="document_id", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
            ModelRoleDefinition(name="relevance_group", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(name="text", kind=ColumnRoleKind.SINGLE_COLUMN, required=True),
            ModelRoleDefinition(name="document_id", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextRetrievalParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        document_id_column = _optional_role_column(request.train_role_bindings, "document_id")
        relevance_group_column = _optional_role_column(request.train_role_bindings, "relevance_group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=None,
            preparer=preparer,
            minimum_rows=2,
        )
        document_ids = _eligible_role_values(dataframe, prepared.source_positions, document_id_column)
        relevance_groups = _eligible_role_values(dataframe, prepared.source_positions, relevance_group_column)
        analyzer = MultilingualTextRetriever(
            preparer=preparer,
            max_features=params.max_features,
            top_k=params.top_k,
            minimum_similarity=params.minimum_similarity,
        ).fit(prepared, document_ids=document_ids, relevance_groups=relevance_groups)
        analyzer.text_column = text_column
        analyzer.document_id_column = document_id_column
        analyzer.relevance_group_column = relevance_group_column
        evaluation = analyzer.evaluate(prepared)
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(analyzer, model_path)
        joblib.dump(analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, snapshot_digest)
        _write_json_report(report_path, evaluation.facts)
        _retrieval_export_frame(analyzer, evaluation.matches).to_csv(export_path, index=False)
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(evaluation_model="full_local_index", apply_model="full_local_index"),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_retrieval_evaluation=evaluation.facts,
            result_summary=_retrieval_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTextRetriever = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=None,
            preparer=analyzer.preparer,
            minimum_rows=2,
        )
        _verify_retrieval_source_identities(analyzer, dataframe, prepared.source_positions)
        facts = analyzer.evaluate(prepared).facts
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        _verify_discovery_evidence(Path(request.evaluate_model.holdout_artifact_path), facts, snapshot_digest)
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_retrieval_candidate_metrics(facts),
            text_retrieval_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTextRetriever = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        query_ids = _concat_optional_apply_column(frames, analyzer.document_id_column)
        application = analyzer.apply(texts, document_ids=query_ids)
        output_rows = []
        query_frame = pd.concat(frames, ignore_index=True)
        for match in application.matches:
            location = locations[match.query_position]
            output_rows.append(
                {
                    **query_frame.iloc[match.query_position].to_dict(),
                    **location,
                    "matched_document_id": analyzer.matched_document_id(match.matched_document_position),
                    "matched_text": analyzer.matched_document_text(match.matched_document_position),
                    "rank": match.rank,
                    "similarity": match.similarity,
                }
            )
        output_path = task_dir / "output" / "text_similarity_matches.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(output_rows).to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output_rows),
                input_file_count=len(frames),
                prediction_column_name="matched_document_id",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_retrieval_apply_facts=application.facts,
        )


class TokenizedTextClusteringService(ModelServiceBase):
    key = "text.clustering.kmeans_tfidf"
    display_name = "Tokenized Text Clustering"
    problem_kind = ProblemKind.CLUSTERING
    evaluation_kind = EvaluationKind.SUMMARY
    summary_metric_name = "cluster_count"
    family = "Text clustering"
    guidance = "Groups tokenized Chinese text rows into clusters using TF-IDF and KMeans."
    recommendation_tier = 35
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.SEGMENTER
    requires_target = False
    supports_hyperparameter_tuning = False
    params_model = TokenizedTextClusteringParams
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Pre-tokenized text column, typically token_text from data.tokenize.",
            )
        ],
        additional_roles=False,
    )
    apply_role_schema = train_role_schema

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = cls.validate_params(request.manual_training.params)
        text_column = _single_role_column(request.train_role_bindings, "text")
        texts = _normalize_token_text_series(dataframe[text_column])
        non_empty_mask = texts.ne("")
        if not non_empty_mask.any():
            raise ValidationError("Text clustering requires at least one non-empty tokenized text row.")
        vectorizer = _tfidf_vectorizer(max_features=params.max_features, ngram_max=params.ngram_max)
        matrix = vectorizer.fit_transform(texts.loc[non_empty_mask])
        model = KMeans(
            n_clusters=params.n_clusters,
            n_init=10,
            max_iter=params.max_iter,
            random_state=_TEXT_RANDOM_STATE,
        )
        labels = model.fit_predict(matrix)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "text_cluster_assignments.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model_key": cls.key,
            "text_column": text_column,
            "vectorizer": vectorizer,
            "model": model,
            "params": params.model_dump(mode="json"),
            "top_terms_by_cluster": _top_terms_from_centers(
                model.cluster_centers_,
                vectorizer.get_feature_names_out(),
                top_n=8,
                label_prefix="cluster",
            ),
        }
        joblib.dump(artifact, model_artifact_path)

        result_frame = dataframe.copy()
        result_frame["cluster_id"] = pd.NA
        result_frame.loc[non_empty_mask, "cluster_id"] = [int(value) for value in labels]
        result_frame.to_csv(export_artifact_path, index=False)

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "cluster_count": int(params.n_clusters),
                "trained_row_count": int(non_empty_mask.sum()),
                "empty_text_row_count": int((~non_empty_mask).sum()),
                "text_column": text_column,
                "top_terms_by_cluster": artifact["top_terms_by_cluster"],
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support evaluation.")

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        artifact = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = str(artifact.get("text_column") or (request.feature_columns[0] if request.feature_columns else ""))
        vectorizer = artifact["vectorizer"]
        model = artifact["model"]
        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if text_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
            texts = _normalize_token_text_series(dataframe[text_column])
            non_empty_mask = texts.ne("")
            result_frame = dataframe.copy()
            result_frame["cluster_id"] = pd.NA
            if non_empty_mask.any():
                predictions = model.predict(vectorizer.transform(texts.loc[non_empty_mask]))
                result_frame.loc[non_empty_mask, "cluster_id"] = [int(value) for value in predictions]
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_path = _write_apply_output(task_dir, "text_cluster_predictions.csv", result_frames)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=int(sum(len(frame.index) for frame in result_frames)),
                input_file_count=len(request.input_files),
                prediction_column_name="cluster_id",
            ),
        )


class TokenizedTextTopicModelingService(ModelServiceBase):
    key = "text.topic_modeling.lda"
    display_name = "Tokenized Topic Modeling"
    evaluation_kind = EvaluationKind.SUMMARY
    summary_metric_name = "topic_count"
    family = "Topic modeling"
    guidance = "Finds recurring tokenized Chinese text themes using CountVectorizer and LDA."
    recommendation_tier = 40
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.SEGMENTER
    requires_target = False
    supports_hyperparameter_tuning = False
    params_model = TokenizedTextTopicModelingParams
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Pre-tokenized text column, typically token_text from data.tokenize.",
            )
        ],
        additional_roles=False,
    )
    apply_role_schema = train_role_schema

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = cls.validate_params(request.manual_training.params)
        text_column = _single_role_column(request.train_role_bindings, "text")
        texts = _normalize_token_text_series(dataframe[text_column])
        non_empty_mask = texts.ne("")
        if not non_empty_mask.any():
            raise ValidationError("Topic modeling requires at least one non-empty tokenized text row.")

        vectorizer = CountVectorizer(
            tokenizer=str.split,
            preprocessor=None,
            token_pattern=None,
            lowercase=False,
            max_features=params.max_features,
        )
        matrix = vectorizer.fit_transform(texts.loc[non_empty_mask])
        model = LatentDirichletAllocation(
            n_components=params.topic_count,
            max_iter=params.max_iter,
            learning_method="batch",
            random_state=_TEXT_RANDOM_STATE,
        )
        topic_matrix = model.fit_transform(matrix)
        dominant_topics = topic_matrix.argmax(axis=1)
        dominant_scores = topic_matrix.max(axis=1)
        top_terms_by_topic = _top_terms_from_centers(
            model.components_,
            vectorizer.get_feature_names_out(),
            top_n=params.top_terms_per_topic,
            label_prefix="topic",
        )

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "topic_assignments.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model_key": cls.key,
            "text_column": text_column,
            "vectorizer": vectorizer,
            "model": model,
            "params": params.model_dump(mode="json"),
            "top_terms_by_topic": top_terms_by_topic,
        }
        joblib.dump(artifact, model_artifact_path)

        result_frame = dataframe.copy()
        result_frame["dominant_topic"] = pd.NA
        result_frame["topic_score"] = pd.NA
        result_frame.loc[non_empty_mask, "dominant_topic"] = [int(value) for value in dominant_topics]
        result_frame.loc[non_empty_mask, "topic_score"] = [float(value) for value in dominant_scores]
        result_frame.to_csv(export_artifact_path, index=False)

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "topic_count": int(params.topic_count),
                "trained_row_count": int(non_empty_mask.sum()),
                "empty_text_row_count": int((~non_empty_mask).sum()),
                "text_column": text_column,
                "top_terms_by_topic": top_terms_by_topic,
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support evaluation.")

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        artifact = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = str(artifact.get("text_column") or (request.feature_columns[0] if request.feature_columns else ""))
        vectorizer = artifact["vectorizer"]
        model = artifact["model"]
        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if text_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
            texts = _normalize_token_text_series(dataframe[text_column])
            non_empty_mask = texts.ne("")
            result_frame = dataframe.copy()
            result_frame["dominant_topic"] = pd.NA
            result_frame["topic_score"] = pd.NA
            if non_empty_mask.any():
                topic_matrix = model.transform(vectorizer.transform(texts.loc[non_empty_mask]))
                result_frame.loc[non_empty_mask, "dominant_topic"] = [int(value) for value in topic_matrix.argmax(axis=1)]
                result_frame.loc[non_empty_mask, "topic_score"] = [float(value) for value in topic_matrix.max(axis=1)]
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_path = _write_apply_output(task_dir, "topic_predictions.csv", result_frames)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=int(sum(len(frame.index) for frame in result_frames)),
                input_file_count=len(request.input_files),
                prediction_column_name="dominant_topic",
            ),
        )


class TokenizedTextSimilarityService(ModelServiceBase):
    key = "text.similarity.tfidf_cosine"
    display_name = "Tokenized Text Similarity Retrieval"
    evaluation_kind = EvaluationKind.SUMMARY
    summary_metric_name = "match_count"
    family = "Similarity retrieval"
    guidance = "Retrieves the most similar tokenized Chinese text rows using TF-IDF cosine similarity."
    recommendation_tier = 40
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.RECOMMENDER
    requires_target = False
    supports_hyperparameter_tuning = False
    params_model = TokenizedTextSimilarityParams
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Pre-tokenized text column, typically token_text from data.tokenize.",
            ),
            ModelRoleDefinition(
                name="text_id",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional identifier column returned with similar matches.",
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
                description="Pre-tokenized text column used as the similarity query.",
            )
        ],
        additional_roles=False,
    )
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = cls.validate_params(request.manual_training.params)
        text_column = _single_role_column(request.train_role_bindings, "text")
        text_id_column = _optional_role_column(request.train_role_bindings, "text_id")
        texts = _normalize_token_text_series(dataframe[text_column])
        non_empty_mask = texts.ne("")
        if not non_empty_mask.any():
            raise ValidationError("Similarity retrieval requires at least one non-empty tokenized text row.")

        vectorizer = _tfidf_vectorizer(max_features=params.max_features, ngram_max=params.ngram_max)
        indexed_texts = texts.loc[non_empty_mask]
        matrix = vectorizer.fit_transform(indexed_texts)
        index_frame = pd.DataFrame(
            {
                "source_row_number": dataframe.index[non_empty_mask].to_series(index=indexed_texts.index).add(1).tolist(),
                "text": indexed_texts.tolist(),
            },
            index=indexed_texts.index,
        )
        if text_id_column is not None:
            index_frame["text_id"] = dataframe.loc[non_empty_mask, text_id_column].tolist()

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "similarity_index.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        index_frame.to_csv(export_artifact_path, index=False)
        joblib.dump(
            {
                "model_key": cls.key,
                "text_column": text_column,
                "text_id_column": text_id_column,
                "params": params.model_dump(mode="json"),
                "vectorizer": vectorizer,
                "matrix": matrix,
                "index_rows": index_frame.to_dict(orient="records"),
            },
            model_artifact_path,
        )

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "match_count": int(len(index_frame.index)),
                "indexed_row_count": int(len(index_frame.index)),
                "empty_text_row_count": int((~non_empty_mask).sum()),
                "text_column": text_column,
                "text_id_column": text_id_column,
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support evaluation.")

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        artifact = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = str(artifact.get("text_column") or (request.feature_columns[0] if request.feature_columns else ""))
        params = TokenizedTextSimilarityParams.model_validate(artifact.get("params") or {})
        vectorizer = artifact["vectorizer"]
        matrix = artifact["matrix"]
        index_rows = [dict(row) for row in artifact.get("index_rows") or []]
        result_rows: list[dict[str, Any]] = []

        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if text_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
            texts = _normalize_token_text_series(dataframe[text_column])
            for row_number, query_text in enumerate(texts.tolist(), start=1):
                if not query_text:
                    continue
                scores = cosine_similarity(vectorizer.transform([query_text]), matrix).ravel()
                ranked_indexes = np.argsort(scores)[::-1]
                rank = 0
                for match_index in ranked_indexes:
                    similarity = float(scores[match_index])
                    if similarity < params.min_similarity:
                        continue
                    rank += 1
                    record = index_rows[int(match_index)]
                    result_rows.append(
                        {
                            "source_file": input_file.file_name,
                            "input_row_number": row_number,
                            "query_text": query_text,
                            "rank": rank,
                            "matched_source_row_number": int(record.get("source_row_number") or 0),
                            "matched_text_id": record.get("text_id"),
                            "matched_text": str(record.get("text") or ""),
                            "similarity": similarity,
                        }
                    )
                    if rank >= params.top_k:
                        break

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "text_similarity_matches.csv"
        pd.DataFrame(
            result_rows,
            columns=[
                "source_file",
                "input_row_number",
                "query_text",
                "rank",
                "matched_source_row_number",
                "matched_text_id",
                "matched_text",
                "similarity",
            ],
        ).to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(result_rows),
                input_file_count=len(request.input_files),
                prediction_column_name="matched_text",
            ),
        )


class _TextVectorizerClassifier:
    def __init__(self, *, vectorizer: TfidfVectorizer, model: LogisticRegression) -> None:
        self.vectorizer = vectorizer
        self.model = model
        self.text_column: str | None = None

    def fit(self, texts: pd.Series, labels: pd.Series):
        matrix = self.vectorizer.fit_transform(texts.tolist())
        self.model.fit(matrix, labels)
        return self

    def predict(self, texts: pd.Series):
        return self.model.predict(self.vectorizer.transform(texts.tolist()))

    def predict_proba(self, texts: pd.Series):
        return self.model.predict_proba(self.vectorizer.transform(texts.tolist()))

    @property
    def classes_(self):
        return self.model.classes_

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {"vectorizer": self.vectorizer, "model": self.model}

    def set_params(self, **params):
        for key, value in params.items():
            if key == "vectorizer":
                self.vectorizer = value
                continue
            if key == "model":
                self.model = value
                continue
            if key.startswith("vectorizer__"):
                self.vectorizer.set_params(**{key.split("__", 1)[1]: value})
                continue
            if key.startswith("model__"):
                self.model.set_params(**{key.split("__", 1)[1]: value})
                continue
            raise ValueError(f"Unsupported parameter '{key}'.")
        return self


def _single_role_column(role_bindings: list[dict[str, Any]], role: str) -> str:
    for binding in role_bindings:
        if binding.get("role") == role and isinstance(binding.get("columns"), list):
            columns = [str(column) for column in binding["columns"]]
            if len(columns) == 1:
                return columns[0]
    raise ValidationError(f"Text analysis model requires exactly one '{role}' column.")


def _optional_role_column(role_bindings: list[dict[str, Any]], role: str) -> str | None:
    for binding in role_bindings:
        if binding.get("role") == role and isinstance(binding.get("columns"), list):
            columns = [str(column) for column in binding["columns"]]
            if len(columns) == 1:
                return columns[0]
    return None


def _text_preparation_input(
    request: FitTaskRequest | HyperparameterTuningTaskRequest,
    params: MultilingualTextClassificationParams | _TextDiscoveryParams,
) -> TextPreparationInput:
    value = getattr(request, "text_preparation", None)
    if value is None:
        raise ValidationError(
            "Multilingual raw-text analysis requires worker-staged text_preparation, including explicit empty resources."
        )
    elif isinstance(value, TextPreparationInput):
        prepared_input = value
    else:
        prepared_input = TextPreparationInput.model_validate(value)
    staged_dictionary_ids = [resource.dataset_id for resource in prepared_input.custom_dictionary_resources]
    staged_stopword_ids = [resource.dataset_id for resource in prepared_input.stopword_resources]
    if prepared_input.tokenizer_profile != params.preparation_profile:
        raise ValidationError("Staged text preparation profile does not match the admitted model parameters.")
    if prepared_input.phrase_mode != params.phrase_mode:
        raise ValidationError("Staged text preparation phrase mode does not match the admitted model parameters.")
    if staged_dictionary_ids != params.custom_dictionary_dataset_ids:
        raise ValidationError("Staged custom dictionary Dataset IDs do not match the admitted model parameters.")
    if staged_stopword_ids != params.stopword_dataset_ids:
        raise ValidationError("Staged stopword Dataset IDs do not match the admitted model parameters.")
    return prepared_input


def _prepare_multilingual_request_data(
    request: FitTaskRequest | HyperparameterTuningTaskRequest | EvaluateTaskRequest,
    preparer: TextPreparer,
) -> PreparedTextClassificationData:
    dataframe = load_dataset(Path(request.dataset_source_path))
    return prepare_text_classification_data(
        dataframe,
        text_column=_single_role_column(request.train_role_bindings, "text"),
        target_column=_single_role_column(request.train_role_bindings, "target"),
        business_group_column=_optional_role_column(request.train_role_bindings, "group"),
        preparer=preparer,
    )


def _multilingual_artifact_paths(model_key: str, task_dir: Path) -> tuple[Path, Path, Path]:
    model_dir = task_dir / "models"
    input_dir = task_dir / "input"
    model_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    stem = model_key.replace(".", "_")
    return (
        model_dir / f"{stem}.joblib",
        model_dir / f"{stem}-final.joblib",
        input_dir / "multilingual_text_holdout.pkl",
    )


def _save_multilingual_holdout(
    texts: pd.Series,
    labels: pd.Series,
    training_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    split_facts: SplitFacts,
    preparation_facts: PreparationFacts,
    text_preparation_facts: TextPreparationQualityFacts,
    text_leakage_facts: TextLeakageFacts,
    text_vectorization_facts: TextVectorizationFacts,
    path: Path,
) -> None:
    holdout = pd.DataFrame({text_column: texts.tolist(), target_column: labels.tolist()})
    attach_evaluation_context(
        holdout,
        training_target=training_labels,
        split_facts=split_facts,
        preparation_facts=preparation_facts,
    )
    holdout.attrs[_TEXT_EVALUATION_CONTEXT_KEY] = {
        "text_preparation_facts": text_preparation_facts.model_dump(mode="json"),
        "text_leakage_facts": text_leakage_facts.model_dump(mode="json"),
        "text_vectorization_facts": text_vectorization_facts.model_dump(mode="json"),
    }
    holdout.to_pickle(path)


def _read_multilingual_holdout_context(
    holdout: pd.DataFrame,
) -> tuple[TextPreparationQualityFacts, TextLeakageFacts, TextVectorizationFacts]:
    payload = holdout.attrs.get(_TEXT_EVALUATION_CONTEXT_KEY)
    if not isinstance(payload, dict):
        raise ValidationError(
            "The holdout artifact predates retained multilingual text evidence; retrain before evaluation."
        )
    return (
        TextPreparationQualityFacts.model_validate(payload.get("text_preparation_facts")),
        TextLeakageFacts.model_validate(payload.get("text_leakage_facts")),
        TextVectorizationFacts.model_validate(payload.get("text_vectorization_facts")),
    )


def _verify_recomputed_text_context(
    holdout: pd.DataFrame,
    recomputed_texts: pd.Series,
    recomputed_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    stored_split: SplitFacts,
    recomputed_split: SplitFacts,
    stored_text_facts: tuple[TextPreparationQualityFacts, TextLeakageFacts, TextVectorizationFacts],
    recomputed_preparation: TextPreparationQualityFacts,
    recomputed_leakage: TextLeakageFacts,
    recomputed_fit_vectorization: TextVectorizationFacts,
) -> None:
    if stored_split.model_dump(mode="json") != recomputed_split.model_dump(mode="json"):
        raise ValidationError("Recomputed text split facts do not match the private FIT evidence.")
    stored_preparation, stored_leakage, stored_vectorization = stored_text_facts
    if (
        stored_preparation != recomputed_preparation
        or stored_leakage != recomputed_leakage
        or stored_vectorization != recomputed_fit_vectorization
    ):
        raise ValidationError(
            "Recomputed text preparation, leakage, or train-only vocabulary facts do not match the private FIT evidence."
        )
    if text_column not in holdout.columns or target_column not in holdout.columns:
        raise ValidationError("The private text holdout artifact is missing its raw text or target column.")
    stored_texts = _as_text_series(holdout[text_column])
    expected_texts = _as_text_series(recomputed_texts)
    if stored_texts.tolist() != expected_texts.tolist():
        raise ValidationError("Recomputed text holdout membership does not match the private FIT evidence.")
    if holdout[target_column].tolist() != recomputed_labels.tolist():
        raise ValidationError("Recomputed text holdout targets do not match the private FIT evidence.")


def _require_zero_text_leakage(facts: TextLeakageFacts) -> None:
    if (
        facts.train_business_group_overlap_count
        or facts.train_template_group_overlap_count
        or facts.train_connected_group_overlap_count
    ):
        raise ValidationError("Text classification rejected a split with business or template leakage.")


def _multilingual_result_summary(
    prepared: PreparedTextClassificationData,
    split: PreparedSupervisedSplit,
    vectorization: TextVectorizationFacts,
) -> dict[str, Any]:
    return {
        "class_count": int(prepared.labels.nunique(dropna=True)),
        "train_row_count": int(len(split.train_target.index)),
        "holdout_row_count": int(len(split.holdout_target.index)),
        "evaluation_model_training_scope": "holdout_train_split",
        "apply_model_training_scope": "all_eligible_rows",
        "preparation_specification_digest": prepared.specification.specification_digest,
        "connected_group_count": int(prepared.connected_groups.nunique(dropna=False)),
        "transformed_feature_count": vectorization.transformed_feature_count,
        "vocabulary_digest": vectorization.vocabulary_digest,
    }


def _as_text_series(values: pd.Series) -> pd.Series:
    return values.astype("string").fillna("").reset_index(drop=True)


def _normalize_token_text_series(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .fillna("")
        .map(lambda value: " ".join(str(value).split()))
        .astype("string")
    )


def _prepare_supervised_text(
    dataframe: pd.DataFrame,
    *,
    text_column: str,
    target_column: str,
    group_column: str | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series | None]:
    if text_column not in dataframe.columns:
        raise ValidationError(f"Text column '{text_column}' is missing.")
    if target_column not in dataframe.columns:
        raise ValidationError(f"Target column '{target_column}' is missing.")
    if group_column is not None and group_column not in dataframe.columns:
        raise ValidationError(f"Group column '{group_column}' is missing.")
    if group_column in {text_column, target_column}:
        raise ValidationError("The group column must be distinct from text and target columns.")
    texts = _normalize_token_text_series(dataframe[text_column])
    labels = dataframe[target_column].copy()
    mask = texts.ne("") & labels.notna()
    if not mask.any():
        raise ValidationError("Text classification requires non-empty tokenized text rows with target labels.")
    filtered_texts = texts.loc[mask].reset_index(drop=True)
    filtered_labels = labels.loc[mask].reset_index(drop=True)
    if filtered_labels.nunique(dropna=True) < 2:
        raise ValidationError("Text classification requires at least two target classes.")
    groups = dataframe.loc[mask, group_column].reset_index(drop=True) if group_column is not None else None
    return filtered_texts, filtered_labels, groups


def _text_train_test_split(
    texts: pd.Series,
    labels: pd.Series,
    request: FitTaskRequest | HyperparameterTuningTaskRequest,
    *,
    groups: pd.Series | None = None,
) -> PreparedSupervisedSplit:
    return prepare_supervised_split(texts, labels, request, groups=groups)


def _save_text_holdout(
    texts: pd.Series,
    labels: pd.Series,
    training_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    split_facts: SplitFacts,
    preparation_facts: PreparationFacts,
    path: Path,
) -> None:
    holdout = pd.DataFrame({text_column: texts.tolist(), target_column: labels.tolist()})
    attach_evaluation_context(
        holdout,
        training_target=training_labels,
        split_facts=split_facts,
        preparation_facts=preparation_facts,
    )
    holdout.to_pickle(path)


def _serialize_search_best_params(best_params: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in best_params.items():
        simple_key = str(key).split("__", 1)[-1]
        if simple_key == "ngram_range" and isinstance(value, tuple) and len(value) == 2:
            serialized["ngram_max"] = int(value[1])
        else:
            serialized[simple_key] = value
    return serialized


def _single_role_column_from_artifact(estimator: Any, fallback_columns: list[str]) -> str:
    text_column = getattr(estimator, "text_column", None)
    if isinstance(text_column, str) and text_column.strip():
        return text_column
    if fallback_columns:
        return str(fallback_columns[0])
    raise ValidationError("The trained text model does not expose its required text column.")


def _write_apply_output(task_dir: Path, file_name: str, frames: list[pd.DataFrame]) -> Path:
    output_dir = task_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / file_name
    pd.concat(frames, ignore_index=True).to_csv(output_path, index=False)
    return output_path


def _tfidf_vectorizer(*, max_features: int, ngram_max: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        max_features=max_features,
        ngram_range=(1, ngram_max),
    )


def _top_terms_from_centers(
    centers: np.ndarray,
    feature_names: Any,
    *,
    top_n: int,
    label_prefix: str,
) -> list[dict[str, Any]]:
    terms = list(feature_names)
    rows: list[dict[str, Any]] = []
    for group_index, weights in enumerate(np.asarray(centers)):
        ranked_indexes = np.argsort(weights)[::-1][:top_n]
        rows.append(
            {
                f"{label_prefix}_id": int(group_index),
                "terms": [str(terms[index]) for index in ranked_indexes],
            }
        )
    return rows


def _discovery_paths(model_key: str, task_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    stem = model_key.replace(".", "_")
    model_dir = task_dir / "models"
    input_dir = task_dir / "input"
    output_dir = task_dir / "output"
    model_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return (
        model_dir / f"{stem}.joblib",
        model_dir / f"{stem}-final.joblib",
        input_dir / f"{stem}-evidence.json",
        output_dir / f"{stem}-results.csv",
        output_dir / f"{stem}-report.json",
    )


def _write_discovery_evidence(path: Path, facts: BaseModel, snapshot_digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_key": facts.__class__.__name__,
                "source_dataset_snapshot_digest": snapshot_digest,
                "facts": facts.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _write_json_report(path: Path, facts: BaseModel) -> None:
    path.write_text(facts.model_dump_json(indent=2), encoding="utf-8")


def _verify_discovery_evidence(path: Path, facts: BaseModel, snapshot_digest: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValidationError("The private text discovery evidence could not be read.") from exc
    if payload.get("source_dataset_snapshot_digest") != snapshot_digest:
        raise ValidationError("The text discovery Dataset snapshot no longer matches FIT evidence.")
    if payload.get("schema_key") != facts.__class__.__name__:
        raise ValidationError("The private text discovery evidence has the wrong fact type.")
    if payload.get("facts") != facts.model_dump(mode="json"):
        raise ValidationError("Recomputed text discovery facts do not match authoritative FIT evidence.")


def _cluster_summary(facts: TextClusteringEvaluationFacts) -> dict[str, Any]:
    return {
        "cluster_count": facts.quality.realized_cluster_count,
        "evaluated_row_count": facts.quality.evaluated_row_count,
        "cosine_silhouette": facts.quality.cosine_silhouette,
        "mean_resampling_stability": facts.stability.mean_adjusted_rand,
        "preparation_specification_digest": facts.specification.specification_digest,
    }


def _topic_summary(facts: TextTopicEvaluationFacts) -> dict[str, Any]:
    return {
        "topic_count": facts.quality.topic_count,
        "train_row_count": facts.split.train_row_count,
        "holdout_row_count": facts.split.holdout_row_count,
        "heldout_perplexity": facts.quality.heldout_perplexity,
        "topic_label_identity_digest": facts.topic_label_identity_digest,
        "preparation_specification_digest": facts.specification.specification_digest,
    }


def _retrieval_summary(facts: TextRetrievalEvaluationFacts) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": facts.mode,
        "indexed_document_count": facts.diagnostics.indexed_document_count,
        "result_row_count": facts.diagnostics.result_row_count,
        "preparation_specification_digest": facts.specification.specification_digest,
    }
    if facts.ranking is not None:
        result.update(facts.ranking.model_dump(mode="json"))
    return result


def _cluster_candidate_metrics(facts: TextClusteringEvaluationFacts) -> CandidateMetrics:
    silhouette = facts.quality.cosine_silhouette
    if silhouette is None:
        raise ValidationError("Text clustering cannot publish evaluation without a defined cosine silhouette.")
    return CandidateMetrics(
        primary_metric_name="cosine_silhouette",
        primary_metric_value=silhouette,
        metrics={
            "cosine_silhouette": silhouette,
            "resampling_stability": facts.stability.mean_adjusted_rand or 0.0,
            "minimum_cluster_share": facts.quality.minimum_cluster_share,
        },
        details={"assignment_digest": facts.quality.assignment_digest},
    )


def _topic_candidate_metrics(facts: TextTopicEvaluationFacts) -> CandidateMetrics:
    return CandidateMetrics(
        primary_metric_name="heldout_perplexity",
        primary_metric_value=facts.quality.heldout_perplexity,
        metrics={
            "heldout_perplexity": facts.quality.heldout_perplexity,
            "coherence": facts.quality.mean_coherence,
            "topic_diversity": facts.quality.term_diversity,
            "resampling_stability": facts.stability.mean_matched_cosine or 0.0,
        },
        details={
            "dominant_topic_digest": facts.quality.dominant_topic_digest,
            "topic_label_identity_digest": facts.topic_label_identity_digest,
        },
    )


def _retrieval_candidate_metrics(facts: TextRetrievalEvaluationFacts) -> CandidateMetrics | None:
    if facts.ranking is None:
        return None
    return CandidateMetrics(
        primary_metric_name="ndcg_at_k",
        primary_metric_value=facts.ranking.ndcg_at_k,
        metrics={
            "ndcg_at_k": facts.ranking.ndcg_at_k,
            "recall_at_k": facts.ranking.recall_at_k,
            "mrr_at_k": facts.ranking.mrr_at_k,
        },
        details={"result_digest": facts.diagnostics.result_digest},
    )


def _required_retained_column(value: str | None, role: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise ValidationError(f"The retained text analyzer does not expose its '{role}' column.")


def _load_raw_text_apply_inputs(
    request: ApplyTaskRequest,
    text_column: str,
) -> tuple[list[pd.DataFrame], pd.Series, list[dict[str, Any]]]:
    frames: list[pd.DataFrame] = []
    texts: list[Any] = []
    locations: list[dict[str, Any]] = []
    for input_file in request.input_files:
        dataframe = load_dataset(Path(input_file.absolute_path))
        if text_column not in dataframe.columns:
            raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
        frames.append(dataframe)
        texts.extend(dataframe[text_column].tolist())
        locations.extend(
            {"source_file": input_file.file_name, "input_row_number": row_number}
            for row_number in range(1, len(dataframe.index) + 1)
        )
    return frames, pd.Series(texts, dtype="object"), locations


def _topic_export_frame(
    source_positions: np.ndarray,
    distributions: list[list[float] | None],
) -> pd.DataFrame:
    topic_count = max((len(row) for row in distributions if row is not None), default=0)
    rows: list[dict[str, Any]] = []
    for source_position, distribution in zip(source_positions.tolist(), distributions, strict=True):
        row: dict[str, Any] = {"source_row_number": int(source_position) + 1}
        if distribution is None:
            row.update({"dominant_topic": None, "topic_score": None})
            row.update({f"topic_{topic}_share": None for topic in range(1, topic_count + 1)})
        else:
            row.update(
                {
                    "dominant_topic": int(np.argmax(distribution)) + 1,
                    "topic_score": float(max(distribution)),
                }
            )
            row.update(
                {f"topic_{topic}_share": float(distribution[topic - 1]) for topic in range(1, topic_count + 1)}
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _append_topic_outputs(
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
    distributions: list[list[float] | None],
) -> pd.DataFrame:
    output = dataframe.copy()
    topic_values = _topic_export_frame(source_positions, distributions).drop(columns=["source_row_number"])
    for column in topic_values.columns:
        output[column] = pd.NA
        output.iloc[source_positions, output.columns.get_loc(column)] = topic_values[column].tolist()
    return output


def _eligible_role_values(
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
    column: str | None,
) -> pd.Series | None:
    if column is None:
        return None
    if column not in dataframe.columns:
        raise ValidationError(f"Text retrieval role column '{column}' is missing.")
    return dataframe.iloc[source_positions][column].reset_index(drop=True)


def _retrieval_export_frame(analyzer: MultilingualTextRetriever, matches: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "query_document_id": analyzer.matched_document_id(match.query_position),
                "query_text": analyzer.matched_document_text(match.query_position),
                "matched_document_id": analyzer.matched_document_id(match.matched_document_position),
                "matched_text": analyzer.matched_document_text(match.matched_document_position),
                "rank": match.rank,
                "similarity": match.similarity,
            }
            for match in matches
        ],
        columns=[
            "query_document_id",
            "query_text",
            "matched_document_id",
            "matched_text",
            "rank",
            "similarity",
        ],
    )


def _verify_retrieval_source_identities(
    analyzer: MultilingualTextRetriever,
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
) -> None:
    document_ids = _eligible_role_values(dataframe, source_positions, analyzer.document_id_column)
    if analyzer.document_id_column is None:
        expected_ids = tuple(f"row-{position + 1}" for position in source_positions)
    else:
        if document_ids is None:
            raise ValidationError("The retained retrieval document identity role is missing.")
        expected_ids = tuple(document_ids.astype("string").fillna("").astype(str).tolist())
    if expected_ids != analyzer.document_ids:
        raise ValidationError("Recomputed retrieval document identities do not match the retained local index.")
    relevance = _eligible_role_values(dataframe, source_positions, analyzer.relevance_group_column)
    current_hashes = (
        tuple(hashlib.sha256(str(value).encode("utf-8")).hexdigest() for value in relevance.tolist())
        if relevance is not None
        else None
    )
    if current_hashes != analyzer.relevance_group_hashes:
        raise ValidationError("Recomputed retrieval relevance truth does not match authoritative FIT evidence.")


def _concat_optional_apply_column(frames: list[pd.DataFrame], column: str | None) -> pd.Series | None:
    if column is None:
        return None
    if any(column not in frame.columns for frame in frames):
        raise ValidationError(f"Retrieval apply inputs are missing retained document ID column '{column}'.")
    return pd.concat([frame[column] for frame in frames], ignore_index=True)
