from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from benchmarks.agent_harness._infra.budgets import (
    BenchmarkBudgetPolicy,
    BenchmarkBudgetSnapshot,
    BenchmarkBudgetStatus,
)
from benchmarks.agent_harness._infra.contracts import (
    AgentHarnessBenchmarkResult,
    BenchmarkExecutionMode,
    BenchmarkIdentity,
    BenchmarkMetrics,
    BenchmarkRunStatus,
    JudgeIndependence,
    JudgeMetrics,
    JudgeResult,
    JudgeStatus,
    OutcomeCheck,
    SemanticVerdict,
    TokenUsage,
)
from benchmarks.agent_harness._infra.judge_calibration import (
    CalibrationObservation,
    JudgeCalibrationReport,
)
from benchmarks.agent_harness._infra.report_policy import (
    ReportPolicyError,
    ReportQualification,
    compare_report_cohorts,
    evaluate_characterization,
    evaluate_formal_acceptance,
    load_agent_report,
)


_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64
_HASH_E = "e" * 64
_HASH_F = "f" * 64
_RUBRIC_ID = "analysis.test.v1"
_SUBJECT_MODEL = "subject/model"
_JUDGE_MODEL = "judge/model"


def test_v4_is_diagnostic_only_and_v5_requires_the_agent_report_kind(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        json.dumps({"schema_version": 4, "case_id": "case", "run_id": "legacy"}),
        encoding="utf-8",
    )
    legacy = load_agent_report(legacy_path)

    assert legacy.qualification is ReportQualification.LEGACY_UNQUALIFIED
    decision = evaluate_characterization((legacy,))
    assert not decision.qualified
    assert decision.reason_codes == ("legacy_unqualified",)

    service_like_path = tmp_path / "service-like.json"
    payload = _result(run_id="v5").to_payload()
    payload.pop("report_kind")
    service_like_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ReportPolicyError, match="report_shape_invalid"):
        load_agent_report(service_like_path)


def test_characterization_qualifies_one_headless_measurement_without_gating(tmp_path: Path) -> None:
    report = _load_result(
        tmp_path,
        _result(
            run_id="characterization",
            semantic=SemanticVerdict.FAIL,
            semantic_check_passed=False,
        ),
    )

    decision = evaluate_characterization((report,))

    assert decision.qualified
    assert not decision.accepted
    assert not decision.gate_eligible
    assert decision.reason_codes == ()


def test_response_boundary_equality_remains_a_valid_measurement(tmp_path: Path) -> None:
    result = _result(run_id="exact-budget-boundary")
    boundary_budget = replace(
        result.budget,
        reported_subject_tokens=500_000,
        invocation_reported_subject_tokens=4_000_000,
    )
    boundary_metrics = replace(
        result.subject_metrics,
        token_usage=TokenUsage(499_000, 0, 1_000, 500_000),
    )

    report = _load_result(
        tmp_path,
        replace(
            result,
            budget=boundary_budget,
            subject_metrics=boundary_metrics,
        ),
    )

    assert evaluate_characterization((report,)).qualified


def test_report_rejects_subject_budget_projection_drift(tmp_path: Path) -> None:
    payload = _result(run_id="projection-drift").to_payload()
    payload["budget"]["reported_subject_tokens"] = 121
    path = tmp_path / "projection-drift.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReportPolicyError, match="subject_budget_projection_invalid"):
        load_agent_report(path)


def test_formal_acceptance_requires_calibrated_independent_judge_and_four_repetitions(
    tmp_path: Path,
) -> None:
    reports = tuple(
        _load_result(
            tmp_path,
            _result(
                run_id=f"headless-{index}",
                judge_required=True,
            ),
        )
        for index in range(3)
    ) + (
        _load_result(
            tmp_path,
            _result(
                run_id="headed-1",
                execution_mode=BenchmarkExecutionMode.HEADED,
                judge_required=True,
            ),
        ),
    )
    calibration = _calibration_report()

    accepted = evaluate_formal_acceptance(reports, calibrations=(calibration,))
    uncalibrated = evaluate_formal_acceptance(reports)
    same_model_payload = dict(reports[0].payload)
    same_model_payload["judge"] = dict(same_model_payload["judge"])
    same_model_payload["judge"]["independence"] = "same_model"
    same_model_report = replace(reports[0], payload=same_model_payload)
    non_independent = evaluate_formal_acceptance(
        (same_model_report, *reports[1:]),
        calibrations=(calibration,),
    )

    assert accepted.accepted
    assert accepted.gate_eligible
    assert "judge_calibration_missing_or_mismatched" in uncalibrated.reason_codes
    assert "judge_not_independent" in non_independent.reason_codes


def test_comparison_allows_commit_and_variant_changes_but_not_effective_settings_drift(
    tmp_path: Path,
) -> None:
    baseline = (
        _load_result(
            tmp_path,
            _result(run_id="baseline", commit="abc123", variant="baseline"),
        ),
    )
    candidate = (
        _load_result(
            tmp_path,
            _result(run_id="candidate", commit="def456", variant="improvement"),
        ),
    )

    comparison = compare_report_cohorts(baseline, candidate)
    assert comparison.comparable
    assert comparison.passed
    assert not comparison.gate_eligible

    drifted_payload = dict(candidate[0].payload)
    drifted_payload["identity"] = dict(drifted_payload["identity"])
    drifted_payload["identity"]["effective_settings_sha256"] = _HASH_F
    drifted = replace(candidate[0], payload=drifted_payload)
    rejected = compare_report_cohorts(baseline, (drifted,))

    assert not rejected.comparable
    assert "comparison_identity_effective_settings_sha256_mismatch" in rejected.reason_codes


def _result(
    *,
    run_id: str,
    execution_mode: BenchmarkExecutionMode = BenchmarkExecutionMode.HEADLESS,
    semantic: SemanticVerdict = SemanticVerdict.PASS,
    judge_required: bool = False,
    commit: str = "abc123",
    variant: str = "baseline",
    semantic_check_passed: bool = True,
) -> AgentHarnessBenchmarkResult:
    rubric_sha256 = _HASH_F.upper() if judge_required else None
    judge = (
        JudgeResult(
            required=True,
            rubric_id=_RUBRIC_ID,
            rubric_sha256=rubric_sha256,
            status=JudgeStatus.COMPLETED,
            verdict=semantic,
            provider_model=_JUDGE_MODEL,
            independence=JudgeIndependence.INDEPENDENT,
            scores={"quality": 2},
            reason_codes=("supported",),
            summary="judge_completed",
            metrics=JudgeMetrics(
                elapsed_seconds=1.0,
                token_usage=TokenUsage(10, 0, 5, 15),
            ),
        )
        if judge_required
        else JudgeResult()
    )
    policy = BenchmarkBudgetPolicy()
    return AgentHarnessBenchmarkResult(
        case_id="analysis.test",
        run_id=run_id,
        provider_model=_SUBJECT_MODEL,
        execution_mode=execution_mode,
        run_status=BenchmarkRunStatus.COMPLETED,
        subject_metrics=BenchmarkMetrics(
            turn_seconds=2.0,
            assessment_seconds=0.1,
            sampling_round_count=1,
            usage_reported_primary_response_count=1,
            token_usage=TokenUsage(100, 0, 20, 120),
        ),
        budget=BenchmarkBudgetSnapshot(
            status=BenchmarkBudgetStatus.WITHIN_LIMITS,
            policy=policy,
            sampling_rounds_admitted=1,
            provider_attempts_dispatched=1,
            reported_subject_tokens=120,
            invocation_reported_subject_tokens=120,
        ),
        semantic_verdict=semantic,
        semantic_checks=(
            OutcomeCheck(
                "terminal_output",
                semantic_check_passed,
                "settled" if semantic_check_passed else "missing",
            ),
        ),
        integrity_checks=(OutcomeCheck("isolated", True, "isolated"),),
        judge=judge,
        identity=BenchmarkIdentity(
            fixture_sha256=_HASH_A,
            settings_sha256=_HASH_B,
            embedding_settings_sha256=_HASH_C,
            judge_settings_sha256=_HASH_D.upper() if judge_required else None,
            repository_commit=commit,
            repository_dirty=False,
            effective_settings_sha256=_HASH_E,
            harness_variant=variant,
            invocation_id=f"invocation-{run_id}",
            case_definition_sha256=_HASH_A,
            runtime_sha256=_HASH_B,
        ),
    )


def _load_result(tmp_path: Path, result: AgentHarnessBenchmarkResult):
    path = tmp_path / f"{result.run_id}.json"
    path.write_text(json.dumps(result.to_payload()), encoding="utf-8")
    return load_agent_report(path)


def _calibration_report() -> JudgeCalibrationReport:
    observations = tuple(
        CalibrationObservation(
            fixture_id="clear-pass",
            repetition_index=index,
            expected_verdict=SemanticVerdict.PASS,
            judge_status=JudgeStatus.COMPLETED.value,
            observed_verdict=SemanticVerdict.PASS,
            independence=JudgeIndependence.INDEPENDENT,
        )
        for index in range(1, 4)
    )
    return JudgeCalibrationReport(
        suite_symbol="benchmarks.agent_harness.test_example:calibrations",
        suite_sha256=_HASH_A,
        rubric_id=_RUBRIC_ID,
        rubric_sha256=_HASH_F,
        judge_model=_JUDGE_MODEL,
        subject_model=_SUBJECT_MODEL,
        judge_settings_sha256=_HASH_D,
        observations=observations,
        packet_count=1,
    )
