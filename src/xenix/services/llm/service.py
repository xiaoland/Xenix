from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from pydantic import BaseModel, Field, model_validator

from ...config import AppPaths
from ...exceptions import NotFoundError, ValidationError
from ..ai_providers import (
    DEFAULT_FQ_MODEL_KEY as DEFAULT_FQ_MODEL_KEY,
    DEFAULT_MODEL_KEY as DEFAULT_MODEL_KEY,
    DEFAULT_PROVIDER_KEY as DEFAULT_PROVIDER_KEY,
    AIModelKind,
    AIModelOption,
    AIModelRef,
    AIProtocol,
    AIProviderConfig,
    fq_model_key,
    model_options,
    parse_fq_model_key,
)
from .providers import (
    LLMRequestMetadata,
    LLMRetryEvent,
    OpenAICompatibleChatProvider,
    ProviderMessage,
    ProviderResponse,
    ProviderStreamEvent,
)
from .tool_protocol import (
    AgentToolSpec,
)

SETTINGS_FILE_NAME = "agent_settings.json"
LLMDialect = AIProtocol
LLMModelOption = AIModelOption
LLMModelRef = AIModelRef
LLMProviderConfig = AIProviderConfig


class ConversationSettings(BaseModel):
    default_fq_model_key: str = DEFAULT_FQ_MODEL_KEY
    turn_completion_guard_fq_model_key: str = ""
    thread_title_fq_model_key: str = ""
    retry_attempts: int = Field(default=5, ge=1, le=20)


class LLMSettings(ConversationSettings):
    providers: list[LLMProviderConfig] = Field(default_factory=lambda: [LLMProviderConfig()])

    def conversation_settings(self) -> ConversationSettings:
        return ConversationSettings.model_construct(
            **self.model_dump(include=set(ConversationSettings.model_fields))
        )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "providers" in value:
            return value
        return _legacy_payload_to_settings(value)

    @model_validator(mode="after")
    def _validate_model_references(self) -> LLMSettings:
        # Older settings may still contain the provider supplied by the installer.
        # Its key was editable, so identify it by the persisted source marker.
        providers: list[LLMProviderConfig] = []
        retired_models: set[str] = set()
        for provider in self.providers:
            if provider.dialect_config.get("secret_source") == "packaged_trial":
                retired_models.update(LLMService.fq_model_key(provider.key, model) for model in provider.models)
            else:
                providers.append(provider)
        self.providers = providers
        if not self.providers:
            self.providers = [LLMProviderConfig()]

        provider_keys: set[str] = set()
        for provider in self.providers:
            if provider.key in provider_keys:
                raise ValueError(f"Provider key '{provider.key}' is duplicated.")
            provider_keys.add(provider.key)
        options = model_options(self.providers, AIModelKind.CHAT)
        available = {option.fq_model_key for option in options}
        if self.default_fq_model_key not in available:
            self.default_fq_model_key = options[0].fq_model_key if options else ""

        for field_name in (
            "turn_completion_guard_fq_model_key",
            "thread_title_fq_model_key",
        ):
            fq_model_key = getattr(self, field_name)
            if fq_model_key and fq_model_key not in available:
                if fq_model_key not in retired_models:
                    raise ValueError(f"{field_name} does not match a configured provider model.")
                setattr(self, field_name, "")
        return self


class LLMSettingsSource(Protocol):
    """Supplies the settings used by an ``LLMService`` instance."""

    def load(self) -> LLMSettings: ...


class FrozenLLMSettingsSource:
    """Read-only, in-memory settings source for an isolated LLM service."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings.model_copy(deep=True)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    def load(self) -> LLMSettings:
        return self._settings.model_copy(deep=True)

    def save(self, settings: LLMSettings) -> None:
        raise ValidationError(
            "LLM settings are read-only for this run.",
            error_code="llm_settings_read_only",
        )


class LLMSettingsService:
    def __init__(self, paths: AppPaths) -> None:
        self._settings_path = paths.config / SETTINGS_FILE_NAME

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    def load(self) -> LLMSettings:
        if not self._settings_path.exists():
            return LLMSettings()
        payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return LLMSettings.model_validate(payload)

    def save(self, settings: LLMSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(
            settings.model_dump_json(indent=2),
            encoding="utf-8",
        )


class LLMService:
    def __init__(self, settings_service: LLMSettingsSource) -> None:
        self._settings_service = settings_service

    @property
    def settings_service(self) -> LLMSettingsSource:
        return self._settings_service

    def load_settings(self) -> LLMSettings:
        return self._settings_service.load()

    def default_fq_model_key(self) -> str:
        return self.load_settings().default_fq_model_key

    def model_options(self) -> list[LLMModelOption]:
        return self.model_options_from_settings(self.load_settings())

    def complete(
        self,
        *,
        fq_model_key: str | None = None,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
        retry_callback: Callable[[LLMRetryEvent], None] | None = None,
        before_provider_request: Callable[[], None] | None = None,
    ) -> ProviderResponse:
        settings = self.load_settings()
        provider = self._build_provider_from_settings(settings, fq_model_key)
        return self._complete_with_retry(
            provider=provider,
            messages=messages,
            tools=tools,
            max_attempts=settings.retry_attempts,
            retry_callback=retry_callback,
            before_provider_request=before_provider_request,
        )

    def stream(
        self,
        *,
        fq_model_key: str | None = None,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
        before_provider_request: Callable[[], None] | None = None,
    ) -> Iterator[ProviderStreamEvent | LLMRetryEvent]:
        settings = self.load_settings()
        provider = self._build_provider_from_settings(settings, fq_model_key)
        max_attempts = self._max_attempts(settings.retry_attempts)
        previous_error: Exception | None = None
        for attempt_number in range(1, max_attempts + 1):
            if previous_error is not None:
                yield self._retry_event(
                    attempt_number=attempt_number,
                    max_attempts=max_attempts,
                    exc=previous_error,
                )
            if before_provider_request is not None:
                before_provider_request()
            try:
                stream = getattr(provider, "stream", None)
                if callable(stream):
                    # Buffer deltas until the attempt succeeds so a retryable
                    # mid-stream error never replays partial text twice.
                    # Tool-call-progress deltas carry no text content, so they
                    # stream live to keep the UI progress indicator immediate.
                    buffered_events = []
                    events = stream(messages, tools)
                    for event in events:
                        if self._is_live_tool_call_progress(event):
                            yield event
                            continue
                        buffered_events.append(event)
                else:
                    response = provider.complete(messages, tools)
                    buffered_events = [ProviderStreamEvent(response=response)]
                yield from buffered_events
                return
            except Exception as exc:
                if not self._should_retry(exc, attempt_number=attempt_number, max_attempts=max_attempts):
                    raise
                previous_error = exc
                self._retry_backoff(attempt_number)

    def _is_live_tool_call_progress(self, event: ProviderStreamEvent) -> bool:
        return event.is_tool_call_delta and not event.delta_text and event.response is None

    def request_metadata(self, fq_model_key: str | None = None) -> LLMRequestMetadata:
        settings = self.load_settings()
        selected_key = fq_model_key or settings.default_fq_model_key
        if not selected_key:
            raise NotFoundError("No chat model is configured.")
        ref = self.parse_fq_model_key(selected_key)
        provider_config = self._provider_for_key(settings, ref.provider_key)
        if ref.model_key not in provider_config.models:
            raise NotFoundError(f"LLM model '{selected_key}' was not found.")
        return LLMRequestMetadata(provider_name=provider_config.key, model=ref.model_key)

    def turn_completion_guard_fq_model_key(self) -> str | None:
        value = self.load_settings().turn_completion_guard_fq_model_key.strip()
        return value or None

    def thread_title_fq_model_key(self) -> str | None:
        value = self.load_settings().thread_title_fq_model_key.strip()
        return value or None

    def build_provider(self, fq_model_key: str | None = None) -> OpenAICompatibleChatProvider:
        return self._build_provider_from_settings(self.load_settings(), fq_model_key)

    def _build_provider_from_settings(
        self,
        settings: LLMSettings,
        fq_model_key: str | None = None,
    ) -> OpenAICompatibleChatProvider:
        selected_key = fq_model_key or settings.default_fq_model_key
        if not selected_key:
            raise NotFoundError("No chat model is configured.")
        ref = self.parse_fq_model_key(selected_key)
        provider_config = self._provider_for_key(settings, ref.provider_key)
        if ref.model_key not in provider_config.models:
            raise NotFoundError(f"LLM model '{selected_key}' was not found.")
        if provider_config.dialect is not LLMDialect.OPENAI_COMPATIBLE:
            raise ValidationError(
                f"LLM dialect '{provider_config.dialect.value}' is not supported yet."
            )
        return OpenAICompatibleChatProvider(
            provider_key=provider_config.key,
            base_url=provider_config.base_url,
            api_key=provider_config.api_key,
            model=ref.model_key,
            timeout_seconds=provider_config.timeout_seconds,
            streaming_enabled=provider_config.streaming_enabled,
        )

    def _complete_with_retry(
        self,
        *,
        provider,
        messages: list[ProviderMessage],
        tools: list[AgentToolSpec],
        max_attempts: int,
        retry_callback: Callable[[LLMRetryEvent], None] | None,
        before_provider_request: Callable[[], None] | None,
    ) -> ProviderResponse:
        attempts = self._max_attempts(max_attempts)
        previous_error: Exception | None = None
        for attempt_number in range(1, attempts + 1):
            if previous_error is not None and retry_callback is not None:
                retry_callback(
                    self._retry_event(
                        attempt_number=attempt_number,
                        max_attempts=attempts,
                        exc=previous_error,
                    )
                )
            if before_provider_request is not None:
                before_provider_request()
            try:
                return provider.complete(messages, tools)
            except Exception as exc:
                if not self._should_retry(exc, attempt_number=attempt_number, max_attempts=attempts):
                    raise
                previous_error = exc
                self._retry_backoff(attempt_number)
        raise AssertionError("LLM retry loop exited without a response or exception.")

    def _should_retry(self, exc: Exception, *, attempt_number: int, max_attempts: int) -> bool:
        if attempt_number >= max_attempts:
            return False
        return getattr(exc, "retryable", None) is True

    def _retry_backoff(self, attempt_number: int) -> None:
        """Sleep before a retry so transient provider throttling can reset."""
        time.sleep(min(2.0 ** (attempt_number - 1), 8.0))

    def _retry_event(self, *, attempt_number: int, max_attempts: int, exc: Exception) -> LLMRetryEvent:
        error_code = getattr(exc, "error_code", None)
        return LLMRetryEvent(
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            reason="retryable_error",
            error_summary=str(exc),
            error_code=error_code if isinstance(error_code, str) else None,
        )

    def _max_attempts(self, value: int) -> int:
        if isinstance(value, bool):
            return 1
        return max(1, min(int(value), 20))

    def build_turn_completion_guard_provider(self) -> "OpenAICompatibleChatProvider | None":
        fq_model_key = self.load_settings().turn_completion_guard_fq_model_key
        if not fq_model_key:
            return None
        return self.build_provider(fq_model_key)

    def build_thread_title_provider(self) -> "OpenAICompatibleChatProvider | None":
        fq_model_key = self.load_settings().thread_title_fq_model_key
        if not fq_model_key:
            return None
        return self.build_provider(fq_model_key)

    def validate_fq_model_key(self, fq_model_key: str) -> str:
        normalized = fq_model_key.strip()
        ref = self.parse_fq_model_key(normalized)
        settings = self.load_settings()
        provider = self._provider_for_key(settings, ref.provider_key)
        if ref.model_key not in provider.models:
            raise NotFoundError(f"LLM model '{normalized}' was not found.")
        return normalized

    fq_model_key = staticmethod(fq_model_key)
    parse_fq_model_key = staticmethod(parse_fq_model_key)

    @staticmethod
    def model_options_from_settings(settings: LLMSettings) -> list[LLMModelOption]:
        return model_options(settings.providers, AIModelKind.CHAT)

    def _provider_for_key(self, settings: LLMSettings, provider_key: str) -> LLMProviderConfig:
        for provider in settings.providers:
            if provider.key == provider_key:
                return provider
        raise NotFoundError(f"LLM provider '{provider_key}' was not found.")


def _legacy_payload_to_settings(payload: dict[str, Any]) -> dict[str, Any]:
    model = str(payload.get("model") or DEFAULT_MODEL_KEY).strip() or DEFAULT_MODEL_KEY
    guard_model = str(payload.get("turn_completion_guard_model") or "").strip()
    title_model = str(payload.get("thread_title_model") or "").strip()
    models = _unique_non_empty([model, guard_model, title_model])
    provider = {
        "key": DEFAULT_PROVIDER_KEY,
        "display_name": "OpenAI-compatible",
        "dialect": LLMDialect.OPENAI_COMPATIBLE.value,
        "base_url": str(payload.get("base_url") or "https://api.openai.com").strip(),
        "api_key": str(payload.get("api_key") or ""),
        "models": models or [DEFAULT_MODEL_KEY],
        "timeout_seconds": payload.get("timeout_seconds", 120),
        "streaming_enabled": payload.get("streaming_enabled", True),
    }
    settings = {
        "providers": [provider],
        "default_fq_model_key": LLMService.fq_model_key(DEFAULT_PROVIDER_KEY, model),
        "turn_completion_guard_fq_model_key": (
            LLMService.fq_model_key(DEFAULT_PROVIDER_KEY, guard_model) if guard_model else ""
        ),
        "thread_title_fq_model_key": (
            LLMService.fq_model_key(DEFAULT_PROVIDER_KEY, title_model) if title_model else ""
        ),
    }
    return settings


def _unique_non_empty(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
