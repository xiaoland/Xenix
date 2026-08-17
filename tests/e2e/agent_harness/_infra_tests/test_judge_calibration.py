from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from xenix.services.llm import LLMSettings

from tests.e2e.agent_harness._infra import judge_calibration
from tests.e2e.agent_harness._infra.budgets import IsolatedCallOutcome, IsolatedCallStatus
from tests.e2e.agent_harness._infra.contracts import (
    JudgeIndependence,
    JudgeInput,
    JudgeResult,
    JudgeRubric,
    JudgeStatus,
    SemanticVerdict,
)
from tests.e2e.agent_harness._infra.judge_calibration import (
    CALIBRATION_PACKET_TIMEOUT_SECONDS,
    JudgeCalibrationError,
    load_calibration_report,
    run_judge_calibration,
    write_calibration_report,
)


@dataclass(frozen=True)
class _Packet:
    fixture_id: str
    expected_verdict: SemanticVerdict
    judge_input: JudgeInput


def test_calibration_is_bounded_repeated_and_persists_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[float] = []
    retry_attempts: list[int] = []

    def complete_call(*args: Any, timeout_seconds: float, **_kwargs: Any) -> IsolatedCallOutcome:
        calls.append(timeout_seconds)
        retry_attempts.append(args[1]["settings"].retry_attempts)
        return IsolatedCallOutcome(
            status=IsolatedCallStatus.COMPLETED,
            value=JudgeResult(
                status=JudgeStatus.COMPLETED,
                verdict=SemanticVerdict.PASS,
                independence=JudgeIndependence.INDEPENDENT,
                reason_codes=("supported",),
            ),
        )

    monkeypatch.setattr(judge_calibration, "run_isolated_call", complete_call)
    packet = _packet("clear-pass", "private evaluator evidence")

    report = run_judge_calibration(
        suite_symbol="tests.e2e.agent_harness.test_example:calibrations",
        packets=(packet,),
        settings=LLMSettings(retry_attempts=9),
        judge_settings_sha256="a" * 64,
        judge_model="judge/model",
        subject_model="subject/model",
    )

    assert report.passed
    assert calls == [CALIBRATION_PACKET_TIMEOUT_SECONDS] * 3
    assert retry_attempts == [3, 3, 3]
    destination = tmp_path / "calibration.json"
    write_calibration_report(destination, report)
    serialized = destination.read_text(encoding="utf-8")
    assert "private evaluator evidence" not in serialized
    assert load_calibration_report(destination) == report


def test_calibration_fails_closed_on_one_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = iter(
        (
            _judge_outcome(SemanticVerdict.FAIL),
            _judge_outcome(SemanticVerdict.PASS),
            _judge_outcome(SemanticVerdict.PASS),
        )
    )
    monkeypatch.setattr(
        judge_calibration,
        "run_isolated_call",
        lambda *_args, **_kwargs: next(outcomes),
    )

    report = run_judge_calibration(
        suite_symbol="tests.e2e.agent_harness.test_example:calibrations",
        packets=(_packet("clear-pass", "safe"),),
        settings=LLMSettings(),
        judge_settings_sha256="a" * 64,
        judge_model="judge/model",
        subject_model="subject/model",
    )

    assert not report.passed
    assert not report.observations[0].passed


def test_calibration_rejects_unbounded_suite_and_same_model_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched = False

    def unexpected_call(*_args: Any, **_kwargs: Any) -> IsolatedCallOutcome:
        nonlocal dispatched
        dispatched = True
        return _judge_outcome(SemanticVerdict.PASS)

    monkeypatch.setattr(judge_calibration, "run_isolated_call", unexpected_call)
    packets = tuple(_packet(f"packet-{index}", "safe") for index in range(5))
    with pytest.raises(JudgeCalibrationError, match="calibration_packet_count_invalid"):
        run_judge_calibration(
            suite_symbol="tests.e2e.agent_harness.test_example:calibrations",
            packets=packets,
            settings=LLMSettings(),
            judge_settings_sha256="a" * 64,
            judge_model="judge/model",
            subject_model="subject/model",
        )
    with pytest.raises(JudgeCalibrationError, match="judge_calibration_model_not_independent"):
        run_judge_calibration(
            suite_symbol="tests.e2e.agent_harness.test_example:calibrations",
            packets=(_packet("clear-pass", "safe"),),
            settings=LLMSettings(),
            judge_settings_sha256="a" * 64,
            judge_model="same/model",
            subject_model="same/model",
        )
    assert not dispatched


def _packet(fixture_id: str, evidence: str) -> _Packet:
    return _Packet(
        fixture_id=fixture_id,
        expected_verdict=SemanticVerdict.PASS,
        judge_input=JudgeInput(
            rubric=JudgeRubric(
                rubric_id="analysis.example.v1",
                score_dimensions=("quality",),
                allowed_reason_codes=("supported",),
            ),
            task_intent="Assess the final public outcome.",
            facts=("One bounded fact.",),
            artifact_evidence=(evidence,),
        ),
    )


def _judge_outcome(verdict: SemanticVerdict) -> IsolatedCallOutcome:
    return IsolatedCallOutcome(
        status=IsolatedCallStatus.COMPLETED,
        value=JudgeResult(
            status=JudgeStatus.COMPLETED,
            verdict=verdict,
            independence=JudgeIndependence.INDEPENDENT,
            reason_codes=("supported",),
        ),
    )
