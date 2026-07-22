from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..services.paddle_ocr_service import (
    PaddleOcrDeploymentService,
    PaddleOcrStatus,
)


class OcrStatusSignals(QObject):
    finished = Signal(int, object)


class OcrStatusTask(QRunnable):
    def __init__(self, deployment: PaddleOcrDeploymentService, generation: int) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self._deployment = deployment
        self._generation = generation
        self.signals = OcrStatusSignals()

    def run(self) -> None:
        try:
            status = self._deployment.status()
        except Exception:
            status = PaddleOcrStatus(False, False, "health_check_failed")
        self.signals.finished.emit(self._generation, status)


class OcrInstallSignals(QObject):
    phase = Signal(int, str)
    finished = Signal(int, object)


class OcrInstallTask(QRunnable):
    def __init__(self, deployment: PaddleOcrDeploymentService, generation: int) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self._deployment = deployment
        self._generation = generation
        self.signals = OcrInstallSignals()

    def run(self) -> None:
        try:
            status = self._deployment.install(
                lambda phase: self.signals.phase.emit(self._generation, phase)
            )
        except Exception:
            status = None
        self.signals.finished.emit(self._generation, status)


__all__ = ["OcrInstallTask", "OcrStatusTask"]
