from __future__ import annotations

import json
from abc import abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .....exceptions import ValidationError
from ...clustering_evidence import ClusteringEvaluationFacts
from ...contracts import (
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
    TrainingScopeFacts,
)
from ...dataset_loader import load_dataset
from ...evaluation import build_evaluation_comparison
from ...types import ModelServiceBase
from .supervised import NumericAndCategoricalModelService


class UnsupervisedClusteringModelService(ModelServiceBase):
    requires_target: bool = False
    supports_hyperparameter_tuning: bool = False
    scaler_for_numeric: bool = True
    cluster_column_name: str = "cluster_id"

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params_model = cls.validate_params(request.manual_training.params)
        fit_with_evidence = getattr(cls, "fit_with_evidence", None)
        if fit_with_evidence is None:
            raise ValidationError(
                f"Model '{cls.key}' does not expose trustworthy clustering evidence."
            )
        fitted = fit_with_evidence(
            dataframe,
            request.column_selection.feature_columns,
            params_model,
        )
        estimator = fitted.estimator
        display_labels = fitted.display_labels
        facts: ClusteringEvaluationFacts = fitted.facts
        cluster_count = facts.quality.cluster_count
        noise_count = facts.quality.noise_row_count

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "cluster_assignments.csv"
        evaluation_context_path = task_dir / "input" / "clustering-evaluation.json"
        report_artifact_path = task_dir / "output" / "clustering-report.json"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        evaluation_context_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)

        result_frame = dataframe.copy()
        result_frame[cls.cluster_column_name] = display_labels
        result_frame.to_csv(export_artifact_path, index=False)
        evidence_payload = facts.model_dump(mode="json")
        serialized_evidence = json.dumps(
            evidence_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        evaluation_context_path.write_text(serialized_evidence, encoding="utf-8")
        report_artifact_path.write_text(serialized_evidence, encoding="utf-8")

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json", by_alias=True),
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(model_artifact_path),
            holdout_artifact_path=str(evaluation_context_path),
            export_artifact_path=str(export_artifact_path),
            report_artifact_path=str(report_artifact_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="all_eligible_rows",
                apply_model=("all_eligible_rows" if cls.supports_apply else None),
            ),
            result_summary={
                "cluster_column_name": cls.cluster_column_name,
                "cluster_count": cluster_count,
                "noise_count": noise_count,
                "row_count": int(len(result_frame.index)),
                "clustering_evaluation": evidence_payload,
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        facts = ClusteringEvaluationFacts.model_validate_json(
            Path(request.evaluate_model.holdout_artifact_path).read_text(encoding="utf-8")
        )
        candidate = None
        baseline = None
        comparison = None
        if (
            facts.quality.silhouette is not None
            and facts.null_baseline.median_silhouette is not None
        ):
            candidate_metrics = {
                "silhouette": facts.quality.silhouette,
            }
            if facts.quality.calinski_harabasz is not None:
                candidate_metrics["calinski_harabasz"] = facts.quality.calinski_harabasz
            if facts.quality.davies_bouldin is not None:
                candidate_metrics["davies_bouldin"] = facts.quality.davies_bouldin
            candidate = CandidateMetrics(
                primary_metric_name="silhouette",
                primary_metric_value=facts.quality.silhouette,
                metrics=candidate_metrics,
                details={
                    "assignment_digest": facts.assignment_digest,
                    "evidence_digest": facts.evidence_digest,
                },
            )
            baseline = CandidateMetrics(
                primary_metric_name="silhouette",
                primary_metric_value=facts.null_baseline.median_silhouette,
                metrics={"silhouette": facts.null_baseline.median_silhouette},
                details={"baseline_protocol": facts.null_baseline.protocol},
            )
            comparison = build_evaluation_comparison(
                request.evaluation_policy,
                candidate,
                baseline,
            )
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=candidate,
            baseline_evaluation=baseline,
            comparison=comparison,
            clustering_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        if not cls.supports_apply:
            raise ValidationError(f"Model '{cls.key}' does not support apply.")
        estimator = joblib.load(request.apply_model.trained_model_artifact_path)
        predict_with_retained_labels = getattr(cls, "predict_with_retained_labels", None)
        if predict_with_retained_labels is None:
            raise ValidationError(
                f"Model '{cls.key}' has no retained clustering label contract."
            )

        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            missing = [column for column in request.feature_columns if column not in dataframe.columns]
            if missing:
                raise ValidationError(
                    f"Apply input '{input_file.file_name}' is missing required columns: {', '.join(missing)}."
                )
            display_labels = predict_with_retained_labels(
                estimator,
                dataframe,
                request.feature_columns,
            )
            result_frame = dataframe.copy()
            result_frame[cls.cluster_column_name] = display_labels
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "cluster_predictions.csv"
        pd.concat(result_frames, ignore_index=True).to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=int(sum(len(frame.index) for frame in result_frames)),
                input_file_count=len(request.input_files),
                prediction_column_name=cls.cluster_column_name,
            ),
        )

    @classmethod
    def _build_pipeline(cls, **estimator_kwargs: Any) -> Pipeline:
        return Pipeline(
            steps=[
                ("preprocess", cls._build_preprocessor()),
                ("model", cls._build_estimator(**estimator_kwargs)),
            ]
        )

    @classmethod
    def _build_preprocessor(cls) -> ColumnTransformer:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, NumericAndCategoricalModelService._numeric_selector),
                ("categorical", categorical_transformer, NumericAndCategoricalModelService._categorical_selector),
            ]
        )

    @classmethod
    @abstractmethod
    def _build_estimator(cls, **estimator_kwargs: Any) -> Any:
        raise NotImplementedError


class UnsupervisedAnomalyModelService(ModelServiceBase):
    requires_target: bool = False
    supports_hyperparameter_tuning: bool = False
    scaler_for_numeric: bool = True
    anomaly_label_column_name: str = "anomaly_label"
    anomaly_score_column_name: str = "anomaly_score"
    anomaly_rank_column_name: str = "anomaly_rank"

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        X = cls._select_features(dataframe, request.column_selection.feature_columns)

        params_model = cls.validate_params(request.manual_training.params)
        estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        raw_labels = estimator.fit_predict(X)
        scores = cls._anomaly_scores(estimator, X, raw_labels)
        display_labels, anomaly_count = cls._normalize_anomaly_labels(raw_labels)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "anomaly_scores.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)

        result_frame = dataframe.copy()
        result_frame[cls.anomaly_label_column_name] = display_labels
        result_frame[cls.anomaly_score_column_name] = scores
        result_frame[cls.anomaly_rank_column_name] = cls._rank_scores(scores)
        result_frame.to_csv(export_artifact_path, index=False)

        row_count = int(len(result_frame.index))
        anomaly_rate = float(anomaly_count / row_count) if row_count else 0.0
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json", by_alias=True),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "anomaly_label_column_name": cls.anomaly_label_column_name,
                "anomaly_score_column_name": cls.anomaly_score_column_name,
                "anomaly_rank_column_name": cls.anomaly_rank_column_name,
                "anomaly_count": anomaly_count,
                "anomaly_rate": anomaly_rate,
                "row_count": row_count,
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
        raise ValidationError(f"Model '{cls.key}' does not support apply.")

    @classmethod
    def _select_features(cls, dataframe: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        if not feature_columns:
            raise ValidationError("Select at least one input column for anomaly detection.")
        return dataframe.loc[:, feature_columns].copy()

    @classmethod
    def _build_pipeline(cls, **estimator_kwargs: Any) -> Pipeline:
        return Pipeline(
            steps=[
                ("preprocess", cls._build_preprocessor()),
                ("model", cls._build_estimator(**estimator_kwargs)),
            ]
        )

    @classmethod
    def _build_preprocessor(cls) -> ColumnTransformer:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, NumericAndCategoricalModelService._numeric_selector),
                ("categorical", categorical_transformer, NumericAndCategoricalModelService._categorical_selector),
            ]
        )

    @classmethod
    def _anomaly_scores(cls, estimator: Pipeline, X: pd.DataFrame, labels: Any) -> np.ndarray:
        if hasattr(estimator, "decision_function"):
            return -np.asarray(estimator.decision_function(X), dtype=float)
        model = estimator.named_steps.get("model")
        if hasattr(model, "negative_outlier_factor_"):
            return -np.asarray(model.negative_outlier_factor_, dtype=float)
        raw_labels = np.asarray(labels, dtype=int)
        return np.where(raw_labels == -1, 1.0, 0.0).astype(float)

    @staticmethod
    def _normalize_anomaly_labels(labels: Any) -> tuple[np.ndarray, int]:
        raw = np.asarray(labels, dtype=int)
        display_labels = np.where(raw == -1, "anomaly", "normal")
        anomaly_count = int(np.sum(raw == -1))
        return display_labels, anomaly_count

    @staticmethod
    def _rank_scores(scores: np.ndarray) -> np.ndarray:
        order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
        ranks = np.empty(len(order), dtype=int)
        ranks[order] = np.arange(1, len(order) + 1)
        return ranks

    @classmethod
    def _estimator_kwargs(cls, params_model: BaseModel) -> dict[str, Any]:
        return params_model.model_dump(exclude_none=True, by_alias=True)

    @classmethod
    @abstractmethod
    def _build_estimator(cls, **estimator_kwargs: Any) -> Any:
        raise NotImplementedError
