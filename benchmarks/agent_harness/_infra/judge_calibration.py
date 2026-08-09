"""Bounded, hand-labelled qualification for an explicit Agent benchmark Judge.

Calibration suites remain case-owned symbols.  This module supplies only the
case-agnostic execution, identity, aggregation, and privacy-bounded report.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence

from xenix.services.llm import FrozenLLMSettingsSource, LLMService, LLMSettings

from .budgets import IsolatedCallStatus, run_isolated_call
from .contracts import JudgeIndependence, JudgeInput, JudgeResult, JudgeRubric, JudgeStatus, SemanticVerdict
from .judge import run_judge


CALIBRATION_POLICY_ID = "agent-harness-judge-calibration-v1"
CALIBRATION_REPORT_KIND = "xenix.agent_harness.judge_calibration"
CALIBRATION_SCHEMA_VERSION = 1
CALIBRATION_REPETITIONS = 3
MAX_CALIBRATION_PACKETS = 4
CALIBRATION_PACKET_TIMEOUT_SECONDS = 300.0
_MAX_REPORT_BYTES = 1_048_576


class JudgeCalibrationError(ValueError):
    """A stable calibration setup or report error without provider content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JudgeCalibrationPacket(Protocol):
    fixture_id: str
    expected_verdict: SemanticVerdict
    judge_input: JudgeInput


@dataclass(frozen=True)
class CalibrationObservation:
    fixture_id: str
    repetition_index: int
    expected_verdict: SemanticVerdict
    judge_status: str
    observed_verdict: SemanticVerdict
    independence: JudgeIndependence
    reason_codes: tuple[str, ...] = ()
    metrics: Mapping[str, Any] | None = None

    @property
    def passed(self) -> bool:
        return (
            self.judge_status == JudgeStatus.COMPLETED.value
            and self.observed_verdict is self.expected_verdict
            and self.independence is JudgeIndependence.INDEPENDENT
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "repetition_index": self.repetition_index,
            "expected_verdict": self.expected_verdict.value,
            "judge_status": self.judge_status,
            "observed_verdict": self.observed_verdict.value,
            "independence": self.independence.value,
            "reason_codes": list(self.reason_codes),
            "metrics": dict(self.metrics) if self.metrics is not None else None,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class JudgeCalibrationReport:
    suite_symbol: str
    suite_sha256: str
    rubric_id: str
    rubric_sha256: str
    judge_model: str
    subject_model: str
    judge_settings_sha256: str
    observations: tuple[CalibrationObservation, ...]
    packet_count: int
    repetitions: int = CALIBRATION_REPETITIONS
    policy_id: str = CALIBRATION_POLICY_ID
    schema_version: int = CALIBRATION_SCHEMA_VERSION

    @property
    def passed(self) -> bool:
        return (
            self.policy_id == CALIBRATION_POLICY_ID
            and self.repetitions == CALIBRATION_REPETITIONS
            and 0 < self.packet_count <= MAX_CALIBRATION_PACKETS
            and len(self.observations) == self.packet_count * self.repetitions
            and _observation_topology_valid(
                self.observations,
                packet_count=self.packet_count,
                repetitions=self.repetitions,
            )
            and all(observation.passed for observation in self.observations)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "report_kind": CALIBRATION_REPORT_KIND,
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "suite_symbol": self.suite_symbol,
            "suite_sha256": self.suite_sha256,
            "rubric_id": self.rubric_id,
            "rubric_sha256": self.rubric_sha256,
            "judge_model": self.judge_model,
            "subject_model": self.subject_model,
            "judge_settings_sha256": self.judge_settings_sha256,
            "packet_count": self.packet_count,
            "repetitions": self.repetitions,
            "passed": self.passed,
            "observations": [observation.to_payload() for observation in self.observations],
        }


def run_judge_calibration(
    *,
    suite_symbol: str,
    packets: Iterable[JudgeCalibrationPacket],
    settings: LLMSettings,
    judge_settings_sha256: str,
    judge_model: str,
    subject_model: str,
) -> JudgeCalibrationReport:
    """Run at most four packets three times, each behind a 300-second process wall."""

    normalized_packets = _validated_packets(packets)
    normalized_suite_symbol = _bounded_string(suite_symbol, "calibration_suite_symbol_invalid", 256)
    normalized_judge_model = _bounded_string(judge_model, "calibration_judge_model_invalid", 256)
    normalized_subject_model = _bounded_string(subject_model, "calibration_subject_model_invalid", 256)
    if normalized_judge_model == normalized_subject_model:
        raise JudgeCalibrationError("judge_calibration_model_not_independent")
    _sha256_string(judge_settings_sha256, "calibration_settings_sha256_invalid")

    rubric = normalized_packets[0].judge_input.rubric
    rubric_sha256 = judge_rubric_sha256(rubric)
    effective_settings = settings.model_copy(
        deep=True,
        update={"retry_attempts": 2},
    )
    observations: list[CalibrationObservation] = []
    for packet in normalized_packets:
        for repetition_index in range(1, CALIBRATION_REPETITIONS + 1):
            outcome = run_isolated_call(
                _run_judge_once,
                {
                    "settings": effective_settings,
                    "judge_input": packet.judge_input,
                    "judge_model": normalized_judge_model,
                    "subject_model": normalized_subject_model,
                },
                timeout_seconds=CALIBRATION_PACKET_TIMEOUT_SECONDS,
            )
            observations.append(
                _observation_from_outcome(
                    fixture_id=packet.fixture_id,
                    repetition_index=repetition_index,
                    expected_verdict=packet.expected_verdict,
                    outcome_status=outcome.status,
                    outcome_value=outcome.value,
                )
            )
    return JudgeCalibrationReport(
        suite_symbol=normalized_suite_symbol,
        suite_sha256=_suite_sha256(normalized_packets),
        rubric_id=rubric.rubric_id,
        rubric_sha256=rubric_sha256,
        judge_model=normalized_judge_model,
        subject_model=normalized_subject_model,
        judge_settings_sha256=judge_settings_sha256.lower(),
        observations=tuple(observations),
        packet_count=len(normalized_packets),
    )


def judge_rubric_sha256(rubric: JudgeRubric) -> str:
    """Match the canonical rubric identity persisted by the benchmark runner."""

    payload = json.dumps(
        {
            "rubric_id": rubric.rubric_id,
            "score_dimensions": list(rubric.score_dimensions),
            "allowed_reason_codes": list(rubric.allowed_reason_codes),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def write_calibration_report(path: Path, report: JudgeCalibrationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.to_payload(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_calibration_report(path: Path) -> JudgeCalibrationReport:
    """Strictly load a bounded calibration report; raw Judge data is never admitted."""

    try:
        if path.stat().st_size > _MAX_REPORT_BYTES:
            raise JudgeCalibrationError("calibration_report_too_large")
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except JudgeCalibrationError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise JudgeCalibrationError("calibration_report_json_invalid") from exc
    if not isinstance(payload, dict):
        raise JudgeCalibrationError("calibration_report_json_invalid")
    return _report_from_payload(payload)


def _run_judge_once(
    *,
    settings: LLMSettings,
    judge_input: JudgeInput,
    judge_model: str,
    subject_model: str,
) -> JudgeResult:
    llm = LLMService(FrozenLLMSettingsSource(settings))
    return run_judge(
        llm=llm,
        judge_input=judge_input,
        judge_model_key=judge_model,
        subject_model_key=subject_model,
    )


def _validated_packets(
    packets: Iterable[JudgeCalibrationPacket],
) -> tuple[JudgeCalibrationPacket, ...]:
    values = tuple(packets)
    if not values or len(values) > MAX_CALIBRATION_PACKETS:
        raise JudgeCalibrationError("calibration_packet_count_invalid")
    fixture_ids: set[str] = set()
    rubric_hash: str | None = None
    for packet in values:
        fixture_id = _bounded_string(
            getattr(packet, "fixture_id", None),
            "calibration_fixture_id_invalid",
            96,
        )
        if fixture_id in fixture_ids:
            raise JudgeCalibrationError("calibration_fixture_id_duplicate")
        fixture_ids.add(fixture_id)
        expected = getattr(packet, "expected_verdict", None)
        if expected not in {
            SemanticVerdict.PASS,
            SemanticVerdict.PARTIAL,
            SemanticVerdict.FAIL,
            SemanticVerdict.INCONCLUSIVE,
        }:
            raise JudgeCalibrationError("calibration_expected_verdict_invalid")
        judge_input = getattr(packet, "judge_input", None)
        if not isinstance(judge_input, JudgeInput):
            raise JudgeCalibrationError("calibration_judge_input_invalid")
        current_hash = judge_rubric_sha256(judge_input.rubric)
        if rubric_hash is None:
            rubric_hash = current_hash
        elif rubric_hash != current_hash:
            raise JudgeCalibrationError("calibration_rubric_mismatch")
    return values


def _suite_sha256(packets: Sequence[JudgeCalibrationPacket]) -> str:
    payload = [
        {
            "fixture_id": packet.fixture_id,
            "expected_verdict": packet.expected_verdict.value,
            "rubric_sha256": judge_rubric_sha256(packet.judge_input.rubric),
            "task_intent": packet.judge_input.task_intent,
            "facts": list(packet.judge_input.facts),
            "artifact_evidence": list(packet.judge_input.artifact_evidence),
        }
        for packet in packets
    ]
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _observation_from_outcome(
    *,
    fixture_id: str,
    repetition_index: int,
    expected_verdict: SemanticVerdict,
    outcome_status: IsolatedCallStatus,
    outcome_value: object,
) -> CalibrationObservation:
    if outcome_status is not IsolatedCallStatus.COMPLETED or not isinstance(outcome_value, JudgeResult):
        return CalibrationObservation(
            fixture_id=fixture_id,
            repetition_index=repetition_index,
            expected_verdict=expected_verdict,
            judge_status=(
                "timed_out"
                if outcome_status is IsolatedCallStatus.TIMED_OUT
                else "crashed"
            ),
            observed_verdict=SemanticVerdict.NOT_EVALUATED,
            independence=JudgeIndependence.NOT_APPLICABLE,
        )
    return CalibrationObservation(
        fixture_id=fixture_id,
        repetition_index=repetition_index,
        expected_verdict=expected_verdict,
        judge_status=outcome_value.status.value,
        observed_verdict=outcome_value.verdict,
        independence=outcome_value.independence,
        reason_codes=outcome_value.reason_codes,
        metrics=outcome_value.metrics.to_payload(),
    )


def _report_from_payload(payload: Mapping[str, Any]) -> JudgeCalibrationReport:
    expected_keys = {
        "report_kind", "schema_version", "policy_id", "suite_symbol", "suite_sha256",
        "rubric_id", "rubric_sha256", "judge_model", "subject_model",
        "judge_settings_sha256", "packet_count", "repetitions", "passed", "observations",
    }
    if set(payload) != expected_keys:
        raise JudgeCalibrationError("calibration_report_shape_invalid")
    if (
        payload["report_kind"] != CALIBRATION_REPORT_KIND
        or payload["schema_version"] != CALIBRATION_SCHEMA_VERSION
        or payload["policy_id"] != CALIBRATION_POLICY_ID
    ):
        raise JudgeCalibrationError("calibration_report_version_invalid")
    suite_symbol = _bounded_string(payload["suite_symbol"], "calibration_report_identity_invalid", 256)
    suite_sha256 = _sha256_string(payload["suite_sha256"], "calibration_report_identity_invalid")
    rubric_id = _bounded_string(payload["rubric_id"], "calibration_report_identity_invalid", 128)
    rubric_sha256 = _sha256_string(payload["rubric_sha256"], "calibration_report_identity_invalid")
    judge_model = _bounded_string(payload["judge_model"], "calibration_report_identity_invalid", 256)
    subject_model = _bounded_string(payload["subject_model"], "calibration_report_identity_invalid", 256)
    settings_sha256 = _sha256_string(payload["judge_settings_sha256"], "calibration_report_identity_invalid")
    packet_count = _bounded_int(payload["packet_count"], "calibration_report_count_invalid", 1, MAX_CALIBRATION_PACKETS)
    repetitions = _bounded_int(
        payload["repetitions"],
        "calibration_report_count_invalid",
        CALIBRATION_REPETITIONS,
        CALIBRATION_REPETITIONS,
    )
    observations_payload = payload["observations"]
    if not isinstance(observations_payload, list) or len(observations_payload) != packet_count * repetitions:
        raise JudgeCalibrationError("calibration_report_observations_invalid")
    observations = tuple(_observation_from_payload(item) for item in observations_payload)
    report = JudgeCalibrationReport(
        suite_symbol=suite_symbol,
        suite_sha256=suite_sha256,
        rubric_id=rubric_id,
        rubric_sha256=rubric_sha256,
        judge_model=judge_model,
        subject_model=subject_model,
        judge_settings_sha256=settings_sha256,
        observations=observations,
        packet_count=packet_count,
    )
    if payload["passed"] is not report.passed:
        raise JudgeCalibrationError("calibration_report_projection_invalid")
    return report


def _observation_from_payload(value: object) -> CalibrationObservation:
    if not isinstance(value, dict) or set(value) != {
        "fixture_id", "repetition_index", "expected_verdict", "judge_status",
        "observed_verdict", "independence", "reason_codes", "metrics", "passed",
    }:
        raise JudgeCalibrationError("calibration_observation_shape_invalid")
    fixture_id = _bounded_string(value["fixture_id"], "calibration_observation_invalid", 96)
    repetition_index = _bounded_int(
        value["repetition_index"],
        "calibration_observation_invalid",
        1,
        CALIBRATION_REPETITIONS,
    )
    try:
        expected = SemanticVerdict(value["expected_verdict"])
        observed = SemanticVerdict(value["observed_verdict"])
        independence = JudgeIndependence(value["independence"])
    except (TypeError, ValueError) as exc:
        raise JudgeCalibrationError("calibration_observation_invalid") from exc
    status = _bounded_string(value["judge_status"], "calibration_observation_invalid", 64)
    if status not in {*(item.value for item in JudgeStatus), "timed_out", "crashed"}:
        raise JudgeCalibrationError("calibration_observation_invalid")
    reason_codes = value["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or len(reason_codes) > 32
        or len(set(reason_codes)) != len(reason_codes)
        or any(not isinstance(code, str) or not code.strip() or len(code) > 128 for code in reason_codes)
    ):
        raise JudgeCalibrationError("calibration_observation_invalid")
    metrics = _validated_metrics(value["metrics"])
    observation = CalibrationObservation(
        fixture_id=fixture_id,
        repetition_index=repetition_index,
        expected_verdict=expected,
        judge_status=status,
        observed_verdict=observed,
        independence=independence,
        reason_codes=tuple(reason_codes),
        metrics=metrics,
    )
    if value["passed"] is not observation.passed:
        raise JudgeCalibrationError("calibration_observation_projection_invalid")
    return observation


def _observation_topology_valid(
    observations: Sequence[CalibrationObservation],
    *,
    packet_count: int,
    repetitions: int,
) -> bool:
    fixture_ids = {observation.fixture_id for observation in observations}
    if len(fixture_ids) != packet_count:
        return False
    expected_indexes = set(range(1, repetitions + 1))
    for fixture_id in fixture_ids:
        fixture_observations = tuple(
            observation
            for observation in observations
            if observation.fixture_id == fixture_id
        )
        if (
            {observation.repetition_index for observation in fixture_observations}
            != expected_indexes
            or len({observation.expected_verdict for observation in fixture_observations})
            != 1
        ):
            return False
    return True


def _validated_metrics(value: object) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "elapsed_seconds",
        "token_usage",
        "provider_retry_count",
    }:
        raise JudgeCalibrationError("calibration_observation_metrics_invalid")
    elapsed = value["elapsed_seconds"]
    if elapsed is not None and (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not 0 <= float(elapsed) <= CALIBRATION_PACKET_TIMEOUT_SECONDS
    ):
        raise JudgeCalibrationError("calibration_observation_metrics_invalid")
    retry_count = value["provider_retry_count"]
    if isinstance(retry_count, bool) or not isinstance(retry_count, int) or not 0 <= retry_count <= 100:
        raise JudgeCalibrationError("calibration_observation_metrics_invalid")
    token_usage = value["token_usage"]
    if token_usage is not None:
        if not isinstance(token_usage, dict) or set(token_usage) != {
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
        }:
            raise JudgeCalibrationError("calibration_observation_metrics_invalid")
        if any(
            isinstance(amount, bool)
            or not isinstance(amount, int)
            or not 0 <= amount <= 100_000_000
            for amount in token_usage.values()
        ):
            raise JudgeCalibrationError("calibration_observation_metrics_invalid")
    return value


def _bounded_string(value: object, code: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise JudgeCalibrationError(code)
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise JudgeCalibrationError(code)
    return normalized


def _sha256_string(value: object, code: str) -> str:
    normalized = _bounded_string(value, code, 64).lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise JudgeCalibrationError(code)
    return normalized


def _bounded_int(value: object, code: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise JudgeCalibrationError(code)
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
