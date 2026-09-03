"""Classify Harness turn events without depending on Qt or service execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...services.agent.harness_service import AgentHarnessStreamEvent


class TurnAction(Enum):
    IGNORE = "ignore"
    ATTACHMENT = "attachment"
    TITLE = "title"
    SNAPSHOT = "snapshot"
    FINAL_SNAPSHOT = "final_snapshot"
    LIVE_EVENT = "live_event"


class FailureRecovery(Enum):
    IGNORE = "ignore"
    PRESERVE_COMPOSER = "preserve_composer"
    RESTORE_SNAPSHOT = "restore_snapshot"


class StopDisposition(Enum):
    PREPARING = "preparing"
    NO_THREAD = "no_thread"
    PAUSE = "pause"


@dataclass(frozen=True)
class TurnUpdate:
    action: TurnAction
    acknowledge_composer: bool = False
    attachment_index: int | None = None
    activate_running: bool = False


@dataclass
class _PendingSubmission:
    submission_id: str
    attachment_count: int
    acknowledged: bool = False


class ConversationTurnController:
    """Own the UI-local turn gate and classify one Harness event at a time."""

    def __init__(self) -> None:
        self._thread_id: str | None = None
        self._pending: _PendingSubmission | None = None
        self._active_submission_id: str | None = None
        self._active_pending_message_id: str | None = None
        self._paused_thread_ids: set[str] = set()
        self._closed = False

    @property
    def thread_id(self) -> str | None:
        return self._thread_id

    @property
    def busy(self) -> bool:
        return self._pending is not None or self._active_pending_message_id is not None

    @property
    def active_submission_id(self) -> str | None:
        return self._active_submission_id

    def begin(self, submission_id: str, attachment_count: int) -> bool:
        if attachment_count < 0:
            raise ValueError("attachment_count must not be negative")
        if self._closed or self.busy:
            return False
        self._pending = _PendingSubmission(submission_id, attachment_count)
        self._active_submission_id = submission_id
        if self._thread_id is not None:
            self._paused_thread_ids.discard(self._thread_id)
        return True

    def select_thread(self, thread_id: str | None) -> None:
        if self._closed:
            return
        self._thread_id = thread_id
        self._clear_active_turn()

    def route(self, event: AgentHarnessStreamEvent) -> TurnUpdate:
        if self._closed or not self._event_belongs_to_current_stream(event):
            return TurnUpdate(TurnAction.IGNORE)
        kind = event.kind
        event_thread_id = event.thread_id
        is_final = event.is_final
        if event_thread_id in self._paused_thread_ids and not (kind == "snapshot" and is_final):
            return TurnUpdate(TurnAction.IGNORE)
        if kind == "attachment_import":
            return self._route_attachment(event)
        if kind == "title" and event.snapshot is not None:
            return TurnUpdate(TurnAction.TITLE)
        if kind == "snapshot" and event.snapshot is not None:
            return self._route_snapshot(event)
        if kind in {"chatbot_event", "thinking", "activity", "connection"} and event.chatbot_event is not None:
            pending_message_id = event.pending_message_id
            if pending_message_id is not None:
                self._active_pending_message_id = pending_message_id
                self._pending = None
            return TurnUpdate(TurnAction.LIVE_EVENT, activate_running=pending_message_id is not None)
        return TurnUpdate(TurnAction.IGNORE)

    def fail(self, submission_id: str) -> FailureRecovery:
        if self._closed or submission_id != self._active_submission_id:
            return FailureRecovery.IGNORE
        pending = self._pending
        recovery = (
            FailureRecovery.PRESERVE_COMPOSER
            if pending is not None and not pending.acknowledged
            else FailureRecovery.RESTORE_SNAPSHOT
        )
        self._clear_active_turn()
        return recovery

    def stop_disposition(self) -> StopDisposition:
        if self._closed:
            return StopDisposition.NO_THREAD
        if self._pending is not None and self._active_pending_message_id is None:
            return StopDisposition.PREPARING
        if self._thread_id is None:
            return StopDisposition.NO_THREAD
        return StopDisposition.PAUSE

    def mark_paused(self, thread_id: str) -> None:
        if not self._closed:
            self._paused_thread_ids.add(thread_id)

    def shutdown(self) -> None:
        self._closed = True
        self._clear_active_turn()

    def _event_belongs_to_current_stream(self, event: AgentHarnessStreamEvent) -> bool:
        submission_id = event.client_submission_id
        if submission_id is not None:
            return submission_id == self._active_submission_id
        event_thread_id = event.thread_id
        return event_thread_id is None or event_thread_id == self._thread_id

    def _route_attachment(self, event: AgentHarnessStreamEvent) -> TurnUpdate:
        pending = self._pending
        if pending is None or event.client_submission_id != pending.submission_id:
            return TurnUpdate(TurnAction.IGNORE)
        progress = event.attachment_import
        if progress is None or not 0 <= progress.source_index < pending.attachment_count:
            return TurnUpdate(TurnAction.IGNORE)
        return TurnUpdate(TurnAction.ATTACHMENT, attachment_index=progress.source_index)

    def _route_snapshot(self, event: AgentHarnessStreamEvent) -> TurnUpdate:
        snapshot = event.snapshot
        assert snapshot is not None
        thread_id = snapshot.thread.id
        self._thread_id = thread_id
        if event.is_final:
            self._clear_active_turn()
            self._paused_thread_ids.discard(thread_id)
            return TurnUpdate(TurnAction.FINAL_SNAPSHOT)
        acknowledged = False
        pending = self._pending
        if pending is not None and event.client_submission_id == pending.submission_id and not pending.acknowledged:
            pending.acknowledged = True
            acknowledged = True
        self._active_pending_message_id = event.pending_message_id
        self._paused_thread_ids.discard(thread_id)
        return TurnUpdate(TurnAction.SNAPSHOT, acknowledge_composer=acknowledged)

    def _clear_active_turn(self) -> None:
        self._pending = None
        self._active_submission_id = None
        self._active_pending_message_id = None
