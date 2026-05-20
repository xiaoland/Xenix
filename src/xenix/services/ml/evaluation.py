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

from ..storage.models import ProblemKind
from .contracts import CandidateMetrics, EvaluationPolicySnapshot, MetricDirection

_POLICIES: dict[ProblemKind, EvaluationPolicySnapshot] = {
    ProblemKind.REGRESSION: EvaluationPolicySnapshot(
        policy_key="regression.default.v1",
        problem_kind=ProblemKind.REGRESSION,
        primary_metric_name="r2",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=["rmse", "mae"],
        split_strategy="holdout",
        test_size=0.2,
        cv_folds=5,
        random_state=42,
    ),
    ProblemKind.CLASSIFICATION: EvaluationPolicySnapshot(
        policy_key="classification.default.v1",
        problem_kind=ProblemKind.CLASSIFICATION,
        primary_metric_name="f1_weighted",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=["accuracy", "precision_weighted", "recall_weighted"],
        split_strategy="stratified_holdout",
        test_size=0.2,
        cv_folds=5,
        random_state=42,
    ),
    ProblemKind.CLUSTERING: EvaluationPolicySnapshot(
        policy_key="clustering.default.v1",
        problem_kind=ProblemKind.CLUSTERING,
        primary_metric_name="cluster_count",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=[],
        split_strategy="none",
        test_size=0.0,
        cv_folds=None,
        random_state=42,
    ),
    ProblemKind.ANOMALY_DETECTION: EvaluationPolicySnapshot(
        policy_key="anomaly_detection.default.v1",
        problem_kind=ProblemKind.ANOMALY_DETECTION,
        primary_metric_name="anomaly_count",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=[],
        split_strategy="none",
        test_size=0.0,
        cv_folds=None,
        random_state=42,
    ),
    ProblemKind.ANALYSIS: EvaluationPolicySnapshot(
        policy_key="analysis.default.v1",
        problem_kind=ProblemKind.ANALYSIS,
        primary_metric_name="result_count",
        primary_metric_direction=MetricDirection.MAX,
        tie_breaker_metrics=[],
        split_strategy="none",
        test_size=0.0,
        cv_folds=None,
        random_state=42,
    ),
}


def get_default_policy(problem_kind: ProblemKind) -> EvaluationPolicySnapshot:
    return _POLICIES[problem_kind]


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
    problem_kind: ProblemKind,
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> CandidateMetrics:
    if problem_kind is ProblemKind.REGRESSION:
        return build_regression_metrics(y_true, y_pred)
    if problem_kind is ProblemKind.CLASSIFICATION:
        return build_classification_metrics(y_true, y_pred)
    raise ValueError(f"Metric snapshots are not supported for problem kind '{problem_kind.value}'.")


def scoring_name_for_policy(policy: EvaluationPolicySnapshot) -> str:
    return policy.primary_metric_name


def metric_names_for_policy(policy: EvaluationPolicySnapshot) -> Iterable[str]:
    yield policy.primary_metric_name
    yield from policy.tie_breaker_metrics
