from __future__ import annotations

import json
import os
from importlib import import_module
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ...config import AppPaths
from ...exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from ..agent.providers import OpenAICompatibleChatProvider

SETTINGS_FILE_NAME = "agent_settings.json"
DEFAULT_PROVIDER_KEY = "openai"
DEFAULT_MODEL_KEY = "gpt-4o-mini"
DEFAULT_FQ_MODEL_KEY = f"{DEFAULT_PROVIDER_KEY}/{DEFAULT_MODEL_KEY}"
TRIAL_PROVIDER_KEY = "trial"
TRIAL_PROVIDER_DISPLAY_NAME = "Trial"
PACKAGED_TRIAL_SECRET_SOURCE = "packaged_trial"
TRIAL_LLM_BASE_URL_FALLBACK = "https://api.openai.com"
TRIAL_LLM_MODEL_FALLBACK = DEFAULT_MODEL_KEY


class XenixEnvironment(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class LLMDialect(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"


class AimockSettings(BaseModel):
    enabled: bool = False
    base_url: str = "http://127.0.0.1:4010"
    api_key: str = "test"


class LLMProviderConfig(BaseModel):
    key: str = DEFAULT_PROVIDER_KEY
    display_name: str = "OpenAI"
    dialect: LLMDialect = LLMDialect.OPENAI_COMPATIBLE
    base_url: str = "https://api.openai.com"
    api_key: str = ""
    models: list[str] = Field(default_factory=lambda: [DEFAULT_MODEL_KEY])
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    streaming_enabled: bool = True
    dialect_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _validate_provider_key(cls, value: str) -> str:
        provider_key = value.strip()
        if not provider_key:
            raise ValueError("Provider key cannot be empty.")
        if "/" in provider_key:
            raise ValueError("Provider key cannot contain '/'.")
        return provider_key

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: list[str]) -> list[str]:
        models: list[str] = []
        seen: set[str] = set()
        for raw_model in value:
            model_key = str(raw_model).strip()
            if not model_key:
                continue
            if "/" in model_key:
                raise ValueError("Model key cannot contain '/'.")
            if model_key not in seen:
                models.append(model_key)
                seen.add(model_key)
        if not models:
            raise ValueError("Provider must define at least one model.")
        return models


class PackagedTrialLLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip())


class LLMModelRef(BaseModel):
    provider_key: str
    model_key: str


class LLMModelOption(BaseModel):
    fq_model_key: str
    provider_key: str
    model_key: str
    label: str


def default_llm_settings() -> "LLMSettings":
    trial_config = load_packaged_trial_llm_config()
    if trial_config.enabled:
        return LLMSettings(
            providers=[
                LLMProviderConfig(
                    key=TRIAL_PROVIDER_KEY,
                    display_name=TRIAL_PROVIDER_DISPLAY_NAME,
                    dialect=LLMDialect.OPENAI_COMPATIBLE,
                    base_url=trial_config.base_url,
                    api_key="",
                    models=[trial_config.model],
                    dialect_config={"secret_source": PACKAGED_TRIAL_SECRET_SOURCE},
                )
            ],
            default_fq_model_key=LLMService.fq_model_key(TRIAL_PROVIDER_KEY, trial_config.model),
        )
    return LLMSettings(
        providers=[LLMProviderConfig()],
        default_fq_model_key=DEFAULT_FQ_MODEL_KEY,
    )


class LLMSettings(BaseModel):
    providers: list[LLMProviderConfig] = Field(
        default_factory=lambda: [LLMProviderConfig()]
    )
    default_fq_model_key: str = DEFAULT_FQ_MODEL_KEY
    turn_completion_guard_fq_model_key: str = ""
    thread_title_fq_model_key: str = ""
    aimock: AimockSettings = Field(default_factory=AimockSettings)

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
        if not self.providers:
            self.providers = [LLMProviderConfig()]

        provider_keys: set[str] = set()
        available: set[str] = set()
        for provider in self.providers:
            if provider.key in provider_keys:
                raise ValueError(f"Provider key '{provider.key}' is duplicated.")
            provider_keys.add(provider.key)
            for model_key in provider.models:
                available.add(LLMService.fq_model_key(provider.key, model_key))

        if self.default_fq_model_key not in available:
            first_provider = self.providers[0]
            self.default_fq_model_key = LLMService.fq_model_key(
                first_provider.key,
                first_provider.models[0],
            )

        for field_name in (
            "turn_completion_guard_fq_model_key",
            "thread_title_fq_model_key",
        ):
            fq_model_key = getattr(self, field_name)
            if fq_model_key and fq_model_key not in available:
                raise ValueError(f"{field_name} does not match a configured provider model.")
        return self


class LLMSettingsService:
    def __init__(self, paths: AppPaths) -> None:
        self._settings_path = paths.config / SETTINGS_FILE_NAME
        self._environment = _read_environment()

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    @property
    def environment(self) -> XenixEnvironment:
        return self._environment

    def is_development(self) -> bool:
        return self._environment is XenixEnvironment.DEVELOPMENT

    def load(self) -> LLMSettings:
        if not self._settings_path.exists():
            return default_llm_settings()
        payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return LLMSettings.model_validate(payload)

    def save(self, settings: LLMSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = sanitize_settings_for_save(settings)
        self._settings_path.write_text(
            sanitized.model_dump_json(indent=2),
            encoding="utf-8",
        )


class LLMService:
    def __init__(self, settings_service: LLMSettingsService) -> None:
        self._settings_service = settings_service

    @property
    def settings_service(self) -> LLMSettingsService:
        return self._settings_service

    def load_settings(self) -> LLMSettings:
        return self._settings_service.load()

    def save_settings(self, settings: LLMSettings) -> None:
        self._settings_service.save(settings)

    def default_fq_model_key(self) -> str:
        return self.load_settings().default_fq_model_key

    def model_options(self) -> list[LLMModelOption]:
        return self.model_options_from_settings(self.load_settings())

    def build_provider(self, fq_model_key: str | None = None) -> "OpenAICompatibleChatProvider":
        from ..agent.providers import OpenAICompatibleChatProvider

        settings = self.load_settings()
        selected_key = fq_model_key or settings.default_fq_model_key
        ref = self.parse_fq_model_key(selected_key)
        provider_config = self._provider_for_key(settings, ref.provider_key)
        if ref.model_key not in provider_config.models:
            raise NotFoundError(f"LLM model '{selected_key}' was not found.")
        if provider_config.dialect is not LLMDialect.OPENAI_COMPATIBLE:
            raise ValidationError(
                f"LLM dialect '{provider_config.dialect.value}' is not supported yet."
            )
        if self._settings_service.is_development() and settings.aimock.enabled:
            return OpenAICompatibleChatProvider(
                provider_key=provider_config.key,
                base_url=settings.aimock.base_url,
                api_key=settings.aimock.api_key,
                model=ref.model_key,
                timeout_seconds=provider_config.timeout_seconds,
                streaming_enabled=provider_config.streaming_enabled,
            )
        trial_config = load_packaged_trial_llm_config()
        if provider_config.dialect_config.get("secret_source") == PACKAGED_TRIAL_SECRET_SOURCE:
            if not trial_config.enabled:
                raise ValidationError("Packaged trial LLM provider is not available in this build.")
            return OpenAICompatibleChatProvider(
                provider_key=provider_config.key,
                base_url=trial_config.base_url,
                api_key=trial_config.api_key,
                model=ref.model_key,
                timeout_seconds=provider_config.timeout_seconds,
                streaming_enabled=provider_config.streaming_enabled,
            )
        return OpenAICompatibleChatProvider(
            provider_key=provider_config.key,
            base_url=provider_config.base_url,
            api_key=provider_config.api_key,
            model=ref.model_key,
            timeout_seconds=provider_config.timeout_seconds,
            streaming_enabled=provider_config.streaming_enabled,
        )

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

    @staticmethod
    def fq_model_key(provider_key: str, model_key: str) -> str:
        provider = provider_key.strip()
        model = model_key.strip()
        if not provider:
            raise ValidationError("Provider key cannot be empty.")
        if not model:
            raise ValidationError("Model key cannot be empty.")
        if "/" in provider:
            raise ValidationError("Provider key cannot contain '/'.")
        if "/" in model:
            raise ValidationError("Model key cannot contain '/'.")
        return f"{provider}/{model}"

    @staticmethod
    def parse_fq_model_key(fq_model_key: str) -> LLMModelRef:
        normalized = fq_model_key.strip()
        parts = normalized.split("/")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValidationError("Model key must use 'provider/model' format.")
        provider_key, model_key = parts[0].strip(), parts[1].strip()
        if "/" in model_key:
            raise ValidationError("Model key cannot contain '/'.")
        return LLMModelRef(provider_key=provider_key, model_key=model_key)

    @staticmethod
    def model_options_from_settings(settings: LLMSettings) -> list[LLMModelOption]:
        options: list[LLMModelOption] = []
        for provider in settings.providers:
            provider_label = provider.display_name or provider.key
            for model_key in provider.models:
                fq_model_key = LLMService.fq_model_key(provider.key, model_key)
                options.append(
                    LLMModelOption(
                        fq_model_key=fq_model_key,
                        provider_key=provider.key,
                        model_key=model_key,
                        label=f"{provider_label} / {model_key}",
                    )
                )
        return options

    def _provider_for_key(self, settings: LLMSettings, provider_key: str) -> LLMProviderConfig:
        for provider in settings.providers:
            if provider.key == provider_key:
                return provider
        raise NotFoundError(f"LLM provider '{provider_key}' was not found.")


def _read_environment() -> XenixEnvironment:
    raw = os.getenv("XENIX_ENV", XenixEnvironment.PRODUCTION.value).strip().lower()
    if raw == XenixEnvironment.DEVELOPMENT.value:
        return XenixEnvironment.DEVELOPMENT
    return XenixEnvironment.PRODUCTION


def load_packaged_trial_llm_config() -> PackagedTrialLLMConfig:
    try:
        generated_trial_llm = import_module("xenix._generated_trial_llm")
    except ModuleNotFoundError as exc:
        if exc.name != "xenix._generated_trial_llm":
            raise
        return PackagedTrialLLMConfig(
            base_url=TRIAL_LLM_BASE_URL_FALLBACK,
            api_key="",
            model=TRIAL_LLM_MODEL_FALLBACK,
        )
    return PackagedTrialLLMConfig(
        base_url=str(
            getattr(generated_trial_llm, "TRIAL_LLM_BASE_URL", TRIAL_LLM_BASE_URL_FALLBACK)
            or TRIAL_LLM_BASE_URL_FALLBACK
        ).rstrip("/"),
        api_key=str(getattr(generated_trial_llm, "TRIAL_LLM_API_KEY", "") or ""),
        model=str(
            getattr(generated_trial_llm, "TRIAL_LLM_MODEL", TRIAL_LLM_MODEL_FALLBACK)
            or TRIAL_LLM_MODEL_FALLBACK
        ).strip()
        or TRIAL_LLM_MODEL_FALLBACK,
    )


def sanitize_settings_for_save(settings: LLMSettings) -> LLMSettings:
    providers: list[LLMProviderConfig] = []
    for provider in settings.providers:
        if provider.dialect_config.get("secret_source") == PACKAGED_TRIAL_SECRET_SOURCE:
            providers.append(provider.model_copy(update={"api_key": ""}))
            continue
        providers.append(provider)
    return settings.model_copy(update={"providers": providers}, deep=True)


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
        "aimock": payload.get("aimock") or {},
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
