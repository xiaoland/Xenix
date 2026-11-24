from __future__ import annotations

from typing import Any

from xenix.services.agent import AgentHarnessService, SubmitUserTurnInput
from xenix.services.llm import (
    AgentToolRegistry,
    FrozenLLMSettingsSource,
    LLMConversationService,
    LLMProviderConfig,
    LLMService,
    LLMSettings,
    OpenAICompatibleChatProvider,
)


def test_switching_thread_model_dispatches_switched_provider_and_model_payload(
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
                api_key="alpha-secret",
                models=["model-a", "model-a2"],
                streaming_enabled=False,
            ),
            LLMProviderConfig(
                key="beta",
                display_name="Beta",
                base_url="https://beta.example.test",
                api_key="beta-secret",
                models=["model-b"],
                streaming_enabled=False,
            ),
        ],
        default_fq_model_key="alpha/model-a",
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
                        "content": f"reply from {self.provider_key}/{payload['model']}",
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleChatProvider, "_post_json", fake_post_json)

    llm_service = LLMService(FrozenLLMSettingsSource(settings))
    conversation = LLMConversationService(
        session_factory=storage.session_factory,
        tool_registry=AgentToolRegistry(paged_results_dir=tmp_path / "pages"),
        llm_service=llm_service,
    )
    harness = AgentHarnessService(conversation_service=conversation, llm_service=llm_service)

    first_turn = harness.submit_user_turn(SubmitUserTurnInput(text="Hello on default model"))
    thread_id = first_turn.thread.id
    assert first_turn.thread.selected_fq_model_key == "alpha/model-a"

    switched = harness.set_thread_model(thread_id, "beta/model-b")
    assert switched.thread.selected_fq_model_key == "beta/model-b"

    second_turn = harness.submit_user_turn(
        SubmitUserTurnInput(thread_id=thread_id, text="Continue on switched model")
    )
    assert second_turn.thread.selected_fq_model_key == "beta/model-b"

    third_turn = harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread_id,
            text="Switch inline on submit",
            fq_model_key="alpha/model-a2",
        )
    )
    assert third_turn.thread.selected_fq_model_key == "alpha/model-a2"

    assert dispatched == [
        {
            "provider_key": "alpha",
            "base_url": "https://alpha.example.test",
            "api_key": "alpha-secret",
            "model": "model-a",
        },
        {
            "provider_key": "beta",
            "base_url": "https://beta.example.test",
            "api_key": "beta-secret",
            "model": "model-b",
        },
        {
            "provider_key": "alpha",
            "base_url": "https://alpha.example.test",
            "api_key": "alpha-secret",
            "model": "model-a2",
        },
    ]
