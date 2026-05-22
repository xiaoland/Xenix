import json
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFrame, QMessageBox, QTextBrowser, QWidget

from xenix.app import build_main_window
from xenix.build_info import BUILD_COMMIT_DISPLAY
from xenix.main import main
from xenix.services.agent import (
    AgentHarnessStreamEvent,
    ChatbotEvent,
    ChatbotEventAuthor,
    ChatbotEventKind,
    ChatbotEventStatus,
)
from xenix.services.agent.dev_fixtures import MESSAGE_RENDERING_FIXTURE_TITLE, ensure_mock_conversation_history
from xenix.services.artifact_service import RegisterArtifactInput
from xenix.services.storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    ArtifactKind,
)
from xenix.ui.chatbot import _format_token_count
from xenix.ui.startup_splash import StartupStage


class _FakeFileDropEvent:
    def __init__(self, mime_data: QMimeData, x: int, y: int, event_type=QEvent.Drop) -> None:
        self._mime_data = mime_data
        self._position = QPointF(x, y)
        self._event_type = event_type
        self.accepted = False
        self.ignored = False

    def type(self):
        return self._event_type

    def mimeData(self) -> QMimeData:
        return self._mime_data

    def position(self) -> QPointF:
        return self._position

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def _seed_mock_history(window) -> None:
    ensure_mock_conversation_history(window._agent_harness_service._conversation_store)
    window._refresh_history_sidebar()
    current_item = window._history_list.currentItem()
    if current_item is not None:
        window._open_history_thread(current_item)


def test_smoke_test_bootstraps_runtime_in_fresh_app_home(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    exit_code = main(["--smoke-test"])

    assert exit_code == 0
    assert (runtime_home / "config").is_dir()
    assert (runtime_home / "logs").is_dir()
    assert (runtime_home / "cache").is_dir()
    assert (runtime_home / "state").is_dir()
    assert (runtime_home / "temp").is_dir()
    assert (runtime_home / "artifacts").is_dir()
    assert (runtime_home / "state" / "xenix.db").is_file()
    assert (runtime_home / "logs" / "xenix.log").is_file()


def test_main_window_reports_startup_splash_stages_when_enabled(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))
    created_splashes = []

    class FakeSplash:
        def __init__(self) -> None:
            self.stages = []
            self.shown = False
            self.retranslated = False
            self.closed = False
            self.deleted = False
            created_splashes.append(self)

        def show_centered(self) -> None:
            self.shown = True

        def set_stage(self, stage: StartupStage) -> None:
            self.stages.append(stage)

        def retranslate_ui(self) -> None:
            self.retranslated = True

        def close(self) -> None:
            self.closed = True

        def deleteLater(self) -> None:
            self.deleted = True

    monkeypatch.setattr("xenix.app.StartupSplash", FakeSplash)

    app, window = build_main_window(show=False)
    try:
        assert created_splashes == []
    finally:
        window.close()

    app, window = build_main_window(show=False, show_splash=True)
    try:
        assert len(created_splashes) == 1
        splash = created_splashes[0]
        assert splash.shown is True
        assert splash.retranslated is True
        assert splash.closed is True
        assert splash.deleted is True
        assert splash.stages == [
            StartupStage.STARTING,
            StartupStage.PREPARING_APP_DATA,
            StartupStage.INITIALIZING_LOGGING,
            StartupStage.INITIALIZING_STORAGE,
            StartupStage.LOADING_WORKBENCH,
            StartupStage.READY,
        ]
    finally:
        window.close()
        app.processEvents()


def test_main_window_holds_ready_splash_before_showing_window(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))
    events = []

    class FakeSplash:
        def __init__(self) -> None:
            events.append("splash.create")

        def show_centered(self) -> None:
            events.append("splash.show")

        def set_stage(self, stage: StartupStage) -> None:
            events.append(f"stage:{stage.name}")

        def retranslate_ui(self) -> None:
            events.append("splash.retranslate")

        def close(self) -> None:
            events.append("splash.close")

        def deleteLater(self) -> None:
            events.append("splash.delete")

    def fake_hold(_app, _splash, hold_ms: int) -> None:
        events.append(f"splash.hold:{hold_ms}")

    def fake_show(_window) -> None:
        events.append("window.show")

    monkeypatch.setattr("xenix.app.StartupSplash", FakeSplash)
    monkeypatch.setattr("xenix.app._hold_startup_splash", fake_hold)
    monkeypatch.setattr("xenix.app.MainWindow.show", fake_show)

    app, window = build_main_window(show=True, show_splash=True, splash_hold_ms=2200)
    try:
        assert events[-5:] == [
            "stage:READY",
            "splash.hold:2200",
            "splash.close",
            "splash.delete",
            "window.show",
        ]
    finally:
        window.close()
        app.processEvents()


def test_main_window_keeps_settings_entry_on_thread_detail_view_shell(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        assert window._thread_detail_view.isVisibleTo(window)
        assert window._settings_button.text() == "Settings"

        window._settings_button.click()
        app.processEvents()

        assert window._settings_dialog is not None
        assert window._settings_dialog.isVisible()
        assert window._settings_dialog._aimock_card.isHidden() is True
        assert window._settings_dialog._build_commit_value.text() == BUILD_COMMIT_DISPLAY
    finally:
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window.close()


def test_main_window_seeds_mock_history_and_renders_sidebar_selection(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        _seed_mock_history(window)
        app.processEvents()

        titles = [window._history_list.item(index).text() for index in range(window._history_list.count())]

        assert MESSAGE_RENDERING_FIXTURE_TITLE in titles
        assert window._history_sidebar.isVisibleTo(window)
        assert window._history_list.count() >= 2
        assert window._thread_detail_view._message_layout.count() > 1
    finally:
        window.close()


def test_main_window_renders_event_list_without_turn_dividers(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        _seed_mock_history(window)
        target_item = None
        for index in range(window._history_list.count()):
            item = window._history_list.item(index)
            if item.text() == MESSAGE_RENDERING_FIXTURE_TITLE:
                target_item = item
                break
        assert target_item is not None

        window._open_history_thread(target_item)
        app.processEvents()

        card_names = []
        for index in range(window._thread_detail_view._message_layout.count()):
            item = window._thread_detail_view._message_layout.itemAt(index)
            bubble = item.widget() if item is not None else None
            card = getattr(bubble, "_card", None)
            if card is not None:
                card_names.append(card.objectName())

        user_indexes = [index for index, name in enumerate(card_names) if name == "chatMessageUser"]
        divider_indexes = [index for index, name in enumerate(card_names) if name == "chatMessageDivider"]

        assert user_indexes
        assert divider_indexes == []
    finally:
        window.close()


def test_main_window_renders_tool_calls(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        _seed_mock_history(window)
        target_item = None
        for index in range(window._history_list.count()):
            item = window._history_list.item(index)
            if item.text() == MESSAGE_RENDERING_FIXTURE_TITLE:
                target_item = item
                break
        assert target_item is not None

        window._open_history_thread(target_item)
        app.processEvents()

        tool_items = []
        tool_bubbles = []
        for index in range(window._thread_detail_view._message_layout.count()):
            item = window._thread_detail_view._message_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if getattr(widget, "objectName", lambda: "")() == "chatToolCallItem":
                tool_items.append(widget)
            if getattr(getattr(widget, "_card", None), "objectName", lambda: "")() == "chatMessageTool":
                tool_bubbles.append(widget)

        assert tool_bubbles == []
        assert tool_items
        assert all(item.width() == window._thread_detail_view._message_column.width() for item in tool_items)
        summaries = [item._summary_label.text() for item in tool_items]
        assert "Inspected dataset" in summaries
        assert "Trained model" in summaries
        assert "Applied model" in summaries
    finally:
        window.close()


def test_thread_detail_view_expands_tool_event_detail(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        view.clear_messages()
        view.apply_chatbot_event(
            ChatbotEvent(
                id="tool-event",
                kind=ChatbotEventKind.TOOL,
                turn_id="turn",
                sequence_index=0,
                author=ChatbotEventAuthor.TOOL,
                status=ChatbotEventStatus.FAILED,
                tool_call_id="tool-call",
                tool_name="data.peek",
                icon_key="table",
                summary="Failed to inspect dataset",
                detail_blocks=[{"type": "markdown", "text": "Source file is missing."}],
            )
        )
        app.processEvents()

        item = view._event_widgets_by_id["tool-event"]
        assert item.objectName() == "chatToolCallItem"
        assert item._summary_label.text() == "Failed to inspect dataset"
        assert item._icon_label.pixmap() is not None
        assert not item._icon_label.pixmap().isNull()
        assert item._detail_browser.isHidden()
        assert item._chevron_button.arrowType() == Qt.NoArrow
        collapsed_icon_key = item._chevron_button.icon().cacheKey()

        item._chevron_button.click()
        app.processEvents()

        assert item._chevron_button.arrowType() == Qt.NoArrow
        assert item._chevron_button.icon().cacheKey() != collapsed_icon_key
        assert item._detail_browser.isVisible()
        assert "Source file is missing." in item._detail_browser.toPlainText()
    finally:
        window.close()


def test_thread_detail_view_renders_turn_usage_overview(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        view.clear_messages()
        view.apply_chatbot_event(
            ChatbotEvent(
                id="turn-usage",
                kind=ChatbotEventKind.USAGE,
                turn_id="turn",
                sequence_index=3,
                author=ChatbotEventAuthor.ASSISTANT,
                status=ChatbotEventStatus.COMPLETED,
                usage_payload={
                    "request_count": 3,
                    "input_tokens": 9800,
                    "cached_input_tokens": 1900,
                    "output_tokens": 2630,
                    "total_tokens": 12430,
                },
            )
        )
        app.processEvents()

        item = view._event_widgets_by_id["turn-usage"]
        assert item.objectName() == "chatUsageOverviewItem"
        assert item._label.text() == "↑ 9.8k (1.9k cached) · ↓ 2.6k"
        assert item._label.alignment() & Qt.AlignLeft
        assert item._label.font().pointSize() < view.font().pointSize()
        assert item._label.palette().color(QPalette.ColorRole.WindowText) == item._label.palette().color(
            QPalette.ColorRole.PlaceholderText
        )
    finally:
        window.close()


def test_token_count_format_uses_k_after_999() -> None:
    assert _format_token_count(999) == "999"
    assert _format_token_count(1000) == "1.0k"
    assert _format_token_count(1050) == "1.1k"
    assert _format_token_count(12430) == "12.4k"


def test_main_window_new_thread_button_creates_and_selects_empty_thread(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        app.processEvents()
        initial_count = window._history_list.count()

        window._new_thread_button.click()
        app.processEvents()

        current_item = window._history_list.currentItem()
        assert window._history_list.count() == initial_count + 1
        assert window._agent_thread_id is not None
        assert current_item is not None
        assert current_item.data(Qt.UserRole) == window._agent_thread_id
        assert current_item.text() == "Untitled conversation"
        assert window._thread_detail_view._message_layout.count() == 1
    finally:
        window.close()


def test_main_window_history_item_handlers_rename_and_delete_thread(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        window._new_thread_button.click()
        app.processEvents()
        thread_id = window._agent_thread_id
        assert thread_id is not None
        item = window._history_list.currentItem()
        assert item is not None

        monkeypatch.setattr(
            "xenix.ui.main_window.QInputDialog.getText",
            lambda *args, **kwargs: ("Renamed analysis", True),
        )
        window._rename_history_thread(item)
        app.processEvents()

        renamed_item = None
        for index in range(window._history_list.count()):
            candidate = window._history_list.item(index)
            if candidate.data(Qt.UserRole) == thread_id:
                renamed_item = candidate
                break

        assert renamed_item is not None
        assert renamed_item.text() == "Renamed analysis"
        assert window._agent_harness_service is not None
        assert window._agent_harness_service.get_thread_snapshot(thread_id).thread.title == "Renamed analysis"

        monkeypatch.setattr(
            "xenix.ui.main_window.QMessageBox.question",
            lambda *args, **kwargs: QMessageBox.Yes,
        )
        window._delete_history_thread(renamed_item)
        app.processEvents()

        remaining_thread_ids = [
            window._history_list.item(index).data(Qt.UserRole)
            for index in range(window._history_list.count())
        ]
        assert thread_id not in remaining_thread_ids
        assert window._agent_thread_id != thread_id
    finally:
        window.close()


def test_main_window_generate_thread_title_prompts_when_model_missing(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        window._new_thread_button.click()
        app.processEvents()
        item = window._history_list.currentItem()
        assert item is not None
        messages: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "xenix.ui.main_window.QMessageBox.information",
            lambda _parent, title, message: messages.append((title, message)),
        )

        window._generate_history_thread_title(item)
        app.processEvents()

        assert messages == [
            ("Generate Thread Title", "Thread title model is not configured."),
        ]
        assert window._thread_title_progress_dialog is None
    finally:
        window.close()


def test_main_window_generate_thread_title_applies_edited_proposal(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        window._new_thread_button.click()
        app.processEvents()
        thread_id = window._agent_thread_id
        item = window._history_list.currentItem()
        assert thread_id is not None
        assert item is not None

        monkeypatch.setattr(window._agent_harness_service, "has_thread_title_provider", lambda: True)

        def fake_generate_title(requested_thread_id: str) -> str:
            assert requested_thread_id == thread_id
            time.sleep(0.02)
            return "Generated title"

        monkeypatch.setattr(window._agent_harness_service, "generate_thread_title", fake_generate_title)
        monkeypatch.setattr(
            "xenix.ui.main_window.QInputDialog.getText",
            lambda *args, **kwargs: ("Edited generated title", True),
        )

        window._generate_history_thread_title(item)
        app.processEvents()

        assert window._thread_title_progress_dialog is not None

        for _ in range(80):
            app.processEvents()
            if window._thread_title_progress_dialog is None:
                break
            time.sleep(0.01)

        assert window._thread_title_progress_dialog is None
        assert window._agent_harness_service.get_thread_snapshot(thread_id).thread.title == "Edited generated title"
        current_item = window._history_list.currentItem()
        assert current_item is not None
        assert current_item.text() == "Edited generated title"
    finally:
        window.close()


def test_main_window_generated_thread_title_cancel_preserves_title(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        snapshot = window._agent_harness_service.create_thread("Original title")
        thread_id = snapshot.thread.id
        monkeypatch.setattr(
            "xenix.ui.main_window.QInputDialog.getText",
            lambda *args, **kwargs: ("Ignored title", False),
        )

        window._finish_generated_thread_title(thread_id, "Generated title")
        app.processEvents()

        assert window._agent_harness_service.get_thread_snapshot(thread_id).thread.title == "Original title"
    finally:
        window.close()


def test_main_window_step_budget_confirmation_can_continue(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        assert window._agent_harness_service is not None
        window._new_thread_button.click()
        app.processEvents()
        thread_id = window._agent_thread_id
        assert thread_id is not None
        snapshot = window._agent_harness_service.get_thread_snapshot(thread_id)
        event = AgentHarnessStreamEvent(
            kind="step_confirmation_required",
            thread_id=thread_id,
            turn_id="turn-for-confirmation",
            run_id="run-for-confirmation",
            snapshot=snapshot,
            used_steps=16,
            suggested_steps=8,
            max_total_steps=64,
        )

        window._render_harness_stream_event(event)
        app.processEvents()

        assert window._pending_step_confirmation == event
        assert window._thread_detail_view._step_confirmation_bar.isVisibleTo(window)
        assert window._thread_detail_view._editor.isEnabled() is False
        assert "16/64" in window._thread_detail_view._step_confirmation_label.text()

        captured_inputs = []

        def fake_continue(input_data):
            captured_inputs.append(input_data)
            yield AgentHarnessStreamEvent(kind="snapshot", thread_id=thread_id, snapshot=snapshot, is_final=True)

        monkeypatch.setattr(window._agent_harness_service, "continue_step_budget_stream", fake_continue)
        window._thread_detail_view._step_continue_button.click()
        for _ in range(40):
            app.processEvents()
            if captured_inputs and not window._thread_detail_view._running:
                break
            time.sleep(0.01)

        assert len(captured_inputs) == 1
        assert captured_inputs[0].thread_id == thread_id
        assert captured_inputs[0].turn_id == "turn-for-confirmation"
        assert captured_inputs[0].run_id == "run-for-confirmation"
        assert captured_inputs[0].additional_steps == 8
        assert window._pending_step_confirmation is None
        assert window._thread_detail_view._step_confirmation_bar.isHidden() is True
    finally:
        window.close()


def test_main_window_stop_cancels_active_agent_run(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        assert window._agent_harness_service is not None
        cancelled_run_ids: list[str] = []
        monkeypatch.setattr(window._agent_harness_service, "cancel_run", lambda run_id: cancelled_run_ids.append(run_id))

        window._active_agent_run_id = "run-to-stop"
        window._thread_detail_view.set_running(True)
        window._thread_detail_view.show_thinking_indicator()
        window._thread_detail_view._send_button.click()
        app.processEvents()

        assert cancelled_run_ids == ["run-to-stop"]
        assert window._thread_detail_view._running is False
        assert window._thread_detail_view._thinking_bubble is None
        assert "run-to-stop" in window._cancelled_agent_run_ids
    finally:
        window.close()


def test_thread_detail_view_composer_switches_layout_when_text_wraps(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        editor = window._thread_detail_view._editor
        compact_height = editor.height()

        assert window._thread_detail_view._attach_button.isHidden() is False
        assert window._thread_detail_view._send_button.isHidden() is False
        assert window._thread_detail_view._expanded_attach_button.isHidden() is True
        assert window._thread_detail_view._expanded_send_button.isHidden() is True
        assert window._thread_detail_view._attach_button.text() == ""
        assert not window._thread_detail_view._attach_button.icon().isNull()

        editor.setPlainText("line one\nline two")
        app.processEvents()

        assert editor.height() > compact_height
        assert window._thread_detail_view._attach_button.isHidden() is True
        assert window._thread_detail_view._send_button.isHidden() is True
        assert window._thread_detail_view._expanded_attach_button.isHidden() is False
        assert window._thread_detail_view._expanded_send_button.isHidden() is False
        assert window._thread_detail_view._expanded_attach_button.text() == ""
        assert not window._thread_detail_view._expanded_attach_button.icon().isNull()
    finally:
        window.close()


def test_thread_detail_view_composer_editor_uses_transparent_native_background(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        app.processEvents()
        editor = window._thread_detail_view._editor

        assert not editor.autoFillBackground()
        assert editor.testAttribute(Qt.WA_TranslucentBackground)
        assert not editor.viewport().autoFillBackground()
        assert editor.viewport().testAttribute(Qt.WA_TranslucentBackground)
        assert editor.palette().color(QPalette.ColorRole.Base).alpha() == 0
        assert editor.viewport().palette().color(QPalette.ColorRole.Base).alpha() == 0
        margins = editor.viewportMargins()
        assert margins.left() == 8
        assert margins.right() == 8
    finally:
        window.close()


def test_thread_detail_view_enter_submits_and_shift_enter_inserts_newline(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        try:
            view.message_submitted.disconnect(window._submit_chat_message)
        except RuntimeError:
            pass
        submitted: list[tuple[str, list[str]]] = []
        view.message_submitted.connect(lambda text, files: submitted.append((text, files)))

        editor = view._editor
        editor.setFocus()
        QTest.keyClicks(editor, "send with enter")
        QTest.keyClick(editor, Qt.Key_Return)
        app.processEvents()

        assert submitted == [("send with enter", [])]
        assert editor.toPlainText() == ""

        editor.setFocus()
        QTest.keyClicks(editor, "line one")
        QTest.keyClick(editor, Qt.Key_Return, Qt.ShiftModifier)
        QTest.keyClicks(editor, "line two")
        app.processEvents()

        assert submitted == [("send with enter", [])]
        assert editor.toPlainText() == "line one\nline two"
    finally:
        window.close()


def test_thread_detail_view_thinking_event_is_bottom_temporary_message(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        view.clear_messages()
        view.add_message("You", [{"type": "text", "text": "Analyze this."}])
        view.apply_chatbot_event(
            ChatbotEvent(
                id="thinking-event",
                kind=ChatbotEventKind.THINKING,
                turn_id="turn",
                author=ChatbotEventAuthor.ASSISTANT,
                status=ChatbotEventStatus.IN_PROGRESS,
                content_blocks=[{"type": "thinking", "text": "Thinking..."}],
            )
        )
        app.processEvents()

        thinking = view._thinking_bubble
        assert thinking is not None
        assert thinking._blocks == [{"type": "thinking", "text": "Thinking..."}]
        assert view._message_layout.itemAt(view._message_layout.count() - 2).widget() is thinking

        view.apply_chatbot_event(
            ChatbotEvent(
                id="thinking-event",
                kind=ChatbotEventKind.THINKING,
                turn_id="turn",
                author=ChatbotEventAuthor.ASSISTANT,
                status=ChatbotEventStatus.COMPLETED,
            )
        )
        app.processEvents()

        assert view._thinking_bubble is None
    finally:
        window.close()


def test_main_window_keeps_thinking_indicator_during_non_final_snapshot(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    release_stream = False
    try:
        window._new_thread_button.click()
        app.processEvents()
        thread_id = window._agent_thread_id
        assert thread_id is not None
        snapshot = window._agent_harness_service.get_thread_snapshot(thread_id)

        def fake_submit(_input_data):
            nonlocal release_stream
            yield AgentHarnessStreamEvent(
                kind="snapshot",
                thread_id=thread_id,
                run_id="run-thinking",
                snapshot=snapshot,
                chatbot_events=[],
                is_final=False,
            )
            yield AgentHarnessStreamEvent(
                kind="chatbot_event",
                thread_id=thread_id,
                run_id="run-thinking",
                chatbot_event=ChatbotEvent(
                    id="run-thinking:thinking",
                    kind=ChatbotEventKind.THINKING,
                    turn_id="turn-thinking",
                    author=ChatbotEventAuthor.ASSISTANT,
                    status=ChatbotEventStatus.IN_PROGRESS,
                    content_blocks=[{"type": "thinking", "text": "Thinking..."}],
                ),
            )
            while not release_stream:
                time.sleep(0.01)

        monkeypatch.setattr(window._agent_harness_service, "submit_user_turn_stream", fake_submit)
        window._submit_chat_message("Analyze this.", [])

        for _ in range(40):
            app.processEvents()
            thinking = window._thread_detail_view._thinking_bubble
            if thinking is not None:
                break
            time.sleep(0.01)

        thinking = window._thread_detail_view._thinking_bubble
        assert thinking is not None
        assert thinking._blocks == [{"type": "thinking", "text": "Thinking..."}]
    finally:
        release_stream = True
        for _ in range(5):
            app.processEvents()
            time.sleep(0.01)
        window.close()


def test_thread_detail_view_composer_file_drag_hover_attaches_files(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    data_file = tmp_path / "customers.csv"
    data_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        for _ in range(8):
            app.processEvents()

        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(data_file))])
        composer_center = view._composer_shell.geometry().center()

        drag_enter = _FakeFileDropEvent(mime_data, composer_center.x(), composer_center.y())
        view.dragEnterEvent(drag_enter)
        app.processEvents()

        assert drag_enter.accepted is True
        assert view._composer_drop_overlay.isVisible() is True

        view._set_composer_drop_hover(False)
        editor_center = view._editor.viewport().rect().center()
        editor_drag_enter = _FakeFileDropEvent(
            mime_data,
            editor_center.x(),
            editor_center.y(),
            QEvent.DragEnter,
        )
        handled = view.eventFilter(view._editor.viewport(), editor_drag_enter)
        app.processEvents()

        assert handled is True
        assert editor_drag_enter.accepted is True
        assert view._composer_drop_overlay.isVisible() is True

        drop = _FakeFileDropEvent(mime_data, editor_center.x(), editor_center.y(), QEvent.Drop)
        handled = view.eventFilter(view._editor.viewport(), drop)
        app.processEvents()

        assert handled is True
        assert drop.accepted is True
        assert view._composer_drop_overlay.isHidden() is True
        assert view._attached_files == [str(data_file.resolve())]
        assert view._attachment_bar.isVisibleTo(window)
    finally:
        window.close()


def test_thread_detail_view_compact_editor_text_is_centered_with_buttons(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        editor = window._thread_detail_view._editor
        editor.setPlainText("Message Xenix")
        for _ in range(8):
            app.processEvents()

        cursor_center_y = (
            editor.geometry().y()
            + editor.viewport().geometry().y()
            + editor.cursorRect().center().y()
        )
        attach_center_y = window._thread_detail_view._attach_button.geometry().center().y()
        send_center_y = window._thread_detail_view._send_button.geometry().center().y()

        assert abs(cursor_center_y - attach_center_y) <= 1
        assert abs(cursor_center_y - send_center_y) <= 1
    finally:
        window.close()


def test_thread_detail_view_uses_available_width_for_user_messages(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        _seed_mock_history(window)
        window.resize(1200, 760)
        app.processEvents()
        view = window._thread_detail_view
        user_bubbles = []
        for item_index in range(view._message_layout.count()):
            item = view._message_layout.itemAt(item_index)
            if item is not None and item.widget() is not None:
                user_bubbles.append(item.widget())
        user_cards = [
            bubble._card
            for bubble in user_bubbles
            if getattr(bubble, "_card", None) is not None and bubble._card.objectName() == "chatMessageUser"
        ]

        assert view.isVisibleTo(window)
        assert user_cards
        assert user_cards[0].maximumWidth() == max(280, int(view._message_column.width() * 0.6))
    finally:
        window.close()


def test_thread_detail_view_message_cards_fit_content_height(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        app.processEvents()
        view = window._thread_detail_view
        for item_index in range(view._message_layout.count()):
            item = view._message_layout.itemAt(item_index)
            bubble = item.widget() if item is not None else None
            card = getattr(bubble, "_card", None)
            if card is None:
                continue
            layout = card.layout()
            margins = layout.contentsMargins() if layout is not None else card.contentsMargins()
            content_bottom = 0
            for child in card.findChildren(QWidget):
                if child.parentWidget() is card and child.isVisible():
                    content_bottom = max(content_bottom, child.geometry().y() + child.height())

            assert card.height() >= content_bottom + margins.bottom()
    finally:
        window.close()


def test_thread_detail_view_message_text_uses_transparent_native_background(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        app.processEvents()
        view = window._thread_detail_view
        view.clear_messages()
        view.add_message("Xenix", [{"type": "markdown", "text": "Transparent message text."}], auto_scroll=False)
        app.processEvents()

        bubble_item = view._message_layout.itemAt(0)
        bubble = bubble_item.widget() if bubble_item is not None else None
        card = getattr(bubble, "_card", None)
        browser = bubble.findChild(QTextBrowser) if bubble is not None else None

        assert card is not None
        assert card.frameShape() == QFrame.StyledPanel
        assert browser is not None
        assert not browser.autoFillBackground()
        assert browser.testAttribute(Qt.WA_TranslucentBackground)
        assert not browser.viewport().autoFillBackground()
        assert browser.viewport().testAttribute(Qt.WA_TranslucentBackground)
    finally:
        window.close()


def test_thread_detail_view_user_message_uses_native_black_panel(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        app.processEvents()
        view = window._thread_detail_view
        view.clear_messages()
        view.add_message("You", [{"type": "markdown", "text": "User message."}], auto_scroll=False)
        app.processEvents()

        bubble_item = view._message_layout.itemAt(0)
        bubble = bubble_item.widget() if bubble_item is not None else None
        card = getattr(bubble, "_card", None)
        browser = bubble.findChild(QTextBrowser) if bubble is not None else None

        assert card is not None
        assert card.objectName() == "chatMessageUser"
        assert card.frameShape() == QFrame.StyledPanel
        assert card.autoFillBackground()
        assert card.palette().color(QPalette.ColorRole.Window).name() == "#000000"
        assert browser is not None
        assert browser.palette().color(QPalette.ColorRole.Text).name() == "#ffffff"
        assert browser.viewport().palette().color(QPalette.ColorRole.Text).name() == "#ffffff"
    finally:
        window.close()


def test_thread_detail_view_scrolls_to_latest_message_after_append(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        scrollbar = view._scroll.verticalScrollBar()
        for _ in range(8):
            app.processEvents()

        scrollbar.setValue(0)
        view.add_message(
            "Xenix",
            [
                {
                    "type": "markdown",
                    "text": "\n\n".join(f"Generated analysis line {index}" for index in range(80)),
                }
            ],
        )
        for _ in range(12):
            app.processEvents()

        assert scrollbar.maximum() > 0
        assert scrollbar.value() == scrollbar.maximum()
    finally:
        window.close()


def test_thread_detail_view_updates_one_assistant_message_by_id(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        view.clear_messages()
        view.apply_message_event(
            AgentMessageRow(
                id="assistant-message",
                thread_id="thread",
                turn_id="turn",
                sequence_index=0,
                kind=AgentMessageKind.ASSISTANT,
                ui_author=AgentMessageAuthor.ASSISTANT,
                content_blocks=[{"type": "markdown", "text": "Streaming "}],
                status=AgentMessageStatus.IN_PROGRESS,
            )
        )
        view.apply_message_event(
            AgentMessageRow(
                id="assistant-message",
                thread_id="thread",
                turn_id="turn",
                sequence_index=0,
                kind=AgentMessageKind.ASSISTANT,
                ui_author=AgentMessageAuthor.ASSISTANT,
                content_blocks=[{"type": "markdown", "text": "Streaming assistant message."}],
                status=AgentMessageStatus.COMPLETED,
            )
        )
        for _ in range(8):
            app.processEvents()

        bubble = view._message_bubbles_by_id["assistant-message"]
        assert bubble is not None
        assert bubble._card.objectName() == "chatMessageAssistant"
        assert bubble._blocks == [{"type": "markdown", "text": "Streaming assistant message."}]
        assert len(view._message_bubbles_by_id) == 1
    finally:
        window.close()


def test_thread_detail_view_artifact_link_resolves_and_opens_file(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    artifact_path = tmp_path / "predictions.csv"
    artifact_path.write_text("prediction\n42\n", encoding="utf-8")
    opened_urls = []

    def fake_open_url(url):
        opened_urls.append(url)
        return True

    monkeypatch.setattr("xenix.ui.main_window.QDesktopServices.openUrl", fake_open_url)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        window._create_agent_thread()
        app.processEvents()
        thread_id = window._agent_thread_id
        assert thread_id is not None
        artifact = window._artifact_service.register_artifact(
            RegisterArtifactInput(
                thread_id=thread_id,
                title="Prediction results",
                absolute_path=str(artifact_path.resolve()),
                kind=ArtifactKind.PREDICTION,
                mime_type="text/csv",
            )
        )
        uri = f"artifact://{artifact.id}?view=preview"

        window._thread_detail_view.add_message(
            "Xenix",
            [{"type": "markdown", "text": f"Prediction results are ready: [Prediction results]({uri})"}],
        )
        app.processEvents()

        bubble = window._thread_detail_view._message_layout.itemAt(window._thread_detail_view._message_layout.count() - 2).widget()
        assert bubble._browser.openLinks() is False

        bubble.link_activated.emit(uri)
        app.processEvents()

        assert [Path(url.toLocalFile()) for url in opened_urls] == [artifact_path.resolve()]
    finally:
        window.close()


def test_main_window_uses_aimock_settings_in_development(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    streamed_text = "AIMock streamed this response."
    captured_urls: list[str] = []
    captured_payload: dict[str, object] = {}

    class FakeAIMockSSE:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def __iter__(self):
            chunks = [
                {"choices": [{"delta": {"content": "AIMock streamed "}}]},
                {"choices": [{"delta": {"content": "this response."}}]},
            ]
            for chunk in chunks:
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

    def fake_urlopen(http_request, timeout):
        captured_urls.append(http_request.full_url)
        captured_payload.update(json.loads(http_request.data.decode("utf-8")))
        return FakeAIMockSSE()

    monkeypatch.setattr("xenix.services.agent.providers.request.urlopen", fake_urlopen)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))
    monkeypatch.setenv("XENIX_ENV", "development")

    app, window = build_main_window(show=True)
    try:
        window._open_settings()
        settings = window._settings_dialog
        assert settings is not None
        assert settings._aimock_card.isVisibleTo(settings)

        settings._llm_model_input.setText("mock-model")
        settings._aimock_enabled_checkbox.setChecked(True)
        settings._aimock_base_url_input.setText("http://aimock.local")
        settings._aimock_api_key_input.setText("test-aimock")
        settings._save_button.click()
        app.processEvents()

        window._submit_chat_message("Use AIMock.", [])
        for _ in range(100):
            app.processEvents()
            if not window._thread_detail_view._running:
                break
            time.sleep(0.01)

        assert window._thread_detail_view._running is False
        assert captured_urls == ["http://aimock.local/v1/chat/completions"]
        assert captured_payload["stream"] is True
        assert captured_payload["model"] == "mock-model"
        assistant_texts = [
            str(block.get("text", ""))
            for index in range(window._thread_detail_view._message_layout.count())
            if (item := window._thread_detail_view._message_layout.itemAt(index)) is not None
            and (bubble := item.widget()) is not None
            and getattr(getattr(bubble, "_card", None), "objectName", lambda: "")() == "chatMessageAssistant"
            for block in getattr(bubble, "_blocks", [])
            if block.get("type") == "markdown"
        ]

        assert streamed_text in assistant_texts
    finally:
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window.close()
