import shutil
from pathlib import Path
from uuid import uuid4

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


@pytest.fixture()
def tmp_path() -> Path:
    root = Path.cwd() / ".codex-test-tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            root.rmdir()
        except OSError:
            pass


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


def test_main_window_language_switch_updates_chat_shell(
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
        window._open_settings()
        settings = window._settings_dialog
        assert settings is not None

        assert window.windowTitle() == "Xenix Native"
        assert window._title_label.text() == "Xenix"
        assert window._settings_button.text() == "Settings"
        assert window._history_label.text() == "History"
        assert settings._open_logs_button.text() == "Open log directory"
        assert settings._build_commit_label.text() == "Build commit"

        zh_index = settings._language_selector.findData("zh_CN")
        settings._language_selector.setCurrentIndex(zh_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix 原生版"
        assert window._title_label.text() == "Xenix"
        assert window._settings_button.text() == "设置"
        assert window._history_label.text() == "历史"
        assert settings._open_logs_button.text() == "打开日志目录"
        assert settings._build_commit_label.text() == "构建提交"
        assert read_saved_locale(paths) == "zh_CN"

        en_index = settings._language_selector.findData("en_US")
        settings._language_selector.setCurrentIndex(en_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix Native"
        assert settings._open_logs_button.text() == "Open log directory"
        assert settings._build_commit_label.text() == "Build commit"
        assert read_saved_locale(paths) == "en_US"
    finally:
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window.close()
