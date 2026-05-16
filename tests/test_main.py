import json
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QWidget

from xenix.app import build_main_window
from xenix.main import main
from xenix.services.agent import AgentHarnessStreamEvent
from xenix.services.agent.dev_fixtures import MESSAGE_RENDERING_FIXTURE_TITLE


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


def test_main_window_keeps_settings_entry_on_chatbox_shell(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        assert window._chat_box.isVisibleTo(window)
        assert window._settings_button.text() == "Settings"

        window._settings_button.click()
        app.processEvents()

        assert window._settings_dialog is not None
        assert window._settings_dialog.isVisible()
        assert window._settings_dialog._aimock_card.isHidden() is True
    finally:
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_main_window_seeds_mock_history_and_renders_sidebar_selection(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        app.processEvents()

        titles = [window._history_list.item(index).text() for index in range(window._history_list.count())]

        assert MESSAGE_RENDERING_FIXTURE_TITLE in titles
        assert window._history_sidebar.isVisibleTo(window)
        assert window._history_list.count() >= 2
        assert window._chat_box._message_layout.count() > 1
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_main_window_renders_turn_end_tool_call_as_divider(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        target_item = None
        for index in range(window._history_list.count()):
            item = window._history_list.item(index)
            if item.text() == MESSAGE_RENDERING_FIXTURE_TITLE:
                target_item = item
                break
        assert target_item is not None

        window._open_history_thread(target_item)
        app.processEvents()

        divider_bubbles = []
        visible_turn_end_results = []
        for index in range(window._chat_box._message_layout.count()):
            item = window._chat_box._message_layout.itemAt(index)
            bubble = item.widget() if item is not None else None
            card = getattr(bubble, "_card", None)
            if card is not None and card.objectName() == "chatMessageDivider":
                divider_bubbles.append(bubble)
            for block in getattr(bubble, "_blocks", []):
                payload = block.get("payload")
                if block.get("type") == "tool_call_result" and block.get("tool_name") == "turn_end":
                    visible_turn_end_results.append(block)
                if block.get("type") == "tool_result_payload" and isinstance(payload, dict) and payload.get("turn_end") is True:
                    visible_turn_end_results.append(block)

        assert divider_bubbles
        assert all(bubble._blocks == [{"type": "turn_end"}] for bubble in divider_bubbles)
        assert visible_turn_end_results == []
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_main_window_renders_non_turn_end_tool_calls(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        target_item = None
        for index in range(window._history_list.count()):
            item = window._history_list.item(index)
            if item.text() == MESSAGE_RENDERING_FIXTURE_TITLE:
                target_item = item
                break
        assert target_item is not None

        window._open_history_thread(target_item)
        app.processEvents()

        tool_call_bubbles = []
        for index in range(window._chat_box._message_layout.count()):
            item = window._chat_box._message_layout.itemAt(index)
            bubble = item.widget() if item is not None else None
            if getattr(getattr(bubble, "_card", None), "objectName", lambda: "")() != "chatMessageTool":
                continue
            if any(block.get("type") == "tool_call" for block in getattr(bubble, "_blocks", [])):
                tool_call_bubbles.append(bubble)

        assert tool_call_bubbles
        assert any("Calling" in bubble._browser.toPlainText() for bubble in tool_call_bubbles)
    finally:
        window._ml_workspace._timer.stop()
        window.close()


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
        assert window._chat_box._message_layout.count() == 1
    finally:
        window._ml_workspace._timer.stop()
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
        window._ml_workspace._timer.stop()
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
        assert window._chat_box._step_confirmation_bar.isVisibleTo(window)
        assert window._chat_box._editor.isEnabled() is False
        assert "16/64" in window._chat_box._step_confirmation_label.text()

        captured_inputs = []

        def fake_continue(input_data):
            captured_inputs.append(input_data)
            yield AgentHarnessStreamEvent(kind="snapshot", thread_id=thread_id, snapshot=snapshot)

        monkeypatch.setattr(window._agent_harness_service, "continue_step_budget_stream", fake_continue)
        window._chat_box._step_continue_button.click()
        for _ in range(40):
            app.processEvents()
            if captured_inputs and not window._chat_box._running:
                break
            time.sleep(0.01)

        assert len(captured_inputs) == 1
        assert captured_inputs[0].thread_id == thread_id
        assert captured_inputs[0].turn_id == "turn-for-confirmation"
        assert captured_inputs[0].run_id == "run-for-confirmation"
        assert captured_inputs[0].additional_steps == 8
        assert window._pending_step_confirmation is None
        assert window._chat_box._step_confirmation_bar.isHidden() is True
    finally:
        window._ml_workspace._timer.stop()
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
        window._chat_box.set_running(True)
        window._chat_box.show_thinking_indicator()
        window._chat_box._send_button.click()
        app.processEvents()

        assert cancelled_run_ids == ["run-to-stop"]
        assert window._chat_box._running is False
        assert window._chat_box._thinking_bubble is None
        assert "run-to-stop" in window._cancelled_agent_run_ids
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_chatbox_composer_switches_layout_when_text_wraps(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
        editor = window._chat_box._editor
        compact_height = editor.height()

        assert window._chat_box._attach_button.isHidden() is False
        assert window._chat_box._send_button.isHidden() is False
        assert window._chat_box._expanded_attach_button.isHidden() is True
        assert window._chat_box._expanded_send_button.isHidden() is True

        editor.setPlainText("line one\nline two")
        app.processEvents()

        assert editor.height() > compact_height
        assert window._chat_box._attach_button.isHidden() is True
        assert window._chat_box._send_button.isHidden() is True
        assert window._chat_box._expanded_attach_button.isHidden() is False
        assert window._chat_box._expanded_send_button.isHidden() is False
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_chatbox_enter_submits_and_shift_enter_inserts_newline(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._chat_box
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
        window._ml_workspace._timer.stop()
        window.close()


def test_chatbox_thinking_indicator_is_bottom_temporary_message(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._chat_box
        view.clear_messages()
        view.add_message("You", [{"type": "text", "text": "Analyze this."}])
        view.show_thinking_indicator()
        app.processEvents()

        thinking = view._thinking_bubble
        assert thinking is not None
        assert thinking._blocks == [{"type": "thinking", "text": "Thinking..."}]
        assert view._message_layout.itemAt(view._message_layout.count() - 2).widget() is thinking

        view.append_assistant_delta("Working")
        app.processEvents()

        assert view._thinking_bubble is None
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_chatbox_composer_file_drag_hover_attaches_files(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    data_file = tmp_path / "customers.csv"
    data_file.write_text("name,value\nAcme,12\n", encoding="utf-8")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._chat_box
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
        window._ml_workspace._timer.stop()
        window.close()


def test_chatbox_compact_editor_text_is_centered_with_buttons(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        editor = window._chat_box._editor
        editor.setPlainText("Message Xenix")
        for _ in range(8):
            app.processEvents()

        cursor_center_y = (
            editor.geometry().y()
            + editor.viewport().geometry().y()
            + editor.cursorRect().center().y()
        )
        attach_center_y = window._chat_box._attach_button.geometry().center().y()
        send_center_y = window._chat_box._send_button.geometry().center().y()

        assert abs(cursor_center_y - attach_center_y) <= 1
        assert abs(cursor_center_y - send_center_y) <= 1
    finally:
        window._ml_workspace._timer.stop()
        window.close()


def test_thread_detail_view_uses_available_width_for_user_messages(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=False)
    try:
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
        window._ml_workspace._timer.stop()
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
        window._ml_workspace._timer.stop()
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
        window._ml_workspace._timer.stop()
        window.close()


def test_thread_detail_view_appends_streaming_delta_to_one_assistant_message(monkeypatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    app, window = build_main_window(show=True)
    try:
        view = window._thread_detail_view
        view.clear_messages()
        view.append_assistant_delta("Streaming ")
        view.append_assistant_delta("assistant ")
        view.append_assistant_delta("message.")
        for _ in range(8):
            app.processEvents()

        bubble = view._streaming_assistant_bubble
        assert bubble is not None
        assert bubble._card.objectName() == "chatMessageAssistant"
        assert bubble._blocks == [{"type": "markdown", "text": "Streaming assistant message."}]

        view.finish_streaming_assistant_message()

        assert view._streaming_assistant_bubble is None
    finally:
        window._ml_workspace._timer.stop()
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
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_turn_end",
                                        "function": {
                                            "name": "turn_end",
                                            "arguments": "{}",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
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
            if not window._chat_box._running:
                break
            time.sleep(0.01)

        assert window._chat_box._running is False
        assert captured_urls == ["http://aimock.local/v1/chat/completions"]
        assert captured_payload["stream"] is True
        assert captured_payload["model"] == "mock-model"
        assistant_texts = [
            str(block.get("text", ""))
            for index in range(window._chat_box._message_layout.count())
            if (item := window._chat_box._message_layout.itemAt(index)) is not None
            and (bubble := item.widget()) is not None
            and getattr(getattr(bubble, "_card", None), "objectName", lambda: "")() == "chatMessageAssistant"
            for block in getattr(bubble, "_blocks", [])
            if block.get("type") == "markdown"
        ]

        assert streamed_text in assistant_texts
    finally:
        if window._settings_dialog is not None:
            window._settings_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()
