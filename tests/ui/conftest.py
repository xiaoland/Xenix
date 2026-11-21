from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def ui_render_environment(qapp):
    # Set up a legible font even for failure screenshots from non-scenario tests.
    from scripts.ui_lab.driver import configure_scenario_application
    from scripts.ui_lab.registry import get_scenario

    configure_scenario_application(qapp, get_scenario("chat.empty"), strict_font=False)
