"""Connected product-path acceptance: real MainWindow -> Harness -> LLM -> SQLite -> restart.

Unlike mocked UI unit tests, this suite wires the real production services and
database end-to-end, stubbing only the outermost HTTP transport boundary, and
reopens a fresh MainWindow against the same SQLite state to verify persistence
across restarts.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QPushButton, QTextBrowser
from pytestqt.qtbot import QtBot

from tests.support.ui_queries import find_control
from xenix.services.agent import AgentHarnessService
from xenix.services.artifact_service import ArtifactService
from xenix.services.link_router import LinkRouter
from xenix.services.llm import (
    AgentToolRegistry,
    FrozenLLMSettingsSource,
    LLMConversationService,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    OpenAICompatibleChatProvider,
)
from xenix.ui.history import HarnessHistoryAdapter
from xenix.ui.main_window import MainWindow
from xenix.ui.windows.auxiliary import AuxiliaryWindowCoordinator


def _build_connected_window(
    qtbot: QtBot,
    *,
    storage,
    tmp_path,
    llm_service: LLMService,
) -> MainWindow:
    artifact_service = ArtifactService(storage.session_factory)
    conversation_service = LLMConversationService(
        session_factory=storage.session_factory,
        tool_registry=AgentToolRegistry(paged_results_dir=tmp_path / "pages"),
        llm_service=llm_service,
    )
    harness = AgentHarnessService(
        conversation_service=conversation_service,
        llm_service=llm_service,
    )
    window = MainWindow(
        current_locale=lambda: "en_US",
        agent_harness_service=harness,
        llm_service=llm_service,
        artifact_service=artifact_service,
        link_router=LinkRouter(artifact_service=artifact_service),
        history_port=HarnessHistoryAdapter(harness),
        auxiliary_factory=lambda owner: AuxiliaryWindowCoordinator(
            owner,
            settings_factory=lambda _parent: None,  # type: ignore[arg-type,return-value]
            knowledge_factory=None,
        ),
    )
    qtbot.addWidget(window)
    window.show()
    return window


def test_desktop_composer_model_switch_persists_and_survives_window_restart(
    qtbot: QtBot,
    storage,
    tmp_path,
    monkeypatch,
) -> None:
    settings = LLMSettings(
        providers=[
            LLMProviderConfig(
                key="alpha",
                display_name="Alpha",
                base_url="https://alpha.example.test",
                api_key="alpha-key",
                models=["default-model"],
                streaming_enabled=False,
            ),
            LLMProviderConfig(
                key="beta",
                display_name="Beta",
                base_url="https://beta.example.test",
                api_key="beta-key",
                models=["analyst-model"],
                streaming_enabled=False,
            ),
        ],
        default_fq_model_key="alpha/default-model",
    )
    dispatched: list[dict[str, Any]] = []

    def fake_post_json(self: OpenAICompatibleChatProvider, payload: dict[str, Any]) -> dict[str, Any]:
        dispatched.append(
            {
                "provider_key": self.provider_key,
                "base_url": self._base_url,
                "api_key": self._api_key,
                "model": payload["model"],
            }
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"Verified response via {self.provider_key}/{payload['model']}",
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatProvider, "_post_json", fake_post_json)
    llm_service = LLMService(FrozenLLMSettingsSource(settings))

    # Session 1: switch to beta/analyst-model via the semantic UI control, send, observe reply.
    first_window = _build_connected_window(
        qtbot,
        storage=storage,
        tmp_path=tmp_path,
        llm_service=llm_service,
    )
    picker = find_control(first_window, "chat.composer.model-picker", QComboBox)
    editor = find_control(first_window, "chat.composer.editor", QPlainTextEdit)
    send_button = find_control(first_window, "chat.composer.send-or-stop", QPushButton)

    target_index = picker.findData("beta/analyst-model")
    assert target_index >= 0
    picker.setCurrentIndex(target_index)
    editor.setPlainText("Summarize Q4 margin")
    qtbot.mouseClick(send_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: first_window.conversation_idle and len(dispatched) == 1,
        timeout=10_000,
    )
    assert dispatched == [
        {
            "provider_key": "beta",
            "base_url": "https://beta.example.test",
            "api_key": "beta-key",
            "model": "analyst-model",
        }
    ]
    assert any(
        "Verified response via beta/analyst-model" in browser.toPlainText()
        for browser in first_window.findChildren(QTextBrowser)
    )
    first_window.close()

    # Session 2: reopen a fresh MainWindow against the same SQLite database and verify continuity.
    reopened_window = _build_connected_window(
        qtbot,
        storage=storage,
        tmp_path=tmp_path,
        llm_service=llm_service,
    )
    reopened_picker = find_control(reopened_window, "chat.composer.model-picker", QComboBox)
    assert reopened_picker.currentData() == "beta/analyst-model"
    assert any(
        "Verified response via beta/analyst-model" in browser.toPlainText()
        for browser in reopened_window.findChildren(QTextBrowser)
    )
    reopened_window.close()
