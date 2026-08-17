from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from xenix.exceptions import ValidationError
from xenix.services.ml.contracts import (
    DatasetSnapshotFact,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    EvaluationVerdict,
    FitTaskRequest,
    ManualTrainingPayload,
)
from xenix.services.ml.evaluation import (
    build_dummy_baseline_metrics,
    build_evaluation_comparison,
    build_metric_snapshot,
    get_default_policy,
)
from xenix.services.ml.preparation import build_group_aware_cv, prepare_supervised_split
from xenix.services.ml.registry import list_model_catalog
from xenix.services.ml.models.classification import LogisticRegressionService
from xenix.services.ml.types import ColumnRoleKind, EvaluationKind


def _snapshot(*, source_sha256: str = "a" * 64) -> DatasetSnapshotFact:
    return DatasetSnapshotFact(
        dataset_id="dataset-1",
        source_sha256=source_sha256,
        source_byte_size=1024,
        schema_digest="b" * 64,
    )


def _request(
    *,
    evaluation_kind: EvaluationKind = EvaluationKind.CLASSIFICATION,
    grouped: bool = False,
    source_sha256: str = "a" * 64,
    dataset_source_path: str = "C:/fixtures/grouped.csv",
) -> FitTaskRequest:
    bindings = [
        {"role": "feature", "columns": ["amount", "region"]},
        {"role": "target", "columns": ["converted"]},
    ]
    if grouped:
        bindings.append({"role": "group", "columns": ["account_id"]})
    return FitTaskRequest(
        task_id="task-1",
        project_id="project-1",
        dataset_id="dataset-1",
        dataset_source_path=dataset_source_path,
        evaluation_kind=evaluation_kind,
        train_role_bindings=bindings,
        evaluation_policy=get_default_policy(evaluation_kind, group_aware=grouped),
        dataset_snapshot=_snapshot(source_sha256=source_sha256),
        manual_training=ManualTrainingPayload(model_key="classification.logistic_regression"),
    )


def test_supervised_catalogs_offer_optional_single_group_role() -> None:
    supervised = [
        entry
        for entry in list_model_catalog()
        if entry.requires_target
        and entry.evaluation_kind in {EvaluationKind.CLASSIFICATION, EvaluationKind.REGRESSION}
    ]

    assert supervised
    for entry in supervised:
        group_roles = [role for role in entry.train_role_schema.roles if role.name == "group"]
        assert len(group_roles) == 1, entry.model_key
        assert group_roles[0].kind is ColumnRoleKind.SINGLE_COLUMN
        assert group_roles[0].required is False
        assert "group" not in {role.name for role in entry.apply_role_schema.roles}


def test_group_hash_holdout_is_versioned_deterministic_and_disjoint() -> None:
    frame = pd.DataFrame(
        {
            "amount": list(range(24)),
            "region": ["north", "south"] * 12,
            "converted": [0, 1] * 12,
            "account_id": [f"account-{index}" for index in range(12) for _ in range(2)],
        }
    )
    request = _request(grouped=True)

    first = prepare_supervised_split(
        frame[["amount", "region"]],
        frame["converted"],
        request,
        groups=frame["account_id"],
    )
    second = prepare_supervised_split(
        frame[["amount", "region"]],
        frame["converted"],
        request,
        groups=frame["account_id"],
    )

    assert first.split_facts == second.split_facts
    assert first.split_facts.requested_strategy == "group_hash_holdout.v1"
    assert first.split_facts.realized_strategy == "group_hash_holdout.v1"
    assert first.split_facts.group_overlap_count == 0
    assert first.train_groups is not None
    assert first.holdout_groups is not None
    assert set(first.train_groups.tolist()).isdisjoint(set(first.holdout_groups.tolist()))
    assert first.split_facts.train_membership_digest != first.split_facts.holdout_membership_digest


def test_group_split_digest_is_bound_to_dataset_snapshot() -> None:
    features = pd.DataFrame({"amount": list(range(16)), "region": ["a", "b"] * 8})
    target = pd.Series([0, 1] * 8)
    groups = pd.Series([f"g{index}" for index in range(8) for _ in range(2)])

    first = prepare_supervised_split(features, target, _request(grouped=True), groups=groups)
    changed = prepare_supervised_split(
        features,
        target,
        _request(grouped=True, source_sha256="c" * 64),
        groups=groups,
    )

    assert (
        first.split_facts.source_dataset_snapshot_digest
        != changed.split_facts.source_dataset_snapshot_digest
    )
    assert first.split_facts.train_membership_digest != changed.split_facts.train_membership_digest


def test_infeasible_stratified_holdout_fails_without_row_random_fallback() -> None:
    request = _request()

    with pytest.raises(ValidationError, match="stratified_holdout.*infeasible"):
        prepare_supervised_split(
            pd.DataFrame({"amount": [1, 2, 3, 4], "region": ["a", "a", "b", "b"]}),
            pd.Series([0, 0, 0, 1]),
            request,
        )


def test_group_role_rejects_non_group_policy() -> None:
    request = _request(grouped=True)
    request.evaluation_policy = get_default_policy(EvaluationKind.CLASSIFICATION)

    with pytest.raises(ValidationError, match="requires evaluation policy 'group_hash_holdout.v1'"):
        prepare_supervised_split(
            pd.DataFrame({"amount": range(8), "region": ["a", "b"] * 4}),
            pd.Series([0, 1] * 4),
            request,
            groups=pd.Series([f"g{index}" for index in range(4) for _ in range(2)]),
        )


def test_group_aware_tuning_requires_class_coverage_across_folds() -> None:
    policy = get_default_policy(EvaluationKind.CLASSIFICATION, group_aware=True)
    target = pd.Series([0, 1] * 10)
    groups = pd.Series([f"g{index}" for index in range(10) for _ in range(2)])

    cv, returned_groups = build_group_aware_cv(policy, EvaluationKind.CLASSIFICATION, target, groups)

    assert cv.n_splits == policy.cv_folds
    assert returned_groups is groups

    with pytest.raises(ValidationError, match="every target class"):
        build_group_aware_cv(
            policy,
            EvaluationKind.CLASSIFICATION,
            pd.Series([0] * 12 + [1] * 8),
            groups,
        )


def test_same_holdout_dummy_baseline_produces_typed_comparison_and_digests() -> None:
    policy = get_default_policy(EvaluationKind.CLASSIFICATION)
    y_train = pd.Series([0, 0, 0, 1, 1, 1])
    y_holdout = pd.Series([0, 1, 0, 1])
    candidate = build_metric_snapshot(
        EvaluationKind.CLASSIFICATION,
        y_holdout,
        pd.Series([0, 1, 0, 1]).to_numpy(),
    )
    baseline = build_dummy_baseline_metrics(EvaluationKind.CLASSIFICATION, y_train, y_holdout)

    comparison = build_evaluation_comparison(policy, candidate, baseline)

    assert comparison.verdict is EvaluationVerdict.CANDIDATE_BETTER
    assert comparison.direction == policy.primary_metric_direction
    assert len(candidate.details["prediction_digest"]) == 64
    assert len(baseline.details["prediction_digest"]) == 64


def test_grouped_tabular_fit_and_evaluate_preserve_typed_facts(tmp_path: Path) -> None:
    source = tmp_path / "grouped.csv"
    frame = pd.DataFrame(
        {
            "amount": [float(index) for index in range(24)],
            "region": ["north", "south"] * 12,
            "converted": [0, 1] * 12,
            "account_id": [f"account-{index}" for index in range(12) for _ in range(2)],
        }
    )
    frame.to_csv(source, index=False)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    request = _request(
        grouped=True,
        source_sha256=source_sha256,
        dataset_source_path=str(source),
    )
    task_dir = tmp_path / "task"

    fit_result = LogisticRegressionService.fit(request, task_dir)

    assert fit_result.split_facts is not None
    assert fit_result.preparation_facts is not None
    assert fit_result.split_facts.group_overlap_count == 0
    assert fit_result.preparation_facts.fit_scope == "outer_train_split"
    assert fit_result.preparation_facts.fit_row_count == fit_result.split_facts.train_row_count
    assert fit_result.final_model_artifact_path != fit_result.model_artifact_path

    evaluation = LogisticRegressionService.evaluate(
        EvaluateTaskRequest(
            task_id="evaluate-1",
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            dataset_source_path=request.dataset_source_path,
            evaluation_kind=request.evaluation_kind,
            train_role_bindings=request.train_role_bindings,
            evaluation_policy=request.evaluation_policy,
            dataset_snapshot=request.dataset_snapshot,
            evaluate_model=EvaluateModelPayload(
                trained_model_id="trained-1",
                model_key=LogisticRegressionService.key,
                trained_model_artifact_path=fit_result.model_artifact_path,
                holdout_artifact_path=fit_result.holdout_artifact_path or "",
            ),
        ),
        task_dir,
    )

    assert evaluation.split_facts == fit_result.split_facts
    assert evaluation.preparation_facts == fit_result.preparation_facts
    assert evaluation.comparison.primary_metric_name == "f1_weighted"
    assert len(evaluation.evaluation.details["prediction_digest"]) == 64
    assert len(evaluation.baseline_evaluation.details["prediction_digest"]) == 64
