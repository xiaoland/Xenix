from __future__ import annotations

from ..llm import AimockSettings, LLMSettings, LLMSettingsService, XenixEnvironment

AgentSettings = LLMSettings
AgentSettingsService = LLMSettingsService

__all__ = [
    "AgentSettings",
    "AgentSettingsService",
    "AimockSettings",
    "XenixEnvironment",
]
