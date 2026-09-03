from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e.agent_harness._infra.telemetry import BenchmarkTrace, load_trace_journal


def test_trace_records_phase_timing_attributes_and_exception_chain() -> None:
    trace = BenchmarkTrace("a" * 32)

    with pytest.raises(RuntimeError, match="outer"):
        with trace.span("benchmark.subject.execute", case_id="example") as attributes:
            attributes["progress"] = "provider_request"
            try:
                raise ValueError("provider detail")
            except ValueError as exc:
                raise RuntimeError("outer") from exc

    payload = trace.payload()
    event = payload["events"][0]
    assert payload["trace_id"] == "a" * 32
    assert event["status"] == "error"
    assert event["attributes"] == {
        "case_id": "example",
        "progress": "provider_request",
    }
    assert [item["type"] for item in event["exception"]["chain"]] == [
        "builtins.RuntimeError",
        "builtins.ValueError",
    ]
    assert "provider detail" in event["exception"]["chain"][1]["stacktrace"]
    json.dumps(payload)


def test_trace_uses_stack_parent_for_nested_events() -> None:
    trace = BenchmarkTrace("b" * 32)

    with trace.span("cell"):
        with trace.span("subject"):
            pass

    subject, cell = trace.events
    assert subject.parent_span_id == cell.span_id
    assert cell.parent_span_id is None


def test_trace_journal_recovers_completed_phases_and_skips_partial_line(tmp_path: Path) -> None:
    journal = tmp_path / "trace.jsonl"
    trace = BenchmarkTrace("c" * 32, journal)
    with trace.span("benchmark.cell.open"):
        pass
    with journal.open("a", encoding="utf-8") as stream:
        stream.write('{"partial":')

    recovered = load_trace_journal(journal)

    assert [event.name for event in recovered] == ["benchmark.cell.open"]
