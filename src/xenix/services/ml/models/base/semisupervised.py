from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder

from .....exceptions import ValidationError
from ...contracts import (
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    PreparationFacts,
    SplitFacts,
    _role_columns,
)
from ...dataset_loader import load_dataset, load_holdout_frame
from ...evaluation import (
    build_dummy_baseline_metrics,
    build_evaluation_comparison,
    build_metric_snapshot,
)
from ...preparation import (
    attach_evaluation_context,
    build_tabular_preparation_facts,
    canonicalize_group_series,
    dataset_snapshot_digest,
    membership_digest,
    prepare_supervised_split,
    read_evaluation_context,
)
from ...types import ColumnRoleKind, ModelRoleDefinition, ModelRoleSchema
from .supervised import NumericAndCategoricalModelService


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
