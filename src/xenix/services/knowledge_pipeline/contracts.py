"""Shared contracts and provider validation for the import stages."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from ...exceptions import ValidationError
from ..knowledge_formats import KnowledgeFormatCapability


MAX_SOURCE_BYTES = 512 * 1024 * 1024
_ProviderT = TypeVar("_ProviderT")
_ANYDOC_PROVIDER_ID = "anydoc"


@dataclass(frozen=True)
class FileProbeResult:
    source_path: Path
    source_format: str
    media_type: str | None
    size: int
    encrypted: bool
    facts: dict[str, Any]


@dataclass(frozen=True)
class NormalizedSource:
    path: Path
    source_format: str
    parser_format: str
    descriptor: dict[str, Any]


@dataclass(frozen=True)
class ParsePlanUnit:
    scope: str
    route_id: str
    reason: str
    page: int | None = None
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsePlan:
    source_format: str
    parser_format: str
    units: tuple[ParsePlanUnit, ...]
    merge_strategy: str
    policy_version: int = 1
    ocr_ready: bool = False


@dataclass(frozen=True)
class ParseResult:
    document: Any
    pipeline: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    projections: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class FormatProbeFacts:
    detected_format: str
    encrypted: bool = False
    facts: dict[str, Any] = field(default_factory=dict)


class FormatProbeProvider(Protocol):
    provider_id: str

    def probe(
        self,
        source: Path,
        *,
        header: bytes,
        size: int,
        capability: KnowledgeFormatCapability,
    ) -> FormatProbeFacts: ...


@dataclass(frozen=True)
class NormalizationRequest:
    probe: FileProbeResult
    capability: KnowledgeFormatCapability
    work_dir: Path
    password: str | None
    input_sha256: str


class FormatNormalizerProvider(Protocol):
    provider_id: str

    def normalize(self, request: NormalizationRequest) -> NormalizedSource: ...


class ParserRouteProvider(Protocol):
    provider_id: str

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan: ...


@dataclass(frozen=True)
class ParserExecutionContext:
    normalized: NormalizedSource
    plan: ParsePlan
    work_dir: Path
    ocr_executor: Any


@dataclass(frozen=True)
class ParsedContent:
    document: Any
    warnings: tuple[str, ...] = ()
    projections: tuple[dict[str, Any], ...] = ()
    ocr_projection_count: int = 0
    ocr_attempted_count: int = 0
    ocr_succeeded_count: int = 0
    ocr_unavailable_count: int = 0
    ocr_payload_hashes: tuple[tuple[int, str], ...] = ()


class DocumentParserProvider(Protocol):
    provider_id: str
    backend: str
    package_distribution: str

    def parse(self, context: ParserExecutionContext) -> ParsedContent: ...


def _provider_map(
    providers: Iterable[_ProviderT],
    *,
    required_ids: tuple[str, ...],
    kind: str,
) -> dict[str, _ProviderT]:
    by_id: dict[str, _ProviderT] = {}
    for provider in providers:
        provider_id = getattr(provider, "provider_id", None)
        if (
            not isinstance(provider_id, str)
            or not provider_id
            or provider_id != provider_id.strip().casefold()
        ):
            raise ValueError(
                f"Knowledge {kind} provider IDs must be normalized strings."
            )
        if provider_id in by_id:
            raise ValueError(f"Knowledge {kind} provider IDs must be unique.")
        by_id[provider_id] = provider
    missing = [provider_id for provider_id in required_ids if provider_id not in by_id]
    if missing:
        raise ValueError(
            f"Knowledge {kind} providers are missing: {', '.join(missing)}"
        )
    unused = sorted(set(by_id) - set(required_ids))
    if unused:
        raise ValueError(
            f"Knowledge {kind} providers have no format capability: "
            + ", ".join(unused)
        )
    return by_id


def _format_mismatch() -> ValidationError:
    return ValidationError(
        "The selected file signature does not match its extension.",
        error_code="knowledge_format_mismatch",
    )
