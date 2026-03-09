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
from .ui.main_window import MainWindow

LOGGER = logging.getLogger("xenix.bootstrap")


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    icon_path = package_resource_path("app-icon.svg")
    app.setWindowIcon(QIcon(str(icon_path)))

    return app


def run() -> int:
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)
    install_exception_hooks()

    app = create_application()
    window = MainWindow(paths=paths, log_path=log_path)
    window.show()

    LOGGER.info("Xenix native shell started")
    return app.exec()
