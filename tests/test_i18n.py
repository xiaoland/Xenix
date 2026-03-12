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

        assert window.windowTitle() == "Xenix Native"
        assert window._open_logs_button.text() == "Open log directory"
        assert window._workspace_tabs.tabText(0) == "Datasets"

        zh_index = window._language_selector.findData("zh_CN")
        window._language_selector.setCurrentIndex(zh_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix 原生版"
        assert window._open_logs_button.text() == "打开日志目录"
        assert window._workspace_tabs.tabText(0) == "数据集"
        assert window._dataset_workspace._create_button.text() == "创建工作项"
        assert window._dataset_workspace._dataset_name_input.text() == "customer-data"
        assert window._dataset_workspace._work_item_name_input.text() == "baseline-run"
        assert read_saved_locale(paths) == "zh_CN"

        en_index = window._language_selector.findData("en_US")
        window._language_selector.setCurrentIndex(en_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix Native"
        assert window._open_logs_button.text() == "Open log directory"
        assert window._workspace_tabs.tabText(0) == "Datasets"
        assert window._dataset_workspace._dataset_name_input.text() == "customer-data"
        assert window._dataset_workspace._work_item_name_input.text() == "baseline-run"
        assert read_saved_locale(paths) == "en_US"
    finally:
        window._ml_workspace._timer.stop()
        window.close()
