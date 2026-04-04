from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xenix.app import build_main_window
from xenix.ui.scenario_data_preparation_dialog import ScenarioDataPreparationDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_scenario_home_card_opens_data_preparation_dialog(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    _app, window = build_main_window(show=False)
    try:
        window._home_view._scenario_buttons["sales_demand_forecast.v1"].click()
        app.processEvents()

        assert isinstance(window._scenario_data_preparation_dialog, ScenarioDataPreparationDialog)
        assert window._scenario_data_preparation_dialog.isVisible()
        assert window._scenario_data_preparation_dialog.windowTitle() == "Prepare Scenario Data"
    finally:
        if window._scenario_data_preparation_dialog is not None:
            window._scenario_data_preparation_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()
