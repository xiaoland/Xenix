from __future__ import annotations

from PySide6.QtGui import QColor, QIcon

import qtawesome as qta

DEFAULT_ICON_COLOR = "#4b5563"
DEFAULT_CHEVRON_COLOR = "#374151"

_TOOL_ICON_NAMES: dict[str, str] = {
    "table": "ph.table",
    "merge": "ph.git-merge",
    "sparkles": "ph.sparkle",
    "table-search": "ph.magnifying-glass",
    "table-transform": "ph.magic-wand",
    "columns": "ph.columns",
    "list-tree": "ph.tree-structure",
    "model": "ph.brain",
    "sliders": "ph.sliders-horizontal",
    "prediction": "ph.trend-up",
    "tool": "ph.wrench",
}


def icon(name: str, *, color: QColor | str = DEFAULT_ICON_COLOR) -> QIcon:
    return qta.icon(name, color=_color_value(color))


def tool_icon(icon_key: str | None, *, color: QColor | str = DEFAULT_ICON_COLOR) -> QIcon:
    return icon(_TOOL_ICON_NAMES.get(icon_key or "tool", _TOOL_ICON_NAMES["tool"]), color=color)


def chevron_icon(*, expanded: bool, color: QColor | str = DEFAULT_CHEVRON_COLOR) -> QIcon:
    name = "ph.caret-down" if expanded else "ph.caret-right"
    return icon(name, color=color)


def _color_value(color: QColor | str) -> str:
    if isinstance(color, QColor):
        return color.name()
    return color
