from __future__ import annotations

import math
import hashlib
import json
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    explained_variance_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.preprocessing import label_binarize

from .contracts import (
    CandidateMetrics,
    EvaluationComparison,
    EvaluationPolicySnapshot,
    EvaluationVerdict,
    MetricDirection,
)
from .types import EvaluationKind

_POLICIES: dict[EvaluationKind, EvaluationPolicySnapshot] = {
    EvaluationKind.REGRESSION: EvaluationPolicySnapshot(
        policy_key="regression.default.v1",
        evaluation_kind=EvaluationKind.REGRESSION,
        primary_metric_name="r2",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=["rmse", "mae"],
        split_strategy="holdout",
        test_size=0.2,
        cv_folds=5,
        random_state=42,
    ),
    EvaluationKind.CLASSIFICATION: EvaluationPolicySnapshot(
        policy_key="classification.default.v1",
        evaluation_kind=EvaluationKind.CLASSIFICATION,
        primary_metric_name="f1_weighted",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=["accuracy", "precision_weighted", "recall_weighted"],
        split_strategy="stratified_holdout",
        test_size=0.2,
        cv_folds=5,
        random_state=42,
    ),
    EvaluationKind.NONE: EvaluationPolicySnapshot(
        policy_key="none.default.v1",
        evaluation_kind=EvaluationKind.NONE,
        primary_metric_name="none",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=[],
        split_strategy="none",
        test_size=0.0,
        cv_folds=None,
        random_state=42,
    ),
    EvaluationKind.FORECASTING: EvaluationPolicySnapshot(
        policy_key="forecasting.rolling_origin.v1",
        evaluation_kind=EvaluationKind.FORECASTING,
        primary_metric_name="mae",
        primary_metric_direction=MetricDirection.MIN,
        tie_breaker_metrics=["rmse", "smape", "mase"],
        split_strategy="rolling_origin.v1",
        test_size=0.0,
        cv_folds=3,
        random_state=42,
    ),
}


def get_default_policy(
    evaluation_kind: EvaluationKind,
    *,
    summary_metric_name: str | None = None,
    group_aware: bool = False,
) -> EvaluationPolicySnapshot:
    if evaluation_kind is EvaluationKind.SUMMARY:
        metric_name = summary_metric_name or "result_count"
        return EvaluationPolicySnapshot(
            policy_key=f"summary.{metric_name}.v1",
            evaluation_kind=EvaluationKind.SUMMARY,
            primary_metric_name=metric_name,
            primary_metric_direction=MetricDirection.MAX,
            tie_breaker_metrics=[],
            split_strategy="none",
            test_size=0.0,
            cv_folds=None,
            random_state=42,
        )
    policy = _POLICIES[evaluation_kind].model_copy(deep=True)
    if not group_aware or evaluation_kind is EvaluationKind.FORECASTING:
        return policy
    if evaluation_kind not in {EvaluationKind.REGRESSION, EvaluationKind.CLASSIFICATION}:
        raise ValueError("Group-aware holdout is supported only for supervised evaluation.")
    return policy.model_copy(
        update={
            "policy_key": f"{evaluation_kind.value}.group_hash_holdout.v1",
            "split_strategy": "group_hash_holdout.v1",
        }
    )


def build_regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> CandidateMetrics:
    residuals = np.asarray(y_true) - np.asarray(y_pred)
    metrics = {
        "r2": float(r2_score(y_true, y_pred)),
        "mse": float(mean_squared_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "mape": float(mean_absolute_percentage_error(y_true, y_pred)),
        "explained_variance": float(explained_variance_score(y_true, y_pred)),
        "residual_mean": float(np.mean(residuals)),
        "residual_std": float(np.std(residuals)),
    }
    return CandidateMetrics(
        primary_metric_name="r2",
        primary_metric_value=metrics["r2"],
        metrics=metrics,
        details={"prediction_digest": prediction_digest(y_pred)},
    )


def build_classification_metrics(
    y_true: pd.Series,
    y_pred: np.ndarray,
    *,
    y_proba: np.ndarray | None = None,
    classes: Iterable[Any] | None = None,
) -> CandidateMetrics:
    labels = _classification_labels(y_true, y_pred, classes)
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision_weighted": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_weighted": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }
    details: dict[str, Any] = {
        "labels": [str(label) for label in labels],
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).astype(int).tolist(),
        "classification_report": _json_safe_classification_report(y_true, y_pred, labels),
        "probability_metrics": {},
        "prediction_digest": prediction_digest(y_pred),
    }
    metrics.update(_probability_metrics(y_true, y_proba, labels, details))
    return CandidateMetrics(
        primary_metric_name="f1_weighted",
        primary_metric_value=metrics["f1_weighted"],
        metrics=metrics,
        details=details,
    )


def compare_metric_snapshots(
    policy: EvaluationPolicySnapshot,
    left: CandidateMetrics,
    right: CandidateMetrics,
) -> int:
    primary = _compare_metric(
        policy.primary_metric_direction,
        left.primary_metric_value,
        right.primary_metric_value,
    )
    if primary != 0:
        return primary

    for metric_name in policy.tie_breaker_metrics:
        direction = _direction_for_metric(metric_name)
        comparison = _compare_metric(
            direction,
            left.metrics.get(metric_name),
            right.metrics.get(metric_name),
        )
        if comparison != 0:
            return comparison
    return 0


def build_dummy_baseline_metrics(
    evaluation_kind: EvaluationKind,
    y_train: pd.Series,
    y_holdout: pd.Series,
) -> CandidateMetrics:
    if y_train.empty or y_holdout.empty:
        raise ValueError("Baseline evaluation requires non-empty training and holdout targets.")
    train_input = np.zeros((len(y_train.index), 1), dtype=float)
    holdout_input = np.zeros((len(y_holdout.index), 1), dtype=float)
    if evaluation_kind is EvaluationKind.CLASSIFICATION:
        estimator = DummyClassifier(strategy="most_frequent")
        estimator.fit(train_input, y_train)
        predictions = estimator.predict(holdout_input)
        probabilities = estimator.predict_proba(holdout_input)
        return build_classification_metrics(
            y_holdout,
            predictions,
            y_proba=probabilities,
            classes=estimator.classes_,
        )
    if evaluation_kind is EvaluationKind.REGRESSION:
        estimator = DummyRegressor(strategy="mean")
        estimator.fit(train_input, y_train)
        return build_regression_metrics(y_holdout, estimator.predict(holdout_input))
    raise ValueError(f"Dummy baselines are not supported for evaluation kind '{evaluation_kind.value}'.")


def build_evaluation_comparison(
    policy: EvaluationPolicySnapshot,
    candidate: CandidateMetrics,
    baseline: CandidateMetrics,
) -> EvaluationComparison:
    result = compare_metric_snapshots(policy, candidate, baseline)
    verdict = EvaluationVerdict.TIED
    if result > 0:
        verdict = EvaluationVerdict.CANDIDATE_BETTER
    elif result < 0:
        verdict = EvaluationVerdict.BASELINE_BETTER
    return EvaluationComparison(
        primary_metric_name=policy.primary_metric_name,
        direction=policy.primary_metric_direction,
        candidate_value=candidate.primary_metric_value,
        baseline_value=baseline.primary_metric_value,
        verdict=verdict,
    )


def _compare_metric(direction: MetricDirection, left: float | None, right: float | None) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return -1
    if right is None:
        return 1
    if math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12):
        return 0
    if direction is MetricDirection.MAX:
        return 1 if left > right else -1
    return 1 if left < right else -1


def _direction_for_metric(metric_name: str) -> MetricDirection:
    if metric_name in {"rmse", "mae", "mse", "mape", "log_loss"}:
        return MetricDirection.MIN
    return MetricDirection.MAX


def build_metric_snapshot(
    evaluation_kind: EvaluationKind,
    y_true: pd.Series,
    y_pred: np.ndarray,
    *,
    y_proba: np.ndarray | None = None,
    classes: Iterable[Any] | None = None,
) -> CandidateMetrics:
    if evaluation_kind is EvaluationKind.REGRESSION:
        return build_regression_metrics(y_true, y_pred)
    if evaluation_kind is EvaluationKind.CLASSIFICATION:
        return build_classification_metrics(y_true, y_pred, y_proba=y_proba, classes=classes)
    raise ValueError(f"Metric snapshots are not supported for evaluation kind '{evaluation_kind.value}'.")


def scoring_name_for_policy(policy: EvaluationPolicySnapshot) -> str:
    return policy.primary_metric_name


def metric_names_for_policy(policy: EvaluationPolicySnapshot) -> Iterable[str]:
    yield policy.primary_metric_name
    yield from policy.tie_breaker_metrics


def prediction_digest(predictions: Iterable[Any]) -> str:
    values = [_canonical_prediction(value) for value in np.asarray(list(predictions), dtype=object).reshape(-1)]
    serialized = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _canonical_prediction(value: Any) -> dict[str, Any]:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": value}
    if isinstance(value, float):
        if math.isnan(value):
            rendered = "nan"
        elif math.isinf(value):
            rendered = "infinity" if value > 0 else "-infinity"
        else:
            rendered = value.hex()
        return {"type": "float", "value": rendered}
    return {"type": type(value).__name__, "value": str(value)}


def _classification_labels(
    y_true: pd.Series,
    y_pred: np.ndarray,
    classes: Iterable[Any] | None,
) -> list[Any]:
    labels: list[Any] = []
    for values in (classes, pd.unique(y_true), pd.unique(y_pred)):
        if values is None:
            continue
        for value in values:
            if not any(value == existing for existing in labels):
                labels.append(value)
    return labels


def _json_safe_classification_report(
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[Any],
) -> dict[str, Any]:
    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    return _json_safe(report)


def _probability_metrics(
    y_true: pd.Series,
    y_proba: np.ndarray | None,
    labels: list[Any],
    details: dict[str, Any],
) -> dict[str, float]:
    probability_details = details["probability_metrics"]
    if y_proba is None:
        probability_details["available"] = False
        probability_details["reason"] = "estimator_does_not_expose_predict_proba"
        return {}

    probabilities = np.asarray(y_proba)
    if probabilities.ndim != 2:
        probability_details["available"] = False
        probability_details["reason"] = "predict_proba_returned_unexpected_shape"
        return {}

    if len(labels) < 2:
        probability_details["available"] = False
        probability_details["reason"] = "holdout_contains_fewer_than_two_classes"
        return {}

    if probabilities.shape[1] != len(labels):
        probability_details["available"] = False
        probability_details["reason"] = "probability_columns_do_not_match_labels"
        return {}

    metrics: dict[str, float] = {}
    probability_details["available"] = True
    probability_details["variant"] = "binary" if len(labels) == 2 else "weighted_ovr"

    try:
        metrics["log_loss"] = float(log_loss(y_true, probabilities, labels=labels))
    except ValueError as exc:
        probability_details["log_loss_unavailable_reason"] = str(exc)

    try:
        if len(labels) == 2:
            positive_label = labels[1]
            positive_scores = probabilities[:, 1]
            y_binary = np.asarray([label == positive_label for label in y_true])
            metrics["roc_auc"] = float(roc_auc_score(y_binary, positive_scores))
            metrics["pr_auc"] = float(average_precision_score(y_binary, positive_scores))
            probability_details["positive_label"] = str(positive_label)
        else:
            y_binarized = label_binarize(y_true, classes=labels)
            metrics["roc_auc"] = float(
                roc_auc_score(
                    y_true,
                    probabilities,
                    labels=labels,
                    average="weighted",
                    multi_class="ovr",
                )
            )
            metrics["pr_auc"] = float(
                average_precision_score(
                    y_binarized,
                    probabilities,
                    average="weighted",
                )
            )
    except ValueError as exc:
        probability_details["auc_unavailable_reason"] = str(exc)

    return metrics


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value
