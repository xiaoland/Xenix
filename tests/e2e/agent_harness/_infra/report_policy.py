"""Versioned, Agent-only acceptance and comparison for benchmark reports.

The live pytest surface deliberately produces measurements.  This module is the
consumer of the outcome and measurement fields needed for acceptance.  It has no service-report input or service-test dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from .judge_calibration import JudgeCalibrationReport


REPORT_POLICY_ID = "agent-harness-report-policy-v2"
AGENT_REPORT_KIND = "xenix.agent_harness.cell"
CURRENT_REPORT_SCHEMA_VERSION = 5
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

    payload = _load_json_object(path)
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
    if not resolved:
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
    return ReportPolicyDecision(
        evaluation=evaluation,
        qualified=qualified,
        accepted=accepted,
        gate_eligible=gate_eligible,
        reason_codes=_unique(reasons),
        case_id=next(iter(case_ids)) if len(case_ids) == 1 else None,
        run_ids=tuple(report.run_id for report in reports if report.run_id is not None),
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
        "effective_settings_sha256",
        "harness_variant",
    )
    for payload in payloads:
        identity = payload["identity"]
        if any(not identity.get(key) for key in required_identity):
            reasons.append("identity_incomplete")
    fields = (
        "provider_model",
        "identity.fixture_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.effective_settings_sha256",
        "identity.harness_variant",
        "budget.policy",
        "judge.required",
        "judge.rubric_id",
        "judge.rubric_sha256",
        "judge.provider_model",
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
        "case_id",
        "provider_model",
        "identity.fixture_sha256",
        "identity.embedding_settings_sha256",
        "identity.judge_settings_sha256",
        "identity.effective_settings_sha256",
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
            and math.isfinite(value)
        ]

    baseline_seconds = values(baseline, "turn_seconds")
    candidate_seconds = values(candidate, "turn_seconds")
    baseline_tokens = [report.payload["budget"]["reported_subject_tokens"] for report in baseline]
    candidate_tokens = [report.payload["budget"]["reported_subject_tokens"] for report in candidate]
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
        report.qualification is ReportQualification.QUALIFIED and report.schema_version == CURRENT_REPORT_SCHEMA_VERSION
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
    semantic: _SemanticFields
    integrity: _IntegrityFields
    judge: _JudgeFields
    budget: _BudgetFields
    identity: _IdentityFields
    subject_metrics: dict[str, Any]


def _validate_legacy_identity(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("case_id"), str) or not isinstance(payload.get("run_id"), str):
        raise ReportPolicyError("legacy_report_identity_invalid")


def _validate_v5_report(payload: Mapping[str, Any]) -> None:
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
