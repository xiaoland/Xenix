from __future__ import annotations

import logging
import sys
import threading
import traceback
from collections import deque
from collections.abc import Callable
from types import TracebackType
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

LOGGER = logging.getLogger("xenix.runtime")


class XenixError(Exception):
    """Base class for domain-facing Xenix errors."""


class NotFoundError(XenixError):
    """Raised when a requested entity does not exist."""


class ValidationError(XenixError):
    """Raised when a validated request is invalid.

    Carries a machine-readable repair contract for the LLM tool boundary:
    error_code is a stable code (blank normalizes to None), error_details is a
    JSON-safe mapping, repair_hints is a list of non-empty strings (blank entries
    dropped), and retryable is True/False/None (non-bool normalizes to None).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        error_details: dict[str, Any] | None = None,
        repair_hints: list[str] | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code.strip() if isinstance(error_code, str) and error_code.strip() else None
        self.error_details = dict(error_details) if isinstance(error_details, dict) and error_details else {}
        self.repair_hints = [
            str(hint).strip()
            for hint in (repair_hints or [])
            if str(hint).strip()
        ]
        self.retryable = retryable if isinstance(retryable, bool) else None


class InvalidStateTransitionError(XenixError):
    """Raised when an entity transition violates the state contract."""


class DatasetSourceMissingError(XenixError):
    """Raised when a registered dataset source file is no longer available."""


class StorageBootstrapError(XenixError):
    """Raised when local storage bootstrap cannot complete."""


class _ExceptionPresenter(QObject):
    requested = Signal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._active: set[str] = set()
        self._pending: deque[str] = deque()
        self._showing = False
        self.requested.connect(self.show, Qt.ConnectionType.QueuedConnection)

    @Slot(str)
    def show(self, summary: str) -> None:
        # A polling callback may fail again while a modal dialog processes events.
        # Keep the existing report visible instead of opening recursive dialogs.
        if summary in self._active:
            return
        self._active.add(summary)
        self._pending.append(summary)
        if self._showing:
            return
        self._showing = True
        try:
            while self._pending:
                current = self._pending.popleft()
                try:
                    self._show_dialog(current)
                finally:
                    self._active.discard(current)
        finally:
            self._showing = False

    def _show_dialog(self, summary: str) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        for window in app.topLevelWindows():
            if window.type() == Qt.WindowType.SplashScreen:
                window.hide()
        message_box = QMessageBox(app.activeWindow())
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle(QCoreApplication.translate("Exceptions", "Xenix"))
        message_box.setText(QCoreApplication.translate(
            "Exceptions",
            "An unexpected error occurred. Check the log file for details.",
        ))
        message_box.setDetailedText(summary)
        message_box.exec()


_presenter: _ExceptionPresenter | None = None
_installed_hook: Callable[[type[BaseException], BaseException, TracebackType | None], None] | None = None


def report_exception(error: BaseException, *, defer: bool = True) -> None:
    """Record a caught internal failure and present it on the GUI thread.

    Headless processes retain the traceback in their logs. GUI callers must
    first settle their failed operation (including stopping failed polling).
    Expected validation and canonical task failures keep their domain feedback.
    """
    LOGGER.error("Operation failed", exc_info=(type(error), error, error.__traceback__))
    summary = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if _presenter is not None and sys.excepthook is _installed_hook and QApplication.instance() is not None:
        if not defer and QThread.currentThread() == _presenter.thread():
            _presenter.show(summary)
        else:
            _presenter.requested.emit(summary)


def install_exception_hooks() -> None:
    """Install once the QApplication exists, on its owning thread."""
    global _presenter, _installed_hook
    app = QApplication.instance()
    if isinstance(app, QApplication):
        if QThread.currentThread() != app.thread():
            raise RuntimeError("Exception hooks must be installed on the GUI thread.")
        if _presenter is not None:
            _presenter.deleteLater()
        _presenter = _ExceptionPresenter(app)

    def handle_exception(
        exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        report_exception(exc_value.with_traceback(exc_traceback), defer=False)

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        error = args.exc_value or RuntimeError(f"Thread failed: {args.exc_type.__name__}")
        handle_exception(type(error), error, args.exc_traceback)

    _installed_hook = handle_exception
    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
