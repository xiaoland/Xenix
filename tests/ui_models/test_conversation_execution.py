from __future__ import annotations

from collections.abc import Iterator
from threading import Event

import pytest

from xenix.services.agent import AgentHarnessStreamEvent, SubmitUserTurnInput
from xenix.ui.conversation.execution import ThreadedSubmissionExecutor


def _submission(generation: str = "generation-1") -> SubmitUserTurnInput:
    return SubmitUserTurnInput(text="Hello", client_submission_id=generation)


def test_threaded_executor_delivers_events_asynchronously() -> None:
    stream_started = Event()
    event_delivered = Event()
    received: list[AgentHarnessStreamEvent] = []
    expected = AgentHarnessStreamEvent(kind="thinking", client_submission_id="generation-1")

    def stream(_submission: SubmitUserTurnInput) -> Iterator[AgentHarnessStreamEvent]:
        stream_started.set()
        yield expected

    executor = ThreadedSubmissionExecutor(stream)
    executor.start(
        _submission(), on_event=lambda event: (received.append(event), event_delivered.set()), on_failure=pytest.fail
    )

    assert stream_started.wait(1)
    assert event_delivered.wait(1)
    assert received == [expected]


def test_threaded_executor_reports_failure_with_original_generation() -> None:
    failure_delivered = Event()
    failures: list[tuple[str, Exception]] = []

    def stream(_submission: SubmitUserTurnInput) -> Iterator[AgentHarnessStreamEvent]:
        raise RuntimeError("stream broke")
        yield  # pragma: no cover

    def on_failure(generation: str, failure: Exception) -> None:
        failures.append((generation, failure))
        failure_delivered.set()

    executor = ThreadedSubmissionExecutor(stream)
    executor.start(_submission("generation-42"), on_event=pytest.fail, on_failure=on_failure)

    assert failure_delivered.wait(1)
    assert failures[0][0] == "generation-42"
    assert isinstance(failures[0][1], RuntimeError)


def test_shutdown_suppresses_later_callbacks_and_rejects_new_work() -> None:
    stream_started = Event()
    allow_yield = Event()
    stream_finished = Event()
    callback_delivered = Event()

    def stream(_submission: SubmitUserTurnInput) -> Iterator[AgentHarnessStreamEvent]:
        stream_started.set()
        assert allow_yield.wait(1)
        try:
            yield AgentHarnessStreamEvent(kind="thinking", client_submission_id="generation-1")
        finally:
            stream_finished.set()

    executor = ThreadedSubmissionExecutor(stream)
    executor.start(_submission(), on_event=lambda _event: callback_delivered.set(), on_failure=pytest.fail)
    assert stream_started.wait(1)

    executor.shutdown()
    allow_yield.set()

    assert stream_finished.wait(1)
    assert not callback_delivered.is_set()
    with pytest.raises(RuntimeError, match="shut down"):
        executor.start(_submission("generation-2"), on_event=pytest.fail, on_failure=pytest.fail)
