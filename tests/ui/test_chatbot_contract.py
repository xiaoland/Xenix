from __future__ import annotations

from PySide6.QtWidgets import QToolButton
from pytestqt.qtbot import QtBot

from xenix.ui.chatbot import AttachmentChip, ComposerAttachmentStatus, ThreadDetailView
from xenix.ui.semantic_identity import item_reference


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


def test_composer_attachment_chip_is_addressable_by_path(qtbot: QtBot, tmp_path) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    attachment = tmp_path / "sample.csv"
    view.restore_composer("", [str(attachment)])

    chips = view.composer.findChildren(AttachmentChip)
    assert len(chips) == 1
    chip = chips[0]
    assert chip.accessibleIdentifier() == "chat.composer.attachment"
    assert item_reference(chip) == str(attachment.resolve())

    remove = chip.findChild(QToolButton, "attachmentChipRemoveButton")
    assert remove is not None
    assert remove.accessibleIdentifier() == "chat.composer.attachment.remove"
    assert item_reference(remove) == str(attachment.resolve())
