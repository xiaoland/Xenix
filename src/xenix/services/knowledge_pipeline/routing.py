from __future__ import annotations

from ...exceptions import ValidationError
from ..knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY, KnowledgeFormatRegistry
from ..knowledge_pdf import PdfPageTextState, probe_pdf_pages
from .contracts import (
    NormalizedSource,
    ParsePlan,
    ParsePlanUnit,
    ParserRouteProvider,
    provider_map,
)

_ANYDOC_PROVIDER_ID = "anydoc"


class _TextRouteProvider:
    provider_id = "text"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        return ParsePlan(
            "txt",
            "txt",
            (ParsePlanUnit("document", "xenix-text", "decoded_text"),),
            "document",
            ocr_ready=ocr_ready,
        )


class _AnyDocRouteProvider:
    provider_id = _ANYDOC_PROVIDER_ID

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        return ParsePlan(
            normalized.source_format,
            normalized.parser_format,
            (
                ParsePlanUnit(
                    "document",
                    f"anydoc-{normalized.parser_format}",
                    "validated_local_document",
                ),
            ),
            "document",
            ocr_ready=ocr_ready,
        )


class _PdfRouteProvider:
    provider_id = "pdf"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        units: list[ParsePlanUnit] = []
        for evidence in probe_pdf_pages(normalized.path):
            payload = evidence.to_payload()
            if evidence.text_state is PdfPageTextState.CREDIBLE:
                route_id = "pdfium-native-text"
                reason = "native_text_credible"
            elif ocr_ready:
                route_id = (
                    "paddleocr-page"
                    if evidence.text_state is PdfPageTextState.ABSENT
                    else "paddleocr-hybrid-page"
                )
                reason = f"native_text_{evidence.text_state.value}"
            else:
                route_id = "text-projection-unavailable"
                reason = f"ocr_unavailable_for_{evidence.text_state.value}_text"
            units.append(ParsePlanUnit("page", route_id, reason, evidence.page, payload))
        return ParsePlan(
            "pdf",
            "pdf",
            tuple(units),
            "docling-document-plus-page-projections",
            policy_version=3,
            ocr_ready=ocr_ready,
        )


class _ImageRouteProvider:
    provider_id = "image"

    def plan(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        units = [ParsePlanUnit("image", "docling-image-shell", "image_content_ir")]
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


class ParserRouter:
    """Select explainable parse routes through an extensible provider registry."""

    def __init__(
        self,
        providers: tuple[ParserRouteProvider, ...] | None = None,
        *,
        registry: KnowledgeFormatRegistry = KNOWLEDGE_FORMAT_REGISTRY,
    ) -> None:
        self._registry = registry
        providers = providers or (
            _TextRouteProvider(),
            _AnyDocRouteProvider(),
            _PdfRouteProvider(),
            _ImageRouteProvider(),
        )
        self._providers = provider_map(
            providers,
            required_ids=registry.route_provider_ids,
            kind="parser route",
        )

    def route(self, normalized: NormalizedSource, *, ocr_ready: bool) -> ParsePlan:
        capability = self._registry.capability_for_format(normalized.source_format)
        if capability is None or capability.parser_format != normalized.parser_format:
            raise ValidationError("No Knowledge parser route is registered for this format.")
        provider = self._providers[capability.route_provider_id]
        return provider.plan(normalized, ocr_ready=ocr_ready)
