import json
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from xenix.app import build_main_window
from xenix.main import main
from xenix.services.agent.dev_fixtures import MESSAGE_RENDERING_FIXTURE_TITLE


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
