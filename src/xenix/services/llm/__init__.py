"""Public LLM services, loaded on access so protocol imports stay lightweight."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import (
        DEFAULT_FQ_MODEL_KEY as DEFAULT_FQ_MODEL_KEY,
        DEFAULT_MODEL_KEY as DEFAULT_MODEL_KEY,
        DEFAULT_PROVIDER_KEY as DEFAULT_PROVIDER_KEY,
        FrozenLLMSettingsSource as FrozenLLMSettingsSource,
        LLMDialect as LLMDialect,
        LLMModelOption as LLMModelOption,
        LLMModelRef as LLMModelRef,
        LLMProviderConfig as LLMProviderConfig,
        LLMService as LLMService,
        LLMSettings as LLMSettings,
        LLMSettingsSource as LLMSettingsSource,
        LLMSettingsService as LLMSettingsService,
        PACKAGED_TRIAL_SECRET_SOURCE as PACKAGED_TRIAL_SECRET_SOURCE,
        PackagedTrialLLMConfig as PackagedTrialLLMConfig,
        TRIAL_PROVIDER_DISPLAY_NAME as TRIAL_PROVIDER_DISPLAY_NAME,
        TRIAL_PROVIDER_KEY as TRIAL_PROVIDER_KEY,
        default_llm_settings as default_llm_settings,
        load_packaged_trial_llm_config as load_packaged_trial_llm_config,
        sanitize_settings_for_save as sanitize_settings_for_save,
    )
    from .providers import (
        AgentProvider as AgentProvider,
        LLMRequestMetadata as LLMRequestMetadata,
        LLMRetryEvent as LLMRetryEvent,
        OpenAICompatibleChatProvider as OpenAICompatibleChatProvider,
        ProviderMessage as ProviderMessage,
        ProviderResponse as ProviderResponse,
        ProviderStreamEvent as ProviderStreamEvent,
        ProviderToolCall as ProviderToolCall,
        ScriptedAgentProvider as ScriptedAgentProvider,
        extract_reasoning_content as extract_reasoning_content,
    )
    from .messages import (
        AssistantOutputItem as AssistantOutputItem,
        CanonicalMessageBlock as CanonicalMessageBlock,
        ContentBlock as ContentBlock,
        DatasetBlock as DatasetBlock,
        MarkdownBlock as MarkdownBlock,
        MessageBlock as MessageBlock,
        MessageContentBlock as MessageContentBlock,
        ProviderOutputItem as ProviderOutputItem,
        SourceAttachmentBlock as SourceAttachmentBlock,
        TextBlock as TextBlock,
        ToolCallOutputItem as ToolCallOutputItem,
        blocks_from_payload as blocks_from_payload,
        blocks_to_json as blocks_to_json,
        blocks_to_markdown as blocks_to_markdown,
        normalize_message_block as normalize_message_block,
        normalize_message_blocks as normalize_message_blocks,
    )
    from .conversation import (
        AppendUserMessageInput as AppendUserMessageInput,
        ConversationLiveEvent as ConversationLiveEvent,
        ConversationSnapshot as ConversationSnapshot,
        ConversationUsageOverview as ConversationUsageOverview,
        CreateConversationThreadInput as CreateConversationThreadInput,
        LLMConversationService as LLMConversationService,
        PendingSampling as PendingSampling,
        SubmissionClaim as SubmissionClaim,
        ThreadPausedError as ThreadPausedError,
    )
    from .tool_protocol import (
        MAX_EXCHANGE_RESULT_BYTES as MAX_EXCHANGE_RESULT_BYTES,
        MAX_TOOL_CALLS as MAX_TOOL_CALLS,
        MAX_TOOL_PAYLOAD_BYTES as MAX_TOOL_PAYLOAD_BYTES,
        AgentToolImplementation as AgentToolImplementation,
        AgentToolSpec as AgentToolSpec,
        ToolFailure as ToolFailure,
        ToolInvocationOutcome as ToolInvocationOutcome,
        ToolResultValue as ToolResultValue,
        ToolSuccess as ToolSuccess,
        ToolExecutionContext as ToolExecutionContext,
        ToolScope as ToolScope,
        StagedToolCall as StagedToolCall,
        TerminalToolResult as TerminalToolResult,
        canonical_tool_result_value as canonical_tool_result_value,
        canonical_json_bytes as canonical_json_bytes,
        ensure_bounded_json as ensure_bounded_json,
        ensure_bounded_tool_result_value as ensure_bounded_tool_result_value,
        scope_fingerprint as scope_fingerprint,
        terminal_tool_result as terminal_tool_result,
        tool_failure_from_exception as tool_failure_from_exception,
    )
    from .tool_registry import (
        AgentToolRegistry as AgentToolRegistry,
    )
    from .xenix_table_text import (
        render_xenix_table_tool_result as render_xenix_table_tool_result,
    )
    from .tool_protocol import (
        AgentTool as AgentTool,
    )

_EXPORTS = {
    "AgentProvider": ".providers",
    "AgentToolSpec": ".tool_protocol",
    "AgentToolImplementation": ".tool_protocol",
    "AgentToolRegistry": ".tool_registry",
    "AppendUserMessageInput": ".conversation",
    "AssistantOutputItem": ".messages",
    "CanonicalMessageBlock": ".messages",
    "ContentBlock": ".messages",
    "DatasetBlock": ".messages",
    "DEFAULT_FQ_MODEL_KEY": ".service",
    "DEFAULT_MODEL_KEY": ".service",
    "DEFAULT_PROVIDER_KEY": ".service",
    "FrozenLLMSettingsSource": ".service",
    "LLMDialect": ".service",
    "LLMRequestMetadata": ".providers",
    "LLMRetryEvent": ".providers",
    "LLMModelOption": ".service",
    "LLMModelRef": ".service",
    "LLMConversationService": ".conversation",
    "LLMProviderConfig": ".service",
    "LLMService": ".service",
    "LLMSettings": ".service",
    "LLMSettingsSource": ".service",
    "LLMSettingsService": ".service",
    "MarkdownBlock": ".messages",
    "MessageBlock": ".messages",
    "MessageContentBlock": ".messages",
    "OpenAICompatibleChatProvider": ".providers",
    "PACKAGED_TRIAL_SECRET_SOURCE": ".service",
    "PackagedTrialLLMConfig": ".service",
    "ProviderMessage": ".providers",
    "ProviderResponse": ".providers",
    "ProviderOutputItem": ".messages",
    "ProviderStreamEvent": ".providers",
    "ProviderToolCall": ".providers",
    "ScriptedAgentProvider": ".providers",
    "SourceAttachmentBlock": ".messages",
    "TextBlock": ".messages",
    "TRIAL_PROVIDER_DISPLAY_NAME": ".service",
    "TRIAL_PROVIDER_KEY": ".service",
    "ToolCallOutputItem": ".messages",
    "ToolFailure": ".tool_protocol",
    "ToolInvocationOutcome": ".tool_protocol",
    "ToolResultValue": ".tool_protocol",
    "ToolSuccess": ".tool_protocol",
    "ToolExecutionContext": ".tool_protocol",
    "ToolScope": ".tool_protocol",
    "ConversationLiveEvent": ".conversation",
    "ConversationSnapshot": ".conversation",
    "ConversationUsageOverview": ".conversation",
    "CreateConversationThreadInput": ".conversation",
    "PendingSampling": ".conversation",
    "SubmissionClaim": ".conversation",
    "ThreadPausedError": ".conversation",
    "StagedToolCall": ".tool_protocol",
    "TerminalToolResult": ".tool_protocol",
    "default_llm_settings": ".service",
    "extract_reasoning_content": ".providers",
    "load_packaged_trial_llm_config": ".service",
    "sanitize_settings_for_save": ".service",
    "MAX_TOOL_CALLS": ".tool_protocol",
    "MAX_TOOL_PAYLOAD_BYTES": ".tool_protocol",
    "MAX_EXCHANGE_RESULT_BYTES": ".tool_protocol",
    "canonical_tool_result_value": ".tool_protocol",
    "canonical_json_bytes": ".tool_protocol",
    "ensure_bounded_json": ".tool_protocol",
    "ensure_bounded_tool_result_value": ".tool_protocol",
    "scope_fingerprint": ".tool_protocol",
    "terminal_tool_result": ".tool_protocol",
    "tool_failure_from_exception": ".tool_protocol",
    "render_xenix_table_tool_result": ".xenix_table_text",
    "blocks_from_payload": ".messages",
    "blocks_to_json": ".messages",
    "blocks_to_markdown": ".messages",
    "normalize_message_block": ".messages",
    "normalize_message_blocks": ".messages",
    "AgentTool": ".tool_protocol",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
