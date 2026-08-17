"""Hard execution guards for paid Agent Harness benchmark cells.

Token limits are deliberately response-boundary stops: an admitted provider
response is counted atomically, then no later sampling round is admitted after
the limit is reached.  Sampling rounds and wall time remain hard pre-dispatch
and process boundaries respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import multiprocessing
from multiprocessing.connection import Connection
import os
import signal
import subprocess
from typing import Any, Callable, ClassVar, Mapping


class BenchmarkBudgetStatus(StrEnum):
    WITHIN_LIMITS = "within_limits"
    EXCEEDED = "exceeded"
    UNVERIFIABLE = "unverifiable"
    NOT_EVALUATED = "not_evaluated"


class BenchmarkBudgetError(RuntimeError):
    """A stable, privacy-safe refusal raised before another paid request."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BenchmarkBudgetPolicy:
    """One comparable benchmark series' non-expandable safety policy."""

    HARD_MAX_SAMPLING_ROUNDS: ClassVar[int] = 12
    HARD_MAX_WALL_SECONDS: ClassVar[float] = 900.0
    HARD_MAX_REPORTED_SUBJECT_TOKENS: ClassVar[int] = 500_000
    HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS: ClassVar[int] = 4_000_000
    HARD_MAX_PROVIDER_ATTEMPTS: ClassVar[int] = 2

    policy_id: str = "agent-harness-budget-v1"
    max_sampling_rounds: int = HARD_MAX_SAMPLING_ROUNDS
    max_wall_seconds: float = HARD_MAX_WALL_SECONDS
    max_reported_subject_tokens: int = HARD_MAX_REPORTED_SUBJECT_TOKENS
    max_reported_invocation_subject_tokens: int = (
        HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS
    )
    max_provider_attempts: int = HARD_MAX_PROVIDER_ATTEMPTS

    def __post_init__(self) -> None:
        _bounded_positive_int(
            "max_sampling_rounds",
            self.max_sampling_rounds,
            self.HARD_MAX_SAMPLING_ROUNDS,
        )
        _bounded_positive_number(
            "max_wall_seconds",
            self.max_wall_seconds,
            self.HARD_MAX_WALL_SECONDS,
        )
        _bounded_positive_int(
            "max_reported_subject_tokens",
            self.max_reported_subject_tokens,
            self.HARD_MAX_REPORTED_SUBJECT_TOKENS,
        )
        _bounded_positive_int(
            "max_reported_invocation_subject_tokens",
            self.max_reported_invocation_subject_tokens,
            self.HARD_MAX_REPORTED_INVOCATION_SUBJECT_TOKENS,
        )
        _bounded_positive_int(
            "max_provider_attempts",
            self.max_provider_attempts,
            self.HARD_MAX_PROVIDER_ATTEMPTS,
        )
        if not self.policy_id.strip() or len(self.policy_id) > 96:
            raise ValueError("budget_policy_id_invalid")

    def to_payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "max_sampling_rounds": self.max_sampling_rounds,
            "max_wall_seconds": self.max_wall_seconds,
            "max_reported_subject_tokens": self.max_reported_subject_tokens,
            "max_reported_invocation_subject_tokens": (
                self.max_reported_invocation_subject_tokens
            ),
            "max_provider_attempts": self.max_provider_attempts,
            "token_enforcement": "response_boundary",
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
    """Admit sampling rounds and count completed subject responses."""

    def __init__(self, policy: BenchmarkBudgetPolicy) -> None:
        self._policy = policy
        self._sampling_rounds = 0
        self._provider_attempts = 0
        self._provider_attempts_in_round = 0
        self._reported_subject_tokens = 0
        self._status = BenchmarkBudgetStatus.WITHIN_LIMITS
        self._exhaustion_reason: str | None = None

    @property
    def policy(self) -> BenchmarkBudgetPolicy:
        return self._policy

    def begin_sampling_round(self) -> None:
        self._raise_if_halted()
        if self._reported_subject_tokens >= self._policy.max_reported_subject_tokens:
            self._halt(
                BenchmarkBudgetStatus.EXCEEDED,
                "subject_token_limit_reached",
            )
            raise BenchmarkBudgetError("subject_token_limit_reached")
        if self._sampling_rounds >= self._policy.max_sampling_rounds:
            self._halt(
                BenchmarkBudgetStatus.EXCEEDED,
                "sampling_round_limit_exceeded",
            )
            raise BenchmarkBudgetError("sampling_round_limit_exceeded")
        self._sampling_rounds += 1
        self._provider_attempts_in_round = 0

    def admit_provider_attempt(self) -> None:
        self._raise_if_halted()
        if self._sampling_rounds < 1:
            self._halt(
                BenchmarkBudgetStatus.UNVERIFIABLE,
                "provider_attempt_without_sampling_round",
            )
            raise BenchmarkBudgetError("provider_attempt_without_sampling_round")
        if self._provider_attempts_in_round >= self._policy.max_provider_attempts:
            self._halt(
                BenchmarkBudgetStatus.EXCEEDED,
                "provider_attempt_limit_exceeded",
            )
            raise BenchmarkBudgetError("provider_attempt_limit_exceeded")
        self._provider_attempts += 1
        self._provider_attempts_in_round += 1

    def observe_subject_response(self, total_tokens: int | None) -> None:
        if total_tokens is None:
            self._halt(
                BenchmarkBudgetStatus.UNVERIFIABLE,
                "subject_usage_unreported",
            )
            return
        if isinstance(total_tokens, bool) or not isinstance(total_tokens, int) or total_tokens < 0:
            self._halt(
                BenchmarkBudgetStatus.UNVERIFIABLE,
                "subject_usage_invalid",
            )
            return
        self._reported_subject_tokens += total_tokens
        if self._reported_subject_tokens > self._policy.max_reported_subject_tokens:
            self._halt(
                BenchmarkBudgetStatus.EXCEEDED,
                "subject_token_limit_exceeded",
            )

    def snapshot(self) -> BenchmarkBudgetSnapshot:
        return BenchmarkBudgetSnapshot(
            status=self._status,
            policy=self._policy,
            sampling_rounds_admitted=self._sampling_rounds,
            provider_attempts_dispatched=self._provider_attempts,
            reported_subject_tokens=self._reported_subject_tokens,
            exhaustion_reason=self._exhaustion_reason,
        )

    def _raise_if_halted(self) -> None:
        if self._status is BenchmarkBudgetStatus.WITHIN_LIMITS:
            return
        raise BenchmarkBudgetError(self._exhaustion_reason or "benchmark_budget_halted")

    def _halt(self, status: BenchmarkBudgetStatus, reason: str) -> None:
        if self._status is BenchmarkBudgetStatus.WITHIN_LIMITS:
            self._status = status
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
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_isolated_call_entry,
        args=(sender, target, dict(arguments)),
        daemon=False,
    )
    try:
        process.start()
        sender.close()
        process.join(timeout_seconds)
        if process.is_alive():
            _terminate_process_tree(process)
            return IsolatedCallOutcome(
                status=IsolatedCallStatus.TIMED_OUT,
                failure_kind="process_wall_time_exceeded",
                exit_code=process.exitcode,
            )
        try:
            result_available = receiver.poll()
        except OSError:
            result_available = False
        if result_available:
            try:
                kind, payload = receiver.recv()
            except (EOFError, OSError):
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
        return IsolatedCallOutcome(
            status=IsolatedCallStatus.CRASHED,
            failure_kind="child_process_no_result",
            exit_code=process.exitcode,
        )
    finally:
        receiver.close()
        sender.close()
        if process.is_alive():
            _terminate_process_tree(process)
        process.close()


def _isolated_call_entry(
    sender: Connection,
    target: Callable[..., Any],
    arguments: dict[str, Any],
) -> None:
    if os.name != "nt":
        os.setsid()
    try:
        value = target(**arguments)
    except BaseException as exc:
        sender.send(("failed", _safe_exception_kind(exc)))
    else:
        sender.send(("completed", value))
    finally:
        sender.close()


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
