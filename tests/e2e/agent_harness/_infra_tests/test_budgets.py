from __future__ import annotations

import os
import time
from typing import Any

import pytest

from tests.e2e.agent_harness._infra import runner
from tests.e2e.agent_harness._infra import pytest_plugin
from tests.e2e.agent_harness._infra.budgets import (
    BenchmarkBudgetController,
    BenchmarkBudgetError,
    BenchmarkBudgetPolicy,
    BenchmarkBudgetSnapshot,
    BenchmarkBudgetStatus,
    IsolatedCallStatus,
    run_isolated_call,
)
from tests.e2e.agent_harness._infra.contracts import (
    AgentHarnessBenchmarkResult,
    BenchmarkExecutionMode,
    BenchmarkMetrics,
    BenchmarkRunStatus,
)
from tests.e2e.agent_harness._infra.pytest_plugin import _InvocationBudgetState
from xenix.services.llm import FrozenLLMSettingsSource, LLMService, LLMSettings
from xenix.services.llm.providers import ProviderResponse


def _sleep_longer_than_watchdog(*, seconds: float) -> None:
    time.sleep(seconds)


def _exit_without_result() -> None:
    os._exit(7)


class _BoundaryOnlyCase:
    case_id = "offline-invocation-boundary"

    def validate_input(self) -> str:
        return "0" * 64


class _ControllerConfig:
    def __init__(self, tmp_path: Any, state: _InvocationBudgetState) -> None:
        self.stash = {pytest_plugin._INVOCATION_BUDGET_KEY: state}
        self._options = {
            "agent_harness_llm_settings": None,
            "agent_harness_embedding_settings": None,
            "agent_harness_headed": False,
            "agent_harness_output_directory": tmp_path,
            "agent_harness_models": [],
            "agent_harness_judge_llm_settings": None,
            "agent_harness_judge_model": None,
            "agent_harness_variant": "baseline",
        }

    def getoption(self, name: str) -> Any:
        return self._options[name]


def _bounded_service() -> tuple[runner._BoundedLLMService, BenchmarkBudgetController]:
    budget = BenchmarkBudgetController(BenchmarkBudgetPolicy())
    service = runner._BoundedLLMService(
        FrozenLLMSettingsSource(LLMSettings()),
        budget,
    )
    return service, budget


def _install_offline_response(
    monkeypatch: pytest.MonkeyPatch,
    *,
    usage_payload: dict[str, Any] | None,
) -> None:
    def complete_without_provider(
        _service: LLMService,
        *,
        fq_model_key: str | None = None,
        messages: list[Any],
        tools: list[Any],
        retry_callback: Any = None,
        before_provider_request: Any = None,
    ) -> ProviderResponse:
        del fq_model_key, messages, tools, retry_callback
        if before_provider_request is not None:
            before_provider_request()
        return ProviderResponse(usage_payload=usage_payload)

    monkeypatch.setattr(LLMService, "complete", complete_without_provider)


def test_thirteenth_sampling_round_is_rejected() -> None:
    budget = BenchmarkBudgetController(BenchmarkBudgetPolicy())

    for _ in range(12):
        budget.begin_sampling_round()

    with pytest.raises(BenchmarkBudgetError) as raised:
        budget.begin_sampling_round()

    assert raised.value.code == "sampling_round_limit_exceeded"
    snapshot = budget.snapshot()
    assert snapshot.status is BenchmarkBudgetStatus.EXCEEDED
    assert snapshot.sampling_rounds_admitted == 12
    assert snapshot.exhaustion_reason == "sampling_round_limit_exceeded"


def test_reported_response_at_500k_boundary_halts_the_next_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_offline_response(monkeypatch, usage_payload={"total_tokens": 500_000})
    service, budget = _bounded_service()

    response = service.complete(messages=[], tools=[])

    assert response.usage_payload == {"total_tokens": 500_000}
    snapshot = budget.snapshot()
    assert snapshot.status is BenchmarkBudgetStatus.WITHIN_LIMITS
    assert snapshot.reported_subject_tokens == 500_000
    assert snapshot.provider_attempts_dispatched == 1
    assert snapshot.exhaustion_reason is None
    with pytest.raises(BenchmarkBudgetError, match="subject_token_limit_reached"):
        service.complete(messages=[], tools=[])
    assert budget.snapshot().status is BenchmarkBudgetStatus.EXCEEDED


def test_missing_provider_usage_is_unverifiable_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_offline_response(monkeypatch, usage_payload=None)
    service, budget = _bounded_service()

    service.complete(messages=[], tools=[])

    snapshot = budget.snapshot()
    assert snapshot.status is BenchmarkBudgetStatus.UNVERIFIABLE
    assert snapshot.reported_subject_tokens == 0
    assert snapshot.exhaustion_reason == "subject_usage_unreported"
    with pytest.raises(BenchmarkBudgetError, match="subject_usage_unreported"):
        service.complete(messages=[], tools=[])


def test_provider_attempt_limit_is_enforced_for_each_sampling_round() -> None:
    budget = BenchmarkBudgetController(BenchmarkBudgetPolicy())
    budget.begin_sampling_round()
    budget.admit_provider_attempt()
    budget.admit_provider_attempt()

    with pytest.raises(BenchmarkBudgetError, match="provider_attempt_limit_exceeded"):
        budget.admit_provider_attempt()

    assert budget.snapshot().provider_attempts_dispatched == 2


def test_four_million_invocation_boundary_stops_before_isolated_cell(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "agent-settings.json"
    settings_path.write_text(LLMSettings().model_dump_json(), encoding="utf-8")
    monkeypatch.delenv(runner.EMBEDDING_SETTINGS_PATH_ENV, raising=False)
    monkeypatch.delenv(runner.JUDGE_LLM_SETTINGS_PATH_ENV, raising=False)

    def fail_if_cell_starts(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("the invocation boundary must stop before the isolated cell")

    monkeypatch.setattr(runner, "run_isolated_call", fail_if_cell_starts)

    run = runner.run_benchmark(
        settings_path=settings_path,
        case=_BoundaryOnlyCase(),
        output_directory=tmp_path / "results",
        invocation_reported_subject_tokens=4_000_000,
    )

    assert run.persisted is True
    assert run.result.run_status is BenchmarkRunStatus.BUDGET_EXCEEDED
    assert run.result.failure_kind == "invocation_token_limit_reached"
    assert run.result.budget.status is BenchmarkBudgetStatus.EXCEEDED
    assert run.result.budget.invocation_reported_subject_tokens == 4_000_000


def test_invalid_setup_preserves_prior_invocation_tokens(tmp_path: Any) -> None:
    run = runner.run_benchmark(
        settings_path=tmp_path / "missing-settings.json",
        case=_BoundaryOnlyCase(),
        output_directory=tmp_path / "results",
        invocation_reported_subject_tokens=123_456,
    )

    assert run.result.run_status is BenchmarkRunStatus.INVALID_SETUP
    assert run.result.budget.invocation_reported_subject_tokens == 123_456


def test_short_watchdog_kills_the_isolated_process() -> None:
    outcome = run_isolated_call(
        _sleep_longer_than_watchdog,
        {"seconds": 5.0},
        timeout_seconds=0.05,
    )

    assert outcome.status is IsolatedCallStatus.TIMED_OUT
    assert outcome.failure_kind == "process_wall_time_exceeded"
    assert outcome.value is None


def test_abrupt_child_exit_is_a_bounded_crash_result() -> None:
    outcome = run_isolated_call(
        _exit_without_result,
        {},
        timeout_seconds=5.0,
    )

    assert outcome.status is IsolatedCallStatus.CRASHED
    assert outcome.failure_kind == "child_process_no_result"
    assert outcome.exit_code == 7


def test_integrity_failure_halts_remaining_invocation_cells() -> None:
    state = _InvocationBudgetState()
    result = AgentHarnessBenchmarkResult(
        case_id="offline-integrity-boundary",
        run_id="integrity-failed",
        provider_model="offline/model",
        execution_mode=BenchmarkExecutionMode.HEADLESS,
        run_status=BenchmarkRunStatus.COMPLETED,
        subject_metrics=BenchmarkMetrics(),
        budget=BenchmarkBudgetSnapshot(
            status=BenchmarkBudgetStatus.WITHIN_LIMITS,
            policy=runner.DEFAULT_BUDGET_POLICY,
        ),
    )

    state.observe(runner.BenchmarkRun(result=result, persisted=True))

    assert state.halted_reason == "benchmark_integrity_invalid"


def test_persistence_failure_halts_remaining_invocation_cells() -> None:
    state = _InvocationBudgetState()
    result = AgentHarnessBenchmarkResult(
        case_id="offline-persistence-boundary",
        run_id="persistence-failed",
        provider_model="offline/model",
        execution_mode=BenchmarkExecutionMode.HEADLESS,
        run_status=BenchmarkRunStatus.COMPLETED,
        subject_metrics=BenchmarkMetrics(),
        budget=BenchmarkBudgetSnapshot(
            status=BenchmarkBudgetStatus.WITHIN_LIMITS,
            policy=runner.DEFAULT_BUDGET_POLICY,
        ),
    )

    state.observe(runner.BenchmarkRun(result=result, persisted=False))

    assert state.halted_reason == "benchmark_result_not_persisted"


def test_unexpected_runner_exception_halts_remaining_invocation_cells(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _InvocationBudgetState()
    config = _ControllerConfig(tmp_path, state)
    controller = pytest_plugin.AgentHarnessBenchmarkController(config=config)  # type: ignore[arg-type]
    monkeypatch.setattr(
        pytest_plugin,
        "run_benchmark",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        controller.run(_BoundaryOnlyCase())

    assert state.halted_reason == "benchmark_runner_exception"
