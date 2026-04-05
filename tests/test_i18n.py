from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xenix.app import build_main_window
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import (
    DEFAULT_LOCALE,
    locale_config_path,
    read_saved_locale,
    resolve_startup_locale,
    translation_file_path,
    write_saved_locale,
)
from xenix.services.scenario_workflow_service import PrepareScenarioWorkItemInput
from xenix.ui.scenario_inference_dialog import ScenarioInferenceDialog
from xenix.ui.scenario_training_dialog import ScenarioTrainingDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_locale_preference_round_trips_and_falls_back_to_supported_system_locale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())

    assert read_saved_locale(paths) is None
    assert resolve_startup_locale(paths, system_locale="zh_CN") == "zh_CN"
    assert resolve_startup_locale(paths, system_locale="fr_FR") == DEFAULT_LOCALE

    write_saved_locale(paths, "en-US")

    assert locale_config_path(paths).is_file()
    assert read_saved_locale(paths) == "en_US"
    assert resolve_startup_locale(paths, system_locale="zh_CN") == "en_US"


def test_main_window_language_switch_updates_ui_without_losing_form_state(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    write_saved_locale(paths, "en_US")

    assert translation_file_path("zh_CN").is_file()

    _app, window = build_main_window(show=False)
    try:
        window._dataset_workspace._dataset_name_input.setText("customer-data")
        window._dataset_workspace._work_item_name_input.setText("baseline-run")
        window._open_settings()
        settings = window._settings_dialog
        assert settings is not None

        assert window.windowTitle() == "Xenix Native"
        assert settings._open_logs_button.text() == "Open log directory"
        assert window._home_view._title_label.text() == "Xenix native ML workspace"
        assert window._home_view._settings_button.text() == "Settings"
        assert window._home_view._history_button.text() == "History"

        zh_index = settings._language_selector.findData("zh_CN")
        settings._language_selector.setCurrentIndex(zh_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix 原生版"
        assert settings._open_logs_button.text() == "打开日志目录"
        assert window._home_view._settings_button.text() == "设置"
        assert window._home_view._history_button.text() == "历史"
        assert window._home_view._scenario_buttons["sales_demand_forecast.v1"].text() == "销售需求预测"
        assert window._dataset_workspace._create_button.text() == "创建工作项"
        assert window._dataset_workspace._dataset_name_input.text() == "customer-data"
        assert window._dataset_workspace._work_item_name_input.text() == "baseline-run"
        assert read_saved_locale(paths) == "zh_CN"

        window._home_view._scenario_buttons["sales_demand_forecast.v1"].click()
        app.processEvents()
        assert window._scenario_data_preparation_dialog is not None
        assert window._scenario_data_preparation_dialog.windowTitle() == "准备场景数据"
        assert window._scenario_data_preparation_dialog._title_label.text() == "销售需求预测"
        window._scenario_data_preparation_dialog.close()

        dataset_file = tmp_path / "demand.csv"
        dataset_file.write_text(
            "feature_a,feature_b,target\n"
            "1,2,5\n"
            "2,1,5\n"
            "3,5,11\n"
            "4,2,10\n",
            encoding="utf-8",
        )
        prepared = window._scenario_workflow_service.prepare_work_item(
            PrepareScenarioWorkItemInput(
                template_key="sales_demand_forecast.v1",
                source_path=str(dataset_file.resolve()),
                feature_columns=["feature_a", "feature_b"],
                target_columns=["target"],
            )
        )
        training_dialog = ScenarioTrainingDialog(
            template=window._scenario_template_service.get_template(prepared.template_key),
            preparation_result=prepared,
            workflow_service=window._scenario_workflow_service,
            ml_service=window._ml_service,
            start_immediately=False,
            parent=window,
        )
        training_dialog.show()
        app.processEvents()

        assert training_dialog.windowTitle() == "训练看板"
        assert training_dialog._title_label.text() == "销售需求预测"
        assert training_dialog._run_again_button.text() == "重新完整运行计划"
        assert training_dialog._continue_button.text() == "继续到预测"
        training_dialog.close()

        inference_dialog = ScenarioInferenceDialog(
            template=window._scenario_template_service.get_template(prepared.template_key),
            preparation_result=prepared,
            work_item_service=window._work_item_service,
            dataset_service=window._dataset_service,
            ml_service=window._ml_service,
            parent=window,
        )
        inference_dialog.show()
        app.processEvents()

        assert inference_dialog.windowTitle() == "预测"
        assert inference_dialog._title_label.text() == "销售需求预测"
        assert inference_dialog._manual_submit_button.text() == "开始预测"
        assert inference_dialog._input_tabs.tabText(0) == "单条预测"
        inference_dialog.close()

        en_index = settings._language_selector.findData("en_US")
        settings._language_selector.setCurrentIndex(en_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix Native"
        assert settings._open_logs_button.text() == "Open log directory"
        assert window._dataset_workspace._dataset_name_input.text() == "customer-data"
        assert window._dataset_workspace._work_item_name_input.text() == "baseline-run"
        assert read_saved_locale(paths) == "en_US"
    finally:
        if window._scenario_data_preparation_dialog is not None:
            window._scenario_data_preparation_dialog.close()
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()
