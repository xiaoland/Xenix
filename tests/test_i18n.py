import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from xenix.app import build_main_window
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import (
    DEFAULT_LOCALE,
    TranslationManager,
    locale_config_path,
    read_saved_locale,
    resolve_startup_locale,
    write_saved_locale,
)
from xenix.ui.startup_splash import StartupSplash, StartupStage


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


def test_main_window_language_switch_retranslates_major_surfaces(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    write_saved_locale(paths, "en_US")

    _app, window = build_main_window(show=False)
    try:
        window._open_settings()
        settings = window._settings_dialog
        assert settings is not None
        window._open_knowledge_workspace()
        workspace = window._knowledge_workspace
        assert workspace is not None
        workspace._queue_button.click()
        task_queue = workspace._queue_dialog
        assert task_queue is not None
        settings._open_about_dialog()
        about = settings._about_dialog
        assert about is not None

        assert window.windowTitle() == "Xenix Native"
        assert settings._tabs.tabText(1) == "Knowledge Base"
        assert workspace._queue_button.text() == "Task queue"
        assert task_queue.windowTitle() == "Task queue"
        assert about.windowTitle() == "About"
        assert window._thread_detail_view._editor.placeholderText() == "Message Xenix"

        zh_index = settings._language_selector.findData("zh_CN")
        settings._language_selector.setCurrentIndex(zh_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix 原生版"
        assert settings._tabs.tabText(1) == "知识库"
        assert workspace._queue_button.text() == "任务队列"
        assert task_queue.windowTitle() == "任务队列"
        assert about.windowTitle() == "关于"
        assert window._thread_detail_view._editor.placeholderText() == "给 Xenix 发消息"
        assert read_saved_locale(paths) == "zh_CN"

        en_index = settings._language_selector.findData("en_US")
        settings._language_selector.setCurrentIndex(en_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix Native"
        assert read_saved_locale(paths) == "en_US"
    finally:
        if window._settings_dialog is not None:
            if window._settings_dialog._about_dialog is not None:
                window._settings_dialog._about_dialog.close()
            window._settings_dialog.close()
        window.close()


def test_startup_splash_language_switch_updates_stage_text(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)

    splash = StartupSplash()
    try:
        splash.set_stage(StartupStage.INITIALIZING_STORAGE)
        assert splash._stage_label.text() == "Initializing local database..."

        translation_manager.set_locale("zh_CN", persist=False)
        app.processEvents()

        assert splash._stage_label.text() == "正在初始化本地数据库..."
    finally:
        splash.close()
        translation_manager.set_locale("en_US", persist=False)


def test_main_window_translates_startup_splash_before_first_stage(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    write_saved_locale(paths, "zh_CN")
    observed_texts = []

    class FakeSplash:
        def __init__(self) -> None:
            observed_texts.append(
                (
                    "constructed",
                    QCoreApplication.translate("StartupSplash", "Starting Xenix..."),
                )
            )

        def show_centered(self) -> None:
            pass

        def set_stage(self, stage: StartupStage) -> None:
            if stage is StartupStage.STARTING:
                observed_texts.append(
                    (
                        "starting",
                        QCoreApplication.translate(
                            "StartupSplash",
                            "Starting Xenix...",
                        ),
                    )
                )

        def retranslate_ui(self) -> None:
            pass

        def close(self) -> None:
            pass

        def deleteLater(self) -> None:
            pass

    monkeypatch.setattr("xenix.app.StartupSplash", FakeSplash)

    _app, window = build_main_window(show=False, show_splash=True)
    try:
        assert observed_texts[:2] == [
            ("constructed", "正在启动 Xenix..."),
            ("starting", "正在启动 Xenix..."),
        ]
    finally:
        window._translation_manager.set_locale("en_US", persist=False)
        window.close()


def test_startup_splash_renders_nonblank_canvas_offscreen(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    splash = StartupSplash()
    try:
        splash.set_stage(StartupStage.LOADING_WORKBENCH)
        splash.show()
        app.processEvents()

        pixmap = splash.grab()
        image = pixmap.toImage()

        assert not pixmap.isNull()
        assert image.width() == splash.width()
        assert image.height() == splash.height()

        sampled_colors = set()
        for x in range(24, image.width() - 24, max(1, image.width() // 8)):
            for y in range(24, image.height() - 24, max(1, image.height() // 8)):
                sampled_colors.add(image.pixelColor(x, y).rgba())

        assert len(sampled_colors) > 8
    finally:
        splash.close()
