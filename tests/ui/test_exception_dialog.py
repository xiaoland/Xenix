import sys
import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QMessageBox

from xenix.exceptions import install_exception_hooks


def test_exception_dialog_dismisses_topmost_bootstrap_before_waiting(qapp, monkeypatch):
    splash = QWindow()
    splash.setFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    shown = []

    def show_error(dialog):
        assert not splash.isVisible()
        assert "history render failed" in dialog.detailedText()
        shown.append(True)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", show_error)
    try:
        install_exception_hooks()
        error = ValueError("history render failed")
        sys.excepthook(type(error), error, None)
        assert shown == [True]
    finally:
        splash.close()
        splash.destroy()
