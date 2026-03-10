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
from ..services.dataset_service import DatasetService
from ..services.project_service import ProjectService
from ..services.work_item_service import WorkItemService
from .dataset_workspace import DatasetWorkspace


class MainWindow(QMainWindow):
    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service

        self.setWindowTitle(f"{APP_NAME} Native")
        self.resize(1080, 760)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Xenix dataset import workspace")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        summary = QLabel(
            "Import a local dataset, inspect its columns, and save feature and target"
            " selections onto a work item. Training will consume this state in later"
            " native issues."
        )
        summary.setWordWrap(True)

        runtime_card = QFrame()
        runtime_card.setFrameShape(QFrame.StyledPanel)
        card_layout = QFormLayout(runtime_card)
        card_layout.addRow("App home", QLabel(str(self._paths.home)))
        card_layout.addRow("State", QLabel(str(self._paths.state)))
        card_layout.addRow("Artifacts", QLabel(str(self._paths.artifacts)))
        card_layout.addRow("Database", QLabel(str(self._db_path)))
        card_layout.addRow("Current log file", QLabel(str(self._log_path)))

        open_logs_button = QPushButton("Open log directory")
        open_logs_button.clicked.connect(self._open_logs_dir)

        workspace = DatasetWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            parent=self,
        )

        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addWidget(runtime_card)
        layout.addWidget(open_logs_button)
        layout.addWidget(workspace, 1)

        self.setCentralWidget(root)

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))
