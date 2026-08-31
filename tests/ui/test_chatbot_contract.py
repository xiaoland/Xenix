from __future__ import annotations

from pytestqt.qtbot import QtBot

from xenix.ui.chatbot import ComposerAttachmentStatus, ThreadDetailView


def test_chat_shell_has_stable_unique_semantic_identities(qtbot: QtBot) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    controls = (
        view.timeline.scroll_to_bottom_button,
        view.composer.attach_button,
        view.composer.editor,
        view.composer.model_picker,
        view.composer.send_button,
        view.composer.step_continue_button,
        view.composer.step_stop_button,
    )

    identities = [control.accessibleIdentifier() for control in controls]

    assert all(identities)
    assert len(identities) == len(set(identities))
    assert view.composer.attach_button.accessibleName() == view.tr("Attach files")
    assert view.composer.editor.accessibleName() == view.tr("Message Xenix")
    assert view.timeline.scroll_to_bottom_button.accessibleName() == view.tr("Scroll to bottom")


def test_send_action_accessible_name_tracks_visual_state(qtbot: QtBot, tmp_path) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    attachment = tmp_path / "sample.csv"
    view.restore_composer("", [str(attachment)])

    view.set_attachment_status(str(attachment), ComposerAttachmentStatus.PENDING)
    assert view.composer.send_button.text() == ""
    assert view.composer.send_button.accessibleName() == view.tr("Preparing attachments")

    view.set_running(True)
    assert view.composer.send_button.text() == view.tr("Stop")
    assert view.composer.send_button.accessibleName() == view.tr("Stop")
