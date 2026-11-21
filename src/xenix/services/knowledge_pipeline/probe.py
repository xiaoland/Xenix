"""Read source signatures and container facts before normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import msoffcrypto
import pikepdf
from PIL import Image, UnidentifiedImageError

from ...exceptions import ValidationError
from ..knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY, KnowledgeFormatRegistry
from .contracts import (
    MAX_SOURCE_BYTES,
    FileProbeResult,
    FormatProbeFacts,
    FormatProbeProvider,
    _format_mismatch,
    _provider_map,
)
from .packages import (
    _DOCX_PACKAGE,
    _PPTX_PACKAGE,
    _ZipPackageProfile,
    _package_error,
    _verify_mimetype_zip_package,
    _verify_ooxml_package,
)
from .text_decoding import _decode_text_payload


MAX_IMAGE_PIXELS = 100_000_000
_CFB_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


class _TextProbeProvider:
    provider_id = "text"

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        facts: dict[str, Any] = {}
        _probe_text(header, facts, sample_is_complete=size <= len(header))
        return FormatProbeFacts("txt", facts=facts)


class _CfbOfficeProbeProvider:
    def __init__(
        self,
        *,
        provider_id: str,
        source_format: str,
        normalized_format: str,
        office_kind: str,
    ) -> None:
        self.provider_id = provider_id
        self._source_format = source_format
        self._normalized_format = normalized_format
        self._office_kind = office_kind

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        if not header.startswith(_CFB_SIGNATURE):
            raise _format_mismatch()
        office_kind, encrypted = _inspect_office_file(source)
        if office_kind != self._office_kind:
            raise _format_mismatch()
        return FormatProbeFacts(
            self._source_format,
            encrypted=encrypted,
            facts={
                "container": "cfb",
                "office_kind": office_kind,
                "normalization_candidate": self._normalized_format,
            },
        )


class _OoxmlOfficeProbeProvider:
    def __init__(self, *, provider_id: str, profile: _ZipPackageProfile) -> None:
        self.provider_id = provider_id
        self._profile = profile

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        if header.startswith(_CFB_SIGNATURE):
            office_kind, encrypted = _inspect_office_file(source)
            if office_kind != "ooxml" or not encrypted:
                raise _package_error(self._profile, "package_invalid", "container is invalid")
            return FormatProbeFacts(
                self._profile.source_format,
                encrypted=True,
                facts={"container": "cfb-encrypted-ooxml"},
            )
        if not header.startswith(b"PK\x03\x04"):
            raise _format_mismatch()
        facts = _verify_ooxml_package(source, self._profile)
        facts["container"] = "ooxml"
        return FormatProbeFacts(self._profile.source_format, facts=facts)


class _PdfProbeProvider:
    provider_id = "pdf"

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        if not header.startswith(b"%PDF-"):
            raise _format_mismatch()
        encrypted, facts = _probe_pdf(source)
        return FormatProbeFacts("pdf", encrypted=encrypted, facts=facts)


class _ImageProbeProvider:
    provider_id = "image"

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        expected = capability.source_format
        signature_matches = (
            expected == "png" and header.startswith(b"\x89PNG\r\n\x1a\n")
        ) or (
            expected == "jpeg" and header.startswith(b"\xff\xd8\xff")
        )
        if not signature_matches:
            raise _format_mismatch()
        return FormatProbeFacts(
            expected,
            facts=_probe_image(source, expected_format=expected),
        )


class _RtfProbeProvider:
    provider_id = "rtf"

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        if not header.lstrip().startswith(b"{\\rtf"):
            raise _format_mismatch()
        return FormatProbeFacts("rtf", facts={"container": "rtf"})


class _ZipMimetypeProbeProvider:
    provider_id = "mimetype-zip"

    def probe(self, source, *, header, size, capability) -> FormatProbeFacts:
        if not header.startswith(b"PK\x03\x04"):
            raise _format_mismatch()
        facts = _verify_mimetype_zip_package(
            source,
            source_format=capability.source_format,
            expected_mimetype=capability.media_type,
        )
        return FormatProbeFacts(
            capability.source_format,
            facts={"container": "zip", **facts},
        )


class FileProbe:
    """Return authoritative byte/container facts without mutating the source."""

    def __init__(
        self,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
        providers: tuple[FormatProbeProvider, ...] | None = None,
    ) -> None:
        self._registry = registry
        providers = providers or (
            _TextProbeProvider(),
            _CfbOfficeProbeProvider(
                provider_id="cfb-word",
                source_format="doc",
                normalized_format="docx",
                office_kind="doc",
            ),
            _OoxmlOfficeProbeProvider(
                provider_id="ooxml-word",
                profile=_DOCX_PACKAGE,
            ),
            _CfbOfficeProbeProvider(
                provider_id="cfb-presentation",
                source_format="ppt",
                normalized_format="pptx",
                office_kind="ppt",
            ),
            _OoxmlOfficeProbeProvider(
                provider_id="ooxml-presentation",
                profile=_PPTX_PACKAGE,
            ),
            _PdfProbeProvider(),
            _ImageProbeProvider(),
            _RtfProbeProvider(),
            _ZipMimetypeProbeProvider(),
        )
        self._providers = _provider_map(
            providers,
            required_ids=registry.probe_provider_ids,
            kind="probe",
        )

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
        provider = self._providers[capability.probe_provider_id]
        result = provider.probe(
            source,
            header=header,
            size=size,
            capability=capability,
        )
        if result.detected_format != capability.source_format:
            raise _format_mismatch()

        facts: dict[str, Any] = {
            "signature": result.detected_format,
            "byte_size": size,
            "format_registry_version": self._registry.version,
            "probe_provider_id": provider.provider_id,
        }
        facts.update(result.facts)
        facts["encrypted"] = result.encrypted
        return FileProbeResult(
            source_path=source,
            source_format=result.detected_format,
            media_type=capability.media_type,
            size=size,
            encrypted=result.encrypted,
            facts=facts,
        )

    @property
    def supported_formats_message(self) -> str:
        return self._registry.supported_formats_message()


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


def _inspect_office_file(path: Path) -> tuple[str | None, bool]:
    try:
        with path.open("rb") as stream:
            office = msoffcrypto.OfficeFile(stream)
            office_kind = {
                "Doc97File": "doc",
                "Ppt97File": "ppt",
                "OOXMLFile": "ooxml",
            }.get(type(office).__name__)
            return office_kind, bool(office.is_encrypted())
    except msoffcrypto.exceptions.FileFormatError:
        return None, False


def _read_prefix(path: Path, size: int) -> bytes:
    with path.open("rb") as stream:
        return stream.read(size)
