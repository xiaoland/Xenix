from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, train_test_split

from ...exceptions import ValidationError
from .contracts import (
    DatasetSnapshotFact,
    EvaluationPolicySnapshot,
    PreparationFacts,
    SplitFacts,
    TaskRequestBase,
)
from .types import EvaluationKind

_GROUP_SPLIT_STRATEGY = "group_hash_holdout.v1"
_HOLDOUT_CONTEXT_KEY = "xenix.evaluation_context.v1"


@dataclass(frozen=True)
class PreparedSupervisedSplit:
    train_features: pd.DataFrame | pd.Series
    holdout_features: pd.DataFrame | pd.Series
    train_target: pd.Series
    holdout_target: pd.Series
    train_groups: pd.Series | None
    holdout_groups: pd.Series | None
    train_positions: np.ndarray
    holdout_positions: np.ndarray
    split_facts: SplitFacts


def prepare_supervised_split(
    features: pd.DataFrame | pd.Series,
    target: pd.Series,
    request: TaskRequestBase,
    *,
    groups: pd.Series | None = None,
) -> PreparedSupervisedSplit:
    if len(features.index) != len(target.index):
        raise ValidationError("Supervised features and target must contain the same rows.")
    if len(target.index) < 2:
        raise ValidationError("Supervised evaluation requires at least two eligible rows.")

    normalized_features = features.reset_index(drop=True)
    normalized_target = target.reset_index(drop=True)
    positions = np.arange(len(normalized_target.index), dtype=int)
    normalized_groups = _canonical_groups(groups, expected_length=len(positions))
    policy = request.evaluation_policy

    if normalized_groups is not None:
        if policy.split_strategy != _GROUP_SPLIT_STRATEGY:
            raise ValidationError(
                "A group role requires evaluation policy 'group_hash_holdout.v1'; re-create the training task."
            )
        train_positions, holdout_positions = _group_hash_positions(
            normalized_groups,
            normalized_target,
            evaluation_kind=request.evaluation_kind,
            test_size=policy.test_size,
            random_state=policy.random_state,
            snapshot=request.dataset_snapshot,
        )
        train_groups = normalized_groups.iloc[train_positions].reset_index(drop=True)
        holdout_groups = normalized_groups.iloc[holdout_positions].reset_index(drop=True)
        train_group_values = set(train_groups.tolist())
        holdout_group_values = set(holdout_groups.tolist())
        overlap_count = len(train_group_values & holdout_group_values)
        if overlap_count:
            raise ValidationError("Group-safe evaluation produced overlapping groups and was rejected.")
        group_counts: tuple[int | None, int | None, int | None] = (
            int(normalized_groups.nunique(dropna=False)),
            len(train_group_values),
            len(holdout_group_values),
        )
        realized_strategy = _GROUP_SPLIT_STRATEGY
    else:
        expected_strategy = _expected_row_strategy(request.evaluation_kind)
        if policy.split_strategy != expected_strategy:
            raise ValidationError(
                f"Evaluation policy declares '{policy.split_strategy}' but this supervised task requires "
                f"'{expected_strategy}'."
            )
        stratify = normalized_target if request.evaluation_kind is EvaluationKind.CLASSIFICATION else None
        try:
            train_positions, holdout_positions = train_test_split(
                positions,
                test_size=policy.test_size,
                random_state=policy.random_state,
                stratify=stratify,
            )
        except ValueError as exc:
            raise ValidationError(
                f"Evaluation split '{policy.split_strategy}' is infeasible for this target distribution: {exc}"
            ) from exc
        train_groups = None
        holdout_groups = None
        group_counts = (None, None, None)
        overlap_count = 0
        realized_strategy = expected_strategy

    train_positions = np.asarray(train_positions, dtype=int)
    holdout_positions = np.asarray(holdout_positions, dtype=int)
    if not len(train_positions) or not len(holdout_positions):
        raise ValidationError("Evaluation split must produce non-empty training and holdout partitions.")

    snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
    split_facts = SplitFacts(
        policy_key=policy.policy_key,
        requested_strategy=policy.split_strategy,
        realized_strategy=realized_strategy,
        source_dataset_snapshot_digest=snapshot_digest,
        eligible_row_count=len(positions),
        train_row_count=len(train_positions),
        holdout_row_count=len(holdout_positions),
        eligible_group_count=group_counts[0],
        train_group_count=group_counts[1],
        holdout_group_count=group_counts[2],
        train_membership_digest=_membership_digest(snapshot_digest, "train", train_positions),
        holdout_membership_digest=_membership_digest(snapshot_digest, "holdout", holdout_positions),
        group_overlap_count=overlap_count,
        random_state=policy.random_state,
    )
    return PreparedSupervisedSplit(
        train_features=normalized_features.iloc[train_positions].reset_index(drop=True),
        holdout_features=normalized_features.iloc[holdout_positions].reset_index(drop=True),
        train_target=normalized_target.iloc[train_positions].reset_index(drop=True),
        holdout_target=normalized_target.iloc[holdout_positions].reset_index(drop=True),
        train_groups=train_groups,
        holdout_groups=holdout_groups,
        train_positions=train_positions,
        holdout_positions=holdout_positions,
        split_facts=split_facts,
    )


def build_group_aware_cv(
    policy: EvaluationPolicySnapshot,
    evaluation_kind: EvaluationKind,
    target: pd.Series,
    groups: pd.Series | None,
) -> tuple[int | GroupKFold | StratifiedGroupKFold, pd.Series | None]:
    if policy.cv_folds is None or policy.cv_folds < 2:
        raise ValidationError("Hyperparameter tuning requires at least two cross-validation folds.")
    if groups is None:
        return policy.cv_folds, None

    group_count = int(groups.nunique(dropna=False))
    if group_count < policy.cv_folds:
        raise ValidationError(
            f"Group-aware tuning requires at least {policy.cv_folds} training groups; found {group_count}."
        )
    if evaluation_kind is EvaluationKind.CLASSIFICATION:
        frame = pd.DataFrame({"target": target.reset_index(drop=True), "group": groups.reset_index(drop=True)})
        groups_per_class = frame.groupby("target", dropna=False)["group"].nunique(dropna=False)
        if groups_per_class.empty or int(groups_per_class.min()) < policy.cv_folds:
            raise ValidationError(
                "Stratified group-aware tuning requires every target class in at least "
                f"{policy.cv_folds} training groups."
            )
        return (
            StratifiedGroupKFold(
                n_splits=policy.cv_folds,
                shuffle=True,
                random_state=policy.random_state,
            ),
            groups,
        )
    if evaluation_kind is EvaluationKind.REGRESSION:
        return GroupKFold(n_splits=policy.cv_folds), groups
    raise ValidationError("Group-aware tuning is supported only for supervised evaluation.")


def build_tabular_preparation_facts(
    estimator: Any,
    train_features: pd.DataFrame,
) -> PreparationFacts:
    try:
        preprocessor = estimator.named_steps["preprocess"]
        output_names = [str(name) for name in preprocessor.get_feature_names_out()]
        resolved = {str(name): list(columns) for name, _transformer, columns in preprocessor.transformers_}
    except Exception as exc:
        raise ValidationError("The fitted model did not expose its preparation output schema.") from exc
    return PreparationFacts(
        fit_row_count=len(train_features.index),
        raw_feature_count=len(train_features.columns),
        transformed_feature_count=len(output_names),
        numeric_feature_count=len(resolved.get("numeric", [])),
        categorical_feature_count=len(resolved.get("categorical", [])),
        text_feature_count=0,
        unknown_category_handling="ignore",
        output_schema_digest=_ordered_digest(output_names),
    )


def build_text_preparation_facts(estimator: Any, *, fit_row_count: int) -> PreparationFacts:
    try:
        output_names = [str(name) for name in estimator.vectorizer.get_feature_names_out()]
    except Exception as exc:
        raise ValidationError("The fitted text model did not expose its vectorizer output schema.") from exc
    return PreparationFacts(
        fit_row_count=fit_row_count,
        raw_feature_count=1,
        transformed_feature_count=len(output_names),
        numeric_feature_count=0,
        categorical_feature_count=0,
        text_feature_count=1,
        unknown_category_handling="not_applicable",
        output_schema_digest=_ordered_digest(output_names),
    )


def attach_evaluation_context(
    holdout: pd.DataFrame,
    *,
    training_target: pd.Series,
    split_facts: SplitFacts,
    preparation_facts: PreparationFacts,
) -> None:
    holdout.attrs[_HOLDOUT_CONTEXT_KEY] = {
        "training_target": training_target.reset_index(drop=True),
        "split_facts": split_facts.model_dump(mode="json"),
        "preparation_facts": preparation_facts.model_dump(mode="json"),
    }


def read_evaluation_context(
    holdout: pd.DataFrame,
) -> tuple[pd.Series, SplitFacts, PreparationFacts]:
    payload = holdout.attrs.get(_HOLDOUT_CONTEXT_KEY)
    if not isinstance(payload, dict) or not isinstance(payload.get("training_target"), pd.Series):
        raise ValidationError(
            "The holdout artifact predates typed evaluation facts; retrain the model before evaluation."
        )
    return (
        payload["training_target"].reset_index(drop=True),
        SplitFacts.model_validate(payload.get("split_facts")),
        PreparationFacts.model_validate(payload.get("preparation_facts")),
    )


def dataset_snapshot_digest(snapshot: DatasetSnapshotFact) -> str:
    serialized = json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonicalize_group_series(groups: pd.Series) -> pd.Series:
    return groups.reset_index(drop=True).map(_canonical_group_value).astype("string")


def membership_digest(snapshot_digest: str, partition: str, positions: np.ndarray) -> str:
    return _membership_digest(snapshot_digest, partition, positions)


def _canonical_groups(groups: pd.Series | None, *, expected_length: int) -> pd.Series | None:
    if groups is None:
        return None
    if len(groups.index) != expected_length:
        raise ValidationError("Group values must align with all eligible supervised rows.")
    return canonicalize_group_series(groups)


def _canonical_group_value(value: Any) -> str:
    if pd.isna(value):
        payload = {"type": "null", "value": None}
    else:
        payload = {"type": type(value).__name__, "value": str(value)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _group_hash_positions(
    groups: pd.Series,
    target: pd.Series,
    *,
    evaluation_kind: EvaluationKind,
    test_size: float,
    random_state: int,
    snapshot: DatasetSnapshotFact,
) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic group-safe holdout split.

    Group order is derived from a hash of (strategy, random_state,
    snapshot_digest, group value) so the split reproduces identically when
    evaluation recomputes it from the request, independent of row order. The final
    group is never assigned to holdout so at least one group always remains in
    training.
    """
    unique_groups = groups.drop_duplicates().tolist()
    if len(unique_groups) < 2:
        raise ValidationError("Group-safe evaluation requires at least two distinct groups.")
    snapshot_digest = dataset_snapshot_digest(snapshot)
    ordered_groups = sorted(
        unique_groups,
        key=lambda value: hashlib.sha256(
            f"{_GROUP_SPLIT_STRATEGY}|{random_state}|{snapshot_digest}|{value}".encode("utf-8")
        ).hexdigest(),
    )
    target_rows = max(1, round(len(groups.index) * test_size))
    cumulative = 0
    candidates: list[tuple[int, int]] = []
    counts = groups.value_counts(dropna=False).to_dict()
    for count, group in enumerate(ordered_groups[:-1], start=1):
        cumulative += int(counts[group])
        candidates.append((abs(cumulative - target_rows), count))
    _distance, selected_count = min(candidates)
    holdout_groups = set(ordered_groups[:selected_count])
    holdout_mask = groups.isin(holdout_groups).to_numpy(dtype=bool)
    holdout_positions = np.flatnonzero(holdout_mask)
    train_positions = np.flatnonzero(~holdout_mask)
    _validate_target_credibility(target, train_positions, holdout_positions, evaluation_kind)
    return train_positions, holdout_positions


def _validate_target_credibility(
    target: pd.Series,
    train_positions: np.ndarray,
    holdout_positions: np.ndarray,
    evaluation_kind: EvaluationKind,
) -> None:
    if len(train_positions) < 2 or len(holdout_positions) < 2:
        raise ValidationError("Group-safe evaluation requires at least two rows in each partition.")
    if evaluation_kind is not EvaluationKind.CLASSIFICATION:
        return
    all_classes = set(target.dropna().astype(str).tolist())
    train_classes = set(target.iloc[train_positions].dropna().astype(str).tolist())
    holdout_classes = set(target.iloc[holdout_positions].dropna().astype(str).tolist())
    if len(all_classes) < 2 or train_classes != all_classes or holdout_classes != all_classes:
        raise ValidationError(
            "Group-safe classification requires every target class in both training and holdout partitions."
        )


def _expected_row_strategy(evaluation_kind: EvaluationKind) -> str:
    if evaluation_kind is EvaluationKind.CLASSIFICATION:
        return "stratified_holdout"
    if evaluation_kind is EvaluationKind.REGRESSION:
        return "holdout"
    raise ValidationError("Row holdout is supported only for supervised evaluation.")


def _membership_digest(snapshot_digest: str, partition: str, positions: np.ndarray) -> str:
    payload = ",".join(str(int(position)) for position in sorted(positions.tolist()))
    return hashlib.sha256(f"{snapshot_digest}|{partition}|{payload}".encode("utf-8")).hexdigest()


def _ordered_digest(values: list[str]) -> str:
    serialized = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
