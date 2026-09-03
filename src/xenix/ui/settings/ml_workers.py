"""ML workers tab content widget: summary and SSH worker setup entry."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QWidget

from ...services.ml.worker_settings import MLWorkerKind, MLWorkerSettingsService
from ..semantic_identity import identify
from ..ssh_worker_setup_wizard import SshWorkerSetupWizard


class MLWorkers(QWidget):
    """ML worker summary plus the guarded SSH worker setup entry."""

    worker_saved = Signal()

    def __init__(
        self,
        ml_worker_settings_service: MLWorkerSettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = ml_worker_settings_service
        self._wizard: SshWorkerSetupWizard | None = None

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._setup_button = QPushButton()
        identify(self._setup_button, "settings.ml-workers.add-ssh")

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(self._title_label)
        layout.addRow(self._summary_label)
        layout.addRow(self._setup_button)
        self._setup_button.clicked.connect(self._open_ssh_worker_wizard)
        self.retranslate_ui()

    def refresh(self) -> None:
        settings = self._service.load()
        enabled = [worker for worker in settings.workers if worker.enabled]
        local_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.LOCAL)
        ssh_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.SSH)
        total_slots = sum(worker.max_concurrent_tasks for worker in enabled)
        self._summary_label.setText(
            QCoreApplication.translate(
                "SettingsDialog",
                "{local_count} local, {ssh_count} SSH, {slots} execution slot(s).",
            ).format(
                local_count=local_count,
                ssh_count=ssh_count,
                slots=total_slots,
            )
        )

    def retranslate_ui(self) -> None:
        self._title_label.setText(QCoreApplication.translate("SettingsDialog", "ML workers"))
        self._setup_button.setText(QCoreApplication.translate("SettingsDialog", "Add SSH worker..."))
        self.refresh()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_ssh_worker_wizard(self) -> None:
        wizard = SshWorkerSetupWizard(self._service, parent=self)
        wizard.worker_saved.connect(self.refresh)
        wizard.worker_saved.connect(self.worker_saved.emit)
        self._wizard = wizard
        wizard.show()
        wizard.raise_()
        wizard.activateWindow()
