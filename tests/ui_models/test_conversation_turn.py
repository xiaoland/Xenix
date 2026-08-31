from __future__ import annotations

from types import SimpleNamespace

from xenix.services.agent import AgentHarnessStreamEvent, AttachmentImportProgress, AttachmentImportStatus
from xenix.ui.conversation.turn_controller import (
    ConversationTurnController,
    FailureRecovery,
    StopDisposition,
    TurnAction,
)


def _snapshot(thread_id: str) -> object:
    return SimpleNamespace(thread=SimpleNamespace(id=thread_id))


def _event(**values: object) -> AgentHarnessStreamEvent:
    return AgentHarnessStreamEvent(**values)


def test_matching_append_acknowledges_once_and_final_unlocks_turn() -> None:
    controller = ConversationTurnController()
    assert controller.begin("generation-1", attachment_count=2)
    append = _event(
        kind="snapshot",
        thread_id="thread-1",
        client_submission_id="generation-1",
        pending_message_id="pending-1",
        snapshot=_snapshot("thread-1"),
    )
    assert controller.route(append).acknowledge_composer is True
    assert controller.route(append).acknowledge_composer is False
    assert controller.busy is True
    final = _event(
        kind="snapshot",
        thread_id="thread-1",
        client_submission_id="generation-1",
        snapshot=_snapshot("thread-1"),
        is_final=True,
    )
    assert controller.route(final).action is TurnAction.FINAL_SNAPSHOT
    assert controller.busy is False
    assert controller.active_submission_id is None


def test_attachment_index_is_bounded_by_pending_submission() -> None:
    controller = ConversationTurnController()
    assert controller.begin("generation-1", attachment_count=1)
    valid = _event(
        kind="attachment_import",
        client_submission_id="generation-1",
        attachment_import=AttachmentImportProgress(0, AttachmentImportStatus.PENDING),
    )
    invalid = _event(
        kind="attachment_import",
        client_submission_id="generation-1",
        attachment_import=AttachmentImportProgress(1, AttachmentImportStatus.FAILED),
    )
    assert controller.route(valid).attachment_index == 0
    assert controller.route(invalid).action is TurnAction.IGNORE


def test_old_generation_failure_and_event_cannot_disturb_new_turn() -> None:
    controller = ConversationTurnController()
    assert controller.begin("old", attachment_count=0)
    controller.select_thread("thread-1")
    assert controller.begin("new", attachment_count=0)
    assert controller.fail("old") is FailureRecovery.IGNORE
    old_final = _event(kind="snapshot", client_submission_id="old", snapshot=_snapshot("thread-1"), is_final=True)
    assert controller.route(old_final).action is TurnAction.IGNORE
    assert controller.active_submission_id == "new"


def test_pause_allows_only_matching_final_snapshot() -> None:
    controller = ConversationTurnController()
    controller.select_thread("thread-1")
    assert controller.begin("generation-1", attachment_count=0)
    controller.mark_paused("thread-1")
    live = _event(kind="thinking", thread_id="thread-1", client_submission_id="generation-1", chatbot_event=object())
    final = _event(
        kind="snapshot",
        thread_id="thread-1",
        client_submission_id="generation-1",
        snapshot=_snapshot("thread-1"),
        is_final=True,
    )
    assert controller.route(live).action is TurnAction.IGNORE
    assert controller.route(final).action is TurnAction.FINAL_SNAPSHOT


def test_failure_stop_and_shutdown_gates() -> None:
    controller = ConversationTurnController()
    assert controller.stop_disposition() is StopDisposition.NO_THREAD
    controller.select_thread("thread-1")
    assert controller.begin("generation-1", attachment_count=0)
    assert controller.stop_disposition() is StopDisposition.PREPARING
    assert controller.fail("generation-1") is FailureRecovery.PRESERVE_COMPOSER
    assert controller.begin("generation-2", attachment_count=0)
    acknowledged = _event(
        kind="snapshot",
        thread_id="thread-1",
        client_submission_id="generation-2",
        pending_message_id="pending-2",
        snapshot=_snapshot("thread-1"),
    )
    controller.route(acknowledged)
    assert controller.stop_disposition() is StopDisposition.PAUSE
    assert controller.fail("generation-2") is FailureRecovery.RESTORE_SNAPSHOT
    controller.shutdown()
    assert controller.begin("generation-3", attachment_count=0) is False
    assert controller.fail("generation-3") is FailureRecovery.IGNORE
