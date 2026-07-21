from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..services.knowledge_import_service import (
    SUPPORTED_KNOWLEDGE_SUFFIXES,
    KnowledgeImportService,
)
from ..services.paddle_ocr_service import PaddleOcrDeploymentService


class _BackgroundSignals(QObject):
    import_finished = Signal(str, bool, str)
    ocr_setup_finished = Signal(bool, str)
    ocr_setup_phase = Signal(str)


class KnowledgeImportQueueDialog(QDialog):
    def __init__(self, import_service: KnowledgeImportService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._service = import_service
        self._list = QListWidget(self)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(self._close_button)
        self.resize(620, 360)
        self.retranslate_ui()

    def refresh(self) -> None:
        self._list.clear()
        for item in self._service.list_imports():
            detail = item.status
            if item.reused_existing:
                detail += " · reused"
            if item.error_summary:
                detail += f" · {item.error_summary}"
            self._list.addItem(f"{item.file_name} — {detail}")

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Knowledge Import Queue"))
        self._close_button.setText(self.tr("Close"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)


class KnowledgeWorkspaceDialog(QDialog):
    def __init__(
        self,
        *,
        import_service: KnowledgeImportService,
        ocr_deployment: PaddleOcrDeploymentService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._import_service = import_service
        self._ocr_deployment = ocr_deployment
        self._queue_dialog: KnowledgeImportQueueDialog | None = None
        self._signals = _BackgroundSignals(self)
        self._signals.import_finished.connect(self._on_import_finished)
        self._signals.ocr_setup_phase.connect(self._on_ocr_phase)
        self._signals.ocr_setup_finished.connect(self._on_ocr_setup_finished)

        self._description = QLabel(self)
        self._description.setWordWrap(True)
        self._ocr_status = QLabel(self)
        self._import_button = QPushButton(self)
        self._queue_button = QPushButton(self)
        self._ocr_button = QPushButton(self)
        self._import_button.clicked.connect(self._choose_files)
        self._queue_button.clicked.connect(self.open_import_queue)
        self._ocr_button.clicked.connect(self._install_ocr)
        buttons = QHBoxLayout()
        buttons.addWidget(self._import_button)
        buttons.addWidget(self._queue_button)
        buttons.addStretch(1)
        buttons.addWidget(self._ocr_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._description)
        layout.addWidget(self._ocr_status)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.resize(760, 440)
        self.retranslate_ui()
        self._refresh_ocr_status()

    def open_import_queue(self) -> None:
        if self._queue_dialog is None:
            self._queue_dialog = KnowledgeImportQueueDialog(self._import_service, self)
        self._queue_dialog.refresh()
        self._queue_dialog.show()
        self._queue_dialog.raise_()
        self._queue_dialog.activateWindow()

    def _choose_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            self.tr("Import Knowledge"),
            "",
            self.tr("Knowledge documents (*.txt *.docx *.doc *.ppt *.pptx *.pdf)"),
        )
        accepted = _accepted_import_paths(paths)
        if not accepted:
            return
        self.open_import_queue()
        for path in accepted:
            threading.Thread(
                target=self._run_import,
                args=(path,),
                name="xenix-knowledge-import",
                daemon=True,
            ).start()

    def _run_import(self, path: Path) -> None:
        try:
            result = self._import_service.import_file(path)
            message = "reused" if result.reused_existing else "imported"
            self._signals.import_finished.emit(path.name, True, message)
        except Exception as exc:
            self._signals.import_finished.emit(path.name, False, str(exc))

    def _on_import_finished(self, file_name: str, succeeded: bool, message: str) -> None:
        if self._queue_dialog is not None:
            self._queue_dialog.refresh()
        if not succeeded:
            QMessageBox.warning(self, self.tr("Knowledge Import Failed"), f"{file_name}: {message}")

    def _install_ocr(self) -> None:
        self._ocr_button.setEnabled(False)
        threading.Thread(
            target=self._run_ocr_setup,
            name="xenix-paddle-ocr-setup",
            daemon=True,
        ).start()

    def _run_ocr_setup(self) -> None:
        try:
            self._ocr_deployment.install(self._signals.ocr_setup_phase.emit)
            self._signals.ocr_setup_finished.emit(True, "")
        except Exception as exc:
            self._signals.ocr_setup_finished.emit(False, str(exc))

    def _on_ocr_phase(self, phase: str) -> None:
        self._ocr_status.setText(self.tr("Local OCR setup: %1").replace("%1", phase))

    def _on_ocr_setup_finished(self, succeeded: bool, message: str) -> None:
        self._ocr_button.setEnabled(True)
        self._refresh_ocr_status()
        if not succeeded:
            QMessageBox.warning(self, self.tr("Local OCR Setup Failed"), message)

    def _refresh_ocr_status(self) -> None:
        status = self._ocr_deployment.status()
        if status.installed and status.models_ready:
            text = self.tr("Local PaddleOCR is ready")
        elif status.installed:
            text = self.tr("Local PaddleOCR runtime is installed; models are not ready")
        else:
            text = self.tr("Local PaddleOCR is not installed")
        self._ocr_status.setText(text)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Knowledge Workspace"))
        self._description.setText(
            self.tr(
                "Import TXT, DOCX, DOC, PPTX, PPT, or PDF documents. "
                "Xenix indexes bounded evidence for Agent analysis."
            )
        )
        self._import_button.setText(self.tr("Import documents"))
        self._queue_button.setText(self.tr("Import queue"))
        self._ocr_button.setText(self.tr("Set up local OCR"))
        if self._queue_dialog is not None:
            self._queue_dialog.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
            self._refresh_ocr_status()
        super().changeEvent(event)


def _accepted_import_paths(paths: list[str]) -> list[Path]:
    accepted: list[Path] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        key = str(path).casefold()
        if path.suffix.casefold() not in SUPPORTED_KNOWLEDGE_SUFFIXES or key in seen:
            continue
        seen.add(key)
        accepted.append(path)
    return accepted
