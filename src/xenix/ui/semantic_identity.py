from __future__ import annotations

import re
from typing import Final, TypeVar

from PySide6.QtWidgets import QWidget


SEMANTIC_ITEM_REFERENCE_PROPERTY: Final = "xenixSemanticItemReference"

_SEGMENT = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_SEMANTIC_ID_PATTERN = re.compile(rf"{_SEGMENT}(?:\.{_SEGMENT})+")
_ITEM_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")

WidgetT = TypeVar("WidgetT", bound=QWidget)


def identify(widget: WidgetT, semantic_id: str) -> WidgetT:
    """Assign a stable, non-localized identity without changing objectName."""
    _require_semantic_id(semantic_id)
    widget.setAccessibleIdentifier(semantic_id)
    return widget


def identify_repeated_item(
    widget: WidgetT,
    *,
    role: str,
    item_reference: str,
) -> WidgetT:
    """Identify a repeated control by semantic role and authoritative item key."""
    _require_semantic_id(role)
    if _ITEM_REFERENCE_PATTERN.fullmatch(item_reference) is None:
        raise ValueError(
            "item_reference must be a non-sensitive stable token of at most 128 "
            "ASCII letters, digits, '.', '_', ':', or '-'"
        )
    widget.setAccessibleIdentifier(role)
    widget.setProperty(SEMANTIC_ITEM_REFERENCE_PROPERTY, item_reference)
    return widget


def item_reference(widget: QWidget) -> str | None:
    value = widget.property(SEMANTIC_ITEM_REFERENCE_PROPERTY)
    return value if isinstance(value, str) and value else None


def _require_semantic_id(value: str) -> None:
    if _SEMANTIC_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "semantic identity must be a dotted, lowercase product role; "
            "segments may contain hyphens"
        )
