from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

from .contracts import CandidateMetrics, EvaluationPolicySnapshot, MetricDirection
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
}


def get_default_policy(
    evaluation_kind: EvaluationKind,
    *,
    summary_metric_name: str | None = None,
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
    return _POLICIES[evaluation_kind].model_copy(deep=True)


def build_regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> CandidateMetrics:
    metrics = {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }
    return CandidateMetrics(
        primary_metric_name="r2",
        primary_metric_value=metrics["r2"],
        metrics=metrics,
    )


def build_classification_metrics(y_true: pd.Series, y_pred: np.ndarray) -> CandidateMetrics:
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_weighted": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall_weighted": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }
    return CandidateMetrics(
        primary_metric_name="f1_weighted",
        primary_metric_value=metrics["f1_weighted"],
        metrics=metrics,
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
    if metric_name in {"rmse", "mae", "mse", "log_loss"}:
        return MetricDirection.MIN
    return MetricDirection.MAX


def build_metric_snapshot(
    evaluation_kind: EvaluationKind,
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> CandidateMetrics:
    if evaluation_kind is EvaluationKind.REGRESSION:
        return build_regression_metrics(y_true, y_pred)
    if evaluation_kind is EvaluationKind.CLASSIFICATION:
        return build_classification_metrics(y_true, y_pred)
    raise ValueError(f"Metric snapshots are not supported for evaluation kind '{evaluation_kind.value}'.")


def scoring_name_for_policy(policy: EvaluationPolicySnapshot) -> str:
    return policy.primary_metric_name


def metric_names_for_policy(policy: EvaluationPolicySnapshot) -> Iterable[str]:
    yield policy.primary_metric_name
    yield from policy.tie_breaker_metrics
