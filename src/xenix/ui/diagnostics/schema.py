from __future__ import annotations

from typing import NotRequired, TypedDict


UI_ARTIFACT_SCHEMA_VERSION = 1


class RectSnapshot(TypedDict):
    x: int
    y: int
    width: int
    height: int


class SizeSnapshot(TypedDict):
    width: int
    height: int


class MarginsSnapshot(TypedDict):
    left: int
    top: int
    right: int
    bottom: int


class WidgetSnapshot(TypedDict):
    geometry: RectSnapshot
    size: SizeSnapshot
    size_hint: SizeSnapshot
    minimum_size_hint: SizeSnapshot
    minimum_size: SizeSnapshot
    maximum_size: SizeSnapshot
    horizontal_size_policy: str
    vertical_size_policy: str
    enabled: bool
    visible: bool
    hidden: bool
    has_focus: bool
    checked: NotRequired[bool]
    current_index: NotRequired[int]


class LayoutSnapshot(TypedDict):
    geometry: RectSnapshot
    margins: MarginsSnapshot
    spacing: int


class OwnershipNode(TypedDict):
    node_id: str
    class_name: str
    object_name: str
    semantic_id: str
    widget: NotRequired[WidgetSnapshot]
    layout: NotRequired[LayoutSnapshot]
    truncated: NotRequired[bool]
    children: list[OwnershipNode]


class LayoutItemNode(TypedDict):
    kind: str
    alignment: int
    object_ref: NotRequired[str]
    size_hint: NotRequired[SizeSnapshot]
    horizontal_size_policy: NotRequired[str]
    vertical_size_policy: NotRequired[str]
    child_layout: NotRequired[LayoutTreeNode]


class LayoutTreeNode(TypedDict):
    object_ref: str
    class_name: str
    geometry: RectSnapshot
    margins: MarginsSnapshot
    spacing: int
    items: list[LayoutItemNode]
    truncated: NotRequired[bool]


class UiTreeArtifact(TypedDict):
    schema_version: int
    ownership: OwnershipNode
    layout: LayoutTreeNode | None


class RenderEnvironment(TypedDict):
    python: str
    pyside: str
    qt: str
    os: str
    qpa: str
    style: str
    locale: str
    logical_dpi: float | None
    device_pixel_ratio: float


class ArtifactFile(TypedDict):
    name: str
    bytes: int
    pixel_width: NotRequired[int]
    pixel_height: NotRequired[int]


class RedactionManifest(TypedDict):
    widget_text: str
    paths: str
    qt_log_max_bytes: int
    qt_log_max_records: int


class UiArtifactManifest(TypedDict):
    schema_version: int
    reason: str
    scenario_id: str | None
    captured_at_utc: str
    policy: str
    redaction: RedactionManifest
    render_environment: RenderEnvironment
    root_geometry: RectSnapshot | None
    files: list[ArtifactFile]
