"""Small, privacy-safe result contracts for Agent Harness benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BenchmarkRunStatus(StrEnum):
    COMPLETED = "completed"
    INVALID_SETUP = "invalid_setup"
    RUNTIME_ERROR = "runtime_error"
    MEASUREMENT_ERROR = "measurement_error"


@dataclass(frozen=True)
class OutcomeCheck:
    name: str
    passed: bool
    summary: str

    def to_payload(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "summary": self.summary}


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int

    def to_payload(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class BenchmarkMetrics:
    turn_seconds: float | None = None
    oracle_seconds: float | None = None
    sampling_round_count: int = 0
    usage_reported_primary_response_count: int | None = None
    token_usage: TokenUsage | None = None
    message_counts: dict[str, int] = field(default_factory=dict)
    tool_call_counts_by_name: dict[str, int] = field(default_factory=dict)
    tool_result_counts_by_status: dict[str, int] = field(default_factory=dict)
    provider_retry_count: int = 0
    derived_dataset_count: int = 0
    terminal_shape: tuple[int, int] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "turn_seconds": self.turn_seconds,
            "oracle_seconds": self.oracle_seconds,
            "sampling_round_count": self.sampling_round_count,
            "usage_reported_primary_response_count": self.usage_reported_primary_response_count,
            "token_usage": self.token_usage.to_payload() if self.token_usage is not None else None,
            "message_counts": dict(sorted(self.message_counts.items())),
            "tool_call_counts_by_name": dict(sorted(self.tool_call_counts_by_name.items())),
            "tool_result_counts_by_status": dict(sorted(self.tool_result_counts_by_status.items())),
            "provider_retry_count": self.provider_retry_count,
            "derived_dataset_count": self.derived_dataset_count,
            "terminal_shape": list(self.terminal_shape) if self.terminal_shape is not None else None,
        }


@dataclass(frozen=True)
class BenchmarkIdentity:
    fixture_sha256: str | None = None
    settings_sha256: str | None = None
    repository_commit: str | None = None
    repository_dirty: bool | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "fixture_sha256": self.fixture_sha256,
            "settings_sha256": self.settings_sha256,
            "repository_commit": self.repository_commit,
            "repository_dirty": self.repository_dirty,
        }


@dataclass(frozen=True)
class AgentHarnessBenchmarkResult:
    case_id: str
    run_id: str
    provider_model: str
    run_status: BenchmarkRunStatus
    metrics: BenchmarkMetrics
    outcome_checks: tuple[OutcomeCheck, ...] = ()
    identity: BenchmarkIdentity = field(default_factory=BenchmarkIdentity)
    failure_kind: str | None = None
    schema_version: int = 1

    @property
    def outcome_passed(self) -> bool:
        return bool(self.outcome_checks) and all(check.passed for check in self.outcome_checks)

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "provider_model": self.provider_model,
            "run_status": self.run_status.value,
            "outcome_passed": self.outcome_passed,
            "outcome_checks": [check.to_payload() for check in self.outcome_checks],
            "metrics": self.metrics.to_payload(),
            "identity": self.identity.to_payload(),
            "failure_kind": self.failure_kind,
        }
