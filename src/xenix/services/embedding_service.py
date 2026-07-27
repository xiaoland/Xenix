from __future__ import annotations

import json
import math
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
)

from ..config import AppPaths
from ..exceptions import ValidationError

SETTINGS_FILE_NAME = "embedding_settings.json"
EMBEDDING_SETTINGS_FILE_NAME = SETTINGS_FILE_NAME
TEXT_PREPARATION_VERSION = "nfkc-trim-v1"
EMBEDDING_ADAPTER_VERSION = "openai-compatible-v1"
MAX_EMBEDDING_TEXT_CHARS = 12_000
MAX_EMBEDDING_DIMENSIONS = 65_536
DEFAULT_EMBEDDING_BATCH_SIZE = 20

_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_PROFILE_SCHEMA = "xenix.embedding-profile/v1"
_ENCODING_FORMAT = "float"


class EmbeddingDialect(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"


class EmbeddingSettings(BaseModel):
    """User-owned settings for the independent embedding provider."""

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
        validate_assignment=True,
    )

    schema_version: Literal[1] = 1
    enabled: bool = False
    provider_key: str = "openai"
    dialect: EmbeddingDialect = EmbeddingDialect.OPENAI_COMPATIBLE
    base_url: str = "https://api.openai.com"
    api_key: str = Field(default="", repr=False)
    model: str = "text-embedding-3-small"
    dimensions: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=MAX_EMBEDDING_DIMENSIONS,
    )
    batch_size: int = Field(
        default=DEFAULT_EMBEDDING_BATCH_SIZE,
        strict=True,
        ge=1,
        le=2_048,
    )
    timeout_seconds: int = Field(default=120, strict=True, ge=1, le=3_600)

    @field_validator("provider_key", "model")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        if not normalized:
            raise ValueError("Embedding provider and model identifiers cannot be empty.")
        return normalized

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)


class EmbeddingValidationError(ValidationError):
    """A bounded embedding-domain failure safe to show outside the adapter."""


class EmbeddingSettingsSource(Protocol):
    def load(self) -> EmbeddingSettings: ...


class EmbeddingSettingsService:
    def __init__(self, paths: AppPaths) -> None:
        self._settings_path = paths.config / SETTINGS_FILE_NAME

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    def load(self) -> EmbeddingSettings:
        if not self._settings_path.exists():
            return EmbeddingSettings()

        invalid = False
        try:
            raw_payload = self._settings_path.read_text(encoding="utf-8")
            payload = json.loads(raw_payload)
            settings = EmbeddingSettings.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, PydanticValidationError):
            invalid = True
            settings = None
        if invalid or settings is None:
            raise EmbeddingValidationError(
                "Embedding settings could not be loaded.",
                error_code="embedding_settings_invalid",
            )
        return settings

    def save(self, settings: EmbeddingSettings) -> None:
        failed = False
        try:
            validated = EmbeddingSettings.model_validate(settings)
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._settings_path.write_text(
                validated.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except (OSError, UnicodeError, PydanticValidationError):
            failed = True
        if failed:
            raise EmbeddingValidationError(
                "Embedding settings could not be saved.",
                error_code="embedding_settings_save_failed",
            )


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    provider_key: str
    model: str
    dimensions: int | None
    profile_fingerprint: str


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    profile: EmbeddingProfile
    vectors: tuple[tuple[float, ...], ...]

    @property
    def dimensions(self) -> int:
        """The provider's actual vector dimension for this validated batch."""

        return len(self.vectors[0])

    @property
    def embeddings(self) -> tuple[tuple[float, ...], ...]:
        """Compatibility-friendly name for consumers that use provider terminology."""

        return self.vectors

    def __len__(self) -> int:
        return len(self.vectors)


@runtime_checkable
class EmbeddingSession(Protocol):
    @property
    def profile(self) -> EmbeddingProfile: ...

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch: ...


@runtime_checkable
class EmbeddingService(Protocol):
    def freeze(self) -> EmbeddingSession | None: ...

    def configured_profile(self) -> EmbeddingProfile | None: ...

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch: ...


@dataclass(frozen=True, slots=True)
class _OpenAICompatibleEmbeddingSession:
    _service: OpenAICompatibleEmbeddingService
    _settings: EmbeddingSettings
    profile: EmbeddingProfile

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._service._embed_texts_with_settings(self._settings, texts)


class OpenAICompatibleEmbeddingService:
    """OpenAI-compatible adapter with an explicit immutable operation snapshot."""

    def __init__(self, settings_source: EmbeddingSettingsSource) -> None:
        self._settings_source = settings_source

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    def freeze(self) -> EmbeddingSession | None:
        settings = self._settings_snapshot()
        if not settings.enabled:
            return None
        self._require_supported_dialect(settings)
        return _OpenAICompatibleEmbeddingSession(
            _service=self,
            _settings=settings,
            profile=_profile_from_settings(settings),
        )

    def configured_profile(self) -> EmbeddingProfile | None:
        session = self.freeze()
        return session.profile if session is not None else None

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        session = self.freeze()
        if session is None:
            raise EmbeddingValidationError(
                "Embedding is not enabled.",
                error_code="embedding_not_enabled",
            )
        return session.embed_texts(texts)

    def _embed_texts_with_settings(
        self,
        settings: EmbeddingSettings,
        texts: Sequence[str],
    ) -> EmbeddingBatch:
        prepared_texts = _prepare_texts(texts)

        resolved_dimensions = settings.dimensions
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(prepared_texts), settings.batch_size):
            input_batch = prepared_texts[start : start + settings.batch_size]
            output_batch = self._embed_batch(
                settings,
                input_batch,
                expected_dimensions=resolved_dimensions,
            )
            if resolved_dimensions is None:
                resolved_dimensions = len(output_batch[0])
            vectors.extend(output_batch)

        profile = _profile_from_settings(settings)
        return EmbeddingBatch(profile=profile, vectors=tuple(vectors))

    def _settings_snapshot(self) -> EmbeddingSettings:
        failed = False
        try:
            loaded = self._settings_source.load()
            if not isinstance(loaded, EmbeddingSettings):
                failed = True
                snapshot = None
            else:
                snapshot = EmbeddingSettings.model_validate(loaded).model_copy(deep=True)
        except EmbeddingValidationError:
            raise
        except Exception:
            failed = True
            snapshot = None
        if failed or snapshot is None:
            raise EmbeddingValidationError(
                "Embedding settings are unavailable.",
                error_code="embedding_settings_unavailable",
            )
        return snapshot

    def _require_supported_dialect(self, settings: EmbeddingSettings) -> None:
        if settings.dialect is not EmbeddingDialect.OPENAI_COMPATIBLE:
            raise EmbeddingValidationError(
                "The configured embedding dialect is not supported.",
                error_code="embedding_dialect_unsupported",
            )

    def _embed_batch(
        self,
        settings: EmbeddingSettings,
        texts: list[str],
        *,
        expected_dimensions: int | None,
    ) -> list[tuple[float, ...]]:
        payload: dict[str, Any] = {
            "model": settings.model,
            "input": texts,
            "encoding_format": _ENCODING_FORMAT,
        }
        if settings.dimensions is not None:
            payload["dimensions"] = settings.dimensions

        request_body: bytes | None = None
        try:
            request_body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            pass
        if request_body is None:
            raise EmbeddingValidationError(
                "Embedding input could not be encoded safely.",
                error_code="embedding_request_invalid_input",
            )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_key = settings.api_key.strip()
        if api_key:
            invalid_api_key = "\r" in api_key or "\n" in api_key
            try:
                api_key.encode("latin-1")
            except UnicodeError:
                invalid_api_key = True
            if invalid_api_key:
                raise EmbeddingValidationError(
                    "Embedding API key cannot be used as an HTTP credential.",
                    error_code="embedding_api_key_invalid",
                )
            headers["Authorization"] = f"Bearer {api_key}"

        http_request: urllib.request.Request | None = None
        try:
            http_request = urllib.request.Request(
                _embeddings_endpoint(settings.base_url),
                data=request_body,
                headers=headers,
                method="POST",
            )
        except Exception:
            pass
        if http_request is None:
            raise EmbeddingValidationError(
                "Embedding request could not be constructed safely.",
                error_code="embedding_request_invalid",
            )
        response_payload = self._post_json(http_request, timeout_seconds=settings.timeout_seconds)
        return _parse_embeddings_response(
            response_payload,
            expected_count=len(texts),
            expected_dimensions=expected_dimensions,
        )

    def _post_json(self, http_request: urllib.request.Request, *, timeout_seconds: int) -> Any:
        failure: EmbeddingValidationError | None = None
        raw_body: bytes | None = None
        try:
            with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
                body = _read_bounded_response(response)
                if isinstance(body, bytes):
                    raw_body = body
                elif isinstance(body, bytearray):
                    raw_body = bytes(body)
                else:
                    failure = EmbeddingValidationError(
                        "Embedding provider returned an invalid response.",
                        error_code="embedding_response_invalid_type",
                    )
        except urllib.error.HTTPError as exc:
            status_code = exc.code if isinstance(exc.code, int) and not isinstance(exc.code, bool) else None
            try:
                exc.close()
            except Exception:
                pass
            failure = EmbeddingValidationError(
                "Embedding provider rejected the request.",
                error_code="embedding_provider_http_error",
                error_details={"status_code": status_code} if status_code is not None else None,
                retryable=status_code in {408, 409, 425, 429, 500, 502, 503, 504},
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            failure = EmbeddingValidationError(
                "Embedding provider is unavailable.",
                error_code="embedding_provider_unavailable",
                retryable=True,
            )
        except Exception:
            failure = EmbeddingValidationError(
                "Embedding provider request failed.",
                error_code="embedding_provider_request_failed",
            )

        if failure is not None:
            raise failure
        if raw_body is None or len(raw_body) > _MAX_RESPONSE_BYTES:
            raise EmbeddingValidationError(
                "Embedding provider returned an invalid response.",
                error_code="embedding_response_invalid_size",
            )

        invalid_json = False
        try:
            decoded = raw_body.decode("utf-8")
            payload = json.loads(decoded)
        except (UnicodeError, ValueError, json.JSONDecodeError):
            invalid_json = True
            payload = None
        if invalid_json:
            raise EmbeddingValidationError(
                "Embedding provider returned invalid JSON.",
                error_code="embedding_response_invalid_json",
            )
        return payload


def _prepare_texts(texts: Sequence[str]) -> list[str]:
    if isinstance(texts, (str, bytes, bytearray)) or not isinstance(texts, Sequence):
        raise EmbeddingValidationError(
            "Embedding input must be a sequence of text values.",
            error_code="embedding_input_invalid_type",
        )
    if not texts:
        raise EmbeddingValidationError(
            "Embedding input cannot be empty.",
            error_code="embedding_input_empty",
        )

    prepared: list[str] = []
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            raise EmbeddingValidationError(
                "Every embedding input must be text.",
                error_code="embedding_text_invalid_type",
                error_details={"text_index": index},
            )
        normalized = unicodedata.normalize("NFKC", text).strip()
        if not normalized:
            raise EmbeddingValidationError(
                "Embedding text cannot be empty after preparation.",
                error_code="embedding_text_empty",
                error_details={"text_index": index},
            )
        if len(normalized) > MAX_EMBEDDING_TEXT_CHARS:
            raise EmbeddingValidationError(
                "Embedding text exceeds the supported length.",
                error_code="embedding_text_too_long",
                error_details={
                    "text_index": index,
                    "max_characters": MAX_EMBEDDING_TEXT_CHARS,
                },
            )
        prepared.append(normalized)
    return prepared


def _read_bounded_response(response: Any) -> Any:
    """Read at most one byte beyond the accepted provider response size."""

    return response.read(_MAX_RESPONSE_BYTES + 1)


def _parse_embeddings_response(
    payload: Any,
    *,
    expected_count: int,
    expected_dimensions: int | None,
) -> list[tuple[float, ...]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise EmbeddingValidationError(
            "Embedding provider returned an invalid response shape.",
            error_code="embedding_response_invalid_shape",
        )

    data = payload["data"]
    if len(data) != expected_count:
        raise EmbeddingValidationError(
            "Embedding provider returned an unexpected result count.",
            error_code="embedding_response_count_mismatch",
            error_details={"expected_count": expected_count, "actual_count": len(data)},
        )

    by_index: dict[int, tuple[float, ...]] = {}
    dimensions_seen: set[int] = set()
    for item in data:
        if not isinstance(item, dict):
            raise EmbeddingValidationError(
                "Embedding provider returned an invalid result item.",
                error_code="embedding_response_invalid_item",
            )

        index = item.get("index")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= expected_count
            or index in by_index
        ):
            raise EmbeddingValidationError(
                "Embedding provider returned an invalid result index.",
                error_code="embedding_response_invalid_index",
            )

        raw_vector = item.get("embedding")
        if not isinstance(raw_vector, list) or not raw_vector:
            raise EmbeddingValidationError(
                "Embedding provider returned an invalid vector.",
                error_code="embedding_response_invalid_vector",
            )

        vector: list[float] = []
        for coordinate in raw_vector:
            if not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool):
                raise EmbeddingValidationError(
                    "Embedding provider returned a non-numeric vector.",
                    error_code="embedding_response_invalid_vector_type",
                )
            try:
                numeric_coordinate = float(coordinate)
            except (OverflowError, TypeError, ValueError):
                raise EmbeddingValidationError(
                    "Embedding provider returned a non-numeric vector.",
                    error_code="embedding_response_invalid_vector_type",
                ) from None
            if not math.isfinite(numeric_coordinate):
                raise EmbeddingValidationError(
                    "Embedding provider returned a non-finite vector.",
                    error_code="embedding_response_non_finite",
                )
            vector.append(numeric_coordinate)

        normalized_vector = tuple(vector)
        by_index[index] = normalized_vector
        dimensions_seen.add(len(normalized_vector))

    if len(dimensions_seen) != 1:
        raise EmbeddingValidationError(
            "Embedding provider returned mixed vector dimensions.",
            error_code="embedding_response_mixed_dimensions",
        )
    actual_dimensions = next(iter(dimensions_seen))
    if actual_dimensions > MAX_EMBEDDING_DIMENSIONS:
        raise EmbeddingValidationError(
            "Embedding provider returned an oversized vector.",
            error_code="embedding_response_dimension_too_large",
            error_details={"maximum_dimensions": MAX_EMBEDDING_DIMENSIONS},
        )
    if expected_dimensions is not None and actual_dimensions != expected_dimensions:
        raise EmbeddingValidationError(
            "Embedding provider returned an unexpected vector dimension.",
            error_code="embedding_response_dimension_mismatch",
            error_details={
                "expected_dimensions": expected_dimensions,
                "actual_dimensions": actual_dimensions,
            },
        )

    return [by_index[index] for index in range(expected_count)]


def _profile_from_settings(settings: EmbeddingSettings) -> EmbeddingProfile:
    fingerprint_payload = {
        "schema": _PROFILE_SCHEMA,
        "adapter_version": EMBEDDING_ADAPTER_VERSION,
        "provider_key": unicodedata.normalize("NFKC", settings.provider_key).strip(),
        "dialect": settings.dialect.value,
        "base_url": _normalize_base_url(settings.base_url),
        "model": unicodedata.normalize("NFKC", settings.model).strip(),
        "dimensions": settings.dimensions,
        "encoding_format": _ENCODING_FORMAT,
        "text_preparation_version": TEXT_PREPARATION_VERSION,
    }
    encoded = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return EmbeddingProfile(
        provider_key=settings.provider_key,
        model=settings.model,
        dimensions=settings.dimensions,
        profile_fingerprint=sha256(encoded).hexdigest(),
    )


def embedding_profile_from_settings(settings: EmbeddingSettings) -> EmbeddingProfile:
    """Return the non-secret vector-space identity for validated settings."""

    validated = EmbeddingSettings.model_validate(settings)
    return _profile_from_settings(validated)


def _embeddings_endpoint(base_url: str) -> str:
    normalized = _normalize_base_url(base_url)
    if normalized.endswith("/v1"):
        return f"{normalized}/embeddings"
    return f"{normalized}/v1/embeddings"


def _normalize_base_url(base_url: str) -> str:
    normalized_input = unicodedata.normalize("NFKC", base_url).strip()
    if not normalized_input:
        raise ValueError("Embedding base URL cannot be empty.")

    try:
        parts = urllib.parse.urlsplit(normalized_input)
        port = parts.port
    except ValueError:
        raise ValueError("Embedding base URL is invalid.") from None
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or parts.hostname is None:
        raise ValueError("Embedding base URL must use HTTP or HTTPS.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("Embedding base URL cannot contain credentials.")
    if parts.query or parts.fragment:
        raise ValueError("Embedding base URL cannot contain a query or fragment.")

    try:
        hostname = parts.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("Embedding base URL host is invalid.") from None
    if ":" in hostname:
        hostname = f"[{hostname}]"
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"

    path = parts.path.rstrip("/")
    return urllib.parse.urlunsplit((scheme, hostname, path, "", ""))
