"""About dialog: runtime locations, version, build identity, and update entry."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..build_info import APP_VERSION, BUILD_COMMIT, BUILD_COMMIT_DISPLAY
from ..config import AppPaths


class AboutDialog(QDialog):
    software_update_requested = Signal()

    def __init__(
        self,
        *,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        software_updates_available: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._software_updates_available = software_updates_available
        self._update_operation_active = False

        self._runtime_card = QFrame()
        self._runtime_card.setFrameShape(QFrame.StyledPanel)
        self._runtime_card_layout = QFormLayout(self._runtime_card)
        self._runtime_card_layout.setContentsMargins(12, 12, 12, 12)

        self._app_home_label = QLabel()
        self._state_label = QLabel()
        self._artifacts_label = QLabel()
        self._database_label = QLabel()
        self._current_log_file_label = QLabel()
        self._app_version_label = QLabel()
        self._build_commit_label = QLabel()
        self._open_logs_button = QPushButton()
        self._check_updates_button = QPushButton()

        self._app_home_value = QLabel(str(self._paths.home))
        self._state_value = QLabel(str(self._paths.state))
        self._artifacts_value = QLabel(str(self._paths.artifacts))
        self._database_value = QLabel(str(self._db_path))
        self._current_log_file_value = QLabel(str(self._log_path))
        self._app_version_value = QLabel(APP_VERSION)
        self._build_commit_value = QLabel(BUILD_COMMIT_DISPLAY)
        if BUILD_COMMIT_DISPLAY != BUILD_COMMIT:
            self._build_commit_value.setToolTip(BUILD_COMMIT)

        self.resize(640, 360)
        self._build_ui()
        self._wire_events()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        for value_label in (
            self._app_home_value,
            self._state_value,
            self._artifacts_value,
            self._database_value,
            self._current_log_file_value,
            self._app_version_value,
            self._build_commit_value,
        ):
            value_label.setWordWrap(True)

        self._runtime_card_layout.addRow(self._app_home_label, self._app_home_value)
        self._runtime_card_layout.addRow(self._state_label, self._state_value)
        self._runtime_card_layout.addRow(self._artifacts_label, self._artifacts_value)
        self._runtime_card_layout.addRow(self._database_label, self._database_value)
        self._runtime_card_layout.addRow(self._current_log_file_label, self._current_log_file_value)
        self._runtime_card_layout.addRow(self._app_version_label, self._app_version_value)
        self._runtime_card_layout.addRow(self._build_commit_label, self._build_commit_value)

        layout.addWidget(self._runtime_card)
        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._open_logs_button)
        actions_layout.addWidget(self._check_updates_button)
        actions_layout.addStretch(1)
        layout.addLayout(actions_layout)

    def _wire_events(self) -> None:
        self._open_logs_button.clicked.connect(self._open_logs_dir)
        self._check_updates_button.clicked.connect(
            self.software_update_requested.emit
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("About"))
        self._app_home_label.setText(self.tr("App home"))
        self._state_label.setText(self.tr("State"))
        self._artifacts_label.setText(self.tr("Artifacts"))
        self._database_label.setText(self.tr("Database"))
        self._current_log_file_label.setText(self.tr("Current log file"))
        self._app_version_label.setText(self.tr("App version"))
        self._build_commit_label.setText(self.tr("Build commit"))
        self._open_logs_button.setText(self.tr("Open log directory"))
        self._check_updates_button.setText(self.tr("Check for updates"))
        self._check_updates_button.setEnabled(
            self._software_updates_available and not self._update_operation_active
        )

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))

    def set_update_operation_active(self, active: bool) -> None:
        self._update_operation_active = active
        self._check_updates_button.setEnabled(
            self._software_updates_available and not active
        )
