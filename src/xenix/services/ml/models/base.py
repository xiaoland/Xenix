from __future__ import annotations

from abc import abstractmethod
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

from ....exceptions import ValidationError
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
    TuningSummary,
    TrainingScopeFacts,
)
from ..clustering_evidence import ClusteringEvaluationFacts
from ..dataset_loader import load_dataset, load_holdout_frame
from ..evaluation import build_metric_snapshot, scoring_name_for_policy
from ..evaluation import build_dummy_baseline_metrics, build_evaluation_comparison
from ..preparation import (
    PreparedSupervisedSplit,
    attach_evaluation_context,
    build_group_aware_cv,
    build_tabular_preparation_facts,
    canonicalize_group_series,
    dataset_snapshot_digest,
    membership_digest,
    prepare_supervised_split,
    read_evaluation_context,
)
from ..types import ColumnRoleKind, ModelRoleDefinition, ModelRoleSchema, ModelServiceBase


class NumericAndCategoricalModelService(ModelServiceBase):
    scaler_for_numeric: bool = False
    dense_preprocessing: bool = False

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = cls._prepare_split(dataframe, request)
        X_train = prepared.train_features
        X_test = prepared.holdout_features
        y_train = prepared.train_target
        y_test = prepared.holdout_target

        params_model = cls.validate_params(request.manual_training.params)
        estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        estimator.fit(X_train, y_train)
        preparation_facts = build_tabular_preparation_facts(estimator, X_train)
        final_estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        final_X, final_y = cls._split_frame(
            dataframe,
            request.column_selection.feature_columns,
            request.column_selection.target_columns,
        )
        final_estimator.fit(final_X, final_y)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        final_model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}-final.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        joblib.dump(final_estimator, final_model_artifact_path)
        cls._save_holdout_frame(
            X_test,
            y_test,
            y_train,
            request,
            prepared.split_facts,
            preparation_facts,
            holdout_artifact_path,
        )
        export_artifact_path, result_summary = cls._write_key_driver_report(final_estimator, final_X, task_dir)
        result_summary = {
            **result_summary,
            "evaluation_model_training_scope": "holdout_train_split",
            "apply_model_training_scope": "all_eligible_rows",
        }

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(final_model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            export_artifact_path=str(export_artifact_path) if export_artifact_path is not None else None,
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            result_summary=result_summary,
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = cls._prepare_split(dataframe, request)
        X_train = prepared.train_features
        X_test = prepared.holdout_features
        y_train = prepared.train_target
        y_test = prepared.holdout_target
        param_grid_model = cls.validate_param_grid(request.hyperparameter_tuning.param_grid)
        base_estimator = cls._build_pipeline()
        cv, fit_groups = build_group_aware_cv(
            request.evaluation_policy,
            request.evaluation_kind,
            y_train,
            prepared.train_groups,
        )
        search = GridSearchCV(
            estimator=base_estimator,
            param_grid=cls._build_param_grid(param_grid_model),
            cv=cv,
            scoring=scoring_name_for_policy(request.evaluation_policy),
            n_jobs=1,
        )
        search.fit(X_train, y_train, groups=fit_groups)
        estimator = search.best_estimator_
        preparation_facts = build_tabular_preparation_facts(estimator, X_train)
        final_estimator = clone(search.best_estimator_)
        final_X, final_y = cls._split_frame(
            dataframe,
            request.column_selection.feature_columns,
            request.column_selection.target_columns,
        )
        final_estimator.fit(final_X, final_y)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        final_model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}-final.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        joblib.dump(final_estimator, final_model_artifact_path)
        cls._save_holdout_frame(
            X_test,
            y_test,
            y_train,
            request,
            prepared.split_facts,
            preparation_facts,
            holdout_artifact_path,
        )
        export_artifact_path, result_summary = cls._write_key_driver_report(final_estimator, final_X, task_dir)
        result_summary = {
            **result_summary,
            "evaluation_model_training_scope": "holdout_train_split",
            "apply_model_training_scope": "all_eligible_rows",
        }

        return HyperparameterTuningTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            best_params={str(key): value for key, value in search.best_params_.items()},
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(final_model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            export_artifact_path=str(export_artifact_path) if export_artifact_path is not None else None,
            split_facts=prepared.split_facts,
            preparation_facts=preparation_facts,
            result_summary=result_summary,
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
        baseline_training_target, split_facts, preparation_facts = read_evaluation_context(holdout)
        X_eval, y_eval = cls._split_frame(holdout, request.column_selection.feature_columns, request.column_selection.target_columns)
        y_pred = estimator.predict(X_eval)
        y_proba = estimator.predict_proba(X_eval) if hasattr(estimator, "predict_proba") else None
        classes = getattr(estimator, "classes_", None)
        metrics = build_metric_snapshot(
            request.evaluation_kind,
            y_eval,
            y_pred,
            y_proba=y_proba,
            classes=classes,
        )
        baseline_metrics = build_dummy_baseline_metrics(
            request.evaluation_kind,
            baseline_training_target,
            y_eval,
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
        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            missing = [column for column in request.feature_columns if column not in dataframe.columns]
            if missing:
                raise ValidationError(
                    f"Apply input '{input_file.file_name}' is missing required columns: {', '.join(missing)}."
                )
            X_apply = dataframe.loc[:, request.feature_columns].copy()
            predictions = estimator.predict(X_apply)
            result_frame = dataframe.copy()
            result_frame["prediction"] = predictions
            if len(request.input_files) > 1:
                result_frame["source_file"] = input_file.file_name
            result_frames.append(result_frame)

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "predictions.csv"
        pd.concat(result_frames, ignore_index=True).to_csv(output_path, index=False)
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
    def _prepare_split(
        cls,
        dataframe: pd.DataFrame,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
    ) -> PreparedSupervisedSplit:
        X, y = cls._split_frame(
            dataframe,
            request.column_selection.feature_columns,
            request.column_selection.target_columns,
        )
        group_columns = request.group_columns
        if len(group_columns) > 1:
            raise ValidationError("Supervised evaluation accepts at most one group column.")
        if set(group_columns) & set(request.column_selection.feature_columns):
            raise ValidationError("The group column cannot also be a model feature.")
        if set(group_columns) & set(request.column_selection.target_columns):
            raise ValidationError("The group column cannot also be the target.")
        groups = dataframe.loc[:, group_columns[0]].copy() if group_columns else None
        return prepare_supervised_split(X, y, request, groups=groups)

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
        y_train: pd.Series,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
        split_facts: SplitFacts,
        preparation_facts: PreparationFacts,
        holdout_artifact_path: Path,
    ) -> None:
        frame = X_test.copy()
        frame[request.column_selection.target_columns[0]] = y_test
        attach_evaluation_context(
            frame,
            training_target=y_train,
            split_facts=split_facts,
            preparation_facts=preparation_facts,
        )
        frame.to_pickle(holdout_artifact_path)

    @classmethod
    def _write_key_driver_report(
        cls,
        estimator: Pipeline,
        X_train: pd.DataFrame,
        task_dir: Path,
    ) -> tuple[Path | None, dict[str, Any]]:
        driver_frame = cls._build_key_driver_frame(estimator, X_train)
        if driver_frame is None or driver_frame.empty:
            return None, {}

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        export_artifact_path = output_dir / "key_drivers.csv"
        driver_frame.to_csv(export_artifact_path, index=False)
        top_key_drivers = [
            {
                "feature": str(row.feature),
                "importance": float(row.importance),
            }
            for row in driver_frame.head(3).itertuples(index=False)
        ]
        return export_artifact_path, {
            "key_driver_report": True,
            "driver_count": int(len(driver_frame.index)),
            "top_key_drivers": top_key_drivers,
        }

    @classmethod
    def _build_key_driver_frame(cls, estimator: Pipeline, X_train: pd.DataFrame) -> pd.DataFrame | None:
        try:
            preprocess = estimator.named_steps["preprocess"]
            model = estimator.named_steps["model"]
            feature_names = list(preprocess.get_feature_names_out())
            importance_values, signed_values = cls._extract_driver_values(model)
        except Exception:
            return None

        if len(feature_names) != len(importance_values):
            return None

        numeric_columns = cls._numeric_selector(X_train)
        categorical_columns = cls._categorical_selector(X_train)
        grouped: dict[str, dict[str, Any]] = {}
        for transformed_name, importance, signed_value in zip(feature_names, importance_values, signed_values, strict=True):
            source_feature = cls._source_feature_name(
                transformed_name,
                numeric_columns=numeric_columns,
                categorical_columns=categorical_columns,
            )
            bucket = grouped.setdefault(
                source_feature,
                {
                    "raw_importance": 0.0,
                    "signed_effect": 0.0,
                    "transformed_feature_count": 0,
                },
            )
            bucket["raw_importance"] += float(abs(importance))
            bucket["signed_effect"] += float(signed_value)
            bucket["transformed_feature_count"] += 1

        total_importance = sum(float(item["raw_importance"]) for item in grouped.values())
        if total_importance <= 0:
            return None

        rows: list[dict[str, Any]] = []
        for feature, values in grouped.items():
            signed_effect = float(values["signed_effect"])
            rows.append(
                {
                    "feature": feature,
                    "importance": float(values["raw_importance"]) / total_importance,
                    "raw_importance": float(values["raw_importance"]),
                    "effect_direction": cls._effect_direction(signed_effect),
                    "transformed_feature_count": int(values["transformed_feature_count"]),
                }
            )
        rows.sort(key=lambda item: (-float(item["importance"]), str(item["feature"])))
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        return pd.DataFrame(
            rows,
            columns=[
                "rank",
                "feature",
                "importance",
                "raw_importance",
                "effect_direction",
                "transformed_feature_count",
            ],
        )

    @staticmethod
    def _extract_driver_values(model: Any) -> tuple[np.ndarray, np.ndarray]:
        if hasattr(model, "feature_importances_"):
            importance_values = np.asarray(model.feature_importances_, dtype=float)
            return importance_values, np.zeros_like(importance_values, dtype=float)
        if hasattr(model, "coef_"):
            coefficient_values = np.asarray(model.coef_, dtype=float)
            if coefficient_values.ndim > 1:
                signed_values = np.mean(coefficient_values, axis=0)
                importance_values = np.mean(np.abs(coefficient_values), axis=0)
            else:
                signed_values = coefficient_values
                importance_values = np.abs(coefficient_values)
            return importance_values, signed_values
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    @classmethod
    def _source_feature_name(
        cls,
        transformed_name: str,
        *,
        numeric_columns: list[str],
        categorical_columns: list[str],
    ) -> str:
        suffix = transformed_name.split("__", 1)[1] if "__" in transformed_name else transformed_name
        for column in sorted(categorical_columns, key=len, reverse=True):
            if suffix == column or suffix.startswith(f"{column}_"):
                return column
        for column in sorted(numeric_columns, key=len, reverse=True):
            if suffix == column:
                return column
        return suffix

    @staticmethod
    def _effect_direction(signed_effect: float) -> str:
        if signed_effect > 0:
            return "positive"
        if signed_effect < 0:
            return "negative"
        return "not_applicable"

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
        encoder_kwargs: dict[str, Any] = {"handle_unknown": "ignore"}
        if cls.dense_preprocessing:
            encoder_kwargs["sparse_output"] = False
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(**encoder_kwargs)),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, cls._numeric_selector),
                ("categorical", categorical_transformer, cls._categorical_selector),
            ],
            sparse_threshold=0.0 if cls.dense_preprocessing else 0.3,
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


class EncodedSemiSupervisedClassifier(BaseEstimator, ClassifierMixin):
    def fit(self, X: Any, y: Any) -> "EncodedSemiSupervisedClassifier":
        y_values = pd.Series(y).reset_index(drop=True)
        labeled_mask = ~y_values.map(_is_unlabeled_value).to_numpy(dtype=bool)
        labeled_values = y_values[labeled_mask].astype(str)
        if labeled_values.empty:
            raise ValidationError("Semi-supervised classification requires at least one labeled row.")
        if labeled_values.nunique(dropna=False) < 2:
            raise ValidationError("Semi-supervised classification requires at least two labeled classes.")

        self.label_encoder_ = LabelEncoder()
        self.label_encoder_.fit(labeled_values)
        encoded_y = np.full(len(y_values.index), -1, dtype=int)
        encoded_y[labeled_mask] = self.label_encoder_.transform(labeled_values)
        self.classes_ = self.label_encoder_.classes_
        self.estimator_ = self._build_semisupervised_estimator()
        self.estimator_.fit(X, encoded_y)
        return self

    def predict(self, X: Any) -> np.ndarray:
        encoded = np.asarray(self.estimator_.predict(X), dtype=int)
        predictions = np.empty(encoded.shape, dtype=object)
        labeled_mask = encoded >= 0
        if np.any(labeled_mask):
            predictions[labeled_mask] = self.label_encoder_.inverse_transform(encoded[labeled_mask])
        predictions[~labeled_mask] = ""
        return predictions

    def predict_proba(self, X: Any) -> np.ndarray:
        if not hasattr(self.estimator_, "predict_proba"):
            raise AttributeError("The wrapped semi-supervised estimator does not expose predict_proba.")
        return self.estimator_.predict_proba(X)

    @abstractmethod
    def _build_semisupervised_estimator(self) -> Any:
        raise NotImplementedError


class SemiSupervisedClassificationModelService(NumericAndCategoricalModelService):
    family = "Semi-supervised classification"
    requires_target: bool = True
    supports_hyperparameter_tuning: bool = False
    scaler_for_numeric: bool = True
    dense_preprocessing: bool = True
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="feature",
                kind=ColumnRoleKind.MANY_COLUMNS,
                required=True,
                description="Input columns used to train the analyzer.",
            ),
            ModelRoleDefinition(
                name="partial_target",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Outcome column where blank values represent unlabeled rows.",
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

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        X_train, X_test, y_train, y_test, split_facts = cls._prepare_semisupervised_split(
            dataframe,
            request,
        )

        params_model = cls.validate_params(request.manual_training.params)
        estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        estimator.fit(X_train, y_train)
        preparation_facts = build_tabular_preparation_facts(estimator, X_train)
        final_estimator = cls._build_pipeline(**cls._estimator_kwargs(params_model))
        final_feature_columns = _role_columns(request.train_role_bindings, "feature")
        final_target_column = cls._partial_target_column(request.train_role_bindings)
        final_X = dataframe.loc[:, final_feature_columns].copy()
        final_y = dataframe.loc[:, final_target_column].copy()
        final_estimator.fit(final_X, final_y)

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        final_model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}-final.joblib"
        holdout_artifact_path = task_dir / "input" / "holdout.pkl"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        holdout_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(estimator, model_artifact_path)
        joblib.dump(final_estimator, final_model_artifact_path)
        baseline_training_target = y_train.loc[~y_train.map(_is_unlabeled_value)].reset_index(drop=True)
        cls._save_semisupervised_holdout_frame(
            X_test,
            y_test,
            baseline_training_target,
            request,
            split_facts,
            preparation_facts,
            holdout_artifact_path,
        )
        export_artifact_path, result_summary = cls._write_key_driver_report(final_estimator, final_X, task_dir)
        result_summary = {
            **result_summary,
            "labeled_training_rows": int(np.sum(~pd.Series(y_train).map(_is_unlabeled_value).to_numpy(dtype=bool))),
            "unlabeled_training_rows": int(np.sum(pd.Series(y_train).map(_is_unlabeled_value).to_numpy(dtype=bool))),
            "labeled_holdout_rows": int(len(pd.Series(y_test).index)),
            "partial_target_column": cls._partial_target_column(request.train_role_bindings),
            "evaluation_model_training_scope": "holdout_train_split",
            "apply_model_training_scope": "all_eligible_rows",
        }

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params_model.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            final_model_artifact_path=str(final_model_artifact_path),
            holdout_artifact_path=str(holdout_artifact_path),
            export_artifact_path=str(export_artifact_path) if export_artifact_path is not None else None,
            split_facts=split_facts,
            preparation_facts=preparation_facts,
            result_summary=result_summary,
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        estimator = joblib.load(request.evaluate_model.trained_model_artifact_path)
        holdout = load_holdout_frame(Path(request.evaluate_model.holdout_artifact_path))
        baseline_training_target, split_facts, preparation_facts = read_evaluation_context(holdout)
        target_column = cls._partial_target_column(request.train_role_bindings)
        feature_columns = _role_columns(request.train_role_bindings, "feature")
        X_eval = holdout.loc[:, feature_columns].copy()
        y_eval = holdout.loc[:, target_column].copy()
        y_pred = estimator.predict(X_eval)
        y_proba = estimator.predict_proba(X_eval) if hasattr(estimator, "predict_proba") else None
        classes = getattr(estimator, "classes_", None)
        metrics = build_metric_snapshot(
            request.evaluation_kind,
            y_eval,
            y_pred,
            y_proba=y_proba,
            classes=classes,
        )
        baseline_metrics = build_dummy_baseline_metrics(
            request.evaluation_kind,
            baseline_training_target,
            y_eval,
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
    def _prepare_semisupervised_split(
        cls,
        dataframe: pd.DataFrame,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, SplitFacts]:
        feature_columns = _role_columns(request.train_role_bindings, "feature")
        target_column = cls._partial_target_column(request.train_role_bindings)
        X = dataframe.loc[:, feature_columns].copy()
        y = dataframe.loc[:, target_column].copy()
        unlabeled_mask = y.map(_is_unlabeled_value)
        labeled_positions = np.flatnonzero((~unlabeled_mask).to_numpy(dtype=bool))
        unlabeled_positions = np.flatnonzero(unlabeled_mask.to_numpy(dtype=bool))
        if len(labeled_positions) < 2:
            raise ValidationError("Semi-supervised classification requires at least two labeled rows.")
        if y.iloc[labeled_positions].astype(str).nunique(dropna=False) < 2:
            raise ValidationError("Semi-supervised classification requires at least two labeled classes.")

        group_columns = request.group_columns
        if len(group_columns) > 1:
            raise ValidationError("Semi-supervised evaluation accepts at most one group column.")
        if set(group_columns) & set(feature_columns):
            raise ValidationError("The group column cannot also be a model feature.")
        if group_columns and group_columns[0] == target_column:
            raise ValidationError("The group column cannot also be the partial target.")
        all_groups = dataframe.loc[:, group_columns[0]].copy() if group_columns else None
        labeled_groups = all_groups.iloc[labeled_positions] if all_groups is not None else None
        prepared = prepare_supervised_split(
            X.iloc[labeled_positions],
            y.iloc[labeled_positions],
            request,
            groups=labeled_groups,
        )
        train_labeled_positions = labeled_positions[prepared.train_positions]
        holdout_positions = labeled_positions[prepared.holdout_positions]

        eligible_unlabeled_positions = unlabeled_positions
        if all_groups is not None and prepared.holdout_groups is not None:
            canonical_groups = canonicalize_group_series(all_groups)
            holdout_group_values = set(prepared.holdout_groups.tolist())
            eligible_unlabeled_positions = np.asarray(
                [
                    position
                    for position in unlabeled_positions
                    if canonical_groups.iloc[position] not in holdout_group_values
                ],
                dtype=int,
            )
        train_positions = np.concatenate([train_labeled_positions, eligible_unlabeled_positions])
        train_positions.sort()

        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        split_update: dict[str, Any] = {
            "eligible_row_count": len(train_positions) + len(holdout_positions),
            "train_row_count": len(train_positions),
            "train_membership_digest": membership_digest(snapshot_digest, "train", train_positions),
            "holdout_membership_digest": membership_digest(snapshot_digest, "holdout", holdout_positions),
            "evaluation_scope": "labeled_holdout_with_unlabeled_training",
        }
        if all_groups is not None:
            canonical_groups = canonicalize_group_series(all_groups)
            eligible_positions = np.concatenate([train_positions, holdout_positions])
            split_update.update(
                {
                    "eligible_group_count": int(canonical_groups.iloc[eligible_positions].nunique()),
                    "train_group_count": int(canonical_groups.iloc[train_positions].nunique()),
                    "holdout_group_count": int(canonical_groups.iloc[holdout_positions].nunique()),
                }
            )
        split_facts = prepared.split_facts.model_copy(update=split_update)
        return (
            X.iloc[train_positions].reset_index(drop=True),
            X.iloc[holdout_positions].reset_index(drop=True),
            y.iloc[train_positions].reset_index(drop=True),
            y.iloc[holdout_positions].reset_index(drop=True),
            split_facts,
        )

    @classmethod
    def _save_semisupervised_holdout_frame(
        cls,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        baseline_training_target: pd.Series,
        request: FitTaskRequest | HyperparameterTuningTaskRequest,
        split_facts: SplitFacts,
        preparation_facts: PreparationFacts,
        holdout_artifact_path: Path,
    ) -> None:
        frame = X_test.copy()
        frame[cls._partial_target_column(request.train_role_bindings)] = y_test
        attach_evaluation_context(
            frame,
            training_target=baseline_training_target,
            split_facts=split_facts,
            preparation_facts=preparation_facts,
        )
        frame.to_pickle(holdout_artifact_path)

    @staticmethod
    def _partial_target_column(role_bindings: list[dict[str, Any]]) -> str:
        columns = _role_columns(role_bindings, "partial_target")
        if len(columns) != 1:
            raise ValidationError("Semi-supervised classification requires exactly one partial_target column.")
        return columns[0]


def _is_unlabeled_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    return isinstance(value, str) and not value.strip()


def _role_columns(role_bindings: list[dict[str, Any]], role: str) -> list[str]:
    for binding in role_bindings:
        if binding.get("role") == role:
            columns = binding.get("columns")
            if isinstance(columns, list):
                return [str(column) for column in columns]
    return []


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
