from __future__ import annotations

from pytestqt.qtbot import QtBot

from xenix.ui.chatbot import ComposerAttachmentStatus, ThreadDetailView


def test_chat_shell_has_stable_unique_semantic_identities(qtbot: QtBot) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    controls = (
        view._scroll_to_bottom_button,
        view._attach_button,
        view._editor,
        view._model_picker,
        view._send_button,
        view._step_continue_button,
        view._step_stop_button,
    )

    identities = [control.accessibleIdentifier() for control in controls]

    assert all(identities)
    assert len(identities) == len(set(identities))
    assert view._attach_button.accessibleName() == view.tr("Attach files")
    assert view._editor.accessibleName() == view.tr("Message Xenix")
    assert view._scroll_to_bottom_button.accessibleName() == view.tr("Scroll to bottom")


def test_send_action_accessible_name_tracks_visual_state(qtbot: QtBot, tmp_path) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    attachment = tmp_path / "sample.csv"
    view.restore_composer("", [str(attachment)])

    view.set_attachment_status(str(attachment), ComposerAttachmentStatus.PENDING)
    assert view._send_button.text() == ""
    assert view._send_button.accessibleName() == view.tr("Preparing attachments")

    view.set_running(True)
    assert view._send_button.text() == view.tr("Stop")
    assert view._send_button.accessibleName() == view.tr("Stop")
