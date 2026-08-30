from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton

from xenix.ui.semantic_identity import identify, identify_repeated_item, item_reference


def test_identify_sets_accessibility_identity_without_touching_object_name(qtbot) -> None:
    button = QPushButton("New thread")
    button.setObjectName("presentationSelector")
    qtbot.addWidget(button)

    returned = identify(button, "main.history.new-thread")

    assert returned is button
    assert button.accessibleIdentifier() == "main.history.new-thread"
    assert button.objectName() == "presentationSelector"


def test_repeated_items_share_role_and_keep_distinct_authoritative_references(qtbot) -> None:
    first = QPushButton("Remove")
    second = QPushButton("Remove")
    qtbot.addWidget(first)
    qtbot.addWidget(second)

    identify_repeated_item(
        first,
        role="chat.attachment.remove",
        item_reference="attachment:01J8A",
    )
    identify_repeated_item(
        second,
        role="chat.attachment.remove",
        item_reference="attachment:01J8B",
    )

    assert first.accessibleIdentifier() == second.accessibleIdentifier()
    assert item_reference(first) == "attachment:01J8A"
    assert item_reference(second) == "attachment:01J8B"


@pytest.mark.parametrize(
    "invalid",
    ["send", "Chat.Send", "chat.send_button", "chat..send", "chat.send button"],
)
def test_semantic_identity_rejects_structural_or_unstable_names(qtbot, invalid: str) -> None:
    button = QPushButton()
    qtbot.addWidget(button)

    with pytest.raises(ValueError):
        identify(button, invalid)


@pytest.mark.parametrize(
    "invalid",
    [r"C:\\Users\\person\\report.csv", "report final.csv", "", "../attachment"],
)
def test_repeated_item_reference_rejects_paths_and_display_content(qtbot, invalid: str) -> None:
    button = QPushButton()
    qtbot.addWidget(button)

    with pytest.raises(ValueError):
        identify_repeated_item(
            button,
            role="chat.attachment.remove",
            item_reference=invalid,
        )
