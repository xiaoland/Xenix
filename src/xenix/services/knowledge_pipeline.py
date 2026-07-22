from __future__ import annotations

import codecs
import hashlib
import io
import inspect
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Callable, Iterable, Protocol
from zipfile import BadZipFile, ZipFile

import msoffcrypto
import pikepdf
from charset_normalizer import from_bytes
from PIL import Image, ImageOps, UnidentifiedImageError, __version__ as pillow_version

from ..exceptions import ValidationError
from .paddle_ocr_service import (
    MAX_OCR_RESULT_BYTES,
    PADDLE_OCR_VERSION,
    SIDECAR_PROTOCOL_VERSION,
    PaddleOcrService,
)

MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_TEXT_LINE_CHARS = 1_000_000
MAX_IMAGE_PIXELS = 100_000_000
MAX_DOCX_PACKAGE_ENTRIES = 20_000
MAX_DOCX_ENTRY_BYTES = 128 * 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 200
MAX_DOCX_MEMBER_NAME_BYTES = 512
MAX_DOCX_MEMBER_DEPTH = 32
MAX_HASHABLE_IR_BYTES = 256 * 1024 * 1024
_CFB_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_IO_CHUNK_BYTES = 1024 * 1024
_PROCESS_POLL_INTERVAL_SECONDS = 0.05
_PROCESS_TERMINATE_GRACE_SECONDS = 2.0
_DOCLING_TIMEOUT_SECONDS = 15 * 60
_LIBREOFFICE_TIMEOUT_SECONDS = 120
_DOCX_RATIO_CHECK_MIN_BYTES = 1024 * 1024
_TEXT_ENCODING_ALLOWLIST = frozenset(
    {"utf-8", "utf-16-le", "utf-16-be", "gb18030"}
)
_TEXT_FALLBACK_ENCODINGS = _TEXT_ENCODING_ALLOWLIST - {
    "utf-8",
    "utf-16-le",
    "utf-16-be",
}
_TEXT_MAX_CANDIDATE_CHAOS = 0.1
_TEXT_MIN_CANDIDATE_SEPARATION = 0.05
_OCR_PROJECTION_FAILURES = (
    ValidationError,
    OSError,
    TimeoutError,
    subprocess.SubprocessError,
)

CancellationCheck = Callable[[], object]


@dataclass(frozen=True)
class KnowledgeFormatCapability:
    """One source-format registration shared by admission, normalization, and routing."""

    source_format: str
    display_name: str
    suffixes: tuple[str, ...]
    media_type: str
    normalizer_backend: str
    parser_format: str
    parser_route_id: str


class KnowledgeFormatRegistry:
    """Validated immutable product-format registry with derived UI/admission views."""

    def __init__(self, capabilities: Iterable[KnowledgeFormatCapability]) -> None:
        ordered = tuple(capabilities)
        if not ordered:
            raise ValueError("Knowledge format registry cannot be empty.")
        by_format: dict[str, KnowledgeFormatCapability] = {}
        by_suffix: dict[str, KnowledgeFormatCapability] = {}
        for capability in ordered:
            source_format = capability.source_format.strip().casefold()
            if not source_format or source_format in by_format:
                raise ValueError("Knowledge source formats must be unique and non-empty.")
            if capability.source_format != source_format:
                raise ValueError("Knowledge source formats must be normalized.")
            if not capability.suffixes:
                raise ValueError("Knowledge format capabilities require suffixes.")
            for suffix in capability.suffixes:
                normalized_suffix = suffix.casefold()
                if suffix != normalized_suffix or not suffix.startswith("."):
                    raise ValueError("Knowledge format suffixes must be normalized extensions.")
                if normalized_suffix in by_suffix:
                    raise ValueError("Knowledge format suffixes must be unique.")
                by_suffix[normalized_suffix] = capability
            by_format[source_format] = capability
        self._capabilities = ordered
        self._by_format = by_format
        self._by_suffix = by_suffix

    @property
    def capabilities(self) -> tuple[KnowledgeFormatCapability, ...]:
        return self._capabilities

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset(self._by_suffix)

    @property
    def parser_route_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.parser_route_id for item in self._capabilities))

    @property
    def display_names(self) -> tuple[str, ...]:
        return tuple(item.display_name for item in self._capabilities)

    def capability_for_suffix(self, suffix: str) -> KnowledgeFormatCapability | None:
        return self._by_suffix.get(suffix.casefold())

    def capability_for_format(self, source_format: str) -> KnowledgeFormatCapability | None:
        return self._by_format.get(source_format.casefold())

    def file_dialog_filter(self, label: str = "Knowledge documents") -> str:
        patterns = " ".join(
            f"*{suffix}"
            for capability in self._capabilities
            for suffix in capability.suffixes
        )
        display_label = label.strip() or "Knowledge documents"
        return f"{display_label} ({patterns})"

    def supported_formats_message(self) -> str:
        names = self.display_names
        joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])}, and {names[-1]}"
        return f"Supported Knowledge formats are {joined}."


KNOWLEDGE_FORMAT_REGISTRY = KnowledgeFormatRegistry(
    (
        KnowledgeFormatCapability(
            "txt",
            "TXT",
            (".txt",),
            "text/plain",
            "python-codecs",
            "txt",
            "xenix-text",
        ),
        KnowledgeFormatCapability(
            "doc",
            "DOC",
            (".doc",),
            "application/msword",
            "libreoffice-doc-to-docx",
            "docx",
            "docling-docx",
        ),
        KnowledgeFormatCapability(
            "docx",
            "DOCX",
            (".docx",),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "ooxml-identity",
            "docx",
            "docling-docx",
        ),
        KnowledgeFormatCapability(
            "pdf",
            "PDF",
            (".pdf",),
            "application/pdf",
            "pdf-identity",
            "pdf",
            "docling-pdf-native",
        ),
        KnowledgeFormatCapability(
            "jpeg",
            "JPEG",
            (".jpg", ".jpeg"),
            "image/jpeg",
            "pillow-image",
            "image",
            "docling-image-shell",
        ),
        KnowledgeFormatCapability(
            "png",
            "PNG",
            (".png",),
            "image/png",
            "pillow-image",
            "image",
            "docling-image-shell",
        ),
    )
)
SUPPORTED_KNOWLEDGE_SUFFIXES = KNOWLEDGE_FORMAT_REGISTRY.supported_suffixes


def knowledge_file_dialog_filter(label: str = "Knowledge documents") -> str:
    """Return the product file-dialog filter derived from the format authority."""

    return KNOWLEDGE_FORMAT_REGISTRY.file_dialog_filter(label)


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
class _OcrBatchResult:
    succeeded_pages: tuple[int, ...]
    unavailable_pages: tuple[int, ...]
    item_count: int
    payload_hashes: tuple[tuple[int, str], ...]


class FileProbe:
    """Return authoritative byte/container facts without mutating the source."""

    def __init__(
        self,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
    ) -> None:
        self._registry = registry

    def probe(self, path: Path) -> FileProbeResult:
        source = path.expanduser().resolve()
        if not source.is_file():
            raise ValidationError("Knowledge source must be an existing local file.")
        size = source.stat().st_size
        if size <= 0 or size > MAX_SOURCE_BYTES:
            raise ValidationError("Knowledge source size is outside the supported range.")
        suffix = source.suffix.casefold()
        capability = self._registry.capability_for_suffix(suffix)
        if capability is None:
            raise ValidationError(
                self._registry.supported_formats_message(),
                error_code="knowledge_format_unsupported",
            )
        header = _read_prefix(source, 64 * 1024)
        detected = _detected_format(header, expected_format=capability.source_format)
        if detected != capability.source_format:
            raise ValidationError(
                "The selected file signature does not match its extension.",
                error_code="knowledge_format_mismatch",
            )

        facts: dict[str, Any] = {
            "signature": detected,
            "byte_size": size,
            "format_registry_version": 1,
        }
        encrypted = False
        if detected == "txt":
            _probe_text(header, facts, sample_is_complete=size <= len(header))
        elif detected == "docx":
            if header.startswith(_CFB_SIGNATURE):
                encrypted = _office_is_encrypted(source)
                if not encrypted:
                    raise ValidationError(
                        "The selected DOCX container is invalid.",
                        error_code="knowledge_docx_package_invalid",
                    )
                facts["container"] = "cfb-encrypted-ooxml"
            else:
                facts.update(_verify_docx(source))
                facts["container"] = "ooxml"
        elif detected == "doc":
            encrypted = _office_is_encrypted(source)
            facts["container"] = "cfb"
            facts["normalization_candidate"] = "docx"
        elif detected == "pdf":
            encrypted, pdf_facts = _probe_pdf(source)
            facts.update(pdf_facts)
        elif detected in {"jpeg", "png"}:
            facts.update(_probe_image(source, expected_format=detected))
        facts["encrypted"] = encrypted
        return FileProbeResult(
            source_path=source,
            source_format=detected,
            media_type=capability.media_type,
            size=size,
            encrypted=encrypted,
            facts=facts,
        )


class FormatNormalizer:
    """Materialize attempt-local parser inputs and a bounded lineage descriptor."""

    def __init__(
        self,
        executable: Path | None = None,
        *,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
    ) -> None:
        self._executable = executable
        self._registry = registry

    def normalize(
        self,
        probe: FileProbeResult,
        *,
        work_dir: Path,
        password: str | None = None,
        check_cancelled: CancellationCheck | None = None,
    ) -> NormalizedSource:
        _check_cancelled(check_cancelled)
        capability = self._registry.capability_for_format(probe.source_format)
        if capability is None:
            raise ValidationError("No Knowledge normalizer is registered for this format.")
        if probe.encrypted and not password:
            raise ValidationError(
                "A password is required to import this encrypted document.",
                error_code="knowledge_password_required",
                retryable=True,
            )
        input_sha256 = _sha256_file_bounded(
            probe.source_path,
            max_bytes=MAX_SOURCE_BYTES,
            check_cancelled=check_cancelled,
        )
        source = probe.source_path
        if probe.encrypted:
            assert password is not None
            source = self._decrypt(
                probe,
                work_dir=work_dir,
                password=password,
                check_cancelled=check_cancelled,
            )
        _check_cancelled(check_cancelled)

        if capability.normalizer_backend == "python-codecs":
            payload = _read_bytes_cooperatively(source, check_cancelled=check_cancelled)
            decoded = _decode_text_payload(payload)
            _check_cancelled(check_cancelled)
            text = _normalize_text(decoded.text, check_cancelled=check_cancelled)
            target = work_dir / "normalized.txt"
            _write_text_cooperatively(target, text, check_cancelled=check_cancelled)
            return NormalizedSource(
                path=target,
                source_format=capability.source_format,
                parser_format=capability.parser_format,
                descriptor=_normalization_descriptor(
                    operation="decode_text",
                    backend=capability.normalizer_backend,
                    package=_runtime_package("python", sys.version.split()[0]),
                    options={
                        "decode_errors": "strict",
                        "allowed_encodings": sorted(_TEXT_ENCODING_ALLOWLIST),
                        "control_policy": "reject",
                    },
                    input_sha256=input_sha256,
                    output_path=target,
                    check_cancelled=check_cancelled,
                    details={
                        "encoding": decoded.encoding,
                        "bom": decoded.bom,
                        "newline": {
                            "input": decoded.newline,
                            "output": "lf",
                        },
                        "normalization": {
                            "bom_removed": decoded.bom != "none",
                            "newlines_normalized": decoded.newline not in {"lf", "none"},
                            "unicode_normalization": "preserved",
                        },
                    },
                ),
            )

        if capability.normalizer_backend == "libreoffice-doc-to-docx":
            normalized = self._convert_doc(
                source,
                work_dir=work_dir,
                check_cancelled=check_cancelled,
            )
            return NormalizedSource(
                path=normalized,
                source_format=capability.source_format,
                parser_format=capability.parser_format,
                descriptor=_normalization_descriptor(
                    operation="decrypt_and_convert" if probe.encrypted else "convert",
                    backend=capability.normalizer_backend,
                    package=_runtime_package("libreoffice", "runtime-resolved"),
                    options={
                        "encrypted_input": probe.encrypted,
                        "headless": True,
                        "isolated_profile": True,
                        "target_format": "docx",
                    },
                    input_sha256=input_sha256,
                    output_path=normalized,
                    check_cancelled=check_cancelled,
                ),
            )
        if capability.normalizer_backend == "ooxml-identity":
            package_facts = _verify_docx(source, check_cancelled=check_cancelled)
            return NormalizedSource(
                source,
                capability.source_format,
                capability.parser_format,
                _normalization_descriptor(
                    operation="decrypt" if probe.encrypted else "identity",
                    backend="msoffcrypto" if probe.encrypted else capability.normalizer_backend,
                    package=(
                        _installed_package("msoffcrypto-tool")
                        if probe.encrypted
                        else _runtime_package("python-zipfile", sys.version.split()[0])
                    ),
                    options={
                        "encrypted_input": probe.encrypted,
                        "package_safety_verified": True,
                        "entry_count": package_facts["container_entry_count"],
                    },
                    input_sha256=input_sha256,
                    output_path=source,
                    check_cancelled=check_cancelled,
                ),
            )
        if capability.normalizer_backend == "pdf-identity":
            _check_cancelled(check_cancelled)
            return NormalizedSource(
                source,
                capability.source_format,
                capability.parser_format,
                _normalization_descriptor(
                    operation="decrypt" if probe.encrypted else "identity",
                    backend="pikepdf" if probe.encrypted else capability.normalizer_backend,
                    package=_installed_package("pikepdf"),
                    options={"encrypted_input": probe.encrypted, "repair": False},
                    input_sha256=input_sha256,
                    output_path=source,
                    check_cancelled=check_cancelled,
                ),
            )
        if capability.normalizer_backend == "pillow-image":
            target = work_dir / "normalized-image.png"
            _check_cancelled(check_cancelled)
            try:
                with Image.open(source) as image:
                    normalized = ImageOps.exif_transpose(image)
                    if normalized.mode not in {"RGB", "RGBA", "L"}:
                        normalized = normalized.convert("RGB")
                    normalized.save(target, format="PNG")
            except (OSError, UnidentifiedImageError) as exc:
                raise ValidationError("The image could not be normalized.") from exc
            _check_cancelled(check_cancelled)
            return NormalizedSource(
                target,
                capability.source_format,
                capability.parser_format,
                _normalization_descriptor(
                    operation="normalize_image",
                    backend=capability.normalizer_backend,
                    package=_runtime_package("Pillow", pillow_version),
                    options={
                        "orientation": "exif_transposed",
                        "pixel_encoding": "png",
                        "source_format": capability.source_format,
                    },
                    input_sha256=input_sha256,
                    output_path=target,
                    check_cancelled=check_cancelled,
                ),
            )
        raise ValidationError("No Knowledge normalizer is registered for this format.")

    def _decrypt(
        self,
        probe: FileProbeResult,
        *,
        work_dir: Path,
        password: str,
        check_cancelled: CancellationCheck | None,
    ) -> Path:
        _check_cancelled(check_cancelled)
        if probe.source_format == "pdf":
            target = work_dir / "decrypted.pdf"
            try:
                with pikepdf.Pdf.open(probe.source_path, password=password) as document:
                    document.save(target)
            except (pikepdf.PasswordError, pikepdf.PdfError) as exc:
                raise ValidationError(
                    "The document password was not accepted.",
                    error_code="knowledge_password_invalid",
                    retryable=True,
                ) from exc
            _check_cancelled(check_cancelled)
            return target
        if probe.source_format not in {"doc", "docx"}:
            raise ValidationError("Encrypted input is not supported for this format.")
        target = work_dir / f"decrypted.{probe.source_format}"
        try:
            with probe.source_path.open("rb") as stream:
                office = msoffcrypto.OfficeFile(stream)
                office.load_key(password=password)
                with target.open("wb") as output:
                    office.decrypt(output)
        except Exception as exc:
            raise ValidationError(
                "The document password was not accepted.",
                error_code="knowledge_password_invalid",
                retryable=True,
            ) from exc
        _check_cancelled(check_cancelled)
        return target

    def _convert_doc(
        self,
        source: Path,
        *,
        work_dir: Path,
        check_cancelled: CancellationCheck | None,
    ) -> Path:
        _check_cancelled(check_cancelled)
        executable = self._executable or _find_libreoffice()
        if executable is None:
            raise ValidationError(
                "Importing legacy DOC requires LibreOffice.",
                error_code="knowledge_office_converter_unavailable",
                retryable=True,
            )
        profile = work_dir / "libreoffice-profile"
        local_source = work_dir / "source.doc"
        if source.resolve() != local_source.resolve():
            _copy_file_cooperatively(
                source,
                local_source,
                check_cancelled=check_cancelled,
            )
        command = [
            str(executable),
            "--headless",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to",
            "docx:Office Open XML Text",
            "--outdir",
            str(work_dir),
            str(local_source),
        ]
        _check_cancelled(check_cancelled)
        try:
            process = subprocess.Popen(
                command,
                cwd=str(work_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_no_console_process_kwargs(),
            )
        except OSError:
            raise ValidationError(
                "LibreOffice could not normalize the legacy DOC document.",
                error_code="knowledge_office_conversion_failed",
                retryable=True,
            ) from None
        returncode = _wait_for_process(
            process,
            timeout_seconds=_LIBREOFFICE_TIMEOUT_SECONDS,
            check_cancelled=check_cancelled,
            timeout_error=ValidationError(
                "LibreOffice could not normalize the legacy DOC document.",
                error_code="knowledge_office_conversion_failed",
                retryable=True,
            ),
        )
        output = work_dir / "source.docx"
        if returncode != 0 or not output.is_file():
            raise ValidationError(
                "LibreOffice could not normalize the legacy DOC document.",
                error_code="knowledge_office_conversion_failed",
                retryable=True,
            )
        _verify_docx(output, check_cancelled=check_cancelled)
        return output


class ParserRouteProvider(Protocol):
    route_id: str

    def supports(self, parser_format: str) -> bool: ...

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan: ...


class ParserRouter:
    """Select explainable parse routes through an extensible provider registry."""

    def __init__(
        self,
        providers: tuple[ParserRouteProvider, ...] | None = None,
        *,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
    ) -> None:
        self._registry = registry
        if providers is None:
            builtins: dict[str, ParserRouteProvider] = {
                "xenix-text": _TextRouteProvider(),
                "docling-docx": _DocxRouteProvider(),
                "docling-pdf-native": _PdfRouteProvider(),
                "docling-image-shell": _ImageRouteProvider(),
            }
            try:
                providers = tuple(
                    builtins[route_id] for route_id in registry.parser_route_ids
                )
            except KeyError as exc:
                raise ValueError(
                    f"Knowledge parser route provider is missing: {exc.args[0]}"
                ) from None
        route_ids = [provider.route_id for provider in providers]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("Knowledge parser route provider IDs must be unique.")
        self._providers = {provider.route_id: provider for provider in providers}

    @property
    def registered_route_ids(self) -> frozenset[str]:
        return frozenset(self._providers)

    def route(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        capability = self._registry.capability_for_format(normalized.source_format)
        if capability is None or capability.parser_format != normalized.parser_format:
            raise ValidationError("No Knowledge parser route is registered for this format.")
        provider = self._providers.get(capability.parser_route_id)
        if provider is None or not provider.supports(normalized.parser_format):
            raise ValidationError("No Knowledge parser route is registered for this format.")
        return provider.plan(normalized, ocr_ready=ocr_ready)


class ParseExecutor:
    def __init__(self, ocr_service: PaddleOcrService | None = None) -> None:
        self._ocr = ocr_service

    @property
    def ocr_ready(self) -> bool:
        if self._ocr is None:
            return False
        readiness = getattr(self._ocr, "is_ready", None)
        return bool(readiness()) if callable(readiness) else True

    def parse(
        self,
        normalized: NormalizedSource,
        plan: ParsePlan,
        *,
        probe: FileProbeResult,
        work_dir: Path,
        check_cancelled: CancellationCheck | None = None,
    ) -> ParseResult:
        _check_cancelled(check_cancelled)
        warnings: list[str] = []
        projections: list[dict[str, Any]] = []
        ocr_ready = plan.ocr_ready
        parser_input_sha256 = _sha256_file_bounded(
            normalized.path,
            max_bytes=MAX_SOURCE_BYTES,
            check_cancelled=check_cancelled,
        )
        ocr_projection_count = 0
        ocr_attempted_count = 0
        ocr_succeeded_count = 0
        ocr_unavailable_count = 0
        ocr_payload_hashes: list[tuple[int, str]] = []
        _check_cancelled(check_cancelled)
        if normalized.parser_format == "txt":
            document = _plain_text_docling_document(
                normalized.path,
                check_cancelled=check_cancelled,
            )
        elif normalized.parser_format == "docx":
            document = _docling_convert(
                normalized.path,
                source_format="docx",
                work_dir=work_dir,
                check_cancelled=check_cancelled,
            )
        elif normalized.parser_format == "pdf":
            document = _docling_convert(
                normalized.path,
                source_format="pdf",
                work_dir=work_dir,
                check_cancelled=check_cancelled,
            )
            missing_pages = [
                unit.page - 1
                for unit in plan.units
                if unit.route_id == "paddleocr-page" and unit.page
            ]
            unavailable_pages = [
                unit.page
                for unit in plan.units
                if unit.route_id == "text-projection-unavailable" and unit.page
            ]
            ocr_projection_count = len(missing_pages) + len(unavailable_pages)
            if missing_pages:
                assert self._ocr is not None
                page_result = _append_paddle_ocr_pages(
                    document,
                    pdf_path=normalized.path,
                    page_indexes=missing_pages,
                    work_dir=work_dir,
                    ocr_service=self._ocr,
                    check_cancelled=check_cancelled,
                )
                ocr_attempted_count += len(missing_pages)
                ocr_succeeded_count += len(page_result.succeeded_pages)
                unavailable_pages.extend(page_result.unavailable_pages)
                ocr_payload_hashes.extend(page_result.payload_hashes)
                if page_result.succeeded_pages:
                    projections.append(
                        {
                            "kind": "ocr_text",
                            "status": "ready",
                            "pages": list(page_result.succeeded_pages),
                            "items": page_result.item_count,
                        }
                    )
            unavailable_pages = sorted(set(unavailable_pages))
            ocr_unavailable_count = len(unavailable_pages)
            if unavailable_pages:
                warnings.append("ocr_projection_unavailable")
                projections.append(
                    {
                        "kind": "ocr_text",
                        "status": "unavailable",
                        "pages": unavailable_pages,
                    }
                )
        elif normalized.parser_format == "image":
            document = _image_docling_document(
                normalized.path,
                check_cancelled=check_cancelled,
            )
            ocr_projection_count = 1
            if ocr_ready:
                assert self._ocr is not None
                output_path = work_dir / "image-ocr.json"
                ocr_attempted_count = 1
                payload = _recognize_projection(
                    self._ocr,
                    normalized.path,
                    output_path=output_path,
                    check_cancelled=check_cancelled,
                )
                if payload is None:
                    ocr_unavailable_count = 1
                    warnings.append("ocr_projection_unavailable")
                    projections.append({"kind": "ocr_text", "status": "unavailable"})
                else:
                    count = _append_ocr_text(document, payload, page_no=1)
                    ocr_succeeded_count = 1
                    ocr_payload_hashes.append(
                        (
                            1,
                            _bounded_json_sha256(
                                payload,
                                label="OCR result",
                                max_bytes=MAX_OCR_RESULT_BYTES,
                            ),
                        )
                    )
                    projections.append(
                        {"kind": "ocr_text", "status": "ready", "items": count}
                    )
            else:
                ocr_unavailable_count = 1
                warnings.append("ocr_projection_unavailable")
                projections.append({"kind": "ocr_text", "status": "unavailable"})
        else:  # pragma: no cover - router and executor evolve together
            raise ValidationError("The selected Knowledge parse plan is invalid.")
        _check_cancelled(check_cancelled)
        parser_output_sha256 = _docling_document_sha256(document)
        ocr_status = _ocr_status(
            projection_count=ocr_projection_count,
            succeeded_count=ocr_succeeded_count,
            unavailable_count=ocr_unavailable_count,
        )
        parser_uses_docling = normalized.parser_format in {"docx", "pdf"}
        return ParseResult(
            document=document,
            pipeline={
                "probe": dict(probe.facts),
                "normalizer": dict(normalized.descriptor),
                "router": {
                    "policy_version": plan.policy_version,
                    "merge_strategy": plan.merge_strategy,
                    "units": [
                        {
                            "scope": unit.scope,
                            "route_id": unit.route_id,
                            "reason": unit.reason,
                            **({"page": unit.page} if unit.page is not None else {}),
                        }
                        for unit in plan.units
                    ],
                },
                "parser": {
                    "content_ir": "DoclingDocument",
                    "version": 2,
                    "package": _installed_package(
                        "docling" if parser_uses_docling else "docling-core"
                    ),
                    "backend": (
                        "docling-worker"
                        if parser_uses_docling
                        else f"xenix-{normalized.parser_format}-adapter"
                    ),
                    "options": {
                        "merge_strategy": plan.merge_strategy,
                        "parser_format": normalized.parser_format,
                    },
                    "status": "succeeded",
                    "input_sha256": parser_input_sha256,
                    "output_sha256": parser_output_sha256,
                },
                "ocr": {
                    "service": "paddleocr",
                    "package": _runtime_package("paddleocr", PADDLE_OCR_VERSION),
                    "backend": "local-sidecar",
                    "options": {
                        "page_scoped": normalized.parser_format == "pdf",
                        "projection": "text",
                        "protocol": SIDECAR_PROTOCOL_VERSION,
                    },
                    "status": ocr_status,
                    "ready": ocr_ready,
                    "input_sha256": parser_input_sha256,
                    "output_sha256": _combined_projection_sha256(ocr_payload_hashes),
                    "projection_count": ocr_projection_count,
                    "attempted_count": ocr_attempted_count,
                    "succeeded_count": ocr_succeeded_count,
                    "unavailable_count": ocr_unavailable_count,
                },
            },
            warnings=warnings,
            projections=projections,
        )


class _TextRouteProvider:
    route_id = "xenix-text"

    def supports(self, parser_format: str) -> bool:
        return parser_format == "txt"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        return ParsePlan(
            "txt",
            "txt",
            (ParsePlanUnit("document", self.route_id, "decoded_text"),),
            "document",
            ocr_ready=ocr_ready,
        )


class _DocxRouteProvider:
    route_id = "docling-docx"

    def supports(self, parser_format: str) -> bool:
        return parser_format == "docx"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        return ParsePlan(
            normalized.source_format,
            "docx",
            (ParsePlanUnit("document", self.route_id, "validated_ooxml"),),
            "document",
            ocr_ready=ocr_ready,
        )


class _PdfRouteProvider:
    route_id = "docling-pdf-native"

    def supports(self, parser_format: str) -> bool:
        return parser_format == "pdf"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        page_routes = _pdf_page_routes(normalized.path)
        units: list[ParsePlanUnit] = []
        for page, native_text in page_routes:
            if native_text:
                units.append(ParsePlanUnit("page", self.route_id, "native_text_sufficient", page))
            elif ocr_ready:
                units.append(ParsePlanUnit("page", "paddleocr-page", "native_text_insufficient", page))
            else:
                units.append(ParsePlanUnit("page", "text-projection-unavailable", "ocr_unavailable", page))
        return ParsePlan(
            "pdf",
            "pdf",
            tuple(units),
            "docling-document-plus-page-projections",
            ocr_ready=ocr_ready,
        )


class _ImageRouteProvider:
    route_id = "docling-image-shell"

    def supports(self, parser_format: str) -> bool:
        return parser_format == "image"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        units = [ParsePlanUnit("image", self.route_id, "image_content_ir")]
        units.append(
            ParsePlanUnit(
                "image",
                "paddleocr-image" if ocr_ready else "text-projection-unavailable",
                "ocr_ready" if ocr_ready else "ocr_unavailable",
            )
        )
        return ParsePlan(
            normalized.source_format,
            "image",
            tuple(units),
            "image-with-optional-text-projection",
            ocr_ready=ocr_ready,
        )


def _check_cancelled(check_cancelled: CancellationCheck | None) -> None:
    if check_cancelled is not None:
        check_cancelled()


def _wait_for_process(
    process: Any,
    *,
    timeout_seconds: float,
    check_cancelled: CancellationCheck | None,
    timeout_error: Exception,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            _check_cancelled(check_cancelled)
            returncode = process.poll()
            if returncode is not None:
                return int(returncode)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise timeout_error
            time.sleep(min(_PROCESS_POLL_INTERVAL_SECONDS, remaining))
    except BaseException:
        _terminate_process(process)
        raise


def _terminate_process(process: Any) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=_PROCESS_TERMINATE_GRACE_SECONDS)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=_PROCESS_TERMINATE_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _no_console_process_kwargs() -> dict[str, int]:
    if sys.platform != "win32":
        return {}
    return {"creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0))}


def _docling_worker_command(
    source_path: Path,
    *,
    source_format: str,
    output_path: Path,
) -> tuple[list[str], dict[str, str]]:
    environment = dict(os.environ)
    if getattr(sys, "frozen", False):
        command = [
            sys.executable,
            "--knowledge-docling-worker",
            source_format,
            str(source_path),
            str(output_path),
        ]
    else:
        source_root = str(Path(__file__).resolve().parents[2])
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            source_root
            if not existing_pythonpath
            else os.pathsep.join([source_root, existing_pythonpath])
        )
        command = [
            sys.executable,
            "-m",
            "xenix.services.knowledge_docling_worker",
            source_format,
            str(source_path),
            str(output_path),
        ]
    return command, environment


def _read_bytes_cooperatively(
    path: Path,
    *,
    check_cancelled: CancellationCheck | None,
) -> bytes:
    blocks: list[bytes] = []
    with path.open("rb") as source:
        while True:
            _check_cancelled(check_cancelled)
            block = source.read(_IO_CHUNK_BYTES)
            if not block:
                break
            blocks.append(block)
    _check_cancelled(check_cancelled)
    return b"".join(blocks)


def _read_text_cooperatively(
    path: Path,
    *,
    check_cancelled: CancellationCheck | None,
) -> str:
    return _read_bytes_cooperatively(
        path,
        check_cancelled=check_cancelled,
    ).decode("utf-8")


def _write_text_cooperatively(
    path: Path,
    text: str,
    *,
    check_cancelled: CancellationCheck | None,
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for start in range(0, len(text), _IO_CHUNK_BYTES):
            _check_cancelled(check_cancelled)
            target.write(text[start : start + _IO_CHUNK_BYTES])
    _check_cancelled(check_cancelled)


def _copy_file_cooperatively(
    source_path: Path,
    target_path: Path,
    *,
    check_cancelled: CancellationCheck | None,
) -> None:
    with source_path.open("rb") as source, target_path.open("wb") as target:
        while True:
            _check_cancelled(check_cancelled)
            block = source.read(_IO_CHUNK_BYTES)
            if not block:
                break
            target.write(block)
    _check_cancelled(check_cancelled)


def _sha256_file_bounded(
    path: Path,
    *,
    max_bytes: int,
    check_cancelled: CancellationCheck | None,
) -> str:
    size = path.stat().st_size
    if size < 0 or size > max_bytes:
        raise ValidationError("Knowledge pipeline hash input exceeds the supported limit.")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as source:
        while True:
            _check_cancelled(check_cancelled)
            block = source.read(_IO_CHUNK_BYTES)
            if not block:
                break
            consumed += len(block)
            if consumed > max_bytes:
                raise ValidationError(
                    "Knowledge pipeline hash input exceeds the supported limit."
                )
            digest.update(block)
    _check_cancelled(check_cancelled)
    return digest.hexdigest()


def _normalization_descriptor(
    *,
    operation: str,
    backend: str,
    package: dict[str, str],
    options: dict[str, Any],
    input_sha256: str,
    output_path: Path,
    check_cancelled: CancellationCheck | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_sha256 = _sha256_file_bounded(
        output_path,
        max_bytes=MAX_SOURCE_BYTES,
        check_cancelled=check_cancelled,
    )
    return {
        "operation": operation,
        "version": 2,
        "package": package,
        "backend": backend,
        "options": dict(options),
        "status": "succeeded",
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        **dict(details or {}),
    }


def _runtime_package(name: str, version: str) -> dict[str, str]:
    return {"name": name, "version": version}


def _installed_package(distribution: str) -> dict[str, str]:
    try:
        installed_version = package_version(distribution)
    except PackageNotFoundError:
        installed_version = "unknown"
    return _runtime_package(distribution, installed_version)


def _bounded_json_sha256(
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


def _docling_document_sha256(document: Any) -> str:
    try:
        exported = document.export_to_dict()
    except Exception as exc:
        raise ValidationError("Docling content cannot be hashed safely.") from exc
    return _bounded_json_sha256(
        _redact_path_values_for_hash(exported),
        label="Docling content",
    )


def _redact_path_values_for_hash(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(item_key): _redact_path_values_for_hash(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_path_values_for_hash(item, key=key) for item in value]
    if isinstance(value, str) and key in {"path", "uri"}:
        candidate = Path(value)
        if candidate.is_absolute() or "://" in value or value.startswith(("~", "\\\\")):
            return "<redacted-path>"
    return value


def _combined_projection_sha256(payload_hashes: Iterable[tuple[int, str]]) -> str | None:
    ordered = [
        {"ordinal": ordinal, "sha256": payload_sha256}
        for ordinal, payload_sha256 in payload_hashes
    ]
    if not ordered:
        return None
    return _bounded_json_sha256(ordered, label="OCR projection hashes", max_bytes=64 * 1024)


def _ocr_status(
    *,
    projection_count: int,
    succeeded_count: int,
    unavailable_count: int,
) -> str:
    if projection_count == 0:
        return "not_requested"
    if unavailable_count and succeeded_count:
        return "partial"
    if unavailable_count:
        return "unavailable"
    return "succeeded"


def _normalize_text(
    raw_text: str,
    *,
    check_cancelled: CancellationCheck | None,
) -> str:
    _reject_unsafe_text_controls(raw_text)
    pieces: list[str] = []
    pending_cr = ""
    current_line_chars = 0
    for start in range(0, len(raw_text), _IO_CHUNK_BYTES):
        _check_cancelled(check_cancelled)
        chunk = pending_cr + raw_text[start : start + _IO_CHUNK_BYTES]
        if chunk.endswith("\r"):
            chunk, pending_cr = chunk[:-1], "\r"
        else:
            pending_cr = ""
        chunk = chunk.replace("\r\n", "\n").replace("\r", "\n")
        lines = chunk.split("\n")
        if len(lines) == 1:
            current_line_chars += len(lines[0])
        else:
            if current_line_chars + len(lines[0]) > MAX_TEXT_LINE_CHARS:
                raise ValidationError(
                    "TXT contains a line longer than the supported limit.",
                    error_code="knowledge_text_line_too_long",
                )
            if any(len(line) > MAX_TEXT_LINE_CHARS for line in lines[1:-1]):
                raise ValidationError(
                    "TXT contains a line longer than the supported limit.",
                    error_code="knowledge_text_line_too_long",
                )
            current_line_chars = len(lines[-1])
        if current_line_chars > MAX_TEXT_LINE_CHARS:
            raise ValidationError(
                "TXT contains a line longer than the supported limit.",
                error_code="knowledge_text_line_too_long",
            )
        pieces.append(chunk)
    if pending_cr:
        pieces.append("\n")
    _check_cancelled(check_cancelled)
    return "".join(pieces)


def _recognize_with_cancellation(
    ocr_service: Any,
    image_path: Path,
    *,
    output_path: Path,
    check_cancelled: CancellationCheck | None,
) -> Any:
    recognize = ocr_service.recognize
    _check_cancelled(check_cancelled)
    if _callable_accepts_keyword(recognize, "check_cancelled"):
        payload = recognize(
            image_path,
            output_path=output_path,
            check_cancelled=check_cancelled,
        )
    else:
        payload = recognize(image_path, output_path=output_path)
    _check_cancelled(check_cancelled)
    return payload


def _recognize_projection(
    ocr_service: Any,
    image_path: Path,
    *,
    output_path: Path,
    check_cancelled: CancellationCheck | None,
) -> Any | None:
    """Return ``None`` only for expected OCR availability failures.

    The callback wrapper preserves cancellation exception identity even when the
    cancellation type also belongs to the expected operational-failure taxonomy.
    """

    callback_error: BaseException | None = None

    def guarded_cancel_check() -> object:
        nonlocal callback_error
        assert check_cancelled is not None
        try:
            return check_cancelled()
        except BaseException as exc:
            callback_error = exc
            raise

    effective_check = guarded_cancel_check if check_cancelled is not None else None
    try:
        return _recognize_with_cancellation(
            ocr_service,
            image_path,
            output_path=output_path,
            check_cancelled=effective_check,
        )
    except _OCR_PROJECTION_FAILURES as exc:
        if exc is callback_error:
            raise
        return None


def _callable_accepts_keyword(function: Any, keyword: str) -> bool:
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        (
            parameter.name == keyword
            and parameter.kind
            in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
        )
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


@dataclass(frozen=True)
class _DecodedText:
    text: str
    encoding: str
    bom: str
    newline: str
    selection: str


def _detected_format(header: bytes, *, expected_format: str) -> str:
    if header.startswith(b"%PDF-"):
        return "pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(_CFB_SIGNATURE):
        if expected_format in {"doc", "docx"}:
            return expected_format
        return "cfb"
    if header.startswith(b"PK\x03\x04"):
        return "docx" if expected_format == "docx" else "zip"
    return "txt" if expected_format == "txt" else "unknown"


def _probe_text(
    payload: bytes,
    facts: dict[str, Any],
    *,
    sample_is_complete: bool,
) -> None:
    decoded = _decode_text_payload(
        payload,
        allow_truncated_tail=not sample_is_complete,
    )
    facts["encoding_candidate"] = decoded.encoding
    facts["encoding_selection"] = decoded.selection
    facts["bom"] = decoded.bom != "none"
    facts["bom_kind"] = decoded.bom
    facts["newline"] = decoded.newline
    facts["control_character_count"] = 0


def _decode_text_payload(
    payload: bytes,
    *,
    allow_truncated_tail: bool = False,
) -> _DecodedText:
    if not payload:
        raise ValidationError(
            "TXT contains no decodable text.",
            error_code="knowledge_text_encoding_unknown",
        )
    bom_encoding, bom_size = _text_bom(payload)
    if bom_encoding in {"utf-32-le", "utf-32-be"}:
        raise ValidationError(
            "TXT encoding is outside the supported allowlist.",
            error_code="knowledge_text_encoding_unknown",
        )
    if bom_encoding is not None:
        text = _strict_decode_text(
            payload[bom_size:],
            encoding=bom_encoding,
            allow_truncated_tail=allow_truncated_tail,
        )
        selection = "bom"
        encoding = bom_encoding
    else:
        try:
            text = _strict_decode_text(
                payload,
                encoding="utf-8",
                allow_truncated_tail=allow_truncated_tail,
            )
            encoding = "utf-8"
            selection = "strict_utf8"
        except ValidationError:
            matches = tuple(from_bytes(payload))
            best = matches[0] if matches else None
            candidate = _canonical_encoding_name(
                str(best.encoding) if best is not None and best.encoding else ""
            )
            best_chaos = float(best.chaos) if best is not None else 1.0
            ambiguous = any(
                _canonical_encoding_name(str(other.encoding or "")) != candidate
                and float(other.chaos) - best_chaos < _TEXT_MIN_CANDIDATE_SEPARATION
                for other in matches[1:]
            )
            if (
            candidate not in _TEXT_FALLBACK_ENCODINGS
                or best_chaos > _TEXT_MAX_CANDIDATE_CHAOS
                or ambiguous
            ):
                raise ValidationError(
                    "TXT encoding could not be determined with sufficient confidence.",
                    error_code="knowledge_text_encoding_unknown",
                ) from None
            encoding = candidate
            selection = "bounded_charset_candidate"
            text = _strict_decode_text(
                payload,
                encoding=encoding,
                allow_truncated_tail=allow_truncated_tail,
            )
    _reject_unsafe_text_controls(text)
    if not text and not allow_truncated_tail:
        raise ValidationError(
            "TXT contains no decodable text.",
            error_code="knowledge_text_encoding_unknown",
        )
    return _DecodedText(
        text=text,
        encoding=encoding,
        bom=encoding if bom_encoding is not None else "none",
        newline=_newline_style(text),
        selection=selection,
    )


def _text_bom(payload: bytes) -> tuple[str | None, int]:
    markers = (
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\xef\xbb\xbf", "utf-8"),
        (b"\xfe\xff", "utf-16-be"),
        (b"\xff\xfe", "utf-16-le"),
    )
    for marker, encoding in markers:
        if payload.startswith(marker):
            return encoding, len(marker)
    return None, 0


def _strict_decode_text(
    payload: bytes,
    *,
    encoding: str,
    allow_truncated_tail: bool,
) -> str:
    try:
        return payload.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        truncated_tail = (
            allow_truncated_tail
            and exc.end == len(payload)
            and ("unexpected end" in exc.reason or "truncated" in exc.reason)
        )
        if truncated_tail:
            return payload[: exc.start].decode(encoding, errors="strict")
        raise ValidationError(
            "TXT bytes are invalid for the selected encoding.",
            error_code="knowledge_text_encoding_invalid",
        ) from None


def _canonical_encoding_name(raw: str) -> str:
    if not raw:
        return ""
    try:
        return codecs.lookup(raw).name.replace("_", "-")
    except LookupError:
        return ""


def _reject_unsafe_text_controls(text: str) -> None:
    if "\ufffd" in text or any(
        unicodedata.category(character) in {"Cc", "Cs"}
        and character not in {"\t", "\n", "\r"}
        for character in text
    ):
        raise ValidationError(
            "TXT contains unsupported control or binary characters.",
            error_code="knowledge_text_controls_invalid",
        )


def _newline_style(text: str) -> str:
    crlf_count = text.count("\r\n")
    without_crlf = text.replace("\r\n", "")
    styles = [
        name
        for name, count in (
            ("crlf", crlf_count),
            ("cr", without_crlf.count("\r")),
            ("lf", without_crlf.count("\n")),
        )
        if count
    ]
    if not styles:
        return "none"
    return styles[0] if len(styles) == 1 else "mixed"


def _probe_pdf(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        with pikepdf.Pdf.open(path) as document:
            warnings = [str(item)[:96] for item in document.check_pdf_syntax()[:16]]
            return False, {"page_count": len(document.pages), "syntax_warning_count": len(warnings)}
    except pikepdf.PasswordError:
        return True, {"page_count": None, "syntax_warning_count": 0}
    except pikepdf.PdfError as exc:
        raise ValidationError(
            "The selected PDF is structurally invalid.",
            error_code="knowledge_pdf_invalid",
        ) from exc


def _probe_image(path: Path, *, expected_format: str) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            width, height = image.size
            actual = str(image.format or "").casefold()
            if actual == "jpg":
                actual = "jpeg"
            if actual != expected_format:
                raise ValidationError("The image container does not match its extension.")
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValidationError("The image dimensions exceed the supported range.")
            image.verify()
        return {"width": width, "height": height, "pixels": width * height}
    except (OSError, UnidentifiedImageError) as exc:
        raise ValidationError("The selected image is invalid.") from exc


def _office_is_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return bool(msoffcrypto.OfficeFile(stream).is_encrypted())
    except Exception:
        return False


def _verify_docx(
    path: Path,
    *,
    check_cancelled: CancellationCheck | None = None,
) -> dict[str, int]:
    _check_cancelled(check_cancelled)
    try:
        with ZipFile(path) as package:
            entries = package.infolist()
            if len(entries) > MAX_DOCX_PACKAGE_ENTRIES:
                raise ValidationError(
                    "The selected DOCX contains too many package entries.",
                    error_code="knowledge_docx_entry_limit",
                )
            names: set[str] = set()
            casefold_names: set[str] = set()
            expanded_bytes = 0
            maximum_ratio = 1
            for entry in entries:
                _check_cancelled(check_cancelled)
                _validate_docx_member_path(entry.filename, is_directory=entry.is_dir())
                folded = entry.filename.casefold()
                if entry.filename in names or folded in casefold_names:
                    raise ValidationError(
                        "The selected DOCX contains ambiguous package entries.",
                        error_code="knowledge_docx_entries_ambiguous",
                    )
                names.add(entry.filename)
                casefold_names.add(folded)
                if entry.flag_bits & 0x1:
                    raise ValidationError(
                        "The selected DOCX contains encrypted package entries.",
                        error_code="knowledge_docx_entry_encrypted",
                    )
                mode = (entry.external_attr >> 16) & 0xFFFF
                if mode and stat.S_ISLNK(mode):
                    raise ValidationError(
                        "The selected DOCX contains an unsafe package entry.",
                        error_code="knowledge_docx_entry_unsafe",
                    )
                if entry.file_size < 0 or entry.compress_size < 0:
                    raise ValidationError(
                        "The selected DOCX has invalid package sizes.",
                        error_code="knowledge_docx_size_invalid",
                    )
                if entry.file_size > MAX_DOCX_ENTRY_BYTES:
                    raise ValidationError(
                        "The selected DOCX package entry is too large.",
                        error_code="knowledge_docx_entry_too_large",
                    )
                expanded_bytes += entry.file_size
                if expanded_bytes > MAX_DOCX_EXPANDED_BYTES:
                    raise ValidationError(
                        "The selected DOCX expands beyond the supported limit.",
                        error_code="knowledge_docx_expansion_limit",
                    )
                ratio = (
                    entry.file_size
                    if entry.compress_size == 0
                    else (entry.file_size + entry.compress_size - 1) // entry.compress_size
                )
                maximum_ratio = max(maximum_ratio, ratio)
                if (
                    entry.file_size >= _DOCX_RATIO_CHECK_MIN_BYTES
                    and ratio > MAX_DOCX_COMPRESSION_RATIO
                ):
                    raise ValidationError(
                        "The selected DOCX compression ratio is unsafe.",
                        error_code="knowledge_docx_compression_ratio",
                    )
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise ValidationError(
                    "The selected DOCX has the wrong Office package type.",
                    error_code="knowledge_docx_package_invalid",
                )
    except (BadZipFile, OSError) as exc:
        raise ValidationError(
            "The selected DOCX is not a valid Office package.",
            error_code="knowledge_docx_package_invalid",
        ) from exc
    _check_cancelled(check_cancelled)
    return {
        "container_entry_count": len(entries),
        "container_expanded_bytes": expanded_bytes,
        "container_max_compression_ratio": maximum_ratio,
    }


def _validate_docx_member_path(name: str, *, is_directory: bool) -> None:
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or len(name.encode("utf-8")) > MAX_DOCX_MEMBER_NAME_BYTES
    ):
        raise ValidationError(
            "The selected DOCX contains an unsafe package path.",
            error_code="knowledge_docx_path_unsafe",
        )
    normalized = name[:-1] if is_directory and name.endswith("/") else name
    raw_parts = normalized.split("/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or relative.is_absolute()
        or len(raw_parts) > MAX_DOCX_MEMBER_DEPTH
        or any(part in {"", ".", ".."} or ":" in part for part in raw_parts)
    ):
        raise ValidationError(
            "The selected DOCX contains an unsafe package path.",
            error_code="knowledge_docx_path_unsafe",
        )


def _read_prefix(path: Path, size: int) -> bytes:
    with path.open("rb") as stream:
        return stream.read(size)


def _find_libreoffice() -> Path | None:
    command = shutil.which("soffice") or shutil.which("libreoffice")
    candidates = (
        Path(command) if command else None,
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    )
    return next((candidate for candidate in candidates if candidate is not None and candidate.is_file()), None)


def _plain_text_docling_document(
    path: Path,
    *,
    check_cancelled: CancellationCheck | None = None,
):
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    text = _read_text_cooperatively(path, check_cancelled=check_cancelled)
    document = DoclingDocument(name=path.stem)
    for paragraph in (part.strip() for part in text.split("\n\n")):
        _check_cancelled(check_cancelled)
        if paragraph:
            document.add_text(DocItemLabel.TEXT, paragraph)
    return document


def _image_docling_document(
    path: Path,
    *,
    check_cancelled: CancellationCheck | None = None,
):
    from docling_core.types.doc import DoclingDocument

    _check_cancelled(check_cancelled)
    document = DoclingDocument(name=path.stem)
    document.add_picture()
    _check_cancelled(check_cancelled)
    return document


def _docling_convert(
    path: Path,
    *,
    source_format: str,
    work_dir: Path,
    check_cancelled: CancellationCheck | None = None,
):
    from docling_core.types.doc import DoclingDocument

    _check_cancelled(check_cancelled)
    output_path = work_dir / f"docling-{source_format}-result.json"
    output_path.unlink(missing_ok=True)
    command, environment = _docling_worker_command(
        path,
        source_format=source_format,
        output_path=output_path,
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=str(work_dir),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_no_console_process_kwargs(),
        )
    except OSError:
        raise ValidationError(
            "Docling could not parse the document.",
            error_code="knowledge_docling_parse_failed",
        ) from None
    returncode = _wait_for_process(
        process,
        timeout_seconds=_DOCLING_TIMEOUT_SECONDS,
        check_cancelled=check_cancelled,
        timeout_error=ValidationError(
            "Docling could not parse the document.",
            error_code="knowledge_docling_parse_failed",
        ),
    )
    if returncode != 0 or not output_path.is_file():
        raise ValidationError(
            "Docling could not parse the document.",
            error_code="knowledge_docling_parse_failed",
        )
    _check_cancelled(check_cancelled)
    try:
        document = DoclingDocument.model_validate_json(output_path.read_bytes())
    except Exception:
        raise ValidationError(
            "Docling could not parse the document.",
            error_code="knowledge_docling_parse_failed",
        ) from None
    _check_cancelled(check_cancelled)
    return document


def _pdf_page_routes(path: Path) -> list[tuple[int, bool]]:
    import pypdfium2

    try:
        document = pypdfium2.PdfDocument(path)
    except Exception as exc:
        raise ValidationError("The PDF page inventory could not be read.") from exc
    try:
        routes: list[tuple[int, bool]] = []
        for index in range(len(document)):
            page = document[index]
            text_page = None
            try:
                text_page = page.get_textpage()
                text = text_page.get_text_range().strip()
            finally:
                if text_page is not None:
                    text_page.close()
                page.close()
            useful = len("".join(character for character in text if character.isalnum())) >= 8
            routes.append((index + 1, useful))
        return routes
    finally:
        document.close()


def _append_paddle_ocr_pages(
    document: Any,
    *,
    pdf_path: Path,
    page_indexes: list[int],
    work_dir: Path,
    ocr_service: PaddleOcrService,
    check_cancelled: CancellationCheck | None = None,
) -> _OcrBatchResult:
    import pypdfium2

    _check_cancelled(check_cancelled)
    succeeded_pages: list[int] = []
    unavailable_pages: list[int] = []
    payload_hashes: list[tuple[int, str]] = []
    item_count = 0
    pdf = pypdfium2.PdfDocument(pdf_path)
    try:
        for page_index in page_indexes:
            _check_cancelled(check_cancelled)
            page = pdf[page_index]
            try:
                image_path = work_dir / f"ocr-page-{page_index + 1}.png"
                page.render(scale=2).to_pil().save(image_path)
            finally:
                page.close()
            _check_cancelled(check_cancelled)
            output_path = work_dir / f"ocr-page-{page_index + 1}.json"
            payload = _recognize_projection(
                ocr_service,
                image_path,
                output_path=output_path,
                check_cancelled=check_cancelled,
            )
            page_number = page_index + 1
            if payload is None:
                unavailable_pages.append(page_number)
                continue
            item_count += _append_ocr_text(document, payload, page_no=page_number)
            succeeded_pages.append(page_number)
            payload_hashes.append(
                (
                    page_number,
                    _bounded_json_sha256(
                        payload,
                        label="OCR result",
                        max_bytes=MAX_OCR_RESULT_BYTES,
                    ),
                )
            )
            _check_cancelled(check_cancelled)
    finally:
        pdf.close()
    return _OcrBatchResult(
        succeeded_pages=tuple(succeeded_pages),
        unavailable_pages=tuple(unavailable_pages),
        item_count=item_count,
        payload_hashes=tuple(payload_hashes),
    )


def _append_ocr_text(document: Any, payload: Any, *, page_no: int) -> int:
    from docling_core.types.doc import BoundingBox, DocItemLabel, ProvenanceItem

    count = 0
    for text, bbox in _paddle_text_boxes(payload):
        clean = text.strip()
        if not clean:
            continue
        document.add_text(
            DocItemLabel.TEXT,
            clean,
            prov=ProvenanceItem(
                page_no=page_no,
                bbox=BoundingBox(l=bbox[0], t=bbox[1], r=bbox[2], b=bbox[3]),
                charspan=(0, len(clean)),
            ),
        )
        count += 1
    return count


def _paddle_text_boxes(payload: Any) -> list[tuple[str, tuple[float, float, float, float]]]:
    matches: list[tuple[str, tuple[float, float, float, float]]] = []
    if isinstance(payload, dict):
        texts = payload.get("rec_texts")
        polygons = payload.get("rec_polys") or payload.get("dt_polys") or []
        if isinstance(texts, list):
            for index, raw_text in enumerate(texts):
                polygon = polygons[index] if isinstance(polygons, list) and index < len(polygons) else None
                matches.append((str(raw_text), _polygon_bbox(polygon)))
        for value in payload.values():
            matches.extend(_paddle_text_boxes(value))
    elif isinstance(payload, list):
        for value in payload:
            matches.extend(_paddle_text_boxes(value))
    return matches


def _polygon_bbox(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, list):
        points = [point for point in value if isinstance(point, list) and len(point) >= 2]
        if points:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            return min(xs), min(ys), max(xs), max(ys)
    return 0.0, 0.0, 0.0, 0.0
