from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPalette,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from ..resources import package_resource_path


class StartupStage(Enum):
    STARTING = "starting"
    PREPARING_APP_DATA = "preparing_app_data"
    INITIALIZING_LOGGING = "initializing_logging"
    INITIALIZING_STORAGE = "initializing_storage"
    LOADING_WORKBENCH = "loading_workbench"
    READY = "ready"


class StartupPulseBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setMinimumWidth(240)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self._advance)

    def sizeHint(self) -> QSize:
        return QSize(560, 14)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _advance(self) -> None:
        self._phase = (self._phase + 0.022) % 1.0
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        track_gradient.setColorAt(0.0, QColor("#0a1724"))
        track_gradient.setColorAt(0.5, QColor("#132b3e"))
        track_gradient.setColorAt(1.0, QColor("#07101a"))
        painter.setBrush(track_gradient)
        painter.setPen(QPen(QColor(121, 158, 186, 130), 1))
        painter.drawRoundedRect(rect, 2, 2)

        inner = rect.adjusted(3, 3, -3, -3)
        segment_count = 28
        gap = 3.0
        segment_width = (inner.width() - gap * (segment_count - 1)) / segment_count
        scan_center = self._phase * (segment_count + 8) - 4

        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(segment_count):
            distance = abs(index - scan_center)
            intensity = max(0.16, 1.0 - distance / 5.0)
            color = QColor("#315d7d")
            if distance < 4.8:
                color = QColor("#83c7ff")
            color.setAlpha(int(70 + 160 * intensity))
            x = inner.left() + index * (segment_width + gap)
            segment = QRectF(x, inner.top(), segment_width, inner.height())
            painter.setBrush(color)
            painter.drawRect(segment)


class StartupSplash(QWidget):
    def __init__(self, *, logo_path: Path | None = None, parent: QWidget | None = None) -> None:
        flags = Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("startupSplash")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(680, 400)

        self._stage = StartupStage.STARTING
        self._logo_path = logo_path or package_resource_path("logo.png")
        self._logo_pixmap = QPixmap(str(self._logo_path))
        self._stage_label = QLabel(parent=self)
        self._pulse_bar = StartupPulseBar(parent=self)

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        self._stage_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._stage_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        stage_font = QFont(self._stage_label.font())
        stage_font.setFamilies(["Segoe UI", "Arial", "Sans Serif"])
        stage_font.setPointSize(10)
        stage_font.setBold(True)
        self._stage_label.setFont(stage_font)
        self._apply_label_color(self._stage_label, QColor("#d9ecff"))
        self._position_status_controls()

    def resizeEvent(self, event) -> None:
        self._position_status_controls()
        super().resizeEvent(event)

    def _position_status_controls(self) -> None:
        width = self.width()
        height = self.height()
        self._stage_label.setGeometry(42, height - 65, width - 84, 22)
        self._pulse_bar.setGeometry(42, height - 36, width - 84, 14)

    def show_centered(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available_geometry = screen.availableGeometry()
            self.move(available_geometry.center() - self.rect().center())
        self.show()
        self.raise_()

    def set_stage(self, stage: StartupStage) -> None:
        self._stage = stage
        self._stage_label.setText(self._stage_text(stage))
        self.update()

    def retranslate_ui(self) -> None:
        self._stage_label.setText(self._stage_text(self._stage))
        self.update()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        panel = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        panel_path = QPainterPath()
        panel_path.addRoundedRect(panel, 9, 9)

        self._draw_shell(painter, panel, panel_path)
        painter.setClipPath(panel_path)
        self._draw_grid(painter, panel)
        self._draw_light_fields(painter, panel)
        self._draw_cad_geometry(painter, panel)
        self._draw_status_bay(painter, panel)
        self._draw_title(painter, panel)
        self._draw_signature(painter, panel)
        painter.setClipping(False)

        painter.setPen(QPen(QColor("#7594ad"), 1))
        painter.drawPath(panel_path)

    def _draw_shell(self, painter: QPainter, panel: QRectF, panel_path: QPainterPath) -> None:
        background = QLinearGradient(panel.topLeft(), panel.bottomRight())
        background.setColorAt(0.0, QColor("#1d2d39"))
        background.setColorAt(0.28, QColor("#0b1723"))
        background.setColorAt(0.68, QColor("#1c3345"))
        background.setColorAt(1.0, QColor("#060b12"))
        painter.fillPath(panel_path, background)

        bevel = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        bevel.setColorAt(0.0, QColor(255, 255, 255, 52))
        bevel.setColorAt(0.16, QColor(255, 255, 255, 8))
        bevel.setColorAt(1.0, QColor(0, 0, 0, 72))
        painter.fillPath(panel_path, bevel)

        top_band = QRectF(panel.left(), panel.top(), panel.width(), 46)
        band = QLinearGradient(top_band.topLeft(), top_band.bottomLeft())
        band.setColorAt(0.0, QColor(138, 162, 181, 92))
        band.setColorAt(1.0, QColor(20, 44, 61, 18))
        painter.fillRect(top_band, band)

    def _draw_grid(self, painter: QPainter, panel: QRectF) -> None:
        vanishing = QPointF(panel.left() + panel.width() * 0.82, panel.top() + panel.height() * 0.12)
        floor_top = panel.top() + panel.height() * 0.47
        floor_bottom = panel.bottom() - 72

        painter.setPen(QPen(QColor(94, 151, 185, 62), 1))
        for index in range(18):
            x = panel.left() - 70 + index * 46
            painter.drawLine(QPointF(x, floor_bottom), vanishing)

        for index in range(12):
            t = index / 11
            y = floor_top + (floor_bottom - floor_top) * (t * t)
            left = panel.left() + 18 + 24 * index
            right = panel.right() - 36 - 10 * index
            painter.drawLine(QPointF(left, y), QPointF(right, y - 20 * (1 - t)))

        painter.setPen(QPen(QColor(141, 196, 230, 78), 1))
        painter.drawLine(QPointF(panel.left() + 32, floor_bottom), QPointF(panel.right() - 28, floor_top - 28))
        painter.drawLine(QPointF(panel.left() + 88, floor_bottom + 6), QPointF(panel.right() - 18, floor_top + 34))

    def _draw_light_fields(self, painter: QPainter, panel: QRectF) -> None:
        beam = QLinearGradient(QPointF(panel.left() + 90, panel.top()), QPointF(panel.right(), panel.top() + 170))
        beam.setColorAt(0.0, QColor(36, 83, 113, 0))
        beam.setColorAt(0.45, QColor(100, 170, 218, 62))
        beam.setColorAt(1.0, QColor(17, 38, 56, 0))

        path = QPainterPath()
        path.moveTo(panel.left() + 28, panel.top() + 54)
        path.lineTo(panel.right(), panel.top() + 4)
        path.lineTo(panel.right(), panel.top() + 112)
        path.lineTo(panel.left() + 156, panel.top() + 226)
        path.closeSubpath()
        painter.fillPath(path, beam)

        painter.setPen(QPen(QColor(165, 219, 255, 80), 1))
        for offset in (0, 38, 82):
            painter.drawLine(
                QPointF(panel.left() + 90 + offset, panel.top() + 36),
                QPointF(panel.right() - 38 + offset * 0.12, panel.top() + 150 + offset * 0.22),
            )

    def _draw_cad_geometry(self, painter: QPainter, panel: QRectF) -> None:
        painter.save()
        painter.setPen(QPen(QColor(111, 183, 220, 86), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        left = panel.left() + 44
        top = panel.top() + 72
        painter.drawRect(QRectF(left, top, 168, 76))
        painter.drawLine(QPointF(left, top + 38), QPointF(left + 168, top + 38))
        painter.drawLine(QPointF(left + 84, top), QPointF(left + 84, top + 76))
        painter.drawEllipse(QRectF(left + 27, top + 9, 56, 56))
        painter.drawEllipse(QRectF(left + 104, top + 19, 36, 36))

        painter.setPen(QPen(QColor(159, 218, 246, 78), 1))
        polyline = [
            QPointF(panel.left() + 72, panel.top() + 230),
            QPointF(panel.left() + 144, panel.top() + 188),
            QPointF(panel.left() + 230, panel.top() + 214),
            QPointF(panel.left() + 288, panel.top() + 168),
            QPointF(panel.left() + 358, panel.top() + 196),
        ]
        for start, end in zip(polyline, polyline[1:]):
            painter.drawLine(start, end)
            painter.drawEllipse(QRectF(start.x() - 3, start.y() - 3, 6, 6))
        last = polyline[-1]
        painter.drawEllipse(QRectF(last.x() - 3, last.y() - 3, 6, 6))

        painter.setPen(QPen(QColor(80, 137, 178, 56), 1))
        for index in range(7):
            painter.drawLine(
                QPointF(panel.left() + 26 + index * 32, panel.top() + 280),
                QPointF(panel.left() + 190 + index * 28, panel.top() + 330),
            )
        painter.restore()

    def _draw_status_bay(self, painter: QPainter, panel: QRectF) -> None:
        bay = QRectF(panel.left() + 22, panel.bottom() - 88, panel.width() - 44, 68)
        bay_path = QPainterPath()
        bay_path.addRoundedRect(bay, 3, 3)
        bay_gradient = QLinearGradient(bay.topLeft(), bay.bottomLeft())
        bay_gradient.setColorAt(0.0, QColor(18, 35, 50, 220))
        bay_gradient.setColorAt(1.0, QColor(6, 12, 21, 235))
        painter.fillPath(bay_path, bay_gradient)
        painter.setPen(QPen(QColor(116, 160, 191, 120), 1))
        painter.drawPath(bay_path)

        painter.setPen(QPen(QColor(123, 180, 220, 70), 1))
        painter.drawLine(QPointF(bay.left() + 14, bay.top() + 34), QPointF(bay.right() - 14, bay.top() + 34))

    def _draw_title(self, painter: QPainter, panel: QRectF) -> None:
        path = self._xenix_vector_path()

        transform = QTransform()
        transform.translate(panel.left(), panel.top() + 206)
        transform.scale(1.45, 1.45)
        transform.shear(-0.18, 0.0)
        transform.rotate(-5.2)
        face = transform.map(path)
        face_bounds = face.boundingRect()
        face = face.translated(
            panel.right() - 30 - face_bounds.right(),
            panel.top() + 54 - face_bounds.top(),
        )

        anchor = QPointF(panel.right() - 52, panel.top() + 40)
        for index in range(28, 0, -1):
            t = index / 28
            depth_transform = QTransform()
            depth_transform.translate(anchor.x(), anchor.y())
            depth_transform.scale(1.0 - 0.085 * t, 1.0 - 0.085 * t)
            depth_transform.translate(-anchor.x(), -anchor.y())
            depth_transform.translate(72 * t, -42 * t)
            depth_path = depth_transform.map(face)
            shade = QColor(4, 13, 23, int(120 + 85 * t))
            painter.fillPath(depth_path, shade)
            if index % 5 == 0:
                painter.setPen(QPen(QColor(96, 153, 190, int(42 + 45 * t)), 1))
                painter.drawPath(depth_path)

        face_bounds = face.boundingRect()
        fill = QLinearGradient(face_bounds.topLeft(), face_bounds.bottomRight())
        fill.setColorAt(0.0, QColor("#fbfdff"))
        fill.setColorAt(0.24, QColor("#b7d4e8"))
        fill.setColorAt(0.58, QColor("#5e91b8"))
        fill.setColorAt(1.0, QColor("#13273a"))
        painter.fillPath(face, fill)

        painter.setPen(QPen(QColor("#ddf3ff"), 1.6))
        painter.drawPath(face)
        painter.setPen(QPen(QColor(10, 24, 38, 150), 1))
        painter.drawPath(face.translated(2.0, 2.2))

    def _xenix_vector_path(self) -> QPainterPath:
        skeleton = QPainterPath()
        letter_width = 62.0
        letter_gap = 16.0
        height = 100.0

        def x_offset(index: int) -> float:
            return index * (letter_width + letter_gap)

        def line(x1: float, y1: float, x2: float, y2: float) -> None:
            skeleton.moveTo(x1, y1)
            skeleton.lineTo(x2, y2)

        x = x_offset(0)
        line(x, 0, x + letter_width, height)
        line(x + letter_width, 0, x, height)

        x = x_offset(1)
        line(x, 0, x, height)
        line(x, 0, x + letter_width, 0)
        line(x, height / 2, x + letter_width * 0.82, height / 2)
        line(x, height, x + letter_width, height)

        x = x_offset(2)
        line(x, height, x, 0)
        line(x, 0, x + letter_width, height)
        line(x + letter_width, height, x + letter_width, 0)

        x = x_offset(3)
        line(x, 0, x + letter_width, 0)
        line(x + letter_width / 2, 0, x + letter_width / 2, height)
        line(x, height, x + letter_width, height)

        x = x_offset(4)
        line(x, 0, x + letter_width, height)
        line(x + letter_width, 0, x, height)

        stroker = QPainterPathStroker()
        stroker.setWidth(13.5)
        stroker.setCapStyle(Qt.PenCapStyle.SquareCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        return stroker.createStroke(skeleton)

    def _draw_signature(self, painter: QPainter, panel: QRectF) -> None:
        painter.save()
        font = QFont(self.font())
        font.setFamilies(["Segoe UI", "Arial", "Sans Serif"])
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(177, 215, 238, 150), 1))
        painter.drawText(QRectF(panel.left() + 38, panel.top() + 28, 240, 20), self.tr("Business ML Workbench"))

        if not self._logo_pixmap.isNull():
            logo = self._logo_pixmap.scaled(
                28,
                28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.setOpacity(0.78)
            painter.drawPixmap(int(panel.left() + 38), int(panel.top() + 54), logo)
            painter.setOpacity(1.0)
        painter.restore()

    def _stage_text(self, stage: StartupStage) -> str:
        stage_text = {
            StartupStage.STARTING: self.tr("Starting Xenix..."),
            StartupStage.PREPARING_APP_DATA: self.tr("Preparing application data..."),
            StartupStage.INITIALIZING_LOGGING: self.tr("Initializing runtime logging..."),
            StartupStage.INITIALIZING_STORAGE: self.tr("Initializing local database..."),
            StartupStage.LOADING_WORKBENCH: self.tr("Loading workbench..."),
            StartupStage.READY: self.tr("Ready."),
        }
        return stage_text[stage]

    @staticmethod
    def _apply_label_color(label: QLabel, color: QColor) -> None:
        palette = QPalette(label.palette())
        palette.setColor(QPalette.ColorRole.WindowText, color)
        label.setPalette(palette)
