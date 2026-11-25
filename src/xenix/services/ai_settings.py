from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import AppPaths
from .ai_providers import AIProviderConfig, fq_model_key
from .embedding_service import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    MAX_EMBEDDING_DIMENSIONS,
    EmbeddingSettings,
    EmbeddingSettingsService,
)
from .llm.service import ConversationSettings, LLMSettings, LLMSettingsService


class KnowledgeEmbeddingSettings(BaseModel):
    fq_model_key: str = ""
    enabled: bool = False
    dimensions: int | None = Field(default=None, ge=1, le=MAX_EMBEDDING_DIMENSIONS)
    batch_size: int = Field(default=DEFAULT_EMBEDDING_BATCH_SIZE, ge=1, le=2048)


class AISettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    providers: list[AIProviderConfig] = Field(default_factory=lambda: [AIProviderConfig()])
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    knowledge: KnowledgeEmbeddingSettings = Field(default_factory=KnowledgeEmbeddingSettings)

    @model_validator(mode="after")
    def _validate_references(self) -> AISettings:
        llm = LLMSettings(providers=self.providers, **self.conversation.model_dump())
        self.providers = llm.providers
        self.conversation = llm.conversation_settings()
        self.embedding_settings()
        return self

    def llm_settings(self) -> LLMSettings:
        return LLMSettings.model_construct(providers=self.providers, **self.conversation.model_dump())

    def embedding_settings(self) -> EmbeddingSettings:
        selection = self.knowledge
        if not selection.fq_model_key:
            if selection.enabled:
                raise ValueError("Select an embedding model to enable text vectors.")
            return EmbeddingSettings(dimensions=selection.dimensions, batch_size=selection.batch_size)
        provider_key, _, model_key = selection.fq_model_key.partition("/")
        provider = next((item for item in self.providers if item.key == provider_key), None)
        if provider is None or model_key not in provider.embedding_models:
            raise ValueError("The selected embedding model is unavailable.")
        return EmbeddingSettings(
            enabled=selection.enabled,
            provider_key=provider.embedding_profile_key or provider.key,
            dialect=provider.dialect,
            base_url=provider.base_url,
            api_key=provider.api_key,
            model=model_key,
            dimensions=selection.dimensions,
            batch_size=selection.batch_size,
            timeout_seconds=provider.timeout_seconds,
        )


class AISettingsService:
    """Own the desktop settings snapshot for providers and their consumers."""

    def __init__(self, paths: AppPaths) -> None:
        self._settings_path = paths.config / "ai_settings.json"
        self._legacy_llm = LLMSettingsService(paths)
        self._legacy_embedding = EmbeddingSettingsService(paths)

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    def load(self) -> AISettings:
        if self._settings_path.exists():
            return AISettings.model_validate_json(self._settings_path.read_bytes())
        llm = self._legacy_llm.load()
        providers = llm.providers
        conversation = llm.conversation_settings()
        if not self._legacy_embedding.settings_path.exists():
            return AISettings(providers=providers, conversation=conversation)

        embedding = self._legacy_embedding.load()
        equivalent = [
            item for item in providers
            if item.dialect == embedding.dialect
            and item.base_url.rstrip("/").removesuffix("/v1") == embedding.base_url.removesuffix("/v1")
            and item.api_key == embedding.api_key
            and item.timeout_seconds == embedding.timeout_seconds
            and item.embedding_profile_key in {None, embedding.provider_key}
        ]
        provider = next(
            (item for item in equivalent if item.key == embedding.provider_key),
            equivalent[0] if equivalent else None,
        )
        if provider is not None:
            # Both adapters use the same API root. Retain the legacy URL spelling
            # and provider key used by the existing vector-space fingerprint.
            provider.base_url = embedding.base_url
            if provider.key != embedding.provider_key:
                provider.embedding_profile_key = embedding.provider_key
            if embedding.model not in provider.embedding_models:
                provider.embedding_models.append(embedding.model)
        else:
            keys = {item.key for item in providers}
            key = embedding.provider_key
            if "/" in key or key in keys:
                key = "embedding"
                suffix = 2
                while key in keys:
                    key = f"embedding-{suffix}"
                    suffix += 1
            provider = AIProviderConfig(
                key=key,
                display_name=embedding.provider_key,
                dialect=embedding.dialect,
                base_url=embedding.base_url,
                api_key=embedding.api_key,
                timeout_seconds=embedding.timeout_seconds,
                models=[],
                embedding_models=[embedding.model],
                embedding_profile_key=embedding.provider_key if key != embedding.provider_key else None,
            )
            providers.append(provider)
        return AISettings(
            providers=providers,
            conversation=conversation,
            knowledge=KnowledgeEmbeddingSettings(
                fq_model_key=fq_model_key(provider.key, embedding.model),
                enabled=embedding.enabled,
                dimensions=embedding.dimensions,
                batch_size=embedding.batch_size,
            ),
        )

    def save(self, settings: AISettings) -> None:
        payload = settings.model_dump_json(indent=2)
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=self._settings_path.parent) as directory:
            temporary = Path(directory) / self._settings_path.name
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(self._settings_path)


class AIConversationSettingsSource:
    def __init__(self, service: AISettingsService) -> None:
        self._service = service

    def load(self) -> LLMSettings:
        return self._service.load().llm_settings()


class AIEmbeddingSettingsSource:
    def __init__(self, service: AISettingsService) -> None:
        self._service = service

    def load(self) -> EmbeddingSettings:
        return self._service.load().embedding_settings()
