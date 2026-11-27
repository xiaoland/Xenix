from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLocale
import pytest


# QPA is selected when the first QApplication is created. Keep this scoped to
# direct UI contracts so headed Agent Harness runs can continue to use qwindows.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def ui_render_environment(qapp):
    """Configure Qt style/locale for UI tests while enforcing Segoe UI on Windows.

    Windows CI keeps the strict UI Lab font contract for every test under
    ``tests/ui/``. Non-Windows environments configure the matching Fusion style
    and locale so pure Qt behavioral tests remain runnable locally; pixel/font
    capture tests remain marked ``ui_capture`` and still enforce the declared
    scenario font strictly.
    """
    if sys.platform == "win32":
        from scripts.ui_lab.driver import configure_scenario_application
        from scripts.ui_lab.registry import get_scenario

        configure_scenario_application(qapp, get_scenario("chat.empty"))
        return

    qapp.setStyle("Fusion")
    QLocale.setDefault(QLocale("en_US"))
