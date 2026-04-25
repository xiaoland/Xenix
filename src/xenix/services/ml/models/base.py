from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ....exceptions import ValidationError
from ...storage.models import ProblemKind
from ..contracts import (
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    InferenceSummary,
    InferenceTaskRequest,
    InferenceTaskResult,
    TuningSummary,
)
from ..dataset_loader import load_dataset, load_holdout_frame
from ..evaluation import build_metric_snapshot, scoring_name_for_policy
from ..types import ModelServiceBase


class NumericAndCategoricalModelService(ModelServiceBase):
    scaler_for_numeric: bool = False

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        X_train, _X_test, y_train, y_test = cls._prepare_split(dataframe, request)

        params_model = cls.validate_params(request.manual_training.params)
        estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        estimator.fit(X_train, y_train)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        cls._save_holdout_frame(_X_test, y_test, request, holdout_artifact_path)

        return FitTaskResult(
            task_id=request.task_id,
            problem_kind=request.problem_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        X_train, _X_test, y_train, y_test = cls._prepare_split(dataframe, request)
        param_grid_model = cls.validate_param_grid(request.hyperparameter_tuning.param_grid)
        base_estimator = cls._build_pipeline()
        search = GridSearchCV(
            estimator=base_estimator,
            param_grid=cls._build_param_grid(param_grid_model),
            cv=request.evaluation_policy.cv_folds,
            scoring=scoring_name_for_policy(request.evaluation_policy),
            n_jobs=1,
        )
        search.fit(X_train, y_train)
        estimator = search.best_estimator_

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        cls._save_holdout_frame(_X_test, y_test, request, holdout_artifact_path)

        return HyperparameterTuningTaskResult(
            task_id=request.task_id,
            problem_kind=request.problem_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            best_params={str(key): value for key, value in search.best_params_.items()},
            model_artifact_path=str(model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            tuning_summary=TuningSummary(
                best_params={str(key): value for key, value in search.best_params_.items()},
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
        X_eval, y_eval = cls._split_frame(holdout, request.column_selection.feature_columns, request.column_selection.target_columns)
        y_pred = estimator.predict(X_eval)
        metrics = build_metric_snapshot(request.problem_kind, y_eval, y_pred)

        return EvaluateTaskResult(
            task_id=request.task_id,
            problem_kind=request.problem_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=metrics,
        )

    @classmethod
    def infer(cls, request: InferenceTaskRequest, task_dir: Path) -> InferenceTaskResult:
        estimator = joblib.load(request.inference_model.trained_model_artifact_path)
        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            missing = [column for column in request.feature_columns if column not in dataframe.columns]
            if missing:
                raise ValidationError(
                    f"Inference input '{input_file.file_name}' is missing required columns: {', '.join(missing)}."
                )
            X_infer = dataframe.loc[:, request.feature_columns].copy()
            predictions = estimator.predict(X_infer)
            result_frame = dataframe.copy()
            result_frame["prediction"] = predictions
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "predictions.csv"
        pd.concat(result_frames, ignore_index=True).to_csv(output_path, index=False)
        return InferenceTaskResult(
            task_id=request.task_id,
            trained_model_id=request.inference_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=InferenceSummary(
                row_count=int(sum(len(frame.index) for frame in result_frames)),
                input_file_count=len(request.input_files),
                prediction_column_name="prediction",
            ),
        )

    @classmethod
    def _prepare_split(
        cls,
        dataframe: pd.DataFrame,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        X, y = cls._split_frame(
            dataframe,
            request.column_selection.feature_columns,
            request.column_selection.target_columns,
        )
        stratify = y if request.problem_kind is ProblemKind.CLASSIFICATION else None
        try:
            return train_test_split(
                X,
                y,
                test_size=request.evaluation_policy.test_size,
                random_state=request.evaluation_policy.random_state,
                stratify=stratify,
            )
        except ValueError:
            return train_test_split(
                X,
                y,
                test_size=request.evaluation_policy.test_size,
                random_state=request.evaluation_policy.random_state,
                stratify=None,
            )

    @classmethod
    def _split_frame(
        cls,
        dataframe: pd.DataFrame,
        feature_columns: list[str],
        target_columns: list[str],
    ) -> tuple[pd.DataFrame, pd.Series]:
        if len(target_columns) != 1:
            raise ValidationError("The current model services require exactly one target column.")
        X = dataframe.loc[:, feature_columns].copy()
        y = dataframe.loc[:, target_columns[0]].copy()
        return X, y

    @classmethod
    def _save_holdout_frame(
        cls,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
        holdout_artifact_path: Path,
    ) -> None:
        frame = X_test.copy()
        frame[request.column_selection.target_columns[0]] = y_test
        frame.to_pickle(holdout_artifact_path)

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
        numeric_transformer_steps: list[tuple[str, Any]] = [
            ("imputer", SimpleImputer(strategy="median")),
        ]
        if cls.scaler_for_numeric:
            numeric_transformer_steps.append(("scaler", StandardScaler()))
        numeric_transformer = Pipeline(steps=numeric_transformer_steps)
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, cls._numeric_selector),
                ("categorical", categorical_transformer, cls._categorical_selector),
            ]
        )

    @staticmethod
    def _numeric_selector(dataframe: pd.DataFrame) -> list[str]:
        return dataframe.select_dtypes(include=["number", "bool"]).columns.tolist()

    @staticmethod
    def _categorical_selector(dataframe: pd.DataFrame) -> list[str]:
        return dataframe.select_dtypes(exclude=["number", "bool"]).columns.tolist()

    @classmethod
    def _estimator_kwargs(cls, params_model: BaseModel) -> dict[str, Any]:
        return params_model.model_dump(exclude_none=True, by_alias=True)

    @classmethod
    def _build_param_grid(cls, param_grid_model: BaseModel) -> dict[str, list[Any]]:
        payload = param_grid_model.model_dump(mode="json", by_alias=True)
        return {
            f"model__{key}": [cls._normalize_grid_value(key, value) for value in values]
            for key, values in payload.items()
        }

    @classmethod
    def _normalize_grid_value(cls, key: str, value: Any) -> Any:
        if key == "max_depth" and value == 0:
            return None
        if key == "max_features" and value == "all":
            return 1.0
        return value

    @classmethod
    @abstractmethod
    def _build_estimator(cls, **estimator_kwargs: Any) -> Any:
        raise NotImplementedError


class BooleanGridModel(BaseModel):
    fit_intercept: list[bool] = Field(
        default=[True, False],
        min_length=1,
        description="Candidate values for fit_intercept.",
    )


class UnsupervisedClusteringModelService(ModelServiceBase):
    requires_target: bool = False
    supports_hyperparameter_tuning: bool = False
    scaler_for_numeric: bool = True
    cluster_column_name: str = "cluster_id"

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        X = cls._select_features(dataframe, request.column_selection.feature_columns)

        params_model = cls.validate_params(request.manual_training.params)
        estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        raw_labels = estimator.fit_predict(X)
        display_labels, cluster_count, noise_count = cls._normalize_cluster_labels(raw_labels)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "cluster_assignments.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)

        result_frame = dataframe.copy()
        result_frame[cls.cluster_column_name] = display_labels
        result_frame.to_csv(export_artifact_path, index=False)

        return FitTaskResult(
            task_id=request.task_id,
            problem_kind=request.problem_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json", by_alias=True),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "cluster_column_name": cls.cluster_column_name,
                "cluster_count": cluster_count,
                "noise_count": noise_count,
                "row_count": int(len(result_frame.index)),
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support evaluation.")

    @classmethod
    def infer(cls, request: InferenceTaskRequest, task_dir: Path) -> InferenceTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support inference.")

    @classmethod
    def _select_features(cls, dataframe: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        if not feature_columns:
            raise ValidationError("Select at least one input column for clustering.")
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
    def _normalize_cluster_labels(cls, labels: Any) -> tuple[np.ndarray, int, int]:
        raw = np.asarray(labels, dtype=int)
        unique_labels = sorted(set(int(value) for value in raw.tolist()))
        if -1 in unique_labels:
            mapped = raw.copy()
            current = 1
            for label in unique_labels:
                if label == -1:
                    continue
                mapped[raw == label] = current
                current += 1
            cluster_count = current - 1
            noise_count = int(np.sum(raw == -1))
            return mapped, cluster_count, noise_count
        mapped = raw + 1
        cluster_count = len(unique_labels)
        return mapped, cluster_count, 0

    @classmethod
    def _estimator_kwargs(cls, params_model: BaseModel) -> dict[str, Any]:
        return params_model.model_dump(exclude_none=True, by_alias=True)

    @classmethod
    @abstractmethod
    def _build_estimator(cls, **estimator_kwargs: Any) -> Any:
        raise NotImplementedError
