from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from tests.ui.pytest_plugin import UiArtifactRegistry
from xenix.services.agent import (
    AgentHarnessStreamEvent,
    AttachmentImportProgress,
    AttachmentImportStatus,
    SubmitUserTurnInput,
)
from xenix.ui.chatbot import ComposerAttachmentStatus
from xenix.services.agent.chatbot_events import (
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
    build_thinking_chatbot_event,
)
from xenix.ui.main_window import MainWindow
from xenix.ui.history import HarnessHistoryAdapter
from xenix.ui.windows.auxiliary import AuxiliaryWindowCoordinator


@dataclass
class _RecordedSubmission:
    submission: SubmitUserTurnInput
    on_event: Callable[[AgentHarnessStreamEvent], None]
    on_failure: Callable[[str, Exception], None]


class _ControlledExecutor:
    def __init__(self) -> None:
        self.submissions: list[_RecordedSubmission] = []
        self.shutdown_calls = 0

    def start(self, submission, *, on_event, on_failure) -> None:
        self.submissions.append(_RecordedSubmission(submission, on_event, on_failure))

    def shutdown(self) -> None:
        self.shutdown_calls += 1


class _Harness:
    def __init__(self) -> None:
        self.threads = [_thread("thread-a", "Thread A"), _thread("thread-b", "Thread B")]
        self.snapshots = {
            thread.id: _snapshot(thread.id, thread.title, [_text_event(f"{thread.id}:stable", "stable")])
            for thread in self.threads
        }
        self.pause_thread = Mock()
        self.get_thread_snapshot = Mock(side_effect=lambda thread_id: self.snapshots[thread_id])
        self.project_chatbot_events = Mock(side_effect=lambda snapshot: list(snapshot.events))

    def list_threads(self):
        return self.threads


def _thread(thread_id: str, title: str) -> SimpleNamespace:
    return SimpleNamespace(id=thread_id, title=title, selected_fq_model_key=None)


def _snapshot(thread_id: str, title: str, events: list[ChatbotEvent] | None = None) -> SimpleNamespace:
    return SimpleNamespace(thread=_thread(thread_id, title), messages=[], events=events or [])


def _text_event(event_id: str, text: str) -> ChatbotEvent:
    return ChatbotEvent(
        id=event_id,
        kind=ChatbotEventKind.TEXT,
        author=ChatbotEventAuthor.ASSISTANT,
        status=ChatbotEventStatus.COMPLETED,
        text=text,
        content_blocks=[{"type": "text", "text": text}],
        source_message_ids=[event_id],
    )


def _window(qtbot: QtBot, ui_artifacts: UiArtifactRegistry, tmp_path):
    executor = _ControlledExecutor()
    harness = _Harness()
    llm = SimpleNamespace(model_options=lambda: [], default_fq_model_key=lambda: None)
    window = MainWindow(
        current_locale=lambda: "en_US",
        agent_harness_service=harness,
        llm_service=llm,
        artifact_service=SimpleNamespace(resolve_uri=lambda _uri: None),
        link_router=Mock(),
        history_port=HarnessHistoryAdapter(harness),
        auxiliary_factory=lambda owner: AuxiliaryWindowCoordinator(
            owner, settings_factory=Mock(), knowledge_factory=None, detail_factory=Mock(),
        ),
        conversation_executor=executor,
    )
    qtbot.addWidget(window)
    ui_artifacts.register(window, name="main-window-conversation")
    window.show()
    return window, harness, executor


def _submit(view, text: str, attachment: Path | None = None) -> None:
    paths: list[str] = []
    if attachment is not None:
        attachment.write_text("a,b\n1,2\n", encoding="utf-8")
        view._add_local_files([str(attachment)])
        paths = [str(attachment.resolve())]
    view._editor.setPlainText(text)
    view.message_submitted.emit(text, paths, "")


def test_pre_ack_failure_preserves_composer_for_retry(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    attachment = tmp_path / "input.csv"

    _submit(view, "Retry this", attachment)
    recorded = executor.submissions[0]
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="attachment_import",
            client_submission_id=recorded.submission.client_submission_id,
            attachment_import=AttachmentImportProgress(0, AttachmentImportStatus.FAILED),
        )
    )
    recorded.on_failure(recorded.submission.client_submission_id, RuntimeError("import failed"))

    assert view._editor.toPlainText() == "Retry this"
    assert view._attached_files == [str(attachment.resolve())]
    assert view._attachment_states[str(attachment.resolve())].status is ComposerAttachmentStatus.FAILED
    assert view._editor.isEnabled()
    assert window.conversation_idle


def test_acknowledged_failure_reloads_canonical_without_restoring_input(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    attachment = tmp_path / "input.csv"
    _submit(view, "Committed", attachment)
    recorded = executor.submissions[0]
    appended = _snapshot("thread-a", "Thread A", [_text_event("append", "Committed")])
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=recorded.submission.client_submission_id,
            snapshot=appended,
        )
    )
    recorded.on_failure(recorded.submission.client_submission_id, RuntimeError("sampling failed"))

    assert view._editor.toPlainText() == ""
    assert view._attached_files == []
    assert harness.get_thread_snapshot.call_args.args == ("thread-a",)
    assert "thread-a:stable" in view._message_bubbles_by_id
    assert "append" not in view._message_bubbles_by_id
    assert window.conversation_idle


def test_history_switch_clears_preparing_turn_and_old_callbacks_cannot_mutate_new_view(
    qtbot: QtBot, ui_artifacts, tmp_path
) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Old turn")
    old = executor.submissions[0]

    window._history_panel.open_thread("thread-b")
    assert window.conversation_thread_id == "thread-b"
    assert window.conversation_idle
    assert view._editor.isEnabled()

    _submit(view, "New turn")
    new = executor.submissions[1]
    harness.get_thread_snapshot.reset_mock()
    old.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=old.submission.client_submission_id,
            snapshot=_snapshot("thread-a", "Thread A", [_text_event("old", "OLD")]),
            is_final=True,
        )
    )
    old.on_failure(old.submission.client_submission_id, RuntimeError("old failure"))

    assert window.conversation_thread_id == "thread-b"
    assert len(executor.submissions) == 2
    assert not window.conversation_idle
    assert view._editor.toPlainText() == "New turn"
    assert new.submission.thread_id == "thread-b"
    assert harness.get_thread_snapshot.call_count == 0


def test_stop_ignores_live_callbacks_but_final_snapshot_unlocks_composer(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Stop after append")
    recorded = executor.submissions[0]
    submission_id = recorded.submission.client_submission_id
    appended = _snapshot("thread-a", "Thread A", [_text_event("append", "Stop after append")])
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=submission_id,
            snapshot=appended,
        )
    )
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="thinking",
            thread_id="thread-a",
            client_submission_id=submission_id,
            pending_message_id="pending",
            chatbot_event=build_thinking_chatbot_event(
                pending_message_id="pending",
                status=ChatbotEventStatus.IN_PROGRESS,
            ),
        )
    )
    view.stop_requested.emit()
    harness.pause_thread.assert_called_once_with("thread-a")
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="thinking",
            thread_id="thread-a",
            client_submission_id=submission_id,
            pending_message_id="pending",
            chatbot_event=build_thinking_chatbot_event(
                pending_message_id="pending",
                status=ChatbotEventStatus.IN_PROGRESS,
            ),
        )
    )
    assert not view._running

    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=submission_id,
            snapshot=_snapshot("thread-a", "Thread A", [_text_event("final", "Final")]),
            is_final=True,
        )
    )
    assert window.conversation_idle
    assert view._editor.isEnabled()
    assert not view._running
    assert "final" in view._message_bubbles_by_id


def test_ack_then_direct_final_snapshot_unlocks_composer(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "No live event")
    recorded = executor.submissions[0]
    submission_id = recorded.submission.client_submission_id
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=submission_id,
            snapshot=_snapshot("thread-a", "Thread A", [_text_event("append", "No live event")]),
        )
    )
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=submission_id,
            snapshot=_snapshot("thread-a", "Thread A", [_text_event("final", "Done")]),
            is_final=True,
        )
    )

    assert window.conversation_idle
    assert view._editor.isEnabled()
    assert not view._running


def test_close_shuts_executor_and_late_callbacks_do_not_change_view(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Closing")
    recorded = executor.submissions[0]
    rendered_ids = set(view._message_bubbles_by_id)
    window.close()
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id="thread-a",
            client_submission_id=recorded.submission.client_submission_id,
            snapshot=_snapshot("thread-a", "Thread A", [_text_event("late", "late")]),
            is_final=True,
        )
    )
    recorded.on_failure(recorded.submission.client_submission_id, RuntimeError("late failure"))

    assert executor.shutdown_calls == 1
    assert view._editor.toPlainText() == "Closing"
    assert set(view._message_bubbles_by_id) == rendered_ids
    assert window.conversation_idle
