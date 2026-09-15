"""Versioned, Agent-only acceptance and comparison for benchmark reports.

The live pytest surface deliberately produces measurements.  This module is the
consumer of the outcome and measurement fields needed for acceptance.  It has no service-report input or service-test dependency.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from .judge_calibration import JudgeCalibrationReport


REPORT_POLICY_ID = "agent-harness-report-policy-v3"
AGENT_REPORT_KIND = "xenix.agent_harness.cell"
CURRENT_REPORT_SCHEMA_VERSION = 6
LEGACY_REPORT_SCHEMA_VERSION = 4


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
    observations: tuple[Mapping[str, Any], ...] = ()
    summary: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "report_kind": "xenix.agent_harness.policy_decision",
            "schema_version": 2,
            "policy_id": REPORT_POLICY_ID,
            "evaluation": self.evaluation,
            "qualified": self.qualified,
            "accepted": self.accepted,
            "gate_eligible": self.gate_eligible,
            "reason_codes": list(self.reason_codes),
            "case_id": self.case_id,
            "run_ids": list(self.run_ids),
            "observations": list(self.observations),
            "summary": dict(self.summary),
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
            "schema_version": 2,
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

    payload = _load_json_object(path)
    schema_version = payload.get("schema_version")
    if schema_version == LEGACY_REPORT_SCHEMA_VERSION:
        _validate_legacy_identity(payload)
        return LoadedAgentReport(
            schema_version=LEGACY_REPORT_SCHEMA_VERSION,
            qualification=ReportQualification.LEGACY_UNQUALIFIED,
            payload=payload,
        )
    if schema_version not in (5, CURRENT_REPORT_SCHEMA_VERSION):
        raise ReportPolicyError("unsupported_report_schema")
    _validate_report(payload)
    return LoadedAgentReport(
        schema_version=schema_version,
        qualification=ReportQualification.QUALIFIED,
        payload=payload,
    )


def load_agent_reports(paths: Iterable[Path]) -> tuple[LoadedAgentReport, ...]:
    resolved = tuple(paths)
    if not resolved:
        raise ReportPolicyError("report_collection_size_invalid")
    return tuple(load_agent_report(path) for path in resolved)


def evaluate_characterization(
    reports: Sequence[LoadedAgentReport],
) -> ReportPolicyDecision:
    """Describe every supplied attempt in one same-mode cohort, including failures."""

    shape = _profile_shape(reports) or (0, 0)
    reasons = _measurement_reasons(
        reports,
        headless_count=shape[0],
        headed_count=shape[1],
        require_semantic_prerequisites=False,
    )
    if all(shape):
        reasons.append("characterization_execution_modes_mixed")
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
    """Apply the formal policy: three headless and one headed cell.

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
    if baseline_shape == (3, 1):
        baseline_decision = evaluate_formal_acceptance(
            baseline,
            calibrations=calibrations,
        )
    else:
        baseline_decision = evaluate_characterization(baseline)
    if candidate_shape == (3, 1):
        candidate_decision = evaluate_formal_acceptance(
            candidate,
            calibrations=calibrations,
        )
    else:
        candidate_decision = evaluate_characterization(candidate)

    reasons: list[str] = []
    if baseline_shape != candidate_shape:
        reasons.append("comparison_repetition_policy_mismatch")
    if any(shape and all(shape) and shape != (3, 1) for shape in (baseline_shape, candidate_shape)):
        reasons.append("characterization_execution_modes_mixed")
    if not _all_supported(baseline) or not _all_supported(candidate):
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
    passed = comparable and (not gate_eligible or candidate_decision.accepted)
    return ReportComparison(
        comparable=comparable,
        gate_eligible=gate_eligible,
        passed=passed,
        reason_codes=_unique(reasons),
        baseline=baseline_decision,
        candidate=candidate_decision,
        metric_deltas=(_metric_deltas(baseline, candidate) if comparable else {}),
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
    observations = tuple(_report_observation(report) for report in reports)
    shape = _profile_shape(reports) or (0, 0)
    coherent = not _measurement_reasons(
        reports, headless_count=shape[0], headed_count=shape[1], require_semantic_prerequisites=False
    ) and (not all(shape) or shape == (3, 1))
    return ReportPolicyDecision(
        evaluation=evaluation,
        qualified=qualified,
        accepted=accepted,
        gate_eligible=gate_eligible,
        reason_codes=_unique(reasons),
        case_id=next(iter(case_ids)) if len(case_ids) == 1 else None,
        run_ids=tuple(report.run_id for report in reports if report.run_id is not None),
        observations=observations,
        summary=_summarize_observations(observations) if coherent else {},
    )


def _report_observation(report: LoadedAgentReport) -> dict[str, Any]:
    """Project task success separately from evaluator availability and resource coverage."""

    payload = report.payload
    if report.qualification is ReportQualification.LEGACY_UNQUALIFIED:
        return {"run_id": report.run_id, "outcome": "unscored", "reason": "legacy_unqualified"}
    status = payload["run_status"]
    budget = payload["budget"]
    judge = payload["judge"]
    semantic = payload["semantic"]
    budget_reason = budget.get("exhaustion_reason")
    stop_reason = budget_reason or payload.get("failure_kind") or ""
    if status in {"invalid_setup", "measurement_error"}:
        outcome, reason = "unscored", status
    elif stop_reason.startswith("invocation_token_limit"):
        # Old reports may have overwritten a completed cell at the dispatch cap.
        # Their original outcome cannot be recovered from the projected flag.
        outcome, reason = "unscored", "invocation_budget_interference"
    elif (
        status == "budget_exceeded"
        and budget["status"] == "unverifiable"
        and budget_reason == payload.get("failure_kind")
    ):
        # Older runners labelled a stop caused by missing usage as exhaustion.
        # A real wall timeout still fails even if its interrupted usage is unknown.
        outcome, reason = "unscored", "accounting_stopped_execution"
    elif status in {"budget_exceeded", "runtime_error"}:
        outcome, reason = "fail", status
    elif status != "completed":
        outcome, reason = "unscored", "execution_status_unknown"
    elif not payload["integrity"]["passed"]:
        outcome, reason = "unscored", "integrity_not_passed"
    elif any(not check["passed"] for check in semantic["checks"]):
        outcome, reason = "fail", "outcome_check_failed"
    elif not semantic["checks"]:
        outcome, reason = "unscored", "outcome_evidence_missing"
    elif judge["required"]:
        if judge["status"] == "completed" and judge["verdict"] in {"pass", "partial", "fail"}:
            outcome, reason = judge["verdict"], "judge_verdict"
        else:
            outcome, reason = "unscored", "judge_unavailable_or_inconclusive"
    elif semantic["verdict"] in {"pass", "partial", "fail"}:
        outcome, reason = semantic["verdict"], "deterministic_verdict"
    else:
        outcome, reason = "unscored", "outcome_not_evaluated"
    metrics = payload["subject_metrics"]
    reported_responses = metrics.get("usage_reported_primary_response_count")
    admitted_rounds = budget.get("sampling_rounds_admitted")
    tokens_complete = (
        budget["status"] in {"within_limits", "exceeded"}
        and metrics.get("token_usage") is not None
        and isinstance(reported_responses, int)
        and reported_responses == admitted_rounds
    )
    return {
        "run_id": report.run_id,
        "outcome": outcome,
        "reason": reason,
        "run_status": status,
        "failure_kind": payload.get("failure_kind"),
        "judge_status": judge["status"],
        "budget_reason": budget_reason,
        "reported_subject_tokens": budget["reported_subject_tokens"],
        "subject_tokens_complete": tokens_complete,
        "turn_seconds": metrics.get("turn_seconds"),
        "sampling_rounds": metrics.get("sampling_round_count"),
        "provenance": {
            key: payload["identity"].get(key)
            for key in ("harness_variant", "repository_commit", "repository_dirty", "case_definition_sha256", "runtime_sha256")
        },
    }


def _summarize_observations(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["outcome"] for item in observations)
    attempts = len(observations)
    scored = attempts - counts["unscored"]
    complete_tokens = sum(bool(item.get("subject_tokens_complete")) for item in observations)
    observed_tokens = sum(item.get("reported_subject_tokens", 0) for item in observations)
    total_tokens = observed_tokens if attempts and complete_tokens == attempts else None

    def full_median(key: str) -> float | None:
        values = [item.get(key) for item in observations]
        if not values or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            for value in values
        ):
            return None
        return float(median(values))

    return {
        "attempt_count": attempts,
        "scored_count": scored,
        "outcome_counts": {key: counts[key] for key in ("pass", "partial", "fail", "unscored")},
        "pass_rate": counts["pass"] / scored if scored else None,
        "observed_subject_tokens": observed_tokens,
        "subject_token_coverage": complete_tokens / attempts if attempts else None,
        "total_subject_tokens": total_tokens,
        "effective_subject_tokens_per_pass": (
            total_tokens / counts["pass"]
            if total_tokens is not None and counts["pass"] and scored == attempts else None
        ),
        "median_turn_seconds": full_median("turn_seconds"),
        "median_sampling_rounds": full_median("sampling_rounds"),
        "median_reported_subject_tokens": full_median("reported_subject_tokens") if total_tokens is not None else None,
    }


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
    if not _all_supported(reports):
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
    if require_semantic_prerequisites:
        for payload in payloads:
            if payload["run_status"] != "completed":
                reasons.append("execution_not_completed")
            if not payload["integrity"]["passed"]:
                reasons.append("integrity_not_passed")
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
        "effective_settings_sha256",
        "harness_variant",
    )
    for payload in payloads:
        identity = payload["identity"]
        if any(not identity.get(key) for key in required_identity):
            reasons.append("identity_incomplete")
    fields = (
        "schema_version",
        "provider_model",
        "identity.fixture_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.effective_settings_sha256",
        "identity.harness_variant",
        "budget.policy",
    )
    # invocation_id is intentionally absent: it identifies one budget-owning
    # dispatch, while formal acceptance combines four independent dispatches.
    for key in fields:
        if len({_nested_value(payload, key) for payload in payloads}) != 1:
            reasons.append(f"cohort_{key.replace('.', '_')}_mismatch")
    reasons.extend(_judge_identity_reasons(payloads, prefix="cohort"))
    return reasons


def _judge_identity_reasons(payloads: Sequence[Mapping[str, Any]], *, prefix: str) -> list[str]:
    # A crash before assessment has no observed rubric. Configured Judge settings
    # still participate in identity; lack of a response is an outcome, not drift.
    assessed = [payload for payload in payloads if payload["judge"]["required"] or payload["run_status"] == "completed"]
    reasons = []
    for key in ("judge.required", "judge.rubric_id", "judge.rubric_sha256", "judge.provider_model"):
        values = {_nested_value(payload, key) for payload in assessed}
        values.discard(None)
        if len(values) > 1:
            reasons.append(f"{prefix}_{key.replace('.', '_')}_mismatch")
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
    verdicts = [payload["judge"]["verdict"] for payload in headless]
    if verdicts.count("pass") < 2:
        reasons.append("headless_semantic_majority_not_passed")
    if any(verdict not in {"pass", "partial"} for verdict in verdicts):
        reasons.append("headless_semantic_disqualifying_verdict")
    if len(headed) != 1 or headed[0]["judge"]["verdict"] != "pass":
        reasons.append("headed_semantic_not_passed")
    return list(_unique(reasons))


def _judge_cell_reasons(payloads: Sequence[Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for payload in payloads:
        judge = payload["judge"]
        if judge["status"] != "completed":
            reasons.append("judge_not_completed")
        if not judge.get("rubric_id") or not judge.get("rubric_sha256"):
            reasons.append("judge_rubric_identity_missing")
        if not judge.get("provider_model"):
            reasons.append("judge_model_missing")
    return reasons


def _calibration_reasons(
    payloads: Sequence[Mapping[str, Any]],
    calibrations: Sequence[JudgeCalibrationReport],
) -> list[str]:
    if not calibrations:
        return []
    reasons: list[str] = []
    for payload in payloads:
        judge = payload["judge"]
        identity = payload["identity"]
        match = next(
            (
                calibration
                for calibration in calibrations
                if calibration.passed
                and calibration.rubric_id == judge.get("rubric_id")
                and _hash_equal(calibration.rubric_sha256, judge.get("rubric_sha256"))
                and calibration.judge_model == judge.get("provider_model")
                and calibration.subject_model == payload["provider_model"]
                and _hash_equal(
                    calibration.judge_settings_sha256,
                    identity.get("judge_settings_sha256"),
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
        "schema_version",
        "case_id",
        "provider_model",
        "identity.fixture_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.effective_settings_sha256",
        "budget.policy",
    )
    return [
        f"comparison_{field.replace('.', '_')}_mismatch"
        for field in fields
        if _nested_value(left, field) != _nested_value(right, field)
    ] + _judge_identity_reasons([report.payload for report in (*baseline, *candidate)], prefix="comparison")


def _comparison_judge_reasons(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
    calibrations: Sequence[JudgeCalibrationReport],
) -> list[str]:
    payloads = [report.payload for report in (*baseline, *candidate)]
    if not payloads or not any(payload["judge"]["required"] for payload in payloads):
        return []
    judged = [payload for payload in payloads if payload["judge"]["status"] == "completed"]
    return _calibration_reasons(judged, calibrations)


def _metric_deltas(
    baseline: Sequence[LoadedAgentReport],
    candidate: Sequence[LoadedAgentReport],
) -> dict[str, float | int | None]:
    left = _summarize_observations(tuple(_report_observation(report) for report in baseline))
    right = _summarize_observations(tuple(_report_observation(report) for report in candidate))
    keys = ("median_turn_seconds", "median_sampling_rounds", "median_reported_subject_tokens", "effective_subject_tokens_per_pass")
    deltas = {key: right[key] - left[key] if left[key] is not None and right[key] is not None else None for key in keys}
    deltas["pass_rate"] = (
        right["pass_rate"] - left["pass_rate"]
        if left["scored_count"] == left["attempt_count"] and right["scored_count"] == right["attempt_count"]
        else None
    )
    return deltas


def _profile_shape(reports: Sequence[LoadedAgentReport]) -> tuple[int, int] | None:
    if not _all_supported(reports):
        return None
    modes = [report.payload["execution_mode"] for report in reports]
    return modes.count("headless"), modes.count("headed")


def _all_supported(reports: Sequence[LoadedAgentReport]) -> bool:
    return bool(reports) and all(
        report.qualification is ReportQualification.QUALIFIED and report.schema_version in (5, CURRENT_REPORT_SCHEMA_VERSION)
        for report in reports
    )


class _PolicyFields(BaseModel):
    # Reports are local runner output. Validate what the policy consumes and let
    # diagnostics evolve without making old measurements unreadable.
    model_config = ConfigDict(strict=True, extra="ignore")


class _CheckFields(_PolicyFields):
    passed: bool


class _IntegrityFields(_PolicyFields):
    passed: bool


class _SemanticFields(_PolicyFields):
    verdict: Literal["pass", "partial", "fail", "inconclusive", "not_evaluated"]
    checks: list[_CheckFields]


class _JudgeFields(_PolicyFields):
    required: bool
    status: str
    verdict: Literal["pass", "partial", "fail", "inconclusive", "not_evaluated"]
    rubric_id: str | None = None
    rubric_sha256: str | None = None
    provider_model: str | None = None


class _BudgetFields(_PolicyFields):
    status: str
    policy: dict[str, Any]
    reported_subject_tokens: int
    exhaustion_reason: str | None = None


class _IdentityFields(_PolicyFields):
    fixture_sha256: str | None = None
    effective_settings_sha256: str | None = None
    embedding_settings_sha256: str | None = None
    judge_settings_sha256: str | None = None
    harness_variant: str | None = None


class _ReportFields(_PolicyFields):
    report_kind: Literal["xenix.agent_harness.cell"]
    case_id: str
    run_id: str
    provider_model: str
    execution_mode: Literal["headless", "headed"]
    run_status: str
    failure_kind: str | None = None
    semantic: _SemanticFields
    integrity: _IntegrityFields
    judge: _JudgeFields
    budget: _BudgetFields
    identity: _IdentityFields
    subject_metrics: dict[str, Any]


def _validate_legacy_identity(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("case_id"), str) or not isinstance(payload.get("run_id"), str):
        raise ReportPolicyError("legacy_report_identity_invalid")


def _validate_report(payload: Mapping[str, Any]) -> None:
    try:
        _ReportFields.model_validate(payload)
    except ValidationError as exc:
        raise ReportPolicyError("report_shape_invalid") from exc


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReportPolicyError("report_json_invalid") from exc
    if not isinstance(value, dict):
        raise ReportPolicyError("report_json_invalid")
    return value


def _nested_value(payload: Mapping[str, Any], dotted: str) -> Any:
    value: Any = payload
    for key in dotted.split("."):
        value = value.get(key) if isinstance(value, Mapping) else None
    return _freeze(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _hash_equal(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left.lower() == right.lower()


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
