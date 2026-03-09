from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_NAME, AppPaths


class MainWindow(QMainWindow):
    def __init__(self, paths: AppPaths, log_path: Path, db_path: Path) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path

        self.setWindowTitle(f"{APP_NAME} Native")
        self.resize(920, 560)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Xenix desktop shell")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        summary = QLabel(
            "Core desktop runtime is ready. Dataset import, training, and prediction"
            " workflows will land in later native sub-issues."
        )
        summary.setWordWrap(True)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card_layout = QFormLayout(card)
        card_layout.addRow("App home", QLabel(str(self._paths.home)))
        card_layout.addRow("Config", QLabel(str(self._paths.config)))
        card_layout.addRow("Logs", QLabel(str(self._paths.logs)))
        card_layout.addRow("Cache", QLabel(str(self._paths.cache)))
        card_layout.addRow("State", QLabel(str(self._paths.state)))
        card_layout.addRow("Temp", QLabel(str(self._paths.temp)))
        card_layout.addRow("Artifacts", QLabel(str(self._paths.artifacts)))
        card_layout.addRow("Database", QLabel(str(self._db_path)))
        card_layout.addRow("Current log file", QLabel(str(self._log_path)))

        open_logs_button = QPushButton("Open log directory")
        open_logs_button.clicked.connect(self._open_logs_dir)

        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addWidget(card)
        layout.addWidget(open_logs_button)
        layout.addStretch(1)

        self.setCentralWidget(root)

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))
