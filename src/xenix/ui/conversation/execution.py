"""Thread-backed execution boundary for one conversation submission."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from threading import Event, Thread
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ...services.agent.harness_service import AgentHarnessStreamEvent, SubmitUserTurnInput


class SubmissionExecutor(Protocol):
    """Starts a submission without exposing a concrete harness implementation."""

    def start(
        self,
        submission: SubmitUserTurnInput,
        *,
        on_event: Callable[[AgentHarnessStreamEvent], None],
        on_failure: Callable[[str, Exception], None],
    ) -> None:
        """Start a submission and report its events using its generation id."""

    def shutdown(self) -> None:
        """Prevent new work and suppress callbacks at later iterator boundaries."""


class ThreadedSubmissionExecutor:
    """Run an injected stream callable on a daemon thread.

    Shutdown does not join the worker or cancel I/O already in progress.  It
    prevents starting new work and suppresses callbacks once the worker reaches
    its next iterator/callback boundary.
    """

    def __init__(
        self,
        stream: Callable[[SubmitUserTurnInput], Iterable[AgentHarnessStreamEvent]],
    ) -> None:
        self._stream = stream
        self._shutdown_requested = Event()

    def start(
        self,
        submission: SubmitUserTurnInput,
        *,
        on_event: Callable[[AgentHarnessStreamEvent], None],
        on_failure: Callable[[str, Exception], None],
    ) -> None:
        generation = submission.client_submission_id
        if not generation:
            raise ValueError("submission.client_submission_id is required")
        if self._shutdown_requested.is_set():
            raise RuntimeError("submission executor is shut down")

        def run() -> None:
            try:
                if self._shutdown_requested.is_set():
                    return
                for event in self._stream(submission):
                    if self._shutdown_requested.is_set():
                        return
                    on_event(event)
            except Exception as exc:
                if not self._shutdown_requested.is_set():
                    on_failure(generation, exc)

        Thread(target=run, name="xenix-conversation-submission", daemon=True).start()

    def shutdown(self) -> None:
        self._shutdown_requested.set()
