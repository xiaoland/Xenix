"""Grouped out-of-fold evidence for retained text classifiers.

Vocabulary and classifier fitting happen inside each partition. Only predictions,
fold membership and decision evidence are retained; evaluation never scores the
all-rows apply model on the data that trained it.
"""
from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GroupKFold

from ...exceptions import ValidationError
from .contracts import EvaluationPolicySnapshot
from .evaluation import build_evaluation_comparison, build_metric_snapshot
from .text_preparation import PreparedTextClassificationData


def write_cross_validation(
    prepared: PreparedTextClassificationData, *,
    build_estimator: Callable[[], Any], policy: EvaluationPolicySnapshot,
    source_sha256: str, path: Path,
) -> None:
    labels = prepared.labels
    groups = prepared.connected_groups
    group_count = int(groups.nunique())
    fold_count = min(policy.cv_folds or 5, group_count)
    classes = np.unique(labels)
    frame = pd.DataFrame({"target": labels, "prediction": [None] * len(labels),
                          "baseline": [None] * len(labels), "fold": [-1] * len(labels)})
    probabilities = np.zeros((len(labels), len(classes)))
    folds = []
    membership = []
    if fold_count >= 2:
        for index, (train, test) in enumerate(GroupKFold(n_splits=fold_count).split(labels, labels, groups)):
            membership.append(test.tolist())
            fact: dict[str, Any] = {"fold": index + 1, "train_rows": len(train), "validation_rows": len(test)}
            fact["train_groups"] = int(groups.iloc[train].nunique())
            fact["validation_groups"] = int(groups.iloc[test].nunique())
            fact["group_overlap_count"] = len(set(groups.iloc[train]) & set(groups.iloc[test]))
            if labels.iloc[train].nunique() < 2:
                fact["unavailable_reason"] = "Training partition contains only one class."
                folds.append(fact)
                continue
            estimator = build_estimator()
            try:
                estimator.fit(prepared.raw_texts.iloc[train], labels.iloc[train])
            except ValidationError as exc:
                # A candidate can fit all rows while lacking a vocabulary in a
                # particular fold. Expose that limitation instead of scoring
                # only its easy folds or discarding the usable apply model.
                fact["unavailable_reason"] = str(exc)
                folds.append(fact)
                continue
            texts = prepared.raw_texts.iloc[test]
            predictions = estimator.predict(texts)
            fold_probabilities = estimator.predict_proba(texts)
            for column, label in enumerate(estimator.classes_):
                probabilities[test, int(np.flatnonzero(classes == label)[0])] = fold_probabilities[:, column]
            dummy = DummyClassifier(strategy="most_frequent").fit(np.zeros((len(train), 1)), labels.iloc[train])
            frame.loc[test, "prediction"] = predictions
            frame.loc[test, "baseline"] = dummy.predict(np.zeros((len(test), 1)))
            frame.loc[test, "fold"] = index
            fact["accuracy"] = float(np.mean(predictions == labels.iloc[test]))
            folds.append(fact)
    evaluated = int(frame.prediction.notna().sum())
    identity = json.dumps({"source": source_sha256, "labels": labels.tolist(), "folds": membership}, sort_keys=True, ensure_ascii=False)
    scores = [fold["accuracy"] for fold in folds if "accuracy" in fold]
    evidence = {
        "method": "group_cross_validation", "evaluation_id": sha256(identity.encode()).hexdigest()[:16],
        "fold_count": fold_count, "group_count": group_count,
        "eligible_row_count": len(labels), "evaluated_row_count": evaluated,
        "status": "complete" if evaluated == len(labels) else "incomplete",
        "folds": folds,
        "accuracy_range": {"min": min(scores), "max": max(scores)} if scores else None,
        "interpretation": "Out-of-fold selection evidence, not independent acceptance after tuning. Matching evaluation_id means reused validation data.",
    }
    if fold_count < 2:
        evidence["unavailable_reason"] = "Only one independent group; grouped validation is unavailable."
    frame.attrs["cross_validation"] = evidence
    frame.attrs["probabilities"] = probabilities
    frame.attrs["classes"] = classes
    frame.to_pickle(path)


def read_cross_validation(path: Path, policy: EvaluationPolicySnapshot) -> dict[str, Any]:
    frame = pd.read_pickle(path)
    facts = frame.attrs["cross_validation"]
    if facts["status"] != "complete":
        return {"cross_validation": facts}
    metrics = build_metric_snapshot(policy.evaluation_kind, frame.target, np.asarray(frame.prediction.tolist()),
        y_proba=frame.attrs["probabilities"], classes=frame.attrs["classes"])
    baseline = build_metric_snapshot(policy.evaluation_kind, frame.target, np.asarray(frame.baseline.tolist()))
    return {"evaluation": metrics, "baseline_evaluation": baseline,
            "comparison": build_evaluation_comparison(policy, metrics, baseline), "cross_validation": facts}
