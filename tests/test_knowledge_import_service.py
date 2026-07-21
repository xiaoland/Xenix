import json
import subprocess
from pathlib import Path

import zstandard
import pytest
from docx import Document
from pptx import Presentation
from PIL import Image, ImageDraw

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.artifact_service import ArtifactService
from xenix.services.knowledge_import_service import KnowledgeImportService, _find_libreoffice
from xenix.services.knowledge_service import KnowledgeService
from xenix.services.storage import StorageBootstrapService


def _service(monkeypatch, tmp_path: Path, *, ocr_service=None) -> tuple[KnowledgeImportService, KnowledgeService]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    knowledge = KnowledgeService(storage.session_factory)
    return (
        KnowledgeImportService(
            paths=paths,
            session_factory=storage.session_factory,
            knowledge_service=knowledge,
            artifact_service=ArtifactService(storage.session_factory),
            ocr_service=ocr_service,
        ),
        knowledge,
    )


def test_txt_import_publishes_docling_ir_cas_and_searchable_units(monkeypatch, tmp_path: Path) -> None:
    importer, knowledge = _service(monkeypatch, tmp_path)
    source = tmp_path / "规则.txt"
    source.write_text("华东雨季的雨具目标库存按三周平均销量计算。", encoding="utf-8-sig")

    result = importer.import_file(source)

    assert result.reused_existing is False
    assert knowledge.lookup("雨具三周销量")[0].document_id == result.document_id
    canonical_path = Path(result.canonical_path or "")
    payload = json.loads(zstandard.ZstdDecompressor().decompress(canonical_path.read_bytes()))
    assert payload["envelope"]["content_ir"] == "DoclingDocument"
    assert payload["envelope"]["source_format"] == "txt"
    assert str(source.resolve()) not in json.dumps(payload, ensure_ascii=False)


def test_same_sha_reuses_document_within_global_library(monkeypatch, tmp_path: Path) -> None:
    importer, _knowledge = _service(monkeypatch, tmp_path)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("相同的知识内容。", encoding="utf-8")
    second.write_bytes(first.read_bytes())

    initial = importer.import_file(first)
    repeated = importer.import_file(second)

    assert repeated.reused_existing is True
    assert repeated.document_id == initial.document_id
    assert repeated.source_sha256 == initial.source_sha256


def test_docx_and_pptx_use_docling_and_become_searchable(monkeypatch, tmp_path: Path) -> None:
    importer, knowledge = _service(monkeypatch, tmp_path)
    docx_path = tmp_path / "经营规则.docx"
    docx = Document()
    docx.add_heading("渠道规则", level=1)
    docx.add_paragraph("会员日活动必须保持毛利率不低于百分之十八。")
    docx.save(docx_path)
    pptx_path = tmp_path / "复盘.pptx"
    pptx = Presentation()
    slide = pptx.slides.add_slide(pptx.slide_layouts[1])
    slide.shapes.title.text = "促销复盘"
    slide.placeholders[1].text = "直播折扣的退货率高于百分之九。"
    pptx.save(pptx_path)

    docx_result = importer.import_file(docx_path)
    pptx_result = importer.import_file(pptx_path)

    assert knowledge.lookup("会员日毛利率")[0].document_id == docx_result.document_id
    assert knowledge.lookup("直播折扣退货率")[0].document_id == pptx_result.document_id


def test_born_digital_pdf_uses_docling_without_builtin_ocr(monkeypatch, tmp_path: Path) -> None:
    importer, knowledge = _service(monkeypatch, tmp_path)
    pdf_path = tmp_path / "policy.pdf"
    _write_simple_pdf(pdf_path, "Rainy season inventory uses three week demand")

    result = importer.import_file(pdf_path)

    assert knowledge.lookup("three week demand")[0].document_id == result.document_id


def test_scanned_pdf_routes_missing_text_page_to_local_paddle_ocr(monkeypatch, tmp_path: Path) -> None:
    class FakeLocalPaddleOcr:
        def recognize(self, image_path: Path, *, output_path: Path, timeout: int = 300) -> dict:
            assert image_path.suffix == ".png"
            return {
                "protocol": 1,
                "pages": [
                    {
                        "res": {
                            "rec_texts": ["扫描页雨具补货使用三周需求"],
                            "rec_polys": [[[10, 10], [300, 10], [300, 40], [10, 40]]],
                        }
                    }
                ],
            }

    importer, knowledge = _service(monkeypatch, tmp_path, ocr_service=FakeLocalPaddleOcr())
    pdf_path = tmp_path / "scanned.pdf"
    image = Image.new("RGB", (600, 300), "white")
    ImageDraw.Draw(image).text((40, 100), "scanned policy", fill="black")
    image.save(pdf_path, "PDF")

    result = importer.import_file(pdf_path)

    match = knowledge.lookup("扫描页雨具补货")[0]
    assert match.document_id == result.document_id
    assert match.locator["page"] == 1


@pytest.mark.skipif(_find_libreoffice() is None, reason="LibreOffice is not installed")
def test_legacy_doc_and_ppt_normalize_through_libreoffice_then_docling(monkeypatch, tmp_path: Path) -> None:
    importer, knowledge = _service(monkeypatch, tmp_path)
    modern_doc = tmp_path / "legacy-rule.docx"
    docx = Document()
    docx.add_paragraph("旧版文档中的渠道库存规则")
    docx.save(modern_doc)
    modern_ppt = tmp_path / "legacy-review.pptx"
    pptx = Presentation()
    slide = pptx.slides.add_slide(pptx.slide_layouts[1])
    slide.shapes.title.text = "旧版演示文稿"
    slide.placeholders[1].text = "促销复盘要求检查退货率"
    pptx.save(modern_ppt)
    executable = _find_libreoffice()
    assert executable is not None
    for path, conversion_filter in (
        (modern_doc, "doc:MS Word 97"),
        (modern_ppt, "ppt:MS PowerPoint 97"),
    ):
        completed = subprocess.run(
            [str(executable), "--headless", "--convert-to", conversion_filter, "--outdir", str(tmp_path), str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert completed.returncode == 0

    doc_result = importer.import_file(tmp_path / "legacy-rule.doc")
    ppt_result = importer.import_file(tmp_path / "legacy-review.ppt")

    assert knowledge.lookup("渠道库存规则")[0].document_id == doc_result.document_id
    assert knowledge.lookup("促销复盘退货率")[0].document_id == ppt_result.document_id


def _write_simple_pdf(path: Path, text: str) -> None:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode())
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)
