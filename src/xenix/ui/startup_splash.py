from __future__ import annotations

from enum import Enum

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
    QTransform,
)
from PySide6.QtWidgets import QApplication, QLabel, QWidget


class StartupStage(Enum):
    STARTING = "starting"
    PREPARING_APP_DATA = "preparing_app_data"
    LOADING_RUNTIME = "loading_runtime"
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

        deep = QColor("#07111b")
        steel = QColor("#9fb7c8")
        accent = QColor("#4da3d8")

        track_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        track_gradient.setColorAt(0.0, deep.lighter(118))
        track_gradient.setColorAt(1.0, deep)
        painter.setBrush(track_gradient)
        steel_border = QColor(steel)
        steel_border.setAlpha(120)
        painter.setPen(QPen(steel_border, 1))
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
            color = QColor(steel)
            if distance < 4.8:
                color = QColor(accent)
            color.setAlpha(int(70 + 160 * intensity))
            x = inner.left() + index * (segment_width + gap)
            segment = QRectF(x, inner.top(), segment_width, inner.height())
            painter.setBrush(color)
            painter.drawRect(segment)


class StartupSplash(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        flags = Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("startupSplash")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(680, 400)

        self._stage = StartupStage.STARTING
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
        self._apply_label_color(self._stage_label, QColor("#9fb7c8"))
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
        self._draw_status_bay(painter, panel)
        self._draw_title(painter, panel)
        painter.setClipping(False)

        border = QColor("#9fb7c8")
        border.setAlpha(150)
        painter.setPen(QPen(border, 1))
        painter.drawPath(panel_path)

    def _draw_shell(self, painter: QPainter, panel: QRectF, panel_path: QPainterPath) -> None:
        deep = QColor("#07111b")
        steel = QColor("#9fb7c8")

        background = QLinearGradient(panel.topLeft(), panel.bottomRight())
        background.setColorAt(0.0, deep.lighter(150))
        background.setColorAt(0.46, deep)
        background.setColorAt(1.0, deep.darker(145))
        painter.fillPath(panel_path, background)

        sheen = QLinearGradient(QPointF(panel.left(), panel.top()), QPointF(panel.right(), panel.top() + 120))
        highlight = QColor(steel)
        highlight.setAlpha(34)
        transparent = QColor(steel)
        transparent.setAlpha(0)
        sheen.setColorAt(0.0, highlight)
        sheen.setColorAt(1.0, transparent)
        painter.fillPath(panel_path, sheen)

    def _draw_grid(self, painter: QPainter, panel: QRectF) -> None:
        steel = QColor("#9fb7c8")
        accent = QColor("#4da3d8")
        vanishing = QPointF(panel.left() + panel.width() * 0.82, panel.top() + panel.height() * 0.12)
        floor_top = panel.top() + panel.height() * 0.52
        floor_bottom = panel.bottom() - 72

        grid_pen_color = QColor(steel)
        grid_pen_color.setAlpha(42)
        painter.setPen(QPen(grid_pen_color, 1))
        for index in range(10):
            x = panel.left() - 60 + index * 76
            painter.drawLine(QPointF(x, floor_bottom), vanishing)

        for index in range(7):
            t = index / 6
            y = floor_top + (floor_bottom - floor_top) * (t * t)
            painter.drawLine(QPointF(panel.left() + 26 + 18 * index, y), QPointF(panel.right() - 34 - 8 * index, y - 16 * (1 - t)))

        accent_line = QColor(accent)
        accent_line.setAlpha(74)
        painter.setPen(QPen(accent_line, 1))
        painter.drawLine(QPointF(panel.left() + 40, floor_bottom), QPointF(panel.right() - 30, floor_top - 20))

    def _draw_status_bay(self, painter: QPainter, panel: QRectF) -> None:
        deep = QColor("#07111b")
        steel = QColor("#9fb7c8")
        bay = QRectF(panel.left() + 26, panel.bottom() - 82, panel.width() - 52, 62)
        bay_path = QPainterPath()
        bay_path.addRoundedRect(bay, 3, 3)
        bay_color = QColor(deep)
        bay_color.setAlpha(218)
        painter.fillPath(bay_path, bay_color)
        border = QColor(steel)
        border.setAlpha(100)
        painter.setPen(QPen(border, 1))
        painter.drawPath(bay_path)

        divider = QColor(steel)
        divider.setAlpha(42)
        painter.setPen(QPen(divider, 1))
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
            panel.top() + 70 - face_bounds.top(),
        )

        anchor = QPointF(panel.right() - 52, panel.top() + 40)
        deep = QColor("#07111b")
        steel = QColor("#9fb7c8")
        accent = QColor("#4da3d8")

        for index in range(10, 0, -1):
            t = index / 10
            depth_transform = QTransform()
            depth_transform.translate(anchor.x(), anchor.y())
            depth_transform.scale(1.0 - 0.055 * t, 1.0 - 0.055 * t)
            depth_transform.translate(-anchor.x(), -anchor.y())
            depth_transform.translate(44 * t, -26 * t)
            depth_path = depth_transform.map(face)
            shade = QColor(deep)
            shade.setAlpha(int(128 + 72 * t))
            painter.fillPath(depth_path, shade)

        face_bounds = face.boundingRect()
        fill = QLinearGradient(face_bounds.topLeft(), face_bounds.bottomRight())
        fill.setColorAt(0.0, steel.lighter(132))
        fill.setColorAt(0.58, steel)
        fill.setColorAt(1.0, accent.darker(122))
        painter.fillPath(face, fill)

        edge = QColor(steel)
        edge.setAlpha(220)
        painter.setPen(QPen(edge, 1.4))
        painter.drawPath(face)

    def _xenix_vector_path(self) -> QPainterPath:
        skeleton = QPainterPath()
        height = 100.0

        def line(x1: float, y1: float, x2: float, y2: float) -> None:
            skeleton.moveTo(x1, y1)
            skeleton.lineTo(x2, y2)

        x = 0.0
        line(x, 0, x + 70, height)
        line(x + 70, 0, x, height)

        x += 92
        line(x + 4, 54, x + 20, 42)
        line(x + 20, 42, x + 58, 42)
        line(x + 58, 42, x + 58, 68)
        line(x + 58, 68, x + 14, 68)
        line(x + 14, 68, x + 14, 88)
        line(x + 14, 88, x + 58, 88)

        x += 82
        line(x, height, x, 44)
        line(x, 44, x + 50, 44)
        line(x + 50, 44, x + 66, 60)
        line(x + 66, 60, x + 66, height)

        x += 82
        line(x + 14, 44, x + 14, height)
        dot = QPainterPath()
        dot.addRect(QRectF(x + 6, 14, 17, 17))

        x += 46
        line(x + 2, 44, x + 58, height)
        line(x + 58, 44, x + 2, height)

        stroker = QPainterPathStroker()
        stroker.setWidth(12.5)
        stroker.setCapStyle(Qt.PenCapStyle.SquareCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        path = stroker.createStroke(skeleton)
        path.addPath(dot)
        return path

    def _stage_text(self, stage: StartupStage) -> str:
        stage_text = {
            StartupStage.STARTING: self.tr("Starting Xenix..."),
            StartupStage.PREPARING_APP_DATA: self.tr("Preparing application data..."),
            StartupStage.LOADING_RUNTIME: self.tr("Loading runtime components..."),
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
