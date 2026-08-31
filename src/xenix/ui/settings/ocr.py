from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QMessageBox, QPushButton, QWidget

from ...services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from ..ocr_deployment_tasks import OcrInstallTask, OcrStatusTask, PaddleOcrDeploymentPort
from ..semantic_identity import identify


class OcrSettingsCard(QFrame):
    """Knowledge-tab OCR presentation plus its short-lived asynchronous work."""

    def __init__(self, deployment: PaddleOcrDeploymentPort | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._deployment = deployment
        self._thread_pool = QThreadPool(self)
        self._shutdown = False
        self._active = False
        self._generation = 0
        self._status: PaddleOcrStatus | None = None
        self._status_task: OcrStatusTask | None = None
        self._install_task: OcrInstallTask | None = None
        self._title_label = QLabel()
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._setup_button = QPushButton()
        identify(self._setup_button, "settings.knowledge.ocr.setup")
        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addRow(self._title_label)
        layout.addRow(self._status_label)
        layout.addRow(self._setup_button)
        self._setup_button.clicked.connect(self._install)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._title_label.setText(QCoreApplication.translate("SettingsDialog", "OCR"))
        self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Set up local PaddleOCR"))
        self._render_status()

    def activate(self) -> None:
        if self._shutdown:
            return
        self._active = True
        self._generation += 1
        self._render_status()
        self._schedule_status_probe()

    @property
    def status(self) -> PaddleOcrStatus | None:
        return self._status

    def deactivate(self) -> None:
        if self._active:
            self._generation += 1
        self._active = False

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self.deactivate()
        self._thread_pool.waitForDone()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _install(self) -> None:
        if self._shutdown or self._deployment is None or self._install_task is not None:
            return
        self._setup_button.setEnabled(False)
        task = OcrInstallTask(self._deployment, self._generation)
        task.signals.phase.connect(self._on_phase)
        task.signals.finished.connect(self._on_install_finished)
        self._install_task = task
        self._thread_pool.start(task)

    def _schedule_status_probe(self) -> None:
        if (
            self._shutdown
            or not self._active
            or self._deployment is None
            or self._status_task is not None
            or self._install_task is not None
        ):
            return
        task = OcrStatusTask(self._deployment, self._generation)
        task.signals.finished.connect(self._on_status_finished)
        self._status_task = task
        self._thread_pool.start(task)

    def _on_phase(self, generation: int, phase: str) -> None:
        if generation != self._generation or not self._active:
            return
        messages = {
            "downloading_bundle": QCoreApplication.translate("SettingsDialog", "Downloading OCR component"),
            "extracting_bundle": QCoreApplication.translate("SettingsDialog", "Unpacking OCR component"),
            "verifying_bundle": QCoreApplication.translate("SettingsDialog", "Verifying OCR component"),
            "self_testing": QCoreApplication.translate("SettingsDialog", "Testing OCR component"),
            "activating_bundle": QCoreApplication.translate("SettingsDialog", "Activating OCR component"),
            "ready": QCoreApplication.translate("SettingsDialog", "Ready"),
        }
        self._status_label.setText(
            QCoreApplication.translate("SettingsDialog", "Local OCR setup: %1").replace(
                "%1", messages.get(phase, QCoreApplication.translate("SettingsDialog", "Preparing local OCR"))
            )
        )

    def _on_install_finished(self, generation: int, status: PaddleOcrStatus) -> None:
        self._install_task = None
        self._status = status
        if generation != self._generation or not self._active:
            if self._active:
                self._schedule_status_probe()
            return
        self._render_status()
        if status.state is PaddleOcrState.FAILED:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("SettingsDialog", "Local OCR Setup Failed"),
                self._failure_message(status.reason_code),
            )

    def _on_status_finished(self, generation: int, status: PaddleOcrStatus) -> None:
        self._status_task = None
        if generation != self._generation or not self._active:
            if self._active:
                self._schedule_status_probe()
            return
        self._status = status
        self._render_status()

    def _render_status(self) -> None:
        status = self._status
        if self._deployment is None:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Local PaddleOCR service is unavailable"),
                False,
            )
        elif status is None:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Checking local PaddleOCR status"),
                self._install_task is None,
            )
        elif status.state is PaddleOcrState.READY:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Local PaddleOCR is ready"),
                self._install_task is None,
            )
            self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Reinstall local PaddleOCR"))
        elif status.state is PaddleOcrState.REPAIR_REQUIRED:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Local PaddleOCR requires repair"),
                self._install_task is None,
            )
            self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Repair local PaddleOCR"))
        elif status.state in {PaddleOcrState.INSTALLING, PaddleOcrState.CHECKING}:
            text, enabled = QCoreApplication.translate("SettingsDialog", "Preparing local PaddleOCR"), False
            self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Preparing local PaddleOCR"))
        elif status.state is PaddleOcrState.FAILED:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Local PaddleOCR setup needs attention"),
                self._install_task is None,
            )
            self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Try local PaddleOCR setup again"))
        else:
            text, enabled = (
                QCoreApplication.translate("SettingsDialog", "Local PaddleOCR is not installed"),
                self._install_task is None,
            )
            self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Set up local PaddleOCR"))
        self._status_label.setText(text)
        self._setup_button.setEnabled(enabled)

    @staticmethod
    def _failure_message(reason_code: str | None) -> str:
        if reason_code == "knowledge_ocr_catalog_unavailable":
            return QCoreApplication.translate(
                "SettingsDialog", "Local OCR is unavailable in this build."
            )
        if reason_code == "knowledge_ocr_download_unavailable":
            return QCoreApplication.translate(
                "SettingsDialog", "Local OCR download source is unavailable."
            )
        if reason_code == "knowledge_ocr_download_failed":
            return QCoreApplication.translate(
                "SettingsDialog", "Local OCR component could not be downloaded."
            )
        if reason_code == "knowledge_ocr_bundle_source_unavailable":
            return QCoreApplication.translate(
                "SettingsDialog", "Local OCR bundle source is unavailable."
            )
        if reason_code in {
            "knowledge_ocr_bundle_source_mismatch",
            "knowledge_ocr_bundle_integrity_failed",
            "knowledge_ocr_bundle_invalid",
        }:
            return QCoreApplication.translate("SettingsDialog", "Local OCR component failed integrity verification.")
        if reason_code in {
            "knowledge_ocr_self_test_failed",
            "knowledge_ocr_initialize_failed",
            "knowledge_ocr_worker_incompatible",
        }:
            return QCoreApplication.translate("SettingsDialog", "Local OCR component failed its self-test.")
        return QCoreApplication.translate(
            "SettingsDialog", "Local OCR setup could not be completed."
        )
