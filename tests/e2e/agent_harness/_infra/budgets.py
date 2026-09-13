"""Cost accounting and external resource limits for live benchmark cells.

Sampling rounds, provider attempts and response tokens are measurements;
production Harness and LLM settings own their execution. Invocation cost gates
the next cell, and wall time is bounded by the benchmark's isolated process.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import multiprocessing
import os
from pathlib import Path
import pickle
import signal
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Callable, ClassVar, Mapping


class BenchmarkBudgetStatus(StrEnum):
    WITHIN_LIMITS = "within_limits"
    EXCEEDED = "exceeded"
    UNVERIFIABLE = "unverifiable"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class BenchmarkBudgetPolicy:
    """External cost and time limits, separate from production execution."""

    HARD_MAX_WALL_SECONDS: ClassVar[float] = 900.0
    HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS: ClassVar[int] = 4_000_000

    policy_id: str = "agent-harness-budget-v2"
    max_wall_seconds: float = HARD_MAX_WALL_SECONDS
    max_reported_invocation_subject_tokens: int = (
        HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS
    )

    def __post_init__(self) -> None:
        _bounded_positive_number(
            "max_wall_seconds",
            self.max_wall_seconds,
            self.HARD_MAX_WALL_SECONDS,
        )
        _bounded_positive_int(
            "max_reported_invocation_subject_tokens",
            self.max_reported_invocation_subject_tokens,
            self.HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS,
        )
        if not self.policy_id.strip() or len(self.policy_id) > 96:
            raise ValueError("budget_policy_id_invalid")

    def to_payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "max_wall_seconds": self.max_wall_seconds,
            "max_reported_invocation_subject_tokens": (
                self.max_reported_invocation_subject_tokens
            ),
            "execution_limits": "production_harness_and_llm_settings",
            "token_enforcement": "next_cell_admission",
        }


@dataclass(frozen=True)
class BenchmarkBudgetSnapshot:
    status: BenchmarkBudgetStatus
    policy: BenchmarkBudgetPolicy
    sampling_rounds_admitted: int = 0
    provider_attempts_dispatched: int = 0
    reported_subject_tokens: int = 0
    invocation_reported_subject_tokens: int = 0
    exhaustion_reason: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "policy": self.policy.to_payload(),
            "sampling_rounds_admitted": self.sampling_rounds_admitted,
            "provider_attempts_dispatched": self.provider_attempts_dispatched,
            "reported_subject_tokens": self.reported_subject_tokens,
            "invocation_reported_subject_tokens": (
                self.invocation_reported_subject_tokens
            ),
            "exhaustion_reason": self.exhaustion_reason,
        }


class BenchmarkBudgetController:
    """Observe Subject usage without changing production provider admission."""

    def __init__(self, policy: BenchmarkBudgetPolicy) -> None:
        self._policy = policy
        self._sampling_rounds = 0
        self._provider_attempts = 0
        self._reported_subject_tokens = 0
        self._status = BenchmarkBudgetStatus.WITHIN_LIMITS
        self._exhaustion_reason: str | None = None

    def begin_sampling_round(self) -> None:
        self._sampling_rounds += 1

    def observe_provider_attempt(self) -> None:
        self._provider_attempts += 1

    def observe_subject_response(self, total_tokens: int | None) -> None:
        if total_tokens is None:
            self._mark_usage_unavailable("subject_usage_unreported")
            return
        if isinstance(total_tokens, bool) or not isinstance(total_tokens, int) or total_tokens < 0:
            self._mark_usage_unavailable("subject_usage_invalid")
            return
        self._reported_subject_tokens += total_tokens

    def snapshot(self) -> BenchmarkBudgetSnapshot:
        return BenchmarkBudgetSnapshot(
            status=self._status,
            policy=self._policy,
            sampling_rounds_admitted=self._sampling_rounds,
            provider_attempts_dispatched=self._provider_attempts,
            reported_subject_tokens=self._reported_subject_tokens,
            exhaustion_reason=self._exhaustion_reason,
        )

    def _mark_usage_unavailable(self, reason: str) -> None:
        if self._status is BenchmarkBudgetStatus.WITHIN_LIMITS:
            self._status = BenchmarkBudgetStatus.UNVERIFIABLE
            self._exhaustion_reason = reason


class IsolatedCallStatus(StrEnum):
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    CRASHED = "crashed"


@dataclass(frozen=True)
class IsolatedCallOutcome:
    status: IsolatedCallStatus
    value: Any | None = None
    failure_kind: str | None = None
    exit_code: int | None = None


def run_isolated_call(
    target: Callable[..., Any],
    arguments: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> IsolatedCallOutcome:
    """Run one picklable call in a spawn child with a hard wall deadline."""

    if timeout_seconds <= 0:
        raise ValueError("isolated_call_timeout_invalid")
    context = multiprocessing.get_context("spawn")
    # A child sending a large report through a Pipe cannot exit until the
    # parent drains it. A temporary result file lets join enforce the process
    # deadline without a pipe-capacity deadlock or a blocking recv afterwards.
    with TemporaryDirectory(prefix="xenix-isolated-result-") as temporary:
        result_path = Path(temporary) / "result.pickle"
        process = context.Process(
            target=_isolated_call_entry,
            args=(result_path, target, dict(arguments)),
            daemon=False,
        )
        try:
            process.start()
            process.join(timeout_seconds)
            if process.is_alive():
                _terminate_process_tree(process)
                return IsolatedCallOutcome(
                    status=IsolatedCallStatus.TIMED_OUT,
                    failure_kind="process_wall_time_exceeded",
                    exit_code=process.exitcode,
                )
            try:
                with result_path.open("rb") as handle:
                    kind, payload = pickle.load(handle)
            except (EOFError, OSError, pickle.UnpicklingError):
                return IsolatedCallOutcome(
                    status=IsolatedCallStatus.CRASHED,
                    failure_kind="child_process_no_result",
                    exit_code=process.exitcode,
                )
            if kind == "completed":
                return IsolatedCallOutcome(
                    status=IsolatedCallStatus.COMPLETED,
                    value=payload,
                    exit_code=process.exitcode,
                )
            return IsolatedCallOutcome(
                status=IsolatedCallStatus.CRASHED,
                failure_kind=str(payload or "child_process_failed")[:80],
                exit_code=process.exitcode,
            )
        finally:
            if process.is_alive():
                _terminate_process_tree(process)
            process.close()


def _isolated_call_entry(
    result_path: Path,
    target: Callable[..., Any],
    arguments: dict[str, Any],
) -> None:
    if os.name != "nt":
        os.setsid()
    try:
        value = target(**arguments)
    except BaseException as exc:
        result = ("failed", _safe_exception_kind(exc))
    else:
        result = ("completed", value)
    with result_path.open("wb") as handle:
        pickle.dump(result, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _terminate_process_tree(process: multiprocessing.Process) -> None:
    pid = process.pid
    if pid is None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            process.terminate()
    process.join(5.0)
    if process.is_alive():
        process.kill()
        process.join(5.0)


def _safe_exception_kind(exc: BaseException) -> str:
    for attribute in ("code", "error_code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
    return (exc.__class__.__name__ or "child_process_failed")[:80]


def _bounded_positive_int(label: str, value: object, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= maximum:
        raise ValueError(f"{label}_invalid")


def _bounded_positive_number(label: str, value: object, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= maximum:
        raise ValueError(f"{label}_invalid")
