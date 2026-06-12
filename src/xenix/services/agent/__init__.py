from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "AppendAgentMessageInput": ".conversation_store",
    "CompleteProviderRequestInput": ".conversation_store",
    "CompleteToolCallInput": ".conversation_store",
    "ConversationStore": ".conversation_store",
    "CreateAgentThreadInput": ".conversation_store",
    "CreateProviderRequestInput": ".conversation_store",
    "CreateToolCallInput": ".conversation_store",
    "CreateTurnCompletionGuardInput": ".conversation_store",
    "FinishAgentRunInput": ".conversation_store",
    "RenameAgentThreadInput": ".conversation_store",
    "StartAgentRunInput": ".conversation_store",
    "StartTurnInput": ".conversation_store",
    "ThreadSnapshot": ".conversation_store",
    "UpdateAgentMessageInput": ".conversation_store",
    "UpdateAgentThreadModelInput": ".conversation_store",
    "ChatbotEvent": ".chatbot_events",
    "ChatbotEventAuthor": ".chatbot_events",
    "ChatbotEventKind": ".chatbot_events",
    "ChatbotEventStatus": ".chatbot_events",
    "build_thinking_chatbot_event": ".chatbot_events",
    "project_chatbot_events": ".chatbot_events",
    "thinking_chatbot_event_id": ".chatbot_events",
    "AgentHarnessService": ".harness_service",
    "AgentHarnessStreamEvent": ".harness_service",
    "ContinueStepBudgetInput": ".harness_service",
    "DatasetAttachmentInput": ".harness_service",
    "SubmitUserTurnInput": ".harness_service",
    "OpenAICompatibleChatProvider": ".providers",
    "ProviderMessage": ".providers",
    "ProviderResponse": ".providers",
    "ProviderStreamEvent": ".providers",
    "ProviderToolCall": ".providers",
    "ScriptedAgentProvider": ".providers",
    "AgentSettings": ".settings",
    "AgentSettingsService": ".settings",
    "AimockSettings": ".settings",
    "LLMDialect": "..llm",
    "LLMModelOption": "..llm",
    "LLMProviderConfig": "..llm",
    "LLMService": "..llm",
    "LLMSettings": "..llm",
    "LLMSettingsService": "..llm",
    "AgentToolRegistry": ".tools",
    "ToolPresentation": ".tool_presentations",
    "tool_presentation_for_name": ".tool_presentations",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> object:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
