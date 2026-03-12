from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.dataset_service import DatasetService
from ..services.ml_service import MLService
from ..services.project_service import ProjectService
from ..services.work_item_service import WorkItemService
from .dataset_workspace import DatasetWorkspace
from .inference_workspace import InferenceWorkspace
from .ml_workspace import MLWorkspace


class MainWindow(QMainWindow):
    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        project_service: ProjectService,
        work_item_service: WorkItemService,
        dataset_service: DatasetService,
        ml_service: MLService,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._project_service = project_service
        self._work_item_service = work_item_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._language_label = QLabel()
        self._language_selector = QComboBox()
        self._open_logs_button = QPushButton()

        self._runtime_card = QFrame()
        self._runtime_card.setFrameShape(QFrame.StyledPanel)
        self._runtime_card_layout = QFormLayout(self._runtime_card)
        self._runtime_card_layout.setContentsMargins(12, 12, 12, 12)

        self._app_home_label = QLabel()
        self._state_label = QLabel()
        self._artifacts_label = QLabel()
        self._database_label = QLabel()
        self._current_log_file_label = QLabel()

        self._app_home_value = QLabel(str(self._paths.home))
        self._state_value = QLabel(str(self._paths.state))
        self._artifacts_value = QLabel(str(self._paths.artifacts))
        self._database_value = QLabel(str(self._db_path))
        self._current_log_file_value = QLabel(str(self._log_path))

        self._dataset_workspace = DatasetWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            parent=self,
        )
        self._ml_workspace = MLWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            ml_service=self._ml_service,
            parent=self,
        )
        self._inference_workspace = InferenceWorkspace(
            project_service=self._project_service,
            work_item_service=self._work_item_service,
            dataset_service=self._dataset_service,
            ml_service=self._ml_service,
            parent=self,
        )
        self._workspace_tabs = QTabWidget(self)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.addWidget(self._title_label, 1)

        language_layout = QHBoxLayout()
        language_layout.setSpacing(8)
        language_layout.addWidget(self._language_label)
        language_layout.addWidget(self._language_selector)
        header_layout.addLayout(language_layout)

        self._title_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        self._summary_label.setWordWrap(True)

        for value_label in (
            self._app_home_value,
            self._state_value,
            self._artifacts_value,
            self._database_value,
            self._current_log_file_value,
        ):
            value_label.setWordWrap(True)

        self._runtime_card_layout.addRow(self._app_home_label, self._app_home_value)
        self._runtime_card_layout.addRow(self._state_label, self._state_value)
        self._runtime_card_layout.addRow(self._artifacts_label, self._artifacts_value)
        self._runtime_card_layout.addRow(self._database_label, self._database_value)
        self._runtime_card_layout.addRow(self._current_log_file_label, self._current_log_file_value)

        self._open_logs_button.clicked.connect(self._open_logs_dir)
        self._language_selector.currentIndexChanged.connect(self._on_language_changed)

        self._workspace_tabs.addTab(self._dataset_workspace, "")
        self._workspace_tabs.addTab(self._ml_workspace, "")
        self._workspace_tabs.addTab(self._inference_workspace, "")
        self._workspace_tabs.currentChanged.connect(self._on_workspace_tab_changed)

        layout.addLayout(header_layout)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._runtime_card)
        layout.addWidget(self._open_logs_button)
        layout.addWidget(self._workspace_tabs, 1)

        self.setCentralWidget(root)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        self._title_label.setText(self.tr("Xenix native ML workspace"))
        self._summary_label.setText(
            self.tr(
                "Create immutable work items from datasets, train models in the background, "
                "then run local inference with result viewing and export."
            )
        )
        self._language_label.setText(self.tr("Language"))
        self._app_home_label.setText(self.tr("App home"))
        self._state_label.setText(self.tr("State"))
        self._artifacts_label.setText(self.tr("Artifacts"))
        self._database_label.setText(self.tr("Database"))
        self._current_log_file_label.setText(self.tr("Current log file"))
        self._open_logs_button.setText(self.tr("Open log directory"))
        self._workspace_tabs.setTabText(0, self.tr("Datasets"))
        self._workspace_tabs.setTabText(1, self.tr("Training"))
        self._workspace_tabs.setTabText(2, self.tr("Inference"))
        self._reload_language_options()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _reload_language_options(self) -> None:
        current_locale = self._translation_manager.current_locale()
        labels = {
            "en_US": self.tr("English"),
            "zh_CN": self.tr("Simplified Chinese"),
        }
        self._language_selector.blockSignals(True)
        self._language_selector.clear()
        for locale_code in self._translation_manager.supported_locales():
            self._language_selector.addItem(labels[locale_code], locale_code)
        index = self._language_selector.findData(current_locale)
        if index >= 0:
            self._language_selector.setCurrentIndex(index)
        self._language_selector.blockSignals(False)

    def _on_language_changed(self, _index: int) -> None:
        locale_code = self._language_selector.currentData()
        if locale_code is None:
            return
        try:
            self._translation_manager.set_locale(str(locale_code))
        except Exception as exc:
            self._reload_language_options()
            QMessageBox.critical(
                self,
                self.tr("Language Switch Failed"),
                self.tr("Unable to switch the application language.\n\n{details}").format(details=str(exc)),
            )

    def _on_workspace_tab_changed(self, index: int) -> None:
        if self._workspace_tabs.widget(index) is self._ml_workspace:
            self._ml_workspace.reload_state()
        elif self._workspace_tabs.widget(index) is self._inference_workspace:
            self._inference_workspace.reload_state()

    def _open_logs_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._paths.logs)))
