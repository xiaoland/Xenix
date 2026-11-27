from __future__ import annotations

import io
import re
import shutil
import subprocess
from collections.abc import Iterable
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from ...exceptions import ValidationError
from ..knowledge_formats import KNOWLEDGE_FORMAT_REGISTRY, KnowledgeFormatRegistry
from ..knowledge_pdf import PdfPageTextState, parse_native_pdf
from ..paddle_ocr import NATIVE_OCR_PROTOCOL_VERSION, PaddleOcrService
from .contracts import (
    MAX_ANYDOC_BLOCKS,
    MAX_ANYDOC_MARKDOWN_BYTES,
    MAX_OCR_RESULT_BYTES,
    MAX_SOURCE_BYTES,
    MAX_TEXT_LINE_CHARS,
    DocumentParserProvider,
    FileProbeResult,
    NormalizedSource,
    OcrBatchResult,
    ParsedContent,
    ParsePlan,
    ParseResult,
    ParserExecutionContext,
    bounded_json_sha256,
    format_mismatch,
    installed_package,
    provider_map,
    read_text,
    runtime_package,
    sha256_file_bounded,
)
from .text_decoding import reject_unsafe_text_controls

_ANYDOC_PROVIDER_ID = "anydoc"
_ANYDOC_DISTRIBUTION = "firecrawl-anydoc"
_ANYDOC_ERROR_CODES = {
    "EncryptedError": "knowledge_password_required",
    "MalformedError": "knowledge_anydoc_malformed",
    "MissingPartError": "knowledge_anydoc_malformed",
    "ResourceLimitError": "knowledge_anydoc_resource_limit",
    "UnsupportedError": "knowledge_anydoc_unsupported",
}
_MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[\t ]+(.+?)[\t ]*#*[\t ]*$")
_MARKDOWN_LIST_ITEM = re.compile(r"^ {0,12}([-+*]|\d+[.)])[\t ]+(.+)$")
_MARKDOWN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^`]*)$")
_OCR_PROJECTION_FAILURES = (
    ValidationError,
    OSError,
    TimeoutError,
    subprocess.SubprocessError,
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
    backend = "pdfium"
    package_distribution = "pypdfium2"

    def parse(self, context: ParserExecutionContext) -> ParsedContent:
        document = parse_native_pdf(
            context.normalized.path,
            text_pages={
                unit.page
                for unit in context.plan.units
                if unit.page is not None
                and unit.evidence.get("text_state") != PdfPageTextState.ABSENT
            },
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
        payload_hash = bounded_json_sha256(
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
        self._providers = provider_map(
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
        parser_input_sha256 = sha256_file_bounded(
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
                    "package": installed_package(provider.package_distribution),
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
                    "package": runtime_package(
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


def _docling_document_sha256(document: Any) -> str:
    try:
        exported = document.export_to_dict()
    except Exception as exc:
        raise ValidationError("Docling content cannot be hashed safely.") from exc
    return bounded_json_sha256(
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
    return bounded_json_sha256(ordered, label="OCR projection hashes", max_bytes=64 * 1024)


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


def _recognize_projection(
    ocr_service: Any,
    image_path: Path,
    *,
    output_path: Path,
) -> Any | None:
    """Return ``None`` only for expected OCR availability failures."""

    try:
        return ocr_service.recognize(image_path, output_path=output_path)
    except _OCR_PROJECTION_FAILURES:
        return None


def _ocr_runtime_payload(value: object) -> dict[str, object] | None:
    descriptor = getattr(value, "runtime_descriptor", None)
    if callable(descriptor):
        descriptor = descriptor()
    to_payload = getattr(descriptor, "to_payload", None)
    if callable(to_payload):
        payload = to_payload()
        if isinstance(payload, dict):
            descriptor = dict(payload)
        else:
            return None
    if isinstance(descriptor, dict):
        descriptor = dict(descriptor)
    else:
        return None
    if descriptor.keys() != {
        "generation_id",
        "runtime_id",
        "model_pack_id",
        "engine",
        "engine_version",
        "protocol_version",
        "manifest_sha256",
    }:
        return None
    if any(
        not isinstance(descriptor[key], str) or not descriptor[key]
        for key in (
            "generation_id",
            "runtime_id",
            "model_pack_id",
            "engine",
            "engine_version",
        )
    ):
        return None
    manifest_sha256 = descriptor["manifest_sha256"]
    if (
        not isinstance(manifest_sha256, str)
        or len(manifest_sha256) != 64
        or any(character not in "0123456789abcdef" for character in manifest_sha256)
        or type(descriptor["protocol_version"]) is not int
    ):
        return None
    return descriptor


def _plain_text_docling_document(path: Path):
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    text = read_text(path)
    document = DoclingDocument(name=path.stem)
    for paragraph in (part.strip() for part in text.split("\n\n")):
        if paragraph:
            document.add_text(DocItemLabel.TEXT, paragraph)
    return document


def _anydoc_convert(path: Path, *, source_format: str):
    try:
        import anydoc

        detected = anydoc.format_from_path(str(path))
        if detected != source_format:
            raise format_mismatch()
        markdown = anydoc.to_markdown(str(path))
    except ValidationError:
        raise
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValidationError(
            "The local AnyDoc parser is unavailable.",
            error_code="knowledge_anydoc_dependency_failed",
            error_details={"diagnostic_code": "anydoc_dependency_error"},
            retryable=True,
        ) from exc
    except Exception as exc:
        error_name = type(exc).__name__
        error_code = _ANYDOC_ERROR_CODES.get(
            error_name,
            "knowledge_anydoc_conversion_failed",
        )
        raise ValidationError(
            "AnyDoc could not parse the document.",
            error_code=error_code,
            error_details={"diagnostic_code": _anydoc_diagnostic_code(error_name)},
            retryable=error_code in {
                "knowledge_password_required",
                "knowledge_anydoc_conversion_failed",
            },
        ) from exc
    if not isinstance(markdown, str):
        raise ValidationError(
            "AnyDoc returned an invalid document.",
            error_code="knowledge_anydoc_conversion_failed",
            error_details={"diagnostic_code": "anydoc_output_invalid"},
            retryable=True,
        )
    return _markdown_to_docling_document(markdown, name=path.stem)


def _anydoc_diagnostic_code(error_name: str) -> str:
    token = re.sub(r"(?<!^)(?=[A-Z])", "_", error_name).casefold()
    token = re.sub(r"[^a-z0-9_.-]+", "_", token).strip("_")
    return f"anydoc_{token or 'conversion_error'}"[:80]


def _markdown_to_docling_document(markdown: str, *, name: str):
    from docling_core.types.doc import DocItemLabel, DoclingDocument, GroupLabel

    encoded_size = len(markdown.encode("utf-8"))
    if encoded_size < 1 or encoded_size > MAX_ANYDOC_MARKDOWN_BYTES:
        raise ValidationError(
            "AnyDoc output exceeds the supported size.",
            error_code="knowledge_anydoc_output_limit",
        )
    reject_unsafe_text_controls(markdown)
    document = DoclingDocument(name=name or "document")
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    fence_marker: str | None = None
    list_group: Any = None
    block_count = 0

    def add_block() -> None:
        nonlocal block_count
        block_count += 1
        if block_count > MAX_ANYDOC_BLOCKS:
            raise ValidationError(
                "AnyDoc output contains too many content blocks.",
                error_code="knowledge_anydoc_output_limit",
            )

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = "\n".join(paragraph_lines).strip()
        paragraph_lines.clear()
        if text:
            add_block()
            document.add_text(DocItemLabel.PARAGRAPH, text)

    for raw_line in _bounded_markdown_lines(markdown):
        line = raw_line.rstrip()
        fence = _MARKDOWN_FENCE.match(line)
        if fence_marker is not None:
            if fence and fence.group(1).startswith(fence_marker[0]) and len(fence.group(1)) >= len(fence_marker):
                add_block()
                document.add_code("\n".join(code_lines).rstrip())
                code_lines.clear()
                fence_marker = None
            else:
                code_lines.append(raw_line)
            continue
        if fence:
            flush_paragraph()
            list_group = None
            fence_marker = fence.group(1)
            continue
        if not line.strip():
            flush_paragraph()
            list_group = None
            continue
        heading = _MARKDOWN_HEADING.match(line)
        if heading:
            flush_paragraph()
            list_group = None
            add_block()
            document.add_heading(heading.group(2).strip(), level=len(heading.group(1)))
            continue
        list_item = _MARKDOWN_LIST_ITEM.match(line)
        if list_item:
            flush_paragraph()
            marker, text = list_item.groups()
            if list_group is None:
                list_group = document.add_group(label=GroupLabel.LIST, name="list")
            add_block()
            document.add_list_item(
                text.strip(),
                enumerated=marker[0].isdigit(),
                marker=marker,
                parent=list_group,
            )
            continue
        list_group = None
        paragraph_lines.append(line)

    if fence_marker is not None:
        paragraph_lines.extend((fence_marker, *code_lines))
    flush_paragraph()
    if block_count == 0:
        raise ValidationError(
            "AnyDoc returned no usable content.",
            error_code="knowledge_anydoc_malformed",
        )
    return document


def _bounded_markdown_lines(markdown: str) -> Iterable[str]:
    with io.StringIO(markdown, newline=None) as stream:
        while buffered_line := stream.readline(MAX_TEXT_LINE_CHARS + 2):
            raw_line = buffered_line.rstrip("\r\n")
            if len(raw_line) > MAX_TEXT_LINE_CHARS:
                raise ValidationError(
                    "AnyDoc output contains a line that is too long.",
                    error_code="knowledge_anydoc_output_limit",
                )
            yield raw_line


def _image_docling_document(path: Path):
    from docling_core.types.doc import DoclingDocument

    document = DoclingDocument(name=path.stem)
    document.add_picture()
    return document


def _append_paddle_ocr_pages(
    document: Any,
    *,
    pdf_path: Path,
    page_indexes: list[int],
    work_dir: Path,
    ocr_service: PaddleOcrService,
) -> OcrBatchResult:
    import pypdfium2

    succeeded_pages: list[int] = []
    unavailable_pages: list[int] = []
    payload_hashes: list[tuple[int, str]] = []
    item_count = 0
    pdf = pypdfium2.PdfDocument(pdf_path)
    try:
        for page_index in page_indexes:
            page = pdf[page_index]
            try:
                image_path = work_dir / f"ocr-page-{page_index + 1}.png"
                page.render(scale=2).to_pil().save(image_path)
            finally:
                page.close()
            output_path = work_dir / f"ocr-page-{page_index + 1}.json"
            payload = _recognize_projection(
                ocr_service,
                image_path,
                output_path=output_path,
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
                    bounded_json_sha256(
                        payload,
                        label="OCR result",
                        max_bytes=MAX_OCR_RESULT_BYTES,
                    ),
                )
            )
    finally:
        pdf.close()
    return OcrBatchResult(
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
        regions = payload.get("regions")
        if isinstance(regions, list):
            for region in regions:
                if not isinstance(region, dict):
                    continue
                matches.append(
                    (
                        str(region.get("text", "")),
                        _polygon_bbox(region.get("polygon")),
                    )
                )
            return matches
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
