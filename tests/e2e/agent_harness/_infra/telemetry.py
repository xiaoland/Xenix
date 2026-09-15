"""Vendor-neutral lifecycle telemetry for one benchmark cell."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
import traceback
from typing import Any, Iterator
from uuid import uuid4


@dataclass(frozen=True)
class BenchmarkTraceEvent:
    """A completed span-like event persisted with the benchmark result."""

    name: str
    span_id: str
    parent_span_id: str | None
    started_offset_seconds: float
    duration_seconds: float
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)
    exception: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "started_offset_seconds": self.started_offset_seconds,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "attributes": self.attributes,
            "exception": self.exception,
        }


class BenchmarkTrace:
    """Small in-report trace recorder independent of exporter configuration."""

    def __init__(self, trace_id: str, journal_path: Path | None = None) -> None:
        self.trace_id = trace_id
        self._journal_path = journal_path
        self._started_at = time.perf_counter()
        self._events: list[BenchmarkTraceEvent] = []
        self._span_stack: list[str] = []

    @property
    def events(self) -> tuple[BenchmarkTraceEvent, ...]:
        return tuple(self._events)

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        span_id = uuid4().hex[:16]
        parent_span_id = self._span_stack[-1] if self._span_stack else None
        started_at = time.perf_counter()
        mutable_attributes = dict(attributes)
        self._span_stack.append(span_id)
        failure: dict[str, Any] | None = None
        try:
            yield mutable_attributes
        except BaseException as exc:
            failure = exception_payload(exc)
            raise
        finally:
            self._span_stack.pop()
            event = BenchmarkTraceEvent(
                name=name,
                span_id=span_id,
                parent_span_id=parent_span_id,
                started_offset_seconds=started_at - self._started_at,
                duration_seconds=time.perf_counter() - started_at,
                status="error" if failure is not None else "ok",
                attributes=mutable_attributes,
                exception=failure,
            )
            self._events.append(event)
            self._append_journal(event)

    def payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "events": [event.to_payload() for event in self._events],
        }

    def _append_journal(self, event: BenchmarkTraceEvent) -> None:
        if self._journal_path is None:
            return
        try:
            with self._journal_path.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps(event.to_payload(), ensure_ascii=False) + "\n")
        except OSError:
            # Export failure must not change the measured Agent outcome.
            pass


def load_trace_journal(path: Path) -> tuple[BenchmarkTraceEvent, ...]:
    """Recover phase evidence written before a timed-out child was terminated."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return ()
    events: list[BenchmarkTraceEvent] = []
    for line in lines:
        try:
            payload = json.loads(line)
            events.append(BenchmarkTraceEvent(**payload))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return tuple(events)


def exception_payload(exc: BaseException) -> dict[str, Any]:
    """Retain actionable exception context, including causes and stack frames."""

    chain: list[dict[str, Any]] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(
            {
                "type": f"{type(current).__module__}.{type(current).__qualname__}",
                "message": str(current),
                "stacktrace": "".join(
                    traceback.format_exception(type(current), current, current.__traceback__)
                ),
            }
        )
        current = current.__cause__ or current.__context__
    return {"chain": chain}
