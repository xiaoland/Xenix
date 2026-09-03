"""Small pytest control surface for explicit real-provider benchmark cells.

Pytest owns collection, selection and item lifecycle.  This module only turns
the selected item's command-line configuration into one case-agnostic runner
invocation; outcome verdicts remain measurements rather than test failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from .contracts import BenchmarkCase, BenchmarkExecutionMode, BenchmarkRunStatus
from .budgets import BenchmarkBudgetStatus
from .runner import (
    DEFAULT_BUDGET_POLICY,
    DEFAULT_OUTPUT_DIRECTORY,
    BenchmarkRun,
    run_benchmark,
)

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.fixtures import FixtureRequest


_LIVE_MARKER = "agent_harness_live: explicit real-provider Agent Harness benchmark case"
_INVOCATION_BUDGET_KEY = pytest.StashKey["_InvocationBudgetState"]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent-harness benchmark")
    group.addoption(
        "--run-agent-harness",
        action="store_true",
        default=False,
        dest="agent_harness_live",
        help="Allow selected Agent Harness benchmark cases to call configured providers.",
    )
    group.addoption(
        "--headed",
        action="store_true",
        default=False,
        dest="agent_harness_headed",
        help="Drive each selected real-provider case through the visible desktop UI.",
    )
    group.addoption(
        "--llm-settings",
        type=Path,
        dest="agent_harness_llm_settings",
        help=(
            "External subject LLM settings JSON; otherwise "
            "XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH."
        ),
    )
    group.addoption(
        "--judge-llm-settings",
        type=Path,
        dest="agent_harness_judge_llm_settings",
        help=(
            "External judge LLM settings JSON; otherwise "
            "XENIX_AGENT_BENCHMARK_JUDGE_LLM_SETTINGS_PATH."
        ),
    )
    group.addoption(
        "--embedding-settings",
        type=Path,
        dest="agent_harness_embedding_settings",
        help=(
            "External subject Embedding settings JSON; otherwise "
            "XENIX_AGENT_BENCHMARK_EMBEDDING_SETTINGS_PATH."
        ),
    )
    group.addoption(
        "--judge-model",
        dest="agent_harness_judge_model",
        help="Optional judge provider/model key from the explicit judge settings.",
    )
    group.addoption(
        "--model",
        action="append",
        default=[],
        dest="agent_harness_models",
        help=(
            "Optional single subject provider/model override; omission selects "
            "default_fq_model_key from the settings snapshot."
        ),
    )
    group.addoption(
        "--harness-variant",
        default="baseline",
        dest="agent_harness_variant",
        help="Stable baseline/improvement/ablation identity for this evidence series.",
    )
    group.addoption(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        dest="agent_harness_output_directory",
        help="Directory for one privacy-bounded JSON result per completed cell.",
    )
    group.addoption(
        "--source",
        type=Path,
        dest="agent_harness_source",
        help="External source for a case that explicitly requires one.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", _LIVE_MARKER)
    _single_model_option(config)
    config.stash[_INVOCATION_BUDGET_KEY] = _InvocationBudgetState()


@dataclass
class _InvocationBudgetState:
    invocation_id: str = field(default_factory=lambda: uuid4().hex)
    reported_subject_tokens: int = 0
    halted_reason: str | None = None

    def observe(self, run: BenchmarkRun) -> None:
        budget = run.result.budget
        self.reported_subject_tokens = budget.invocation_reported_subject_tokens
        if not run.persisted:
            self.halted_reason = "benchmark_result_not_persisted"
        elif budget.status in {
            BenchmarkBudgetStatus.EXCEEDED,
            BenchmarkBudgetStatus.UNVERIFIABLE,
        }:
            self.halted_reason = budget.exhaustion_reason or "benchmark_budget_halted"
        elif run.result.run_status is not BenchmarkRunStatus.COMPLETED:
            self.halted_reason = run.result.failure_kind or "benchmark_execution_halted"
        elif not run.result.integrity_passed:
            self.halted_reason = "benchmark_integrity_invalid"
        elif (
            self.reported_subject_tokens
            >= DEFAULT_BUDGET_POLICY.max_reported_invocation_subject_tokens
        ):
            self.halted_reason = "invocation_token_limit_reached"


@dataclass(frozen=True)
class AgentHarnessBenchmarkController:
    """The deliberately small interface exposed to every benchmark case."""

    config: Config

    def require_source(self) -> Path:
        source = self.config.getoption("agent_harness_source")
        if source is None:
            pytest.skip("this benchmark case requires --source PATH")
        return Path(source)

    def run(self, case: BenchmarkCase) -> BenchmarkRun:
        """Run exactly one model/case cell and fail for infrastructure faults."""

        invocation = self.config.stash[_INVOCATION_BUDGET_KEY]
        if invocation.halted_reason is not None:
            pytest.skip(f"Agent Harness invocation halted ({invocation.halted_reason})")
        try:
            run = run_benchmark(
                settings_path=_path_option(self.config, "agent_harness_llm_settings"),
                embedding_settings_path=_path_option(
                    self.config,
                    "agent_harness_embedding_settings",
                ),
                case=case,
                execution_mode=(
                    BenchmarkExecutionMode.HEADED
                    if self.config.getoption("agent_harness_headed")
                    else BenchmarkExecutionMode.HEADLESS
                ),
                output_directory=Path(
                    self.config.getoption("agent_harness_output_directory")
                ),
                requested_model=_single_model_option(self.config),
                judge_settings_path=_path_option(
                    self.config,
                    "agent_harness_judge_llm_settings",
                ),
                judge_model_key=self.config.getoption("agent_harness_judge_model"),
                budget_policy=DEFAULT_BUDGET_POLICY,
                harness_variant=self.config.getoption("agent_harness_variant"),
                invocation_reported_subject_tokens=invocation.reported_subject_tokens,
                invocation_id=invocation.invocation_id,
            )
        except BaseException:
            invocation.halted_reason = "benchmark_runner_exception"
            raise
        invocation.observe(run)
        self._report(run)

        failure = _infrastructure_failure(run)
        if failure is not None:
            pytest.fail(failure)
        return run

    def _report(self, run: BenchmarkRun) -> None:
        result = run.result
        usage = result.subject_metrics.token_usage
        token_total = usage.total_tokens if usage is not None else None
        seconds = result.subject_metrics.turn_seconds
        summary = " ".join(
            (
                "agent-harness-benchmark:",
                f"case={result.case_id}",
                f"model={result.provider_model}",
                f"mode={result.execution_mode.value}",
                f"run={result.run_status.value}",
                f"semantic={result.semantic_verdict.value}",
                f"integrity={result.integrity_passed}",
                f"judge={result.judge.status.value}",
                f"budget={result.budget.status.value}",
                f"rounds={result.budget.sampling_rounds_admitted}",
                f"tokens={token_total if token_total is not None else 'unreported'}",
                f"invocation_tokens={result.budget.invocation_reported_subject_tokens}",
                f"seconds={seconds:.3f}" if seconds is not None else "seconds=unreported",
                f"persisted={run.persisted}",
                f"trace_id={result.trace.trace_id if result.trace is not None else 'unavailable'}",
                f"report={run.output_path if run.output_path is not None else 'unavailable'}",
            )
        )
        terminal_reporter = self.config.pluginmanager.getplugin("terminalreporter")
        if terminal_reporter is not None:
            terminal_reporter.write_line(summary)


@pytest.fixture
def agent_harness_benchmark(request: FixtureRequest) -> AgentHarnessBenchmarkController:
    """Gate paid execution until a caller gives the explicit live switch."""

    config = request.config
    if not config.getoption("agent_harness_live"):
        pytest.skip("pass --run-agent-harness to execute real-provider benchmark cells")
    return AgentHarnessBenchmarkController(config=config)


def _path_option(config: Config, option_name: str) -> Path | None:
    value = config.getoption(option_name)
    return Path(value) if value is not None else None


def _infrastructure_failure(run: BenchmarkRun) -> str | None:
    if not run.persisted:
        return "Agent Harness benchmark could not persist its measurement"
    if run.result.run_status is not BenchmarkRunStatus.COMPLETED:
        return (
            "Agent Harness benchmark execution failed "
            f"({run.result.provider_model}:{run.result.run_status.value})"
        )
    return None


def _single_model_option(config: Config) -> str | None:
    values = tuple(
        value.strip()
        for value in config.getoption("agent_harness_models")
        if isinstance(value, str) and value.strip()
    )
    if len(values) > 1:
        raise pytest.UsageError("--model may be supplied at most once")
    if values and "," in values[0]:
        raise pytest.UsageError("--model accepts one provider/model key")
    return values[0] if values else None
