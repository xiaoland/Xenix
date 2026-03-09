from __future__ import annotations

import logging
import sys
import threading
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

LOGGER = logging.getLogger("xenix.runtime")


def install_exception_hooks() -> None:
    def handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: object) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        LOGGER.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        summary = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        app = QApplication.instance()
        if app is None:
            sys.stderr.write(summary)
            return

        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Critical)
        message_box.setWindowTitle("Xenix")
        message_box.setText("An unexpected error occurred. Check the log file for details.")
        message_box.setDetailedText(summary)
        message_box.exec()

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
