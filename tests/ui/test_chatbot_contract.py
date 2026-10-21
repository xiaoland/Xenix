from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QPixmap, QTextDocument
from PySide6.QtWidgets import QToolButton
from pytestqt.qtbot import QtBot

from xenix.ui.chatbot import AttachmentChip, ComposerAttachmentStatus, ThreadDetailView
from xenix.ui.semantic_identity import item_reference


@pytest.mark.parametrize("author", ["You", "Xenix"])
@pytest.mark.parametrize("image_format", ["svg", "png"])
def test_result_image_resizes_and_opens_its_registered_file(
    author, image_format, qtbot: QtBot, storage, tmp_path, monkeypatch,
) -> None:
    import vl_convert as vlc

    from xenix.services.artifact_service import ArtifactService, RegisterArtifactInput
    from xenix.services.link_router import LinkRouter
    from xenix.ui.conversation.presentation import ChatbotBlock
    from xenix.ui.conversation.widgets import ChatMessageBubble

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600" viewBox="0 0 1200 600">'
        '<rect width="1200" height="600" fill="white"/>'
        '<circle cx="550" cy="300" r="80" fill="#1f77b4"/>'
        '<text x="1050" y="40" font-family="sans-serif" font-size="20">客户分群</text></svg>'
    )
    path = tmp_path / f"segments.{image_format}"
    if image_format == "svg":
        path.write_text(svg, encoding="utf-8")
    else:
        path.write_bytes(vlc.svg_to_png(svg))
    artifacts = ArtifactService(storage.session_factory)
    result = artifacts.register_artifact(RegisterArtifactInput(
        title="Segments", absolute_path=str(path),
        mime_type="image/svg+xml" if image_format == "svg" else "image/png",
    ))
    opened = []
    monkeypatch.setattr("xenix.services.artifact_service._open_file_with_os", lambda target: opened.append(target) or True)
    router = LinkRouter(artifact_service=artifacts)
    bubble = ChatMessageBubble(
        author=author,
        blocks=[ChatbotBlock(type="text", text=f"![Segments](artifact://{result.id}?view=image)")],
        artifact_resolver=artifacts.resolve_uri,
    )
    qtbot.addWidget(bubble)
    bubble.link_activated.connect(router.activate)
    bubble.resize(900, 500)
    bubble.set_available_width(900)
    bubble.show()
    body = bubble._browser

    def preview() -> QPixmap:
        document = body.document()
        fragment = document.begin().begin().fragment()
        name = fragment.charFormat().toImageFormat().name()
        image = document.resource(QTextDocument.ImageResource, QUrl(name))
        assert isinstance(image, QPixmap) and not image.isNull()
        return image

    qtbot.waitUntil(lambda: preview().deviceIndependentSize().width() > 300)
    wide_width = preview().deviceIndependentSize().width()
    ratio = body.devicePixelRatioF()
    assert preview().devicePixelRatioF() == ratio
    assert preview().width() >= wide_width * ratio - 1
    target = body.viewport() if hasattr(body, "viewport") else body
    qtbot.mouseClick(target, Qt.LeftButton, pos=QPoint(20, 20))
    assert opened == [path]

    bubble.set_available_width(380)
    bubble.resize(380, bubble.height())
    qtbot.waitUntil(lambda: preview().deviceIndependentSize().width() < wide_width)
    available_width = target.width()
    assert preview().deviceIndependentSize().width() <= available_width - 24
    assert body.height() >= int(body.document().size().height())

    bubble.set_available_width(900)
    bubble.resize(900, bubble.height())
    qtbot.waitUntil(lambda: preview().deviceIndependentSize().width() == wide_width)
    assert preview().devicePixelRatioF() == ratio


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
                    "dataset_id": 101,
                    "operation_name": "clean_dataset",
                    "generation": 2,
                    "created_at": "2026-09-03T10:00:00+08:00",
                    "inputs": [
                        {
                            "position": 0,
                            "name": "raw",
                            "dataset_id": 102,
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
    assert "Dataset: `clean\\`data` (`101`)" in markdown
    assert "Input 1: `raw` (`102`) — alias `source`" in markdown
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
            "type": "dataset_audit", "dataset_id": 101,
            "name": "Cleaned data", "agent_explanation": explanation,
        }],
    )])
    from PySide6.QtWidgets import QTextBrowser
    assert any("101" in browser.toPlainText() for browser in view.findChildren(QTextBrowser))


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
