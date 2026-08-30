from __future__ import annotations

import re

from PySide6.QtCore import QObject, QRect, QSize
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLayout, QWidget
from shiboken6 import isValid

from .schema import (
    LayoutItemNode,
    LayoutSnapshot,
    LayoutTreeNode,
    OwnershipNode,
    RectSnapshot,
    SizeSnapshot,
    UI_ARTIFACT_SCHEMA_VERSION,
    UiTreeArtifact,
    WidgetSnapshot,
)


_SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")
MAX_UI_SNAPSHOT_NODES = 5_000
MAX_UI_SNAPSHOT_DEPTH = 64


def capture_ui_snapshot(root: QObject) -> UiTreeArtifact:
    if not isValid(root):
        raise ValueError("Cannot capture a deleted Qt object")

    references: dict[int, str] = {}
    emitted = [0]
    ownership = _capture_ownership(root, references, emitted, depth=0)
    root_layout = root if isinstance(root, QLayout) else root.layout() if isinstance(root, QWidget) else None
    layout = (
        _capture_layout(root_layout, references, set(), emitted, depth=0)
        if root_layout is not None
        else None
    )
    return {
        "schema_version": UI_ARTIFACT_SCHEMA_VERSION,
        "ownership": ownership,
        "layout": layout,
    }


def _capture_ownership(
    obj: QObject,
    references: dict[int, str],
    emitted: list[int],
    *,
    depth: int,
) -> OwnershipNode:
    emitted[0] += 1
    node_id = references.setdefault(id(obj), f"o{len(references)}")
    node: OwnershipNode = {
        "node_id": node_id,
        "class_name": type(obj).__name__,
        "object_name": _safe_identity(obj.objectName()),
        "semantic_id": _safe_identity(obj.accessibleIdentifier()) if isinstance(obj, QWidget) else "",
        "children": [],
    }
    if isinstance(obj, QWidget):
        node["widget"] = _capture_widget(obj)
    if isinstance(obj, QLayout):
        node["layout"] = _capture_layout_properties(obj)
    children = [
        child
        for child in obj.children()
        if isinstance(child, (QWidget, QLayout)) and isValid(child)
    ]
    if depth >= MAX_UI_SNAPSHOT_DEPTH or emitted[0] >= MAX_UI_SNAPSHOT_NODES:
        node["truncated"] = bool(children)
        return node
    captured_children: list[OwnershipNode] = []
    for child in children:
        if emitted[0] >= MAX_UI_SNAPSHOT_NODES:
            node["truncated"] = True
            break
        captured_children.append(
            _capture_ownership(child, references, emitted, depth=depth + 1)
        )
    node["children"] = captured_children
    return node


def _capture_widget(widget: QWidget) -> WidgetSnapshot:
    policy = widget.sizePolicy()
    result: WidgetSnapshot = {
        "geometry": _rect(widget.geometry()),
        "size": _size(widget.size()),
        "size_hint": _size(widget.sizeHint()),
        "minimum_size_hint": _size(widget.minimumSizeHint()),
        "minimum_size": _size(widget.minimumSize()),
        "maximum_size": _size(widget.maximumSize()),
        "horizontal_size_policy": _enum_name(policy.horizontalPolicy()),
        "vertical_size_policy": _enum_name(policy.verticalPolicy()),
        "enabled": widget.isEnabled(),
        "visible": widget.isVisible(),
        "hidden": widget.isHidden(),
        "has_focus": widget.hasFocus(),
    }
    if isinstance(widget, QAbstractButton):
        result["checked"] = widget.isChecked()
    if isinstance(widget, QComboBox):
        result["current_index"] = widget.currentIndex()
    return result


def _capture_layout_properties(layout: QLayout) -> LayoutSnapshot:
    margins = layout.contentsMargins()
    return {
        "geometry": _rect(layout.geometry()),
        "margins": {
            "left": margins.left(),
            "top": margins.top(),
            "right": margins.right(),
            "bottom": margins.bottom(),
        },
        "spacing": layout.spacing(),
    }


def _capture_layout(
    layout: QLayout,
    references: dict[int, str],
    visited: set[int],
    emitted: list[int],
    *,
    depth: int,
) -> LayoutTreeNode:
    emitted[0] += 1
    object_ref = references.setdefault(id(layout), f"o{len(references)}")
    properties = _capture_layout_properties(layout)
    if id(layout) in visited:
        return {
            "object_ref": object_ref,
            "class_name": type(layout).__name__,
            "geometry": properties["geometry"],
            "margins": properties["margins"],
            "spacing": properties["spacing"],
            "items": [],
        }
    visited.add(id(layout))
    items: list[LayoutItemNode] = []
    truncated = depth >= MAX_UI_SNAPSHOT_DEPTH or emitted[0] >= MAX_UI_SNAPSHOT_NODES
    if truncated:
        return {
            "object_ref": object_ref,
            "class_name": type(layout).__name__,
            "geometry": properties["geometry"],
            "margins": properties["margins"],
            "spacing": properties["spacing"],
            "items": [],
            "truncated": layout.count() > 0,
        }
    for index in range(layout.count()):
        if emitted[0] >= MAX_UI_SNAPSHOT_NODES:
            truncated = True
            break
        item = layout.itemAt(index)
        if item is None:
            continue
        entry: LayoutItemNode = {
            "kind": "spacer",
            "alignment": int(item.alignment()),
        }
        child_layout = item.layout()
        widget = item.widget()
        spacer = item.spacerItem()
        if child_layout is not None:
            entry["kind"] = "layout"
            entry["object_ref"] = references.setdefault(id(child_layout), f"o{len(references)}")
            entry["child_layout"] = _capture_layout(
                child_layout,
                references,
                visited,
                emitted,
                depth=depth + 1,
            )
        elif widget is not None and isValid(widget):
            entry["kind"] = "widget"
            entry["object_ref"] = references.setdefault(id(widget), f"o{len(references)}")
            widget_layout = widget.layout()
            if widget_layout is not None:
                entry["child_layout"] = _capture_layout(
                    widget_layout,
                    references,
                    visited,
                    emitted,
                    depth=depth + 1,
                )
        elif spacer is not None:
            entry["size_hint"] = _size(spacer.sizeHint())
            entry["horizontal_size_policy"] = _enum_name(spacer.sizePolicy().horizontalPolicy())
            entry["vertical_size_policy"] = _enum_name(spacer.sizePolicy().verticalPolicy())
        items.append(entry)
    result: LayoutTreeNode = {
        "object_ref": object_ref,
        "class_name": type(layout).__name__,
        "geometry": properties["geometry"],
        "margins": properties["margins"],
        "spacing": properties["spacing"],
        "items": items,
    }
    if truncated:
        result["truncated"] = True
    return result


def _safe_identity(value: str) -> str:
    if not value:
        return ""
    return value if _SAFE_ID.fullmatch(value) is not None else "<redacted>"


def _rect(rect: QRect) -> RectSnapshot:
    return {"x": rect.x(), "y": rect.y(), "width": rect.width(), "height": rect.height()}


def _size(size: QSize) -> SizeSnapshot:
    return {"width": size.width(), "height": size.height()}


def _enum_name(value: object) -> str:
    name = getattr(value, "name", None)
    return name if isinstance(name, str) else str(value)
