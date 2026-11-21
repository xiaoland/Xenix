"""Request OCR projections and add their text and page provenance to Docling."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...exceptions import ValidationError
from ..paddle_ocr_service import MAX_PROTOCOL_MESSAGE_BYTES, PaddleOcrService
from .provenance import _bounded_json_sha256


MAX_OCR_RESULT_BYTES = MAX_PROTOCOL_MESSAGE_BYTES
_OCR_PROJECTION_FAILURES = (
    ValidationError,
    OSError,
    TimeoutError,
    subprocess.SubprocessError,
)


@dataclass(frozen=True)
class _OcrBatchResult:
    succeeded_pages: tuple[int, ...]
    unavailable_pages: tuple[int, ...]
    item_count: int
    payload_hashes: tuple[tuple[int, str], ...]


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


def _append_paddle_ocr_pages(
    document: Any,
    *,
    pdf_path: Path,
    page_indexes: list[int],
    work_dir: Path,
    ocr_service: PaddleOcrService,
) -> _OcrBatchResult:
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
                    _bounded_json_sha256(
                        payload,
                        label="OCR result",
                        max_bytes=MAX_OCR_RESULT_BYTES,
                    ),
                )
            )
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
