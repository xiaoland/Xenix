from __future__ import annotations

import os
import pytest


# QPA is selected when the first QApplication is created. Keep this scoped to
# direct UI contracts so headed Agent Harness runs can continue to use qwindows.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def ui_render_environment(qapp):
    # Share the lab's rendering contract so early test failures also have legible
    # screenshots, before any scenario test happens to register the text font.
    from scripts.ui_lab.driver import configure_scenario_application
    from scripts.ui_lab.registry import get_scenario

    configure_scenario_application(qapp, get_scenario("chat.empty"))
