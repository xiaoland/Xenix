from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QToolButton
from pytestqt.qtbot import QtBot

from tests.ui.pytest_plugin import UiArtifactRegistry
from xenix.exceptions import ValidationError
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
from xenix.services.agent.harness_service import MessageDraft, MessageDraftAttachment
from xenix.services.llm import FrozenLLMSettingsSource, LLMProviderConfig, LLMService, LLMSettings
from xenix.ui.main_window import MainWindow
from xenix.ui.conversation.message_editor import UserMessageEditor
from xenix.ui.conversation.shortcuts import ConversationShortcuts
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
        self.threads = [_thread(102, "Thread A"), _thread(101, "Thread B")]
        self.snapshots = {
            thread.id: _snapshot(thread.id, thread.title, [_text_event(thread.id + 1000, "stable")])
            for thread in self.threads
        }
        self.pause_thread = Mock()
        self.get_thread_snapshot = Mock(side_effect=lambda thread_id: self.snapshots[thread_id])
        self.project_chatbot_events = Mock(side_effect=lambda snapshot: list(snapshot.events))
        self.set_thread_model = Mock(side_effect=self._apply_thread_model)

    def _apply_thread_model(self, thread_id: int, fq_model_key: str):
        snapshot = self.snapshots[thread_id]
        snapshot.thread.selected_fq_model_key = fq_model_key
        return snapshot

    def list_threads(self):
        return self.threads


def _thread(thread_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(id=thread_id, title=title, selected_fq_model_key=None)


def _snapshot(thread_id: int, title: str, events: list[ChatbotEvent] | None = None) -> SimpleNamespace:
    return SimpleNamespace(thread=_thread(thread_id, title), messages=[], events=events or [])


def _text_event(event_id: int, text: str) -> ChatbotEvent:
    return ChatbotEvent(
        id=str(event_id),
        kind=ChatbotEventKind.TEXT,
        author=ChatbotEventAuthor.ASSISTANT,
        status=ChatbotEventStatus.COMPLETED,
        text=text,
        content_blocks=[{"type": "text", "text": text}],
        source_message_ids=[event_id],
    )


def _window(qtbot: QtBot, ui_artifacts: UiArtifactRegistry, tmp_path, *, llm_service=None):
    executor = _ControlledExecutor()
    harness = _Harness()
    llm = llm_service or SimpleNamespace(model_options=lambda: [], default_fq_model_key=lambda: None)
    window = MainWindow(
        current_locale=lambda: "en_US",
        agent_harness_service=harness,
        llm_service=llm,
        artifact_service=SimpleNamespace(resolve_uri=lambda _uri: None),
        link_router=Mock(),
        history_port=HarnessHistoryAdapter(harness),
        auxiliary_factory=lambda owner: AuxiliaryWindowCoordinator(
            owner, settings_factory=Mock(), knowledge_factory=None,
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
        view.composer.add_local_files([str(attachment)])
        paths = [str(attachment.resolve())]
    view.composer.editor.setPlainText(text)
    view.message_submitted.emit(text, paths, "")


def _snapshot_event(recorded, *, final: bool) -> AgentHarnessStreamEvent:
    return AgentHarnessStreamEvent(
        kind="snapshot", client_submission_id=recorded.submission.client_submission_id,
        thread_id=102, snapshot=_snapshot(102, "Thread A"), is_final=final,
    )


def test_composer_queues_and_prioritizes_steering_at_the_next_boundary(qtbot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    window._history_panel.open_thread(102)
    view = window._thread_detail_view
    _submit(view, "Active")
    active = executor.submissions[0]
    active.on_event(_snapshot_event(active, final=False))

    view.composer.editor.setPlainText("Ordinary follow-up")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return)
    view.composer.editor.setPlainText("Change direction")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert len(executor.submissions) == 1
    assert view.message_queue.isVisible()
    assert view.layout().indexOf(view.timeline) < view.layout().indexOf(view.message_queue) < view.layout().indexOf(view.composer)
    assert [row.text for row in view.message_queue._rows] == ["Change direction", "Ordinary follow-up"]
    active.on_event(_snapshot_event(active, final=True))
    steer = executor.submissions[1]
    assert steer.submission.text == "Change direction"
    steer.on_event(_snapshot_event(steer, final=True))
    followup = executor.submissions[2]
    assert followup.submission.text == "Ordinary follow-up"


def test_queued_message_uses_its_model_after_the_previous_request_fails(qtbot, ui_artifacts, tmp_path) -> None:
    settings = LLMSettings(
        providers=[LLMProviderConfig(key="custom", models=["broken", "working"])],
        default_fq_model_key="custom/broken",
    )
    window, _harness, executor = _window(
        qtbot, ui_artifacts, tmp_path, llm_service=LLMService(FrozenLLMSettingsSource(settings)),
    )
    window._history_panel.open_thread(102)
    view = window._thread_detail_view
    view.composer.editor.setPlainText("First request")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return)
    active = executor.submissions[0]
    assert active.submission.fq_model_key == "custom/broken"
    active.on_event(_snapshot_event(active, final=False))

    view.set_selected_fq_model_key("custom/working")
    view.composer.editor.setPlainText("Try the working model")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return)
    active.on_failure(active.submission.client_submission_id, ValidationError("Request failed"))

    assert len(executor.submissions) == 2
    queued = executor.submissions[1].submission
    assert queued.thread_id == 102
    assert queued.fq_model_key == "custom/working"
    assert queued.text == "Try the working model"


def test_chat_shortcuts_can_be_reassigned(qtbot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    window._history_panel.open_thread(102)
    _submit(view, "Active")
    active = executor.submissions[0]
    active.on_event(_snapshot_event(active, final=False))

    view.composer.set_conversation_shortcuts(ConversationShortcuts(send="Ctrl+Return", steer="Return"))
    view.composer.editor.setPlainText("Queued using the remapped key")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    view.composer.editor.setPlainText("Steered using the remapped key")
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_Return)
    assert [row.steering for row in view.message_queue._rows] == [True, False]


def test_copy_message_to_other_composer_keeps_original_attachment_paths(qtbot, ui_artifacts, tmp_path, request) -> None:
    window, harness, _executor = _window(qtbot, ui_artifacts, tmp_path)
    clipboard = QApplication.clipboard()
    request.addfinalizer(clipboard.clear)
    path = tmp_path / "source.csv"
    path.write_text("a,b\n1,2", encoding="utf-8")
    missing = tmp_path / "moved.csv"
    harness.message_draft = Mock(return_value=MessageDraft(
        text="Use this data",
        following_ids=(),
        attachments=(
            MessageDraftAttachment(path.name, str(path), (42,)),
            MessageDraftAttachment(missing.name, str(missing), (43,)),
        ),
    ))
    view = window._thread_detail_view
    window._history_panel.open_thread(102)
    view.timeline.add_message("You", [], message_id=42, actions=True)
    bubble = view.timeline.message_bubbles_by_id[42]
    copy = next(button for button in bubble.findChildren(QToolButton)
                if button.accessibleIdentifier() == "chat.message.copy")
    qtbot.mouseClick(copy, Qt.MouseButton.LeftButton)
    assert clipboard.text() == "Use this data"
    window._history_panel.open_thread(101)
    qtbot.keyClick(view.composer.editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert view.composer.editor.toPlainText() == "Use this data"
    assert view.composer.attached_files == [str(path), str(missing)]
    assert view.composer.attachment_states[str(path)].status is ComposerAttachmentStatus.READY
    assert view.composer.attachment_states[str(missing)].status is ComposerAttachmentStatus.FAILED


@pytest.mark.parametrize("following", [(), (43, 44)])
def test_edit_message_confirms_only_a_nonempty_suffix(qtbot, ui_artifacts, tmp_path, monkeypatch, following) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    harness.message_draft = Mock(return_value=MessageDraft("Original", following, ()))
    confirm = Mock(return_value=QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "question", confirm)
    view = window._thread_detail_view
    window._history_panel.open_thread(102)
    view.timeline.add_message("You", [], message_id=42, actions=True)
    bubble = view.timeline.message_bubbles_by_id[42]

    def save_edit():
        editor = next(widget for widget in QApplication.topLevelWidgets()
                      if isinstance(widget, UserMessageEditor) and widget.isVisible())
        editor.editor.setPlainText("Revised")
        save = next(button for button in editor.findChildren(QPushButton)
                    if button.accessibleIdentifier() == "chat.message-editor.save")
        save.click()

    QTimer.singleShot(0, save_edit)
    edit = next(button for button in bubble.findChildren(QToolButton)
                if button.accessibleIdentifier() == "chat.message.edit")
    qtbot.mouseClick(edit, Qt.MouseButton.LeftButton)
    submission = executor.submissions[0].submission
    assert submission.text == "Revised"
    assert submission.replacement.message_id == 42
    assert submission.replacement.confirmed_following_ids == following
    assert confirm.call_count == bool(following)


def test_main_window_exposes_dataset_audit_entry(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    from PySide6.QtWidgets import QPushButton
    from tests.support.ui_queries import find_control

    window, _harness, _executor = _window(qtbot, ui_artifacts, tmp_path)
    audit_button = find_control(window, "main.header.audit", QPushButton)

    assert audit_button.isVisible()
    assert audit_button.text() == window.tr("Audit Center")


def test_opening_old_trial_thread_sends_with_current_default_model(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QPushButton
    from tests.support.ui_queries import find_control

    settings = LLMSettings(
        providers=[LLMProviderConfig(key="custom", models=["first", "preferred"])],
        default_fq_model_key="custom/preferred",
    )
    llm_service = LLMService(FrozenLLMSettingsSource(settings))
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path, llm_service=llm_service)
    harness.snapshots[102].thread.selected_fq_model_key = "custom/first"
    harness.snapshots[101].thread.selected_fq_model_key = "trial/old-model"
    picker = find_control(window, "chat.composer.model-picker", QComboBox)
    editor = find_control(window, "chat.composer.editor", QPlainTextEdit)
    send_button = find_control(window, "chat.composer.send-or-stop", QPushButton)

    window._history_panel.open_thread(102)
    assert picker.currentData() == "custom/first"
    window._history_panel.open_thread(101)
    assert picker.currentData() == "custom/preferred"
    window._chat_workspace.sync_model_options()
    assert picker.currentData() == "custom/preferred"
    editor.setPlainText("Continue the analysis")
    qtbot.mouseClick(send_button, Qt.MouseButton.LeftButton)

    submission = executor.submissions[0].submission
    assert submission.thread_id == 101
    assert submission.fq_model_key == "custom/preferred"


def test_composer_model_switch_updates_thread_reverts_on_failure_and_keeps_pre_thread_choice(
    qtbot: QtBot, ui_artifacts, tmp_path,
) -> None:
    from PySide6.QtWidgets import QComboBox, QPlainTextEdit
    from tests.support.ui_queries import find_control

    settings = LLMSettings(
        providers=[
            LLMProviderConfig(key="alpha", models=["first", "second"]),
            LLMProviderConfig(key="beta", models=["other"]),
        ],
        default_fq_model_key="alpha/first",
    )
    llm_service = LLMService(FrozenLLMSettingsSource(settings))
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path, llm_service=llm_service)
    picker = find_control(window, "chat.composer.model-picker", QComboBox)
    editor = find_control(window, "chat.composer.editor", QPlainTextEdit)
    send_button = find_control(window, "chat.composer.send-or-stop", QPushButton)

    # Switch model on an open thread: persists via set_thread_model and submits selected model.
    beta_index = picker.findData("beta/other")
    assert beta_index >= 0
    picker.setCurrentIndex(beta_index)
    assert harness.set_thread_model.call_args.args == (102, "beta/other")
    assert picker.currentData() == "beta/other"

    editor.setPlainText("Use switched model")
    qtbot.mouseClick(send_button, Qt.MouseButton.LeftButton)
    active = executor.submissions[0]
    assert active.submission.fq_model_key == "beta/other"
    active.on_event(_snapshot_event(active, final=True))
    assert window.conversation_idle

    harness.set_thread_model.side_effect = ValidationError("Model switch rejected")
    second_index = picker.findData("alpha/second")
    picker.setCurrentIndex(second_index)
    assert harness.set_thread_model.call_args.args == (102, "alpha/second")
    assert picker.currentData() == "beta/other"

    # With no active thread, a pre-selected composer model survives options re-sync (e.g., retranslate).
    window._chat_workspace._select_conversation_thread(None)
    picker.setCurrentIndex(second_index)
    assert picker.currentData() == "alpha/second"
    window._chat_workspace.sync_model_options()
    assert picker.currentData() == "alpha/second"


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

    assert view.composer.editor.toPlainText() == "Retry this"
    assert view.composer.attached_files == [str(attachment.resolve())]
    assert view.composer.attachment_states[str(attachment.resolve())].status is ComposerAttachmentStatus.FAILED
    assert view.composer.editor.isEnabled()
    assert window.conversation_idle


def test_acknowledged_failure_reloads_canonical_without_restoring_input(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    attachment = tmp_path / "input.csv"
    _submit(view, "Committed", attachment)
    recorded = executor.submissions[0]
    appended = _snapshot(102, "Thread A", [_text_event(901, "Committed")])
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=recorded.submission.client_submission_id,
            snapshot=appended,
        )
    )
    recorded.on_failure(recorded.submission.client_submission_id, RuntimeError("sampling failed"))

    assert view.composer.editor.toPlainText() == ""
    assert view.composer.attached_files == []
    assert harness.get_thread_snapshot.call_args.args == (102,)
    assert 1102 in view.timeline.message_bubbles_by_id
    assert "append" not in view.timeline.message_bubbles_by_id
    assert window.conversation_idle


def test_history_switch_clears_preparing_turn_and_old_callbacks_cannot_mutate_new_view(
    qtbot: QtBot, ui_artifacts, tmp_path
) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Old turn")
    old = executor.submissions[0]

    window._history_panel.open_thread(101)
    assert window.conversation_thread_id == 101
    assert window.conversation_idle
    assert view.composer.editor.isEnabled()

    _submit(view, "New turn")
    new = executor.submissions[1]
    harness.get_thread_snapshot.reset_mock()
    old.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=old.submission.client_submission_id,
            snapshot=_snapshot(102, "Thread A", [_text_event(902, "OLD")]),
            is_final=True,
        )
    )
    old.on_failure(old.submission.client_submission_id, RuntimeError("old failure"))

    assert window.conversation_thread_id == 101
    assert len(executor.submissions) == 2
    assert not window.conversation_idle
    assert view.composer.editor.toPlainText() == "New turn"
    assert new.submission.thread_id == 101
    assert harness.get_thread_snapshot.call_count == 0


def test_stop_ignores_live_callbacks_but_final_snapshot_unlocks_composer(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Stop after append")
    recorded = executor.submissions[0]
    submission_id = recorded.submission.client_submission_id
    appended = _snapshot(102, "Thread A", [_text_event(901, "Stop after append")])
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=submission_id,
            snapshot=appended,
        )
    )
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="thinking",
            thread_id=102,
            client_submission_id=submission_id,
            pending_message_id=103,
            chatbot_event=build_thinking_chatbot_event(
                pending_message_id=103,
                status=ChatbotEventStatus.IN_PROGRESS,
            ),
        )
    )
    view.stop_requested.emit()
    harness.pause_thread.assert_called_once_with(102)
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="thinking",
            thread_id=102,
            client_submission_id=submission_id,
            pending_message_id=103,
            chatbot_event=build_thinking_chatbot_event(
                pending_message_id=103,
                status=ChatbotEventStatus.IN_PROGRESS,
            ),
        )
    )
    assert not view.composer.running

    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=submission_id,
            snapshot=_snapshot(102, "Thread A", [_text_event(903, "Final")]),
            is_final=True,
        )
    )
    assert window.conversation_idle
    assert view.composer.editor.isEnabled()
    assert not view.composer.running
    assert 903 in view.timeline.message_bubbles_by_id


def test_ack_then_direct_final_snapshot_unlocks_composer(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "No live event")
    recorded = executor.submissions[0]
    submission_id = recorded.submission.client_submission_id
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=submission_id,
            snapshot=_snapshot(102, "Thread A", [_text_event(901, "No live event")]),
        )
    )
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=submission_id,
            snapshot=_snapshot(102, "Thread A", [_text_event(903, "Done")]),
            is_final=True,
        )
    )

    assert window.conversation_idle
    assert view.composer.editor.isEnabled()
    assert not view.composer.running


def test_close_shuts_executor_and_late_callbacks_do_not_change_view(qtbot: QtBot, ui_artifacts, tmp_path) -> None:
    window, _harness, executor = _window(qtbot, ui_artifacts, tmp_path)
    view = window._thread_detail_view
    _submit(view, "Closing")
    recorded = executor.submissions[0]
    rendered_ids = set(view.timeline.message_bubbles_by_id)
    window.close()
    recorded.on_event(
        AgentHarnessStreamEvent(
            kind="snapshot",
            thread_id=102,
            client_submission_id=recorded.submission.client_submission_id,
            snapshot=_snapshot(102, "Thread A", [_text_event(904, "late")]),
            is_final=True,
        )
    )
    recorded.on_failure(recorded.submission.client_submission_id, RuntimeError("late failure"))

    assert executor.shutdown_calls == 1
    assert view.composer.editor.toPlainText() == "Closing"
    assert set(view.timeline.message_bubbles_by_id) == rendered_ids
    assert window.conversation_idle
