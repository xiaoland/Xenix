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
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from xenix.resources import package_resource_path


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

        paper = QColor("#f6f7f3")
        graphite = QColor("#242429")
        accent = QColor("#ed6609")

        track_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        track_gradient.setColorAt(0.0, paper)
        track_gradient.setColorAt(1.0, QColor("#e5e8e1"))
        painter.setBrush(track_gradient)
        border = QColor(graphite)
        border.setAlpha(42)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 2, 2)

        inner = rect.adjusted(3, 3, -3, -3)
        segment_count = 30
        gap = 3.0
        segment_width = (inner.width() - gap * (segment_count - 1)) / segment_count
        scan_center = self._phase * (segment_count + 8) - 4

        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(segment_count):
            distance = abs(index - scan_center)
            intensity = max(0.16, 1.0 - distance / 5.0)
            color = QColor(graphite)
            if distance < 4.8:
                color = QColor(accent)
            color.setAlpha(int(44 + 188 * intensity))
            x = inner.left() + index * (segment_width + gap)
            segment = QRectF(x, inner.top(), segment_width, inner.height())
            painter.setBrush(color)
            painter.drawRect(segment)


class StartupSplash(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        flags = Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("startupSplash")
        self.setFixedSize(680, 400)

        self._stage = StartupStage.STARTING
        self._logo_renderer = QSvgRenderer(str(package_resource_path("app-icon.svg")), self)
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
        self._apply_label_color(self._stage_label, QColor("#242429"))
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        panel = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        panel_path = QPainterPath()
        panel_path.addRoundedRect(panel, 9, 9)

        self._draw_shell(painter, panel, panel_path)
        painter.setClipPath(panel_path)
        self._draw_signal_field(painter, panel)
        self._draw_status_bay(painter, panel)
        self._draw_brand(painter, panel)
        painter.setClipping(False)

        border = QColor("#242429")
        border.setAlpha(54)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(panel_path)

    def _draw_shell(self, painter: QPainter, panel: QRectF, panel_path: QPainterPath) -> None:
        background = QLinearGradient(panel.topLeft(), panel.bottomRight())
        background.setColorAt(0.0, QColor("#fbfbf8"))
        background.setColorAt(0.58, QColor("#f1f3ee"))
        background.setColorAt(1.0, QColor("#dfe5dd"))
        painter.fillPath(panel_path, background)

        sheen = QLinearGradient(QPointF(panel.left(), panel.top()), QPointF(panel.right(), panel.bottom()))
        highlight = QColor("#ed6609")
        highlight.setAlpha(32)
        transparent = QColor("#ed6609")
        transparent.setAlpha(0)
        sheen.setColorAt(0.0, highlight)
        sheen.setColorAt(0.42, transparent)
        painter.fillPath(panel_path, sheen)

    def _draw_signal_field(self, painter: QPainter, panel: QRectF) -> None:
        graphite = QColor("#242429")
        accent = QColor("#ed6609")
        green = QColor("#1f7a68")

        lane_pen = QColor(graphite)
        lane_pen.setAlpha(26)
        painter.setPen(QPen(lane_pen, 1))
        for index in range(6):
            y = panel.top() + 42 + index * 37
            painter.drawLine(QPointF(panel.left() + 210, y), QPointF(panel.right() - 42, y))

        node_pen = QColor(graphite)
        node_pen.setAlpha(48)
        painter.setPen(QPen(node_pen, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        nodes = [
            QPointF(panel.left() + 446, panel.top() + 74),
            QPointF(panel.left() + 514, panel.top() + 126),
            QPointF(panel.left() + 590, panel.top() + 88),
            QPointF(panel.left() + 558, panel.top() + 190),
        ]
        for start, end in zip(nodes, nodes[1:]):
            painter.drawLine(start, end)
        for index, point in enumerate(nodes):
            color = QColor(accent if index == 1 else green if index == 3 else graphite)
            color.setAlpha(122)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, 4.5, 4.5)

        accent_fill = QColor(accent)
        accent_fill.setAlpha(18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent_fill)
        painter.drawRoundedRect(QRectF(panel.right() - 176, panel.top() + 42, 116, 12), 6, 6)
        painter.drawRoundedRect(QRectF(panel.right() - 136, panel.top() + 214, 78, 12), 6, 6)

    def _draw_status_bay(self, painter: QPainter, panel: QRectF) -> None:
        bay = QRectF(panel.left() + 26, panel.bottom() - 82, panel.width() - 52, 62)
        bay_path = QPainterPath()
        bay_path.addRoundedRect(bay, 3, 3)
        bay_color = QColor("#ffffff")
        bay_color.setAlpha(228)
        painter.fillPath(bay_path, bay_color)
        border = QColor("#242429")
        border.setAlpha(48)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(bay_path)

        divider = QColor("#ed6609")
        divider.setAlpha(90)
        painter.setPen(QPen(divider, 1))
        painter.drawLine(QPointF(bay.left() + 14, bay.top() + 34), QPointF(bay.right() - 14, bay.top() + 34))

    def _draw_brand(self, painter: QPainter, panel: QRectF) -> None:
        mark_rect = QRectF(panel.left() + 48, panel.top() + 56, 138, 138)
        if self._logo_renderer.isValid():
            self._logo_renderer.render(painter, mark_rect)

        wordmark = self._xenix_vector_path()
        transform = QTransform()
        transform.translate(panel.left() + 210, panel.top() + 72)
        transform.scale(0.62, 0.62)
        wordmark = transform.map(wordmark)
        painter.fillPath(wordmark, QColor("#242429"))

        accent = QColor("#ed6609")
        graphite = QColor("#242429")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(panel.left() + 212, panel.top() + 148, 92, 6), 3, 3)
        graphite.setAlpha(190)
        painter.setBrush(graphite)
        painter.drawRoundedRect(QRectF(panel.left() + 316, panel.top() + 148, 34, 6), 3, 3)
        painter.setBrush(Qt.BrushStyle.NoBrush)

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
