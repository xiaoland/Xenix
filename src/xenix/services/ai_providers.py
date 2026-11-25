from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..exceptions import ValidationError

DEFAULT_PROVIDER_KEY = "openai"
DEFAULT_MODEL_KEY = "gpt-4o-mini"
DEFAULT_FQ_MODEL_KEY = f"{DEFAULT_PROVIDER_KEY}/{DEFAULT_MODEL_KEY}"


class AIProtocol(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"


class AIModelKind(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"


class AIProviderConfig(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    key: str = DEFAULT_PROVIDER_KEY
    display_name: str = "OpenAI"
    dialect: AIProtocol = AIProtocol.OPENAI_COMPATIBLE
    base_url: str = "https://api.openai.com"
    api_key: str = Field(default="", repr=False)
    models: list[str] = Field(default_factory=lambda: [DEFAULT_MODEL_KEY])
    embedding_models: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    streaming_enabled: bool = True
    dialect_config: dict[str, Any] = Field(default_factory=dict)
    # Preserve the vector-space identity if a legacy provider key collides.
    embedding_profile_key: str | None = None

    @field_validator("key")
    @classmethod
    def _validate_provider_key(cls, value: str) -> str:
        key = value.strip()
        if not key or "/" in key:
            raise ValueError("Provider key must be nonempty and cannot contain '/'.")
        return key

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("models", "embedding_models")
    @classmethod
    def _normalize_models(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(model.strip() for model in value if model.strip()))

    @model_validator(mode="after")
    def _require_models(self) -> AIProviderConfig:
        if not self.models and not self.embedding_models:
            raise ValueError("Provider must define at least one model.")
        return self


class AIModelRef(BaseModel):
    provider_key: str
    model_key: str


class AIModelOption(AIModelRef):
    fq_model_key: str
    label: str


def fq_model_key(provider_key: str, model_key: str) -> str:
    provider, model = provider_key.strip(), model_key.strip()
    if not provider or "/" in provider or not model:
        raise ValidationError("Model key must use 'provider/model' format.")
    return f"{provider}/{model}"


def parse_fq_model_key(value: str) -> AIModelRef:
    provider, separator, model = value.strip().partition("/")
    if not separator or not provider.strip() or not model.strip():
        raise ValidationError("Model key must use 'provider/model' format.")
    return AIModelRef(provider_key=provider.strip(), model_key=model.strip())


def model_options(providers: list[AIProviderConfig], kind: AIModelKind) -> list[AIModelOption]:
    return [
        AIModelOption(
            fq_model_key=fq_model_key(provider.key, model),
            provider_key=provider.key,
            model_key=model,
            label=f"{provider.display_name or provider.key} / {model}",
        )
        for provider in providers
        for model in (provider.models if kind is AIModelKind.CHAT else provider.embedding_models)
    ]
