"""Artifact preview pixmap helpers for the chatbot presentation widgets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..presentation import ArtifactResolver

_ARTIFACT_PREVIEW_MIN_WIDTH = 160
_ARTIFACT_PREVIEW_MAX_WIDTH = 720
_ARTIFACT_PREVIEW_MAX_HEIGHT = 360
_ARTIFACT_PREVIEW_BACKGROUND = QColor("#ffffff")


def _load_artifact_preview_pixmap(
    artifact_resolver: ArtifactResolver | None,
    uri: str,
    *,
    available_width: int,
) -> QPixmap:
    if artifact_resolver is None:
        return QPixmap()
    try:
        artifact = artifact_resolver(uri)
    except Exception:
        return QPixmap()

    mime_type = str(getattr(artifact, "mime_type", "") or "")
    if mime_type and not mime_type.startswith("image/"):
        return QPixmap()
    if not bool(getattr(artifact, "ready_to_open", False)):
        return QPixmap()
    if not bool(getattr(artifact, "exists", False)):
        return QPixmap()

    artifact_path = Path(str(getattr(artifact, "absolute_path", "") or "")).expanduser()
    if not artifact_path.is_file():
        return QPixmap()

    max_width = max(
        _ARTIFACT_PREVIEW_MIN_WIDTH,
        min(_ARTIFACT_PREVIEW_MAX_WIDTH, available_width - 24),
    )
    if _artifact_uses_svg_preview(mime_type, artifact_path):
        return _render_svg_preview_pixmap(
            artifact_path,
            max_width=max_width,
            max_height=_ARTIFACT_PREVIEW_MAX_HEIGHT,
        )

    pixmap = QPixmap(str(artifact_path))
    if pixmap.isNull():
        return pixmap
    return _scale_artifact_preview_pixmap(
        pixmap,
        max_width=max_width,
        max_height=_ARTIFACT_PREVIEW_MAX_HEIGHT,
    )


def _artifact_uses_svg_preview(mime_type: str, artifact_path: Path) -> bool:
    normalized_mime_type = mime_type.split(";", 1)[0].strip().lower()
    return normalized_mime_type == "image/svg+xml" or artifact_path.suffix.lower() == ".svg"


def _render_svg_preview_pixmap(path: Path, *, max_width: int, max_height: int) -> QPixmap:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()

    source_size = renderer.defaultSize()
    if source_size.width() <= 0 or source_size.height() <= 0:
        view_box = renderer.viewBoxF()
        if view_box.width() > 0 and view_box.height() > 0:
            source_size = QSize(int(round(view_box.width())), int(round(view_box.height())))
        else:
            source_size = QSize(max_width, max_height)
    target_size = _fit_artifact_preview_size(
        source_size,
        max_width=max_width,
        max_height=max_height,
    )
    image = QImage(target_size, QImage.Format_ARGB32_Premultiplied)
    image.fill(_ARTIFACT_PREVIEW_BACKGROUND)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        renderer.render(painter, QRectF(0, 0, target_size.width(), target_size.height()))
    finally:
        painter.end()
    return QPixmap.fromImage(image)


def _scale_artifact_preview_pixmap(pixmap: QPixmap, *, max_width: int, max_height: int) -> QPixmap:
    if pixmap.width() <= max_width and pixmap.height() <= max_height:
        return pixmap
    return pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _fit_artifact_preview_size(source_size: QSize, *, max_width: int, max_height: int) -> QSize:
    source_width = max(1, source_size.width())
    source_height = max(1, source_size.height())
    scale = min(max_width / source_width, max_height / source_height, 1.0)
    return QSize(
        max(1, int(round(source_width * scale))),
        max(1, int(round(source_height * scale))),
    )
