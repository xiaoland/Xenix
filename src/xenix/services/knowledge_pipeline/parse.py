"""Execute parse plans and assemble their content and provenance."""

from __future__ import annotations

import shutil
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from ...exceptions import ValidationError
from ..knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY, KnowledgeFormatRegistry
from ..paddle_ocr_service import NATIVE_OCR_PROTOCOL_VERSION, PaddleOcrService
from .contracts import (
    MAX_SOURCE_BYTES,
    DocumentParserProvider,
    FileProbeResult,
    NormalizedSource,
    ParsedContent,
    ParsePlan,
    ParserExecutionContext,
    ParseResult,
    _ANYDOC_PROVIDER_ID,
    _provider_map,
)
from .docling_adapters import (
    _anydoc_convert,
    _docling_convert,
    _image_docling_document,
    _plain_text_docling_document,
)
from .ocr import (
    MAX_OCR_RESULT_BYTES,
    _append_ocr_text,
    _append_paddle_ocr_pages,
    _ocr_runtime_payload,
    _ocr_status,
    _recognize_projection,
)
from .provenance import (
    _bounded_json_sha256,
    _combined_projection_sha256,
    _docling_document_sha256,
    _installed_package,
    _runtime_package,
    _sha256_file_bounded,
)


_ANYDOC_DISTRIBUTION = "firecrawl-anydoc"


class ParseExecutor:
    def __init__(
        self,
        ocr_service: PaddleOcrService | None = None,
        *,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
        providers: tuple[DocumentParserProvider, ...] | None = None,
    ) -> None:
        self._ocr = ocr_service
        self._registry = registry
        providers = providers or (
            _TextParserProvider(),
            _AnyDocParserProvider(),
            _PdfParserProvider(),
            _ImageParserProvider(),
        )
        self._providers = _provider_map(
            providers,
            required_ids=registry.parser_provider_ids,
            kind="document parser",
        )

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
    ) -> ParseResult:
        ocr_ready = plan.ocr_ready
        capability = self._registry.capability_for_format(normalized.source_format)
        if (
            capability is None
            or capability.parser_format != normalized.parser_format
            or plan.parser_format != normalized.parser_format
        ):
            raise ValidationError("The selected Knowledge parse plan is invalid.")
        provider = self._providers[capability.parser_provider_id]
        parser_input_sha256 = _sha256_file_bounded(
            normalized.path,
            max_bytes=MAX_SOURCE_BYTES,
        )
        needs_ocr = any(unit.route_id.startswith("paddleocr-") for unit in plan.units)
        ocr_runtime_descriptor: dict[str, object] | None = None
        with ExitStack() as stack:
            ocr_executor: Any = self._ocr
            if needs_ocr:
                assert self._ocr is not None
                open_session = getattr(self._ocr, "open_session", None)
                if callable(open_session):
                    ocr_executor = stack.enter_context(
                        open_session(
                            allowed_root=work_dir,
                            log_path=work_dir / "paddle-ocr.log",
                        )
                    )
                ocr_runtime_descriptor = _ocr_runtime_payload(ocr_executor)
            content = provider.parse(
                ParserExecutionContext(
                    normalized=normalized,
                    plan=plan,
                    work_dir=work_dir,
                    ocr_executor=ocr_executor,
                )
            )
        parser_output_sha256 = _docling_document_sha256(content.document)
        ocr_status = _ocr_status(
            projection_count=content.ocr_projection_count,
            succeeded_count=content.ocr_succeeded_count,
            unavailable_count=content.ocr_unavailable_count,
        )
        return ParseResult(
            document=content.document,
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
                            **({"evidence": unit.evidence} if unit.evidence else {}),
                        }
                        for unit in plan.units
                    ],
                },
                "parser": {
                    "content_ir": "DoclingDocument",
                    "version": 2,
                    "package": _installed_package(provider.package_distribution),
                    "backend": provider.backend,
                    "options": {
                        "merge_strategy": plan.merge_strategy,
                        "parser_format": normalized.parser_format,
                    },
                    "status": "succeeded",
                    "input_sha256": parser_input_sha256,
                    "output_sha256": parser_output_sha256,
                },
                "ocr": {
                    "service": "paddle-inference",
                    "package": _runtime_package(
                        "paddle-inference",
                        str(
                            (ocr_runtime_descriptor or {}).get(
                                "engine_version",
                                "runtime-resolved",
                            )
                        ),
                    ),
                    "backend": "xenix-native-worker",
                    "options": {
                        "page_scoped": normalized.parser_format == "pdf",
                        "projection": "text",
                        "protocol": NATIVE_OCR_PROTOCOL_VERSION,
                    },
                    "status": ocr_status,
                    "ready": ocr_ready,
                    "input_sha256": parser_input_sha256,
                    "output_sha256": _combined_projection_sha256(
                        content.ocr_payload_hashes
                    ),
                    "projection_count": content.ocr_projection_count,
                    "attempted_count": content.ocr_attempted_count,
                    "succeeded_count": content.ocr_succeeded_count,
                    "unavailable_count": content.ocr_unavailable_count,
                    **(
                        {"runtime": ocr_runtime_descriptor}
                        if ocr_runtime_descriptor is not None
                        else {}
                    ),
                },
            },
            warnings=list(content.warnings),
            projections=list(content.projections),
        )


class _TextParserProvider:
    provider_id = "text"
    backend = "xenix-txt-adapter"
    package_distribution = "docling-core"

    def parse(self, context: ParserExecutionContext) -> ParsedContent:
        return ParsedContent(
            _plain_text_docling_document(context.normalized.path)
        )


class _AnyDocParserProvider:
    provider_id = _ANYDOC_PROVIDER_ID
    backend = "anydoc-rust-markdown"
    package_distribution = _ANYDOC_DISTRIBUTION

    def parse(self, context: ParserExecutionContext) -> ParsedContent:
        return ParsedContent(
            _anydoc_convert(
                context.normalized.path,
                source_format=context.normalized.parser_format,
            )
        )


class _PdfParserProvider:
    provider_id = "pdf"
    backend = "docling"
    package_distribution = "docling"

    def parse(self, context: ParserExecutionContext) -> ParsedContent:
        document = _docling_convert(
            context.normalized.path,
            source_format="pdf",
            work_dir=context.work_dir,
        )
        ocr_pages = [
            unit.page - 1
            for unit in context.plan.units
            if unit.route_id in {"paddleocr-page", "paddleocr-hybrid-page"}
            and unit.page
        ]
        unavailable_pages = [
            unit.page
            for unit in context.plan.units
            if unit.route_id == "text-projection-unavailable" and unit.page
        ]
        projection_count = len(ocr_pages) + len(unavailable_pages)
        warnings: list[str] = []
        projections: list[dict[str, Any]] = []
        succeeded_count = 0
        payload_hashes: tuple[tuple[int, str], ...] = ()
        if ocr_pages:
            page_result = _append_paddle_ocr_pages(
                document,
                pdf_path=context.normalized.path,
                page_indexes=ocr_pages,
                work_dir=context.work_dir,
                ocr_service=context.ocr_executor,
            )
            succeeded_count = len(page_result.succeeded_pages)
            unavailable_pages.extend(page_result.unavailable_pages)
            payload_hashes = page_result.payload_hashes
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
        if unavailable_pages:
            warnings.append("ocr_projection_unavailable")
            projections.append(
                {
                    "kind": "ocr_text",
                    "status": "unavailable",
                    "pages": unavailable_pages,
                }
            )
        return ParsedContent(
            document,
            warnings=tuple(warnings),
            projections=tuple(projections),
            ocr_projection_count=projection_count,
            ocr_attempted_count=len(ocr_pages),
            ocr_succeeded_count=succeeded_count,
            ocr_unavailable_count=len(unavailable_pages),
            ocr_payload_hashes=payload_hashes,
        )


class _ImageParserProvider:
    provider_id = "image"
    backend = "xenix-image-adapter"
    package_distribution = "docling-core"

    def parse(self, context: ParserExecutionContext) -> ParsedContent:
        document = _image_docling_document(context.normalized.path)
        if not context.plan.ocr_ready:
            return ParsedContent(
                document,
                warnings=("ocr_projection_unavailable",),
                projections=({"kind": "ocr_text", "status": "unavailable"},),
                ocr_projection_count=1,
                ocr_unavailable_count=1,
            )
        staged_image = (
            context.work_dir / f"ocr-image{context.normalized.path.suffix.lower()}"
        )
        shutil.copyfile(context.normalized.path, staged_image)
        payload = _recognize_projection(
            context.ocr_executor,
            staged_image,
            output_path=context.work_dir / "image-ocr.json",
        )
        if payload is None:
            return ParsedContent(
                document,
                warnings=("ocr_projection_unavailable",),
                projections=({"kind": "ocr_text", "status": "unavailable"},),
                ocr_projection_count=1,
                ocr_attempted_count=1,
                ocr_unavailable_count=1,
            )
        count = _append_ocr_text(document, payload, page_no=1)
        payload_hash = _bounded_json_sha256(
            payload,
            label="OCR result",
            max_bytes=MAX_OCR_RESULT_BYTES,
        )
        return ParsedContent(
            document,
            projections=({"kind": "ocr_text", "status": "ready", "items": count},),
            ocr_projection_count=1,
            ocr_attempted_count=1,
            ocr_succeeded_count=1,
            ocr_payload_hashes=((1, payload_hash),),
        )
