"""Versioned, Agent-only acceptance and comparison for benchmark reports.

The live pytest surface deliberately produces measurements.  This module is the
separate fail-closed consumer which may turn schema-v5 Agent reports into an
acceptance decision.  It has no service-report input or service-test dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from .budgets import BenchmarkBudgetPolicy
from .judge_calibration import JudgeCalibrationReport


REPORT_POLICY_ID = "agent-harness-report-policy-v1"
AGENT_REPORT_KIND = "xenix.agent_harness.cell"
CURRENT_REPORT_SCHEMA_VERSION = 5
LEGACY_REPORT_SCHEMA_VERSION = 4
_MAX_REPORT_BYTES = 1_048_576
_MAX_COLLECTION_SIZE = 128
_SHA256_LENGTH = 64


class ReportPolicyError(ValueError):
    """A stable, content-free report rejection."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReportQualification(StrEnum):
    QUALIFIED = "qualified"
    LEGACY_UNQUALIFIED = "legacy_unqualified"


@dataclass(frozen=True)
class LoadedAgentReport:
    """One bounded Agent report after version dispatch and validation."""

    schema_version: int
    qualification: ReportQualification
    payload: Mapping[str, Any]

    @property
    def case_id(self) -> str | None:
        value = self.payload.get("case_id")
        return value if isinstance(value, str) else None

    @property
    def run_id(self) -> str | None:
        value = self.payload.get("run_id")
        return value if isinstance(value, str) else None


@dataclass(frozen=True)
class ReportPolicyDecision:
    """A privacy-bounded policy result suitable for stdout or JSON persistence."""

    evaluation: str
    qualified: bool
    accepted: bool
    gate_eligible: bool
    reason_codes: tuple[str, ...]
    case_id: str | None = None
    run_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "report_kind": "xenix.agent_harness.policy_decision",
            "schema_version": 1,
            "policy_id": REPORT_POLICY_ID,
            "evaluation": self.evaluation,
            "qualified": self.qualified,
            "accepted": self.accepted,
            "gate_eligible": self.gate_eligible,
            "reason_codes": list(self.reason_codes),
            "case_id": self.case_id,
            "run_ids": list(self.run_ids),
        }


@dataclass(frozen=True)
class ReportComparison:
    """Comparable identity verdict plus small descriptive subject deltas."""

    comparable: bool
    gate_eligible: bool
    passed: bool
    reason_codes: tuple[str, ...]
    baseline: ReportPolicyDecision
    candidate: ReportPolicyDecision
    metric_deltas: Mapping[str, float | int | None]

    def to_payload(self) -> dict[str, Any]:
        return {
            "report_kind": "xenix.agent_harness.report_comparison",
            "schema_version": 1,
            "policy_id": REPORT_POLICY_ID,
            "comparable": self.comparable,
            "gate_eligible": self.gate_eligible,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "baseline": self.baseline.to_payload(),
            "candidate": self.candidate.to_payload(),
            "metric_deltas": dict(self.metric_deltas),
        }


def load_agent_report(path: Path) -> LoadedAgentReport:
    """Read one Agent report; schema v4 remains diagnostic-only."""

    payload = _load_json_object(path, maximum_bytes=_MAX_REPORT_BYTES)
    schema_version = payload.get("schema_version")
    if schema_version == LEGACY_REPORT_SCHEMA_VERSION:
        _validate_legacy_identity(payload)
        return LoadedAgentReport(
            schema_version=LEGACY_REPORT_SCHEMA_VERSION,
            qualification=ReportQualification.LEGACY_UNQUALIFIED,
            payload=payload,
        )
    if schema_version != CURRENT_REPORT_SCHEMA_VERSION:
        raise ReportPolicyError("unsupported_report_schema")
    _validate_v5_report(payload)
    return LoadedAgentReport(
        schema_version=CURRENT_REPORT_SCHEMA_VERSION,
        qualification=ReportQualification.QUALIFIED,
        payload=payload,
    )


def load_agent_reports(paths: Iterable[Path]) -> tuple[LoadedAgentReport, ...]:
    resolved = tuple(paths)
    if not resolved or len(resolved) > _MAX_COLLECTION_SIZE:
        raise ReportPolicyError("report_collection_size_invalid")
    return tuple(load_agent_report(path) for path in resolved)


def evaluate_characterization(
    reports: Sequence[LoadedAgentReport],
) -> ReportPolicyDecision:
    """Qualify one headless measurement without turning it into a gate."""

    reasons = _measurement_reasons(
        reports,
        headless_count=1,
        headed_count=0,
        require_semantic_prerequisites=False,
    )
    qualified = not reasons
    return _decision(
        evaluation="characterization",
        reports=reports,
        qualified=qualified,
        accepted=False,
        gate_eligible=False,
        reasons=reasons,
    )


def evaluate_formal_acceptance(
    reports: Sequence[LoadedAgentReport],
    *,
    calibrations: Sequence[JudgeCalibrationReport] = (),
) -> ReportPolicyDecision:
    """Apply the v1 formal policy: three headless and one headed cell.

    Invocation identity is dispatch-local rather than a cohort key.  The four
    cells may therefore come from distinct, independently budgeted pytest
    invocations while every report must still carry its own invocation ID.
    """

    reasons = _measurement_reasons(
        reports,
        headless_count=3,
        headed_count=1,
        require_semantic_prerequisites=True,
    )
    if not reasons:
        reasons.extend(_semantic_reasons(reports, calibrations=calibrations))
    accepted = not reasons
    return _decision(
        evaluation="formal_acceptance",
        reports=reports,
        qualified=accepted,
        accepted=accepted,
        gate_eligible=True,
        reasons=reasons,
    )


def compare_report_cohorts(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
    *,
    calibrations: Sequence[JudgeCalibrationReport] = (),
) -> ReportComparison:
    """Compare like-shaped Agent cohorts; variant and commit may intentionally differ."""

    baseline_shape = _profile_shape(baseline)
    candidate_shape = _profile_shape(candidate)
    if baseline_shape == (1, 0):
        baseline_decision = evaluate_characterization(baseline)
    elif baseline_shape == (3, 1):
        baseline_decision = evaluate_formal_acceptance(
            baseline,
            calibrations=calibrations,
        )
    else:
        baseline_decision = _invalid_shape_decision("baseline", baseline)
    if candidate_shape == (1, 0):
        candidate_decision = evaluate_characterization(candidate)
    elif candidate_shape == (3, 1):
        candidate_decision = evaluate_formal_acceptance(
            candidate,
            calibrations=calibrations,
        )
    else:
        candidate_decision = _invalid_shape_decision("candidate", candidate)

    reasons: list[str] = []
    if baseline_shape != candidate_shape:
        reasons.append("comparison_repetition_policy_mismatch")
    if not _all_v5(baseline) or not _all_v5(candidate):
        reasons.append("legacy_report_not_comparable")
    if not reasons:
        if baseline_shape is not None:
            baseline_measurement_reasons = _measurement_reasons(
                baseline,
                headless_count=baseline_shape[0],
                headed_count=baseline_shape[1],
                require_semantic_prerequisites=False,
            )
            if baseline_measurement_reasons:
                reasons.append("baseline_measurement_unqualified")
        if candidate_shape is not None:
            candidate_measurement_reasons = _measurement_reasons(
                candidate,
                headless_count=candidate_shape[0],
                headed_count=candidate_shape[1],
                require_semantic_prerequisites=False,
            )
            if candidate_measurement_reasons:
                reasons.append("candidate_measurement_unqualified")
        reasons.extend(_comparison_identity_reasons(baseline, candidate))
        reasons.extend(_comparison_judge_reasons(baseline, candidate, calibrations))
    comparable = not reasons
    gate_eligible = comparable and baseline_shape == candidate_shape == (3, 1)
    passed = comparable and (
        not gate_eligible or candidate_decision.accepted
    )
    return ReportComparison(
        comparable=comparable,
        gate_eligible=gate_eligible,
        passed=passed,
        reason_codes=_unique(reasons),
        baseline=baseline_decision,
        candidate=candidate_decision,
        metric_deltas=(
            _metric_deltas(baseline, candidate) if comparable else {}
        ),
    )


def write_policy_payload(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically persist one already-bounded policy decision."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _decision(
    *,
    evaluation: str,
    reports: Sequence[LoadedAgentReport],
    qualified: bool,
    accepted: bool,
    gate_eligible: bool,
    reasons: Sequence[str],
) -> ReportPolicyDecision:
    case_ids = {report.case_id for report in reports if report.case_id is not None}
    return ReportPolicyDecision(
        evaluation=evaluation,
        qualified=qualified,
        accepted=accepted,
        gate_eligible=gate_eligible,
        reason_codes=_unique(reasons),
        case_id=next(iter(case_ids)) if len(case_ids) == 1 else None,
        run_ids=tuple(
            report.run_id for report in reports if report.run_id is not None
        ),
    )


def _measurement_reasons(
    reports: Sequence[LoadedAgentReport],
    *,
    headless_count: int,
    headed_count: int,
    require_semantic_prerequisites: bool,
) -> list[str]:
    reasons: list[str] = []
    if len(reports) != headless_count + headed_count:
        reasons.append("repetition_count_invalid")
    if not _all_v5(reports):
        reasons.append("legacy_unqualified")
        return reasons
    payloads = [report.payload for report in reports]
    modes = [payload["execution_mode"] for payload in payloads]
    if modes.count("headless") != headless_count or modes.count("headed") != headed_count:
        reasons.append("execution_mode_repetition_invalid")
    run_ids = [payload["run_id"] for payload in payloads]
    if len(set(run_ids)) != len(run_ids):
        reasons.append("duplicate_run_id")
    if len({payload["case_id"] for payload in payloads}) != 1:
        reasons.append("case_identity_mismatch")
    reasons.extend(_cohort_identity_reasons(payloads))
    for payload in payloads:
        if payload["run_status"] != "completed":
            reasons.append("execution_not_completed")
        if not payload["integrity"]["passed"]:
            reasons.append("integrity_not_passed")
        if require_semantic_prerequisites:
            semantic_checks = payload["semantic"]["checks"]
            if not semantic_checks or not all(check["passed"] for check in semantic_checks):
                reasons.append("semantic_prerequisite_not_passed")
        if payload["budget"]["status"] != "within_limits":
            reasons.append("budget_not_within_limits")
    return list(_unique(reasons))


def _cohort_identity_reasons(payloads: Sequence[Mapping[str, Any]]) -> list[str]:
    if not payloads:
        return []
    reasons: list[str] = []
    required_identity = (
        "fixture_sha256",
        "settings_sha256",
        "effective_settings_sha256",
        "repository_commit",
        "harness_variant",
        "invocation_id",
        "case_definition_sha256",
        "runtime_sha256",
    )
    for payload in payloads:
        identity = payload["identity"]
        if any(not identity[key] for key in required_identity):
            reasons.append("identity_incomplete")
        if identity["repository_dirty"] is not False:
            reasons.append("repository_not_clean")
    fields = (
        "provider_model",
        "identity.fixture_sha256",
        "identity.settings_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.repository_commit",
        "identity.effective_settings_sha256",
        "identity.harness_variant",
        "identity.case_definition_sha256",
        "identity.runtime_sha256",
        "budget.policy",
    )
    # invocation_id is intentionally absent: it identifies one budget-owning
    # dispatch, while formal acceptance combines four independent dispatches.
    for field in fields:
        if len({_nested_value(payload, field) for payload in payloads}) != 1:
            reasons.append(f"cohort_{field.replace('.', '_')}_mismatch")
    return reasons


def _semantic_reasons(
    reports: Sequence[LoadedAgentReport],
    *,
    calibrations: Sequence[JudgeCalibrationReport],
) -> list[str]:
    payloads = [report.payload for report in reports]
    judge_required_values = {payload["judge"]["required"] for payload in payloads}
    if len(judge_required_values) != 1:
        return ["judge_requirement_mismatch"]
    if judge_required_values == {False}:
        return (
            []
            if all(payload["semantic"]["verdict"] == "pass" for payload in payloads)
            else ["semantic_verdict_not_passed"]
        )
    reasons = _judge_cell_reasons(payloads)
    reasons.extend(_calibration_reasons(payloads, calibrations))
    headless = [payload for payload in payloads if payload["execution_mode"] == "headless"]
    headed = [payload for payload in payloads if payload["execution_mode"] == "headed"]
    verdicts = [payload["semantic"]["verdict"] for payload in headless]
    if verdicts.count("pass") < 2:
        reasons.append("headless_semantic_majority_not_passed")
    if any(verdict not in {"pass", "partial"} for verdict in verdicts):
        reasons.append("headless_semantic_disqualifying_verdict")
    if len(headed) != 1 or headed[0]["semantic"]["verdict"] != "pass":
        reasons.append("headed_semantic_not_passed")
    return list(_unique(reasons))


def _judge_cell_reasons(payloads: Sequence[Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for payload in payloads:
        judge = payload["judge"]
        if judge["status"] != "completed":
            reasons.append("judge_not_completed")
        if judge["independence"] != "independent":
            reasons.append("judge_not_independent")
        if not judge["rubric_id"] or not judge["rubric_sha256"]:
            reasons.append("judge_rubric_identity_missing")
        if not judge["provider_model"]:
            reasons.append("judge_model_missing")
    return reasons


def _calibration_reasons(
    payloads: Sequence[Mapping[str, Any]],
    calibrations: Sequence[JudgeCalibrationReport],
) -> list[str]:
    reasons: list[str] = []
    for payload in payloads:
        judge = payload["judge"]
        identity = payload["identity"]
        match = next(
            (
                calibration
                for calibration in calibrations
                if calibration.passed
                and calibration.rubric_id == judge["rubric_id"]
                and _hash_equal(calibration.rubric_sha256, judge["rubric_sha256"])
                and calibration.judge_model == judge["provider_model"]
                and calibration.subject_model == payload["provider_model"]
                and _hash_equal(
                    calibration.judge_settings_sha256,
                    identity["judge_settings_sha256"],
                )
            ),
            None,
        )
        if match is None:
            reasons.append("judge_calibration_missing_or_mismatched")
    return reasons


def _comparison_identity_reasons(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
) -> list[str]:
    if not baseline or not candidate:
        return ["comparison_reports_missing"]
    left = baseline[0].payload
    right = candidate[0].payload
    fields = (
        "case_id",
        "provider_model",
        "identity.fixture_sha256",
        "identity.settings_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.effective_settings_sha256",
        "identity.case_definition_sha256",
        "identity.runtime_sha256",
        "budget.policy",
        "judge.required",
        "judge.rubric_id",
        "judge.rubric_sha256",
        "judge.provider_model",
    )
    return [
        f"comparison_{field.replace('.', '_')}_mismatch"
        for field in fields
        if _nested_value(left, field) != _nested_value(right, field)
    ]


def _comparison_judge_reasons(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
    calibrations: Sequence[JudgeCalibrationReport],
) -> list[str]:
    payloads = [report.payload for report in (*baseline, *candidate)]
    if not payloads or not any(payload["judge"]["required"] for payload in payloads):
        return []
    reasons = _judge_cell_reasons(payloads)
    reasons.extend(_calibration_reasons(payloads, calibrations))
    return list(_unique(reasons))


def _metric_deltas(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
) -> dict[str, float | int | None]:
    def values(reports: Sequence[LoadedAgentReport], key: str) -> list[float]:
        return [
            float(value)
            for report in reports
            if isinstance((value := report.payload["subject_metrics"].get(key)), (int, float))
            and not isinstance(value, bool)
        ]

    baseline_seconds = values(baseline, "turn_seconds")
    candidate_seconds = values(candidate, "turn_seconds")
    baseline_tokens = [
        report.payload["budget"]["reported_subject_tokens"] for report in baseline
    ]
    candidate_tokens = [
        report.payload["budget"]["reported_subject_tokens"] for report in candidate
    ]
    return {
        "median_turn_seconds": _median_delta(baseline_seconds, candidate_seconds),
        "median_reported_subject_tokens": _median_delta(
            baseline_tokens,
            candidate_tokens,
        ),
    }


def _median_delta(left: Sequence[float | int], right: Sequence[float | int]) -> float | None:
    if not left or not right:
        return None
    return float(median(right) - median(left))


def _profile_shape(reports: Sequence[LoadedAgentReport]) -> tuple[int, int] | None:
    if not _all_v5(reports):
        return None
    modes = [report.payload["execution_mode"] for report in reports]
    return modes.count("headless"), modes.count("headed")


def _invalid_shape_decision(label: str, reports: Sequence[LoadedAgentReport]) -> ReportPolicyDecision:
    return _decision(
        evaluation=f"{label}_comparison_input",
        reports=reports,
        qualified=False,
        accepted=False,
        gate_eligible=False,
        reasons=("comparison_profile_invalid",),
    )


def _all_v5(reports: Sequence[LoadedAgentReport]) -> bool:
    return bool(reports) and all(
        report.qualification is ReportQualification.QUALIFIED
        and report.schema_version == CURRENT_REPORT_SCHEMA_VERSION
        for report in reports
    )


def _validate_legacy_identity(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("case_id"), str) or not isinstance(payload.get("run_id"), str):
        raise ReportPolicyError("legacy_report_identity_invalid")


def _validate_v5_report(payload: Mapping[str, Any]) -> None:
    _exact_keys(
        payload,
        {
            "report_kind", "schema_version", "case_id", "run_id", "provider_model",
            "execution_mode", "run_status", "semantic", "integrity", "judge",
            "subject_metrics", "budget", "identity", "failure_kind",
            "trace",
        },
        "report_shape_invalid",
    )
    if payload["report_kind"] != AGENT_REPORT_KIND:
        raise ReportPolicyError("report_kind_invalid")
    _bounded_string(payload["case_id"], "case_id_invalid", maximum=160)
    _bounded_string(payload["run_id"], "run_id_invalid", maximum=96)
    _bounded_string(payload["provider_model"], "provider_model_invalid", maximum=256)
    _enum_string(payload["execution_mode"], {"headless", "headed"}, "execution_mode_invalid")
    _enum_string(
        payload["run_status"],
        {"completed", "budget_exceeded", "invalid_setup", "runtime_error", "measurement_error"},
        "run_status_invalid",
    )
    _validate_outcome_channel(payload["semantic"], semantic=True)
    _validate_outcome_channel(payload["integrity"], semantic=False)
    integrity_checks = payload["integrity"]["checks"]
    expected_integrity = (
        payload["run_status"] == "completed"
        and bool(integrity_checks)
        and all(check["passed"] for check in integrity_checks)
    )
    if payload["integrity"]["passed"] is not expected_integrity:
        raise ReportPolicyError("integrity_projection_invalid")
    _validate_judge(payload["judge"])
    _validate_subject_metrics(payload["subject_metrics"])
    _validate_budget(payload["budget"])
    _validate_subject_budget_projection(
        subject_metrics=payload["subject_metrics"],
        budget=payload["budget"],
        run_status=payload["run_status"],
    )
    _validate_identity(payload["identity"])
    _optional_bounded_string(payload["failure_kind"], "failure_kind_invalid", maximum=128)
    _validate_trace(payload["trace"])


def _validate_trace(value: object) -> None:
    if value is None:
        return
    trace = _object(value, "trace_shape_invalid")
    _exact_keys(trace, {"trace_id", "events"}, "trace_shape_invalid")
    _bounded_string(trace["trace_id"], "trace_id_invalid", maximum=96)
    events = trace["events"]
    if not isinstance(events, list) or len(events) > 128:
        raise ReportPolicyError("trace_events_invalid")
    for value in events:
        event = _object(value, "trace_event_invalid")
        _exact_keys(
            event,
            {
                "name", "span_id", "parent_span_id", "started_offset_seconds",
                "duration_seconds", "status", "attributes", "exception",
            },
            "trace_event_invalid",
        )
        _bounded_string(event["name"], "trace_event_invalid", maximum=160)
        _bounded_string(event["span_id"], "trace_event_invalid", maximum=32)
        _optional_bounded_string(event["parent_span_id"], "trace_event_invalid", maximum=32)
        if not isinstance(event["started_offset_seconds"], (int, float)):
            raise ReportPolicyError("trace_event_invalid")
        if not isinstance(event["duration_seconds"], (int, float)):
            raise ReportPolicyError("trace_event_invalid")
        _enum_string(event["status"], {"ok", "error"}, "trace_event_invalid")
        _object(event["attributes"], "trace_event_invalid")
        if event["exception"] is not None:
            _object(event["exception"], "trace_event_invalid")


def _validate_outcome_channel(value: object, *, semantic: bool) -> None:
    channel = _object(value, "outcome_channel_invalid")
    keys = {"verdict", "passed", "checks"} if semantic else {"passed", "checks"}
    _exact_keys(channel, keys, "outcome_channel_invalid")
    if semantic:
        _enum_string(
            channel["verdict"],
            {"pass", "partial", "fail", "inconclusive", "not_evaluated"},
            "semantic_verdict_invalid",
        )
        if channel["passed"] is not (channel["verdict"] == "pass"):
            raise ReportPolicyError("semantic_projection_invalid")
    _boolean(channel["passed"], "outcome_passed_invalid")
    checks = channel["checks"]
    if not isinstance(checks, list) or len(checks) > 64:
        raise ReportPolicyError("outcome_checks_invalid")
    for check in checks:
        item = _object(check, "outcome_check_invalid")
        _exact_keys(item, {"name", "passed", "summary"}, "outcome_check_invalid")
        _bounded_string(item["name"], "outcome_check_invalid", maximum=128)
        _boolean(item["passed"], "outcome_check_invalid")
        _bounded_string(item["summary"], "outcome_check_invalid", maximum=512)


def _validate_judge(value: object) -> None:
    judge = _object(value, "judge_shape_invalid")
    _exact_keys(
        judge,
        {
            "required", "rubric_id", "rubric_sha256", "status", "verdict",
            "provider_model", "independence", "scores", "reason_codes", "summary", "metrics",
        },
        "judge_shape_invalid",
    )
    _boolean(judge["required"], "judge_required_invalid")
    _optional_bounded_string(judge["rubric_id"], "judge_rubric_id_invalid", maximum=128)
    _optional_sha256(judge["rubric_sha256"], "judge_rubric_sha256_invalid")
    _enum_string(
        judge["status"],
        {"not_requested", "not_configured", "blocked", "invalid_setup", "provider_error", "invalid_response", "completed"},
        "judge_status_invalid",
    )
    _enum_string(
        judge["verdict"],
        {"pass", "partial", "fail", "inconclusive", "not_evaluated"},
        "judge_verdict_invalid",
    )
    _optional_bounded_string(judge["provider_model"], "judge_model_invalid", maximum=256)
    _enum_string(
        judge["independence"],
        {"not_applicable", "independent", "same_model"},
        "judge_independence_invalid",
    )
    scores = _object(judge["scores"], "judge_scores_invalid")
    if len(scores) > 32:
        raise ReportPolicyError("judge_scores_invalid")
    for key, score in scores.items():
        _bounded_string(key, "judge_scores_invalid", maximum=128)
        _bounded_int(score, "judge_scores_invalid", maximum=2)
    reason_codes = judge["reason_codes"]
    if not isinstance(reason_codes, list) or len(reason_codes) > 32:
        raise ReportPolicyError("judge_reason_codes_invalid")
    if len(set(reason_codes)) != len(reason_codes):
        raise ReportPolicyError("judge_reason_codes_invalid")
    for code in reason_codes:
        _bounded_string(code, "judge_reason_codes_invalid", maximum=128)
    _bounded_string(judge["summary"], "judge_summary_invalid", maximum=256)
    _validate_metrics(judge["metrics"], judge_metrics=True)


def _validate_subject_metrics(value: object) -> None:
    metrics = _object(value, "subject_metrics_invalid")
    _exact_keys(
        metrics,
        {
            "turn_seconds", "assessment_seconds", "sampling_round_count",
            "usage_reported_primary_response_count", "token_usage", "message_counts",
            "tool_call_counts_by_name", "tool_result_counts_by_status",
            "provider_retry_count", "derived_dataset_count", "terminal_shape",
        },
        "subject_metrics_invalid",
    )
    _optional_nonnegative_number(metrics["turn_seconds"], "subject_metrics_invalid")
    _optional_nonnegative_number(metrics["assessment_seconds"], "subject_metrics_invalid")
    for key in ("sampling_round_count", "provider_retry_count", "derived_dataset_count"):
        _bounded_int(metrics[key], "subject_metrics_invalid")
    value_count = metrics["usage_reported_primary_response_count"]
    if value_count is not None:
        _bounded_int(value_count, "subject_metrics_invalid")
    _validate_token_usage(metrics["token_usage"])
    for key in ("message_counts", "tool_call_counts_by_name", "tool_result_counts_by_status"):
        _validate_count_map(metrics[key])
    shape = metrics["terminal_shape"]
    if shape is not None and (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in shape)
    ):
        raise ReportPolicyError("subject_metrics_invalid")


def _validate_metrics(value: object, *, judge_metrics: bool) -> None:
    metrics = _object(value, "judge_metrics_invalid")
    expected = {"elapsed_seconds", "token_usage", "provider_retry_count"}
    _exact_keys(metrics, expected, "judge_metrics_invalid")
    _optional_nonnegative_number(metrics["elapsed_seconds"], "judge_metrics_invalid")
    _validate_token_usage(metrics["token_usage"])
    _bounded_int(metrics["provider_retry_count"], "judge_metrics_invalid")


def _validate_token_usage(value: object) -> None:
    if value is None:
        return
    usage = _object(value, "token_usage_invalid")
    _exact_keys(
        usage,
        {"input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"},
        "token_usage_invalid",
    )
    for amount in usage.values():
        _bounded_int(amount, "token_usage_invalid", maximum=100_000_000)


def _validate_count_map(value: object) -> None:
    counts = _object(value, "metric_count_map_invalid")
    if len(counts) > 128:
        raise ReportPolicyError("metric_count_map_invalid")
    for key, count in counts.items():
        _bounded_string(key, "metric_count_map_invalid", maximum=128)
        _bounded_int(count, "metric_count_map_invalid", maximum=1_000_000)


def _validate_budget(value: object) -> None:
    budget = _object(value, "budget_shape_invalid")
    _exact_keys(
        budget,
        {
            "status", "policy", "sampling_rounds_admitted", "provider_attempts_dispatched",
            "reported_subject_tokens", "invocation_reported_subject_tokens", "exhaustion_reason",
        },
        "budget_shape_invalid",
    )
    _enum_string(
        budget["status"],
        {"within_limits", "exceeded", "unverifiable", "not_evaluated"},
        "budget_status_invalid",
    )
    policy = _object(budget["policy"], "budget_policy_invalid")
    _exact_keys(
        policy,
        {
            "policy_id", "max_sampling_rounds", "max_wall_seconds",
            "max_reported_subject_tokens", "max_reported_invocation_subject_tokens",
            "max_provider_attempts", "token_enforcement",
        },
        "budget_policy_invalid",
    )
    _bounded_string(policy["policy_id"], "budget_policy_invalid", maximum=96)
    _bounded_int(policy["max_sampling_rounds"], "budget_policy_invalid", minimum=1, maximum=BenchmarkBudgetPolicy.HARD_MAX_SAMPLING_ROUNDS)
    _bounded_number(policy["max_wall_seconds"], "budget_policy_invalid", minimum=0.001, maximum=BenchmarkBudgetPolicy.HARD_MAX_WALL_SECONDS)
    _bounded_int(policy["max_reported_subject_tokens"], "budget_policy_invalid", minimum=1, maximum=BenchmarkBudgetPolicy.HARD_MAX_REPORTED_SUBJECT_TOKENS)
    _bounded_int(policy["max_reported_invocation_subject_tokens"], "budget_policy_invalid", minimum=1, maximum=BenchmarkBudgetPolicy.HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS)
    _bounded_int(policy["max_provider_attempts"], "budget_policy_invalid", minimum=1, maximum=BenchmarkBudgetPolicy.HARD_MAX_PROVIDER_ATTEMPTS)
    if policy["token_enforcement"] != "response_boundary":
        raise ReportPolicyError("budget_policy_invalid")
    _bounded_int(budget["sampling_rounds_admitted"], "budget_measurement_invalid", maximum=BenchmarkBudgetPolicy.HARD_MAX_SAMPLING_ROUNDS)
    _bounded_int(budget["provider_attempts_dispatched"], "budget_measurement_invalid", maximum=100)
    _bounded_int(budget["reported_subject_tokens"], "budget_measurement_invalid", maximum=100_000_000)
    _bounded_int(budget["invocation_reported_subject_tokens"], "budget_measurement_invalid", maximum=100_000_000)
    _optional_bounded_string(budget["exhaustion_reason"], "budget_reason_invalid", maximum=128)
    if budget["status"] == "within_limits":
        if (
            budget["sampling_rounds_admitted"] > policy["max_sampling_rounds"]
            or budget["provider_attempts_dispatched"]
            > policy["max_sampling_rounds"] * policy["max_provider_attempts"]
            or budget["reported_subject_tokens"]
            > policy["max_reported_subject_tokens"]
            or budget["invocation_reported_subject_tokens"]
            > policy["max_reported_invocation_subject_tokens"]
            or budget["exhaustion_reason"] is not None
        ):
            raise ReportPolicyError("budget_projection_invalid")
    elif budget["status"] in {"exceeded", "unverifiable"} and budget["exhaustion_reason"] is None:
        raise ReportPolicyError("budget_projection_invalid")


def _validate_subject_budget_projection(
    *,
    subject_metrics: Mapping[str, Any],
    budget: Mapping[str, Any],
    run_status: str,
) -> None:
    if subject_metrics["sampling_round_count"] != budget["sampling_rounds_admitted"]:
        raise ReportPolicyError("subject_budget_projection_invalid")
    usage = subject_metrics["token_usage"]
    if usage is not None and usage["total_tokens"] != budget["reported_subject_tokens"]:
        raise ReportPolicyError("subject_budget_projection_invalid")
    if run_status == "completed" and (
        usage is None
        or subject_metrics["usage_reported_primary_response_count"] is None
        or budget["status"] != "within_limits"
    ):
        raise ReportPolicyError("subject_budget_projection_invalid")


def _validate_identity(value: object) -> None:
    identity = _object(value, "identity_shape_invalid")
    _exact_keys(
        identity,
        {
            "fixture_sha256", "settings_sha256", "embedding_settings_sha256",
            "judge_settings_sha256", "repository_commit", "repository_dirty",
            "effective_settings_sha256", "harness_variant", "invocation_id",
            "case_definition_sha256", "runtime_sha256",
        },
        "identity_shape_invalid",
    )
    for key in (
        "fixture_sha256", "settings_sha256", "embedding_settings_sha256",
        "judge_settings_sha256", "effective_settings_sha256",
        "case_definition_sha256", "runtime_sha256",
    ):
        _optional_sha256(identity[key], "identity_hash_invalid")
    _optional_bounded_string(identity["repository_commit"], "repository_commit_invalid", maximum=64)
    if identity["repository_dirty"] is not None:
        _boolean(identity["repository_dirty"], "repository_dirty_invalid")
    _bounded_string(identity["harness_variant"], "harness_variant_invalid", maximum=96)
    _optional_bounded_string(identity["invocation_id"], "invocation_id_invalid", maximum=96)


def _load_json_object(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    try:
        if path.stat().st_size > maximum_bytes:
            raise ReportPolicyError("report_too_large")
        text = path.read_text(encoding="utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except ReportPolicyError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReportPolicyError("report_json_invalid") from exc
    if not isinstance(value, dict):
        raise ReportPolicyError("report_json_invalid")
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non_standard_json_constant")


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportPolicyError(code)
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        raise ReportPolicyError(code)


def _bounded_string(value: object, code: str, *, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ReportPolicyError(code)


def _optional_bounded_string(value: object, code: str, *, maximum: int) -> None:
    if value is not None:
        _bounded_string(value, code, maximum=maximum)


def _optional_sha256(value: object, code: str) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character.lower() not in "0123456789abcdef" for character in value)
    ):
        raise ReportPolicyError(code)


def _boolean(value: object, code: str) -> None:
    if not isinstance(value, bool):
        raise ReportPolicyError(code)


def _enum_string(value: object, choices: set[str], code: str) -> None:
    if not isinstance(value, str) or value not in choices:
        raise ReportPolicyError(code)


def _bounded_int(
    value: object,
    code: str,
    *,
    minimum: int = 0,
    maximum: int = 10_000_000,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ReportPolicyError(code)


def _bounded_number(
    value: object,
    code: str,
    *,
    minimum: float,
    maximum: float,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not minimum <= float(value) <= maximum
    ):
        raise ReportPolicyError(code)


def _optional_nonnegative_number(value: object, code: str) -> None:
    if value is not None:
        _bounded_number(value, code, minimum=0.0, maximum=1_000_000.0)


def _nested_value(payload: Mapping[str, Any], dotted: str) -> Any:
    value: Any = payload
    for key in dotted.split("."):
        value = value[key]
    return _freeze(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _hash_equal(left: object, right: object) -> bool:
    return (
        isinstance(left, str)
        and isinstance(right, str)
        and left.lower() == right.lower()
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
