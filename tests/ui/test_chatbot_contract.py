from __future__ import annotations

import pytest
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


@pytest.mark.parametrize("explanation", [None, "", "Removed incomplete rows."])
def test_dataset_audit_block_is_rendered_in_tool_detail(explanation, qtbot) -> None:
    from xenix.services.agent import ChatbotEvent, ChatbotEventAuthor, ChatbotEventKind
    from xenix.ui.conversation.presentation import coerce_blocks, render_content_blocks

    markdown = render_content_blocks(
        coerce_blocks(
            [
                {
                    "type": "dataset_audit",
                    "name": "clean`data",
                    "dataset_id": "dataset-2",
                    "operation_name": "clean_dataset",
                    "generation": 2,
                    "created_at": "2026-09-03T10:00:00+08:00",
                    "inputs": [
                        {
                            "position": 0,
                            "name": "raw",
                            "dataset_id": "dataset-1",
                            "alias": "source",
                        }
                    ],
                    "parameters_payload": {"drop_nulls": True},
                    "agent_explanation": explanation,
                }
            ]
        )
    )

    assert "### Dataset audit" in markdown
    assert "Dataset: `clean\\`data` (`dataset-2`)" in markdown
    assert "Input 1: `raw` (`dataset-1`) — alias `source`" in markdown
    assert '"drop_nulls": true' in markdown
    if explanation:
        assert explanation in markdown
    else:
        assert "Agent-authored explanation" not in markdown

    view = ThreadDetailView()
    qtbot.addWidget(view)
    view.render_events([ChatbotEvent(
        id="history-tool", kind=ChatbotEventKind.TOOL, author=ChatbotEventAuthor.TOOL,
        tool_name="data.clean", summary="Cleaned dataset",
        detail_blocks=[{
            "type": "dataset_audit", "dataset_id": "dataset-2",
            "name": "Cleaned data", "agent_explanation": explanation,
        }],
    )])
    from PySide6.QtWidgets import QTextBrowser
    assert any("dataset-2" in browser.toPlainText() for browser in view.findChildren(QTextBrowser))


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


def test_attachment_remove_is_disabled_while_running(qtbot: QtBot, tmp_path) -> None:
    view = ThreadDetailView()
    qtbot.addWidget(view)
    attachment = tmp_path / "sample.csv"
    view.restore_composer("", [str(attachment)])

    def remove_button() -> QToolButton | None:
        return view.composer.findChild(QToolButton, "attachmentChipRemoveButton")

    assert remove_button() is not None
    assert remove_button().isEnabled()

    view.set_running(True)
    assert not remove_button().isEnabled()

    view.set_running(False)
    assert remove_button().isEnabled()
