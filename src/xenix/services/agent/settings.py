from __future__ import annotations

import json
import os
from enum import StrEnum

from pydantic import BaseModel, Field

from ...config import AppPaths
from .providers import OpenAICompatibleChatProvider

SETTINGS_FILE_NAME = "agent_settings.json"


class XenixEnvironment(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class AimockSettings(BaseModel):
    enabled: bool = False
    base_url: str = "http://127.0.0.1:4010"
    api_key: str = "test"


class AgentSettings(BaseModel):
    base_url: str = "https://api.openai.com"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    streaming_enabled: bool = True
    aimock: AimockSettings = Field(default_factory=AimockSettings)


class AgentSettingsService:
    def __init__(self, paths: AppPaths) -> None:
        self._settings_path = paths.config / SETTINGS_FILE_NAME
        self._environment = _read_environment()

    @property
    def settings_path(self):
        return self._settings_path

    @property
    def environment(self) -> XenixEnvironment:
        return self._environment

    def is_development(self) -> bool:
        return self._environment is XenixEnvironment.DEVELOPMENT

    def load(self) -> AgentSettings:
        if not self._settings_path.exists():
            return AgentSettings()
        payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return AgentSettings.model_validate(payload)

    def save(self, settings: AgentSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(
            settings.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def build_provider(self) -> OpenAICompatibleChatProvider:
        settings = self.load()
        if self.is_development() and settings.aimock.enabled:
            return OpenAICompatibleChatProvider(
                base_url=settings.aimock.base_url,
                api_key=settings.aimock.api_key,
                model=settings.model,
                timeout_seconds=settings.timeout_seconds,
                streaming_enabled=settings.streaming_enabled,
            )
        return OpenAICompatibleChatProvider(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            streaming_enabled=settings.streaming_enabled,
        )


def _read_environment() -> XenixEnvironment:
    raw = os.getenv("XENIX_ENV", XenixEnvironment.PRODUCTION.value).strip().lower()
    if raw == XenixEnvironment.DEVELOPMENT.value:
        return XenixEnvironment.DEVELOPMENT
    return XenixEnvironment.PRODUCTION
