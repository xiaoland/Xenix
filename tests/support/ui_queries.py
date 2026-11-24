"""Semantic widget lookup helpers anchored to production accessibility identities.

UI tests should locate controls through the same semantic identities exported
for accessibility and diagnostics rather than reaching into private ``._*``
widget attributes.
"""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtWidgets import QWidget

from xenix.ui.semantic_identity import item_reference

WidgetT = TypeVar("WidgetT", bound=QWidget)


def find_controls(
    root: QWidget,
    semantic_id: str,
    widget_type: type[WidgetT] = QWidget,  # type: ignore[assignment]
    *,
    reference: str | None = None,
) -> list[WidgetT]:
    """Return all descendant widgets matching ``semantic_id`` (and optional item reference)."""
    matches: list[WidgetT] = []
    candidates: list[QWidget] = [root, *root.findChildren(widget_type)]
    seen: set[int] = set()
    for widget in candidates:
        if id(widget) in seen or not isinstance(widget, widget_type):
            continue
        seen.add(id(widget))
        if widget.accessibleIdentifier() != semantic_id:
            continue
        if reference is not None and item_reference(widget) != reference:
            continue
        matches.append(widget)
    return matches


def find_control(
    root: QWidget,
    semantic_id: str,
    widget_type: type[WidgetT] = QWidget,  # type: ignore[assignment]
    *,
    reference: str | None = None,
) -> WidgetT:
    """Return the unique descendant widget matching ``semantic_id``."""
    matches = find_controls(root, semantic_id, widget_type, reference=reference)
    if len(matches) != 1:
        detail = f" (reference={reference!r})" if reference is not None else ""
        raise AssertionError(
            f"Expected exactly 1 {widget_type.__name__} with semantic id {semantic_id!r}{detail}, "
            f"found {len(matches)}."
        )
    return matches[0]
