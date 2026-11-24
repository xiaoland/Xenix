from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Protocol, TypeVar

from ...exceptions import ValidationError
from ..knowledge_formats import KnowledgeFormatCapability
from ..paddle_ocr.contracts import MAX_PROTOCOL_MESSAGE_BYTES

MAX_OCR_RESULT_BYTES = MAX_PROTOCOL_MESSAGE_BYTES
MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_TEXT_LINE_CHARS = 1_000_000
MAX_IMAGE_PIXELS = 100_000_000
MAX_PACKAGE_ENTRIES = 20_000
MAX_PACKAGE_ENTRY_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_PACKAGE_COMPRESSION_RATIO = 200
MAX_PACKAGE_MEMBER_NAME_BYTES = 512
MAX_PACKAGE_MEMBER_DEPTH = 32
MAX_HASHABLE_IR_BYTES = 256 * 1024 * 1024
MAX_ANYDOC_MARKDOWN_BYTES = 64 * 1024 * 1024
MAX_ANYDOC_BLOCKS = 100_000

CFB_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
IO_CHUNK_BYTES = 1024 * 1024
PACKAGE_RATIO_CHECK_MIN_BYTES = 1024 * 1024
TEXT_ENCODING_ALLOWLIST = frozenset({"utf-8", "utf-16-le", "utf-16-be", "gb18030"})

_ProviderT = TypeVar("_ProviderT")


@dataclass(frozen=True)
class ZipPackageProfile:
    source_format: str
    display_name: str
    main_part: str


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
class OcrBatchResult:
    succeeded_pages: tuple[int, ...]
    unavailable_pages: tuple[int, ...]
    item_count: int
    payload_hashes: tuple[tuple[int, str], ...]


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


def provider_map(
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


def format_mismatch() -> ValidationError:
    return ValidationError(
        "The selected file signature does not match its extension.",
        error_code="knowledge_format_mismatch",
    )


def read_bytes(path: Path) -> bytes:
    blocks: list[bytes] = []
    with path.open("rb") as source:
        while True:
            block = source.read(IO_CHUNK_BYTES)
            if not block:
                break
            blocks.append(block)
    return b"".join(blocks)


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8")


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for start in range(0, len(text), IO_CHUNK_BYTES):
            target.write(text[start : start + IO_CHUNK_BYTES])


def read_prefix(path: Path, size: int) -> bytes:
    with path.open("rb") as stream:
        return stream.read(size)


def sha256_file_bounded(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    if size < 0 or size > max_bytes:
        raise ValidationError("Knowledge pipeline hash input exceeds the supported limit.")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as source:
        while True:
            block = source.read(IO_CHUNK_BYTES)
            if not block:
                break
            consumed += len(block)
            if consumed > max_bytes:
                raise ValidationError(
                    "Knowledge pipeline hash input exceeds the supported limit."
                )
            digest.update(block)
    return digest.hexdigest()


def bounded_json_sha256(
    value: Any,
    *,
    label: str,
    max_bytes: int = MAX_HASHABLE_IR_BYTES,
) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError(f"{label} cannot be hashed safely.") from exc
    if len(payload) > max_bytes:
        raise ValidationError(f"{label} exceeds the supported hash limit.")
    return hashlib.sha256(payload).hexdigest()


def runtime_package(name: str, version: str) -> dict[str, str]:
    return {"name": name, "version": version}


def installed_package(distribution: str) -> dict[str, str]:
    try:
        installed_version = package_version(distribution)
    except PackageNotFoundError:
        installed_version = "unknown"
    return runtime_package(distribution, installed_version)
