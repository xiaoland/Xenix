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
    translation_file_path,
    write_saved_locale,
)
from xenix.services.agent import (
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
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
        assert settings._llm_title_label.text() == "LLM providers"
        assert settings._llm_default_model_label.text() == "Default model"
        assert settings._llm_thread_title_model_label.text() == "Thread title model"
        assert settings._ml_workers_title_label.text() == "ML workers"
        assert settings._ml_workers_setup_button.text() == "Add SSH worker..."
        assert window.tr("Generate title...") == "Generate title..."
        assert window.tr("Copy thread ID") == "Copy thread ID"
        assert window.tr("Generating thread title...") == "Generating thread title..."
        chat_view = window._thread_detail_view
        chat_view.clear_messages()
        chat_view.show_error("Stopped.")
        error_bubble = chat_view._message_layout.itemAt(0).widget()
        chat_view.apply_chatbot_event(
            ChatbotEvent(
                id="run-i18n:thinking",
                kind=ChatbotEventKind.THINKING,
                author=ChatbotEventAuthor.ASSISTANT,
                status=ChatbotEventStatus.IN_PROGRESS,
                content_blocks=[{"type": "thinking", "text": "Thinking..."}],
            ),
            auto_scroll=False,
        )
        tool_item = chat_view.add_tool_event(
            ChatbotEvent(
                id="tool-event",
                kind=ChatbotEventKind.TOOL,
                author=ChatbotEventAuthor.TOOL,
                status=ChatbotEventStatus.PENDING,
                summary="Inspecting dataset...",
                detail_blocks=[
                    {
                        "type": "tool_call_result",
                        "tool_name": "data.peek",
                        "status": "completed",
                    }
                ],
            ),
            auto_scroll=False,
        )
        profile_tool_item = chat_view.add_tool_event(
            ChatbotEvent(
                id="profile-tool-event",
                kind=ChatbotEventKind.TOOL,
                author=ChatbotEventAuthor.TOOL,
                status=ChatbotEventStatus.PENDING,
                summary="Profiling dataset...",
            ),
            auto_scroll=False,
        )
        graph_tool_item = chat_view.add_tool_event(
            ChatbotEvent(
                id="graph-tool-event",
                kind=ChatbotEventKind.TOOL,
                author=ChatbotEventAuthor.TOOL,
                status=ChatbotEventStatus.COMPLETED,
                summary="Drew graph",
            ),
            auto_scroll=False,
        )
        usage_item = chat_view.add_usage_event(
            ChatbotEvent(
                id="usage-event",
                kind=ChatbotEventKind.USAGE,
                author=ChatbotEventAuthor.ASSISTANT,
                usage_payload={
                    "request_count": 3,
                    "input_tokens": 9800,
                    "cached_input_tokens": 1900,
                    "output_tokens": 2630,
                    "total_tokens": 12430,
                },
            ),
            auto_scroll=False,
        )

        assert chat_view._editor.placeholderText() == "Message Xenix"
        assert chat_view._send_button.text() == "Send"
        assert chat_view._attach_button.toolTip() == "Attach files"
        assert chat_view._model_picker.toolTip() == "Model for the next turn"
        assert chat_view._step_continue_button.text() == "Continue"
        assert chat_view._step_stop_button.text() == "Stop"
        assert chat_view._composer_drop_title.text() == "Drop files to attach"
        assert chat_view._composer_drop_hint.text() == "Release here to add them to the next message"
        assert error_bubble._browser.toPlainText() == "Error: Stopped."
        assert chat_view._thinking_bubble._browser.toPlainText() == "Thinking..."
        assert tool_item._summary_label.text() == "Inspecting dataset..."
        assert profile_tool_item._summary_label.text() == "Profiling dataset..."
        assert graph_tool_item._summary_label.text() == "Drew graph"
        assert tool_item._chevron_button.toolTip() == "Show result"
        assert "data.peek" in tool_item._detail_browser.toPlainText()
        assert "completed" in tool_item._detail_browser.toPlainText()
        assert usage_item._label.text() == "↑ 9.8k (1.9k cached) · ↓ 2.6k"

        zh_index = settings._language_selector.findData("zh_CN")
        settings._language_selector.setCurrentIndex(zh_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix 原生版"
        assert window._title_label.text() == "Xenix"
        assert window._settings_button.text() == "设置"
        assert window._history_label.text() == "历史"
        assert settings._open_logs_button.text() == "打开日志目录"
        assert settings._build_commit_label.text() == "构建提交"
        assert settings._llm_title_label.text() == "LLM 提供商"
        assert settings._llm_default_model_label.text() == "默认模型"
        assert settings._llm_thread_title_model_label.text() == "线程标题模型"
        assert settings._ml_workers_title_label.text() == "ML 工作器"
        assert settings._ml_workers_setup_button.text() == "添加 SSH 工作器..."
        assert window.tr("Generate title...") == "生成标题..."
        assert window.tr("Copy thread ID") == "复制线程 ID"
        assert window.tr("Generating thread title...") == "正在生成线程标题..."
        assert chat_view._editor.placeholderText() == "给 Xenix 发消息"
        assert chat_view._send_button.text() == "发送"
        assert chat_view._attach_button.toolTip() == "添加文件"
        assert chat_view._model_picker.toolTip() == "下一轮使用的模型"
        assert chat_view._step_continue_button.text() == "继续"
        assert chat_view._step_stop_button.text() == "停止"
        assert chat_view._composer_drop_title.text() == "拖放文件以添加附件"
        assert chat_view._composer_drop_hint.text() == "松开后添加到下一条消息"
        assert error_bubble._browser.toPlainText() == "错误：Stopped."
        assert chat_view._thinking_bubble._browser.toPlainText() == "思考中..."
        assert tool_item._summary_label.text() == "正在检查数据集..."
        assert profile_tool_item._summary_label.text() == "正在分析数据集..."
        assert graph_tool_item._summary_label.text() == "图表已绘制"
        assert tool_item._chevron_button.toolTip() == "显示结果"
        assert "data.peek" in tool_item._detail_browser.toPlainText()
        assert "已完成" in tool_item._detail_browser.toPlainText()
        assert usage_item._label.text() == "↑ 9.8k（1.9k 缓存命中） · ↓ 2.6k"
        assert read_saved_locale(paths) == "zh_CN"

        en_index = settings._language_selector.findData("en_US")
        settings._language_selector.setCurrentIndex(en_index)
        app.processEvents()

        assert window.windowTitle() == "Xenix Native"
        assert settings._open_logs_button.text() == "Open log directory"
        assert settings._build_commit_label.text() == "Build commit"
        assert settings._llm_title_label.text() == "LLM providers"
        assert settings._llm_default_model_label.text() == "Default model"
        assert settings._llm_thread_title_model_label.text() == "Thread title model"
        assert settings._ml_workers_title_label.text() == "ML workers"
        assert settings._ml_workers_setup_button.text() == "Add SSH worker..."
        assert window.tr("Generate title...") == "Generate title..."
        assert window.tr("Copy thread ID") == "Copy thread ID"
        assert window.tr("Generating thread title...") == "Generating thread title..."
        assert chat_view._editor.placeholderText() == "Message Xenix"
        assert chat_view._send_button.text() == "Send"
        assert chat_view._attach_button.toolTip() == "Attach files"
        assert chat_view._model_picker.toolTip() == "Model for the next turn"
        assert error_bubble._browser.toPlainText() == "Error: Stopped."
        assert chat_view._thinking_bubble._browser.toPlainText() == "Thinking..."
        assert tool_item._summary_label.text() == "Inspecting dataset..."
        assert profile_tool_item._summary_label.text() == "Profiling dataset..."
        assert graph_tool_item._summary_label.text() == "Drew graph"
        assert usage_item._label.text() == "↑ 9.8k (1.9k cached) · ↓ 2.6k"
        assert read_saved_locale(paths) == "en_US"
    finally:
        if window._settings_dialog is not None:
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
                        QCoreApplication.translate("StartupSplash", "Starting Xenix..."),
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
