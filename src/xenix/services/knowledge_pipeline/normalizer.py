from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL import __version__ as pillow_version

from ...exceptions import ValidationError
from ..knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY, KnowledgeFormatRegistry
from .archive_inspect import (
    OOXML_PACKAGE_PROFILES,
    decrypt_pdf,
    office_source,
    verify_ooxml_package,
)
from .contracts import (
    MAX_SOURCE_BYTES,
    TEXT_ENCODING_ALLOWLIST,
    FileProbeResult,
    FormatNormalizerProvider,
    NormalizationRequest,
    NormalizedSource,
    installed_package,
    provider_map,
    read_bytes,
    runtime_package,
    sha256_file_bounded,
    write_text,
)
from .text_decoding import decode_text_payload, normalize_text


class _TextNormalizerProvider:
    provider_id = "text"

    def normalize(self, request: NormalizationRequest) -> NormalizedSource:
        payload = read_bytes(request.probe.source_path)
        decoded = decode_text_payload(payload)
        text = normalize_text(decoded.text)
        target = request.work_dir / "normalized.txt"
        write_text(target, text)
        return NormalizedSource(
            target,
            request.capability.source_format,
            request.capability.parser_format,
            _normalization_descriptor(
                operation="decode_text",
                backend="python-codecs",
                package=runtime_package("python", sys.version.split()[0]),
                options={
                    "decode_errors": "strict",
                    "allowed_encodings": sorted(TEXT_ENCODING_ALLOWLIST),
                    "control_policy": "reject",
                },
                input_sha256=request.input_sha256,
                output_path=target,
                details={
                    "encoding": decoded.encoding,
                    "bom": decoded.bom,
                    "newline": {"input": decoded.newline, "output": "lf"},
                    "normalization": {
                        "bom_removed": decoded.bom != "none",
                        "newlines_normalized": decoded.newline not in {"lf", "none"},
                        "unicode_normalization": "preserved",
                    },
                },
            ),
        )


class _DocumentNormalizerProvider:
    provider_id = "document"

    def normalize(self, request: NormalizationRequest) -> NormalizedSource:
        source = request.probe.source_path
        if request.probe.encrypted:
            source = office_source(request)
        profile = OOXML_PACKAGE_PROFILES.get(request.capability.parser_format)
        if profile is not None:
            verify_ooxml_package(source, profile)
        if request.probe.encrypted:
            backend = "msoffcrypto"
            package = installed_package("msoffcrypto-tool")
        elif profile is not None:
            backend = "zip-package-identity"
            package = runtime_package("python-zipfile", sys.version.split()[0])
        else:
            backend = "document-identity"
            package = runtime_package("python", sys.version.split()[0])
        return NormalizedSource(
            source,
            request.capability.source_format,
            request.capability.parser_format,
            _normalization_descriptor(
                operation="decrypt" if request.probe.encrypted else "identity",
                backend=backend,
                package=package,
                options={
                    "encrypted_input": request.probe.encrypted,
                    "parser_format": request.capability.parser_format,
                    "source_safety_verified": True,
                },
                input_sha256=request.input_sha256,
                output_path=source,
            ),
        )


class _PdfNormalizerProvider:
    provider_id = "pdf"

    def normalize(self, request: NormalizationRequest) -> NormalizedSource:
        source = request.probe.source_path
        if request.probe.encrypted:
            assert request.password is not None
            source = decrypt_pdf(
                source,
                password=request.password,
                work_dir=request.work_dir,
            )
        return NormalizedSource(
            source,
            request.capability.source_format,
            request.capability.parser_format,
            _normalization_descriptor(
                operation="decrypt" if request.probe.encrypted else "identity",
                backend="pikepdf" if request.probe.encrypted else "pdf-identity",
                package=installed_package("pikepdf"),
                options={"encrypted_input": request.probe.encrypted, "repair": False},
                input_sha256=request.input_sha256,
                output_path=source,
            ),
        )


class _ImageNormalizerProvider:
    provider_id = "image"

    def normalize(self, request: NormalizationRequest) -> NormalizedSource:
        target = request.work_dir / "normalized-image.png"
        try:
            with Image.open(request.probe.source_path) as image:
                normalized = ImageOps.exif_transpose(image)
                if normalized.mode not in {"RGB", "RGBA", "L"}:
                    normalized = normalized.convert("RGB")
                normalized.save(target, format="PNG")
        except (OSError, UnidentifiedImageError) as exc:
            raise ValidationError("The image could not be normalized.") from exc
        return NormalizedSource(
            target,
            request.capability.source_format,
            request.capability.parser_format,
            _normalization_descriptor(
                operation="normalize_image",
                backend="pillow-image",
                package=runtime_package("Pillow", pillow_version),
                options={
                    "orientation": "exif_transposed",
                    "pixel_encoding": "png",
                    "source_format": request.capability.source_format,
                },
                input_sha256=request.input_sha256,
                output_path=target,
            ),
        )


class FormatNormalizer:
    """Dispatch normalization through one registered capability provider."""

    def __init__(
        self,
        *,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
        providers: tuple[FormatNormalizerProvider, ...] | None = None,
    ) -> None:
        self._registry = registry
        providers = providers or (
            _TextNormalizerProvider(),
            _DocumentNormalizerProvider(),
            _PdfNormalizerProvider(),
            _ImageNormalizerProvider(),
        )
        self._providers = provider_map(
            providers,
            required_ids=registry.normalizer_provider_ids,
            kind="normalizer",
        )

    def normalize(
        self,
        probe: FileProbeResult,
        *,
        work_dir: Path,
        password: str | None = None,
    ) -> NormalizedSource:
        capability = self._registry.capability_for_format(probe.source_format)
        if capability is None:
            raise ValidationError("No Knowledge normalizer is registered for this format.")
        if probe.encrypted and not password:
            raise ValidationError(
                "A password is required to import this encrypted document.",
                error_code="knowledge_password_required",
                retryable=True,
            )
        request = NormalizationRequest(
            probe=probe,
            capability=capability,
            work_dir=work_dir,
            password=password,
            input_sha256=sha256_file_bounded(
                probe.source_path,
                max_bytes=MAX_SOURCE_BYTES,
            ),
        )
        return self._providers[capability.normalizer_provider_id].normalize(request)


def _normalization_descriptor(
    *,
    operation: str,
    backend: str,
    package: dict[str, str],
    options: dict[str, Any],
    input_sha256: str,
    output_path: Path,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_sha256 = sha256_file_bounded(
        output_path,
        max_bytes=MAX_SOURCE_BYTES,
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
