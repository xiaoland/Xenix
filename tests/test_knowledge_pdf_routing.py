from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pikepdf
from PIL import Image

from xenix.services.knowledge_pdf import PdfPageTextState, classify_pdf_page_text, probe_pdf_pages
from xenix.services.knowledge_pipeline import NormalizedSource, ParserRouter


def test_generated_pdf_corpus_labels_born_digital_scanned_mixed_and_ocr_layer(
    tmp_path: Path,
) -> None:
    born_digital = tmp_path / "born-digital.pdf"
    with pikepdf.Pdf.new() as pdf:
        _add_text_page(pdf, "Born digital business policy with credible text 12345")
        pdf.save(born_digital)

    scanned = tmp_path / "scanned.pdf"
    with pikepdf.Pdf.new() as pdf:
        _add_image_page(pdf)
        pdf.save(scanned)

    mixed = tmp_path / "mixed.pdf"
    with pikepdf.Pdf.new() as pdf:
        _add_text_page(pdf, "Mixed PDF native page with credible text 12345")
        _add_image_page(pdf)
        pdf.save(mixed)

    suspect_layer = tmp_path / "suspect-ocr-layer.pdf"
    with pikepdf.Pdf.new() as pdf:
        _add_image_page(pdf, text="Sparse OCR layer 123")
        pdf.save(suspect_layer)

    assert [item.text_state for item in probe_pdf_pages(born_digital)] == [
        PdfPageTextState.CREDIBLE
    ]
    assert [item.text_state for item in probe_pdf_pages(scanned)] == [
        PdfPageTextState.ABSENT
    ]
    assert [item.text_state for item in probe_pdf_pages(mixed)] == [
        PdfPageTextState.CREDIBLE,
        PdfPageTextState.ABSENT,
    ]
    suspect = probe_pdf_pages(suspect_layer)[0]
    assert suspect.text_state is PdfPageTextState.SUSPECT
    assert "image_dominant_sparse_text_layer" in suspect.reasons

    plan = ParserRouter().route(
        NormalizedSource(mixed, "pdf", "pdf", {"operation": "identity"}),
        ocr_ready=True,
    )
    assert [unit.route_id for unit in plan.units] == [
        "docling-pdf-native",
        "paddleocr-page",
    ]


def test_broken_font_evidence_is_not_mislabelled_as_credible_text() -> None:
    state, reasons = classify_pdf_page_text(
        extracted_characters=120,
        alphanumeric_characters=100,
        suspicious_characters=0,
        image_coverage=0.0,
        unembedded_nonstandard_fonts=1,
    )

    assert state is PdfPageTextState.SUSPECT
    assert reasons == ("unembedded_nonstandard_font",)


def _add_text_page(pdf: pikepdf.Pdf, text: str) -> None:
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(
            F1=pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
            )
        )
    )
    encoded = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    page.Contents = pikepdf.Stream(
        pdf,
        f"BT /F1 12 Tf 72 720 Td ({encoded}) Tj ET".encode("ascii"),
    )


def _add_image_page(pdf: pikepdf.Pdf, *, text: str | None = None) -> None:
    width, height = 612, 792
    image_buffer = BytesIO()
    Image.new("RGB", (width, height), "white").save(
        image_buffer,
        format="JPEG",
        quality=80,
    )
    image = pikepdf.Stream(pdf, image_buffer.getvalue())
    image.Type = pikepdf.Name.XObject
    image.Subtype = pikepdf.Name.Image
    image.Width = width
    image.Height = height
    image.ColorSpace = pikepdf.Name.DeviceRGB
    image.BitsPerComponent = 8
    image.Filter = pikepdf.Name.DCTDecode

    page = pdf.add_blank_page(page_size=(width, height))
    resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im1=image))
    commands = f"q {width} 0 0 {height} 0 0 cm /Im1 Do Q"
    if text is not None:
        resources.Font = pikepdf.Dictionary(
            F1=pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
            )
        )
        commands += f" BT /F1 10 Tf 20 20 Td ({text}) Tj ET"
    page.Resources = resources
    page.Contents = pikepdf.Stream(pdf, commands.encode("ascii"))
