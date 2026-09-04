from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQuick import QQuickView

from xenix.resources import package_resource_path


_STARTUP_FONT_FILES = (
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
    Path("C:/Windows/Fonts/courbd.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)
_STARTUP_FONTS_LOADED = False


class StartupStage(Enum):
    STARTING = "starting"
    PREPARING_APP_DATA = "preparing_app_data"
    LOADING_RUNTIME = "loading_runtime"
    INITIALIZING_LOGGING = "initializing_logging"
    INITIALIZING_STORAGE = "initializing_storage"
    LOADING_WORKBENCH = "loading_workbench"
    READY = "ready"


class StartupSplash(QQuickView):
    """Bootstrap window whose pulse is rendered independently of the GUI thread."""

    def __init__(self) -> None:
        super().__init__()
        self._stage = StartupStage.STARTING
        self._ensure_text_fonts_loaded()
        self.setFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)
        self.setSource(QUrl.fromLocalFile(str(package_resource_path("startup-splash.qml"))))
        if self.status() == QQuickView.Status.Error:
            details = "; ".join(error.toString() for error in self.errors())
            raise RuntimeError(f"Failed to load the startup splash scene: {details}")
        self.retranslate_ui()

    def show_centered(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available_geometry = screen.availableGeometry()
            self.setPosition(
                available_geometry.center()
                - QPoint(self.width() // 2, self.height() // 2)
            )
        self.show()
        self.raise_()

    def set_stage(self, stage: StartupStage) -> None:
        self._stage = stage
        self._set_stage_text(self._stage_text(stage))

    def retranslate_ui(self) -> None:
        self._set_stage_text(self._stage_text(self._stage))

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.LanguageChange and hasattr(self, "_stage"):
            self.retranslate_ui()
        return super().event(event)

    def _set_stage_text(self, text: str) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("stageText", text)

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
    def _ensure_text_fonts_loaded() -> None:
        global _STARTUP_FONTS_LOADED
        if _STARTUP_FONTS_LOADED or QFontDatabase.families():
            _STARTUP_FONTS_LOADED = True
            return
        for font_path in _STARTUP_FONT_FILES:
            if font_path.is_file():
                QFontDatabase.addApplicationFont(str(font_path))
        _STARTUP_FONTS_LOADED = True
