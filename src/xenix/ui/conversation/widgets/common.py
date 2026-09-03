"""Shared geometry helpers for the chatbot presentation widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

UNBOUNDED_WIDGET_WIDTH = 16777215


def _propagate_geometry_change(widget: QWidget) -> None:
    current: QWidget | None = widget
    while current is not None:
        current.updateGeometry()
        current = current.parentWidget()
