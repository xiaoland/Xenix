"""Private styled-panel container for assembling settings content widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


class Card(QFrame):
    """Host one content widget behind a styled panel frame.

    Content widgets stay plain ``QWidget``s and own their fields, behavior, and
    lifecycle.  The card owns only the panel chrome (frame shape and margins) and
    is assembled by the owning tab or dialog via :meth:`set_content`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(0)

    def set_content(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)
