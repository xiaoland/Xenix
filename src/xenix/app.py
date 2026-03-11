from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .config import APP_NAME, APP_ORGANIZATION, ensure_app_dirs, get_app_paths
from .exceptions import install_exception_hooks
from .logging import setup_logging
from .resources import package_resource_path
from .services.dataset_service import DatasetService
from .services.ml_service import MLService
from .services.ml_task_service import MLTaskService
from .services.project_service import ProjectService
from .services.storage import StorageBootstrapService
from .services.storage.layout import database_path
from .services.work_item_service import WorkItemService
from .ui.main_window import MainWindow

LOGGER = logging.getLogger("xenix.bootstrap")


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    icon_path = package_resource_path("logo.png")
    app.setWindowIcon(QIcon(str(icon_path)))

    return app


def build_main_window(*, show: bool = True) -> tuple[QApplication, MainWindow]:
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)
    install_exception_hooks()
    context = StorageBootstrapService().initialize(paths)

    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )

    app = create_application()
    window = MainWindow(
        paths=paths,
        log_path=log_path,
        db_path=database_path(paths),
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
    )
    if show:
        window.show()

    LOGGER.info("Xenix native shell started")
    return app, window


def run(*, smoke_test: bool = False) -> int:
    app, window = build_main_window(show=not smoke_test)
    if smoke_test:
        window.show()
        app.processEvents()
        window.close()
        LOGGER.info("Xenix smoke test completed")
        return 0
    return app.exec()
