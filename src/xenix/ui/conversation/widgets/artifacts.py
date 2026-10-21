"""Artifact preview pixmap helpers for the chatbot presentation widgets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QTextDocument
from PySide6.QtSvg import QSvgRenderer

from ....exceptions import report_exception
from ..presentation import ArtifactResolver

_ARTIFACT_PREVIEW_MAX_WIDTH = 720
_ARTIFACT_PREVIEW_MAX_HEIGHT = 360
_ARTIFACT_PREVIEW_BACKGROUND = QColor("#ffffff")


class ArtifactPreviewDocument(QTextDocument):
    """Keep inline results sized for their viewport, including after a resize.

    QTextDocument caches image resources by URL. Changing only its text width
    leaves the old image size and density in that cache, so refresh the current
    images when the viewport width or screen density changes.
    """

    def __init__(
        self,
        *,
        artifact_resolver: ArtifactResolver | None,
        available_width: int,
        device_pixel_ratio: float,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._artifact_resolver = artifact_resolver
        self._preview_context = (available_width, device_pixel_ratio)
        self._preview_sources: dict[str, QPixmap] = {}

    def set_artifact_resolver(self, resolver: ArtifactResolver | None) -> None:
        self._artifact_resolver = resolver
        self._preview_sources.clear()
        self._refresh_previews()

    def update_preview_context(self, *, available_width: int, device_pixel_ratio: float) -> None:
        context = (available_width, device_pixel_ratio)
        if context != self._preview_context:
            if device_pixel_ratio != self._preview_context[1]:
                self._preview_sources.clear()
            self._preview_context = context
            self._refresh_previews()

    def loadResource(self, resource_type: int, name):  # type: ignore[override]
        if resource_type == QTextDocument.ImageResource and name.scheme() == "artifact":
            return self._load_preview(name.toString())
        return super().loadResource(resource_type, name)

    def _load_preview(self, uri: str) -> QPixmap:
        width, ratio = self._preview_context
        if uri not in self._preview_sources:
            # Render once at the maximum preview size for this screen density.
            # Dragging a window only resizes this source, never reruns SVG text
            # layout or resamples an already narrowed image.
            self._preview_sources[uri] = _load_artifact_preview_pixmap(
                self._artifact_resolver, uri,
                available_width=_ARTIFACT_PREVIEW_MAX_WIDTH + 24,
                device_pixel_ratio=ratio,
            )
        source = self._preview_sources[uri]
        if source.isNull():
            return source
        return _scale_artifact_preview_pixmap(
            source,
            max_width=max(1, min(_ARTIFACT_PREVIEW_MAX_WIDTH, width - 24)),
            max_height=_ARTIFACT_PREVIEW_MAX_HEIGHT,
            device_pixel_ratio=ratio,
        )

    def _refresh_previews(self) -> None:
        urls: set[str] = set()
        block = self.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    name = fragment.charFormat().toImageFormat().name()
                    if QUrl(name).scheme() == "artifact":
                        urls.add(name)
                iterator += 1
            block = block.next()
        for name in urls:
            self.addResource(QTextDocument.ImageResource, QUrl(name), self._load_preview(name))
        if urls:
            self.markContentsDirty(0, self.characterCount())


def _load_artifact_preview_pixmap(
    artifact_resolver: ArtifactResolver | None,
    uri: str,
    *,
    available_width: int,
    device_pixel_ratio: float = 1.0,
) -> QPixmap:
    if artifact_resolver is None:
        return QPixmap()
    try:
        artifact = artifact_resolver(uri)
    except Exception as exc:
        report_exception(exc)
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

    max_width = max(1, min(_ARTIFACT_PREVIEW_MAX_WIDTH, available_width - 24))
    if _artifact_uses_svg_preview(mime_type, artifact_path):
        return _render_svg_preview_pixmap(
            artifact_path,
            max_width=max_width,
            max_height=_ARTIFACT_PREVIEW_MAX_HEIGHT,
            device_pixel_ratio=device_pixel_ratio,
        )

    pixmap = QPixmap(str(artifact_path))
    if pixmap.isNull():
        return pixmap
    return _scale_artifact_preview_pixmap(
        pixmap,
        max_width=max_width,
        max_height=_ARTIFACT_PREVIEW_MAX_HEIGHT,
        device_pixel_ratio=device_pixel_ratio,
    )


def _artifact_uses_svg_preview(mime_type: str, artifact_path: Path) -> bool:
    normalized_mime_type = mime_type.split(";", 1)[0].strip().lower()
    return normalized_mime_type == "image/svg+xml" or artifact_path.suffix.lower() == ".svg"


def _render_svg_preview_pixmap(
    path: Path, *, max_width: int, max_height: int, device_pixel_ratio: float = 1.0,
) -> QPixmap:
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
    # Use the chart renderer's SVG text engine. QSvgRenderer resolves generic
    # fonts/styles differently from Vega and can push a right-hand legend past
    # the canvas. It is used above only to read the intrinsic canvas size.
    import vl_convert as vlc

    scale = min(target_size.width() / source_size.width(), target_size.height() / source_size.height())
    try:
        png = vlc.svg_to_png(path.read_text(encoding="utf-8"), scale=scale * device_pixel_ratio)
    except Exception as exc:
        report_exception(exc)
        return QPixmap()
    rendered = QImage.fromData(png)
    if rendered.isNull():
        return QPixmap()
    image = QImage(rendered.size(), QImage.Format_ARGB32_Premultiplied)
    image.fill(_ARTIFACT_PREVIEW_BACKGROUND)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        painter.drawImage(0, 0, rendered)
    finally:
        painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap


def _scale_artifact_preview_pixmap(
    pixmap: QPixmap, *, max_width: int, max_height: int, device_pixel_ratio: float = 1.0,
) -> QPixmap:
    target_size = _fit_artifact_preview_size(
        pixmap.deviceIndependentSize().toSize(), max_width=max_width, max_height=max_height,
    )
    scaled = pixmap.scaled(target_size * device_pixel_ratio, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(device_pixel_ratio)
    return scaled


def _fit_artifact_preview_size(source_size: QSize, *, max_width: int, max_height: int) -> QSize:
    source_width = max(1, source_size.width())
    source_height = max(1, source_size.height())
    scale = min(max_width / source_width, max_height / source_height, 1.0)
    return QSize(
        max(1, int(round(source_width * scale))),
        max(1, int(round(source_height * scale))),
    )
