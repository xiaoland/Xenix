from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pikepdf
import pypdfium2

from ..config import AppPaths, ensure_app_dirs, package_root
from .artifact_service import ArtifactService
from .knowledge_content_store import KnowledgeContentStore
from .knowledge_import_service import KnowledgeImportService
from .knowledge_import_worker import read_worker_result
from .knowledge_vector_store import KnowledgeVectorRecord, LanceKnowledgeVectorStore
from .storage import StorageBootstrapService
from .storage.layout import knowledge_import_result_path


def run_knowledge_packaged_smoke(paths: AppPaths) -> None:
    """Exercise Knowledge native/data boundaries from the running executable."""

    # Keep heavy document runtimes operation-scoped. Importing Docling mutates the
    # process-wide ElementTree namespace registry, which must not affect unrelated
    # SVG generation merely because this smoke module was discovered.
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc import DocItemLabel, DoclingDocument
    from docx import Document

    with TemporaryDirectory(prefix="xenix-knowledge-smoke-", dir=paths.temp) as temporary:
        root = Path(temporary)
        smoke_paths = ensure_app_dirs(
            AppPaths(
                home=root,
                config=root / "config",
                logs=root / "logs",
                cache=root / "cache",
                state=root / "state",
                temp=root / "temp",
                artifacts=root / "artifacts",
                resources=paths.resources,
            )
        )
        pdf_path = root / "knowledge-smoke.pdf"
        _write_simple_pdf(pdf_path, "Knowledge packaged smoke")

        with pikepdf.Pdf.open(pdf_path) as document:
            if len(document.pages) != 1:
                raise RuntimeError("pikepdf packaged Knowledge smoke failed.")

        pdfium_document = pypdfium2.PdfDocument(pdf_path)
        try:
            page = pdfium_document[0]
            try:
                image = page.render(scale=0.25).to_pil()
                if image.width < 1 or image.height < 1:
                    raise RuntimeError("PDFium packaged Knowledge render failed.")
            finally:
                page.close()
        finally:
            pdfium_document.close()

        docling_path = root / "knowledge-smoke.docling.json"
        seed_document = DoclingDocument(name="knowledge-packaged-smoke")
        seed_document.add_text(
            label=DocItemLabel.PARAGRAPH,
            text="Knowledge packaged smoke",
        )
        seed_document.save_as_json(docling_path)
        docling_document = DocumentConverter(
            allowed_formats=[InputFormat.JSON_DOCLING]
        ).convert(docling_path).document
        if "Knowledge packaged smoke" not in docling_document.export_to_text():
            raise RuntimeError("Docling packaged Knowledge IR parse failed.")

        worker_input = root / "knowledge-worker-smoke.docx"
        worker_document = Document()
        worker_document.add_paragraph("Knowledge frozen worker smoke")
        worker_document.save(worker_input)
        worker_output = root / "knowledge-worker-smoke.json"
        worker_environment = dict(os.environ)
        if getattr(sys, "frozen", False):
            worker_command = [
                sys.executable,
                "--knowledge-docling-worker",
                "docx",
                str(worker_input),
                str(worker_output),
            ]
        else:
            source_root = str(Path(__file__).resolve().parents[2])
            existing_pythonpath = worker_environment.get("PYTHONPATH")
            worker_environment["PYTHONPATH"] = (
                source_root
                if not existing_pythonpath
                else os.pathsep.join([source_root, existing_pythonpath])
            )
            worker_command = [
                sys.executable,
                "-m",
                "xenix.services.knowledge_docling_worker",
                "docx",
                str(worker_input),
                str(worker_output),
            ]
        completed = subprocess.run(
            worker_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
            check=False,
            env=worker_environment,
        )
        if completed.returncode != 0 or not worker_output.is_file():
            raise RuntimeError("Docling packaged worker smoke failed.")
        if worker_output.stat().st_size > 8 * 1024 * 1024:
            raise RuntimeError("Docling packaged worker output is unbounded.")
        worker_result = DoclingDocument.model_validate_json(
            worker_output.read_text(encoding="utf-8")
        )
        if "Knowledge frozen worker smoke" not in worker_result.export_to_text():
            raise RuntimeError("Docling packaged worker round-trip failed.")

        content_store = KnowledgeContentStore(smoke_paths)
        stored = content_store.write_canonical_bundle(
            envelope={"canonical_generation_id": "packaged-smoke"},
            docling_document=docling_document.export_to_dict(),
        )
        reopened = content_store.read_canonical_bundle(
            stored.relative_path,
            expected_envelope_sha256=stored.envelope_sha256,
            expected_content_ir_sha256=stored.content_ir_sha256,
        )
        if reopened.envelope.get("canonical_generation_id") != "packaged-smoke":
            raise RuntimeError("Zstandard canonical packaged Knowledge smoke failed.")

        import_source = root / "knowledge-import-worker-smoke.txt"
        import_source.write_text("Knowledge import spawned worker smoke", encoding="utf-8")
        storage = StorageBootstrapService().initialize(smoke_paths)
        importer = KnowledgeImportService(
            paths=smoke_paths,
            session_factory=storage.session_factory,
            artifact_service=ArtifactService(storage.session_factory),
        )
        try:
            imported = importer.import_file(import_source, timeout=90)
            import_worker_result = read_worker_result(
                knowledge_import_result_path(smoke_paths, imported.import_id)
            )
            if import_worker_result.worker_pid == os.getpid():
                raise RuntimeError("Knowledge import did not use a spawned worker.")
        finally:
            importer.shutdown()
            storage.engine.dispose()

        vector_store = LanceKnowledgeVectorStore(smoke_paths)
        relative_path = vector_store.write_generation(
            generation_id="packaged-smoke",
            records=(
                KnowledgeVectorRecord("unit-a", (1.0, 0.0, 0.0)),
                KnowledgeVectorRecord("unit-b", (0.0, 1.0, 0.0)),
            ),
            dimensions=3,
            corpus_fingerprint="corpus-smoke",
            profile_fingerprint="profile-smoke",
        )
        if vector_store.search(relative_path, query_vector=(0.9, 0.1, 0.0), limit=1) != ["unit-a"]:
            raise RuntimeError("LanceDB packaged Knowledge search failed.")

        worker = package_root() / "resources" / "knowledge_ocr" / "paddle_worker.py"
        if not worker.is_file():
            raise RuntimeError("Packaged PaddleOCR worker resource is missing.")
        compile(worker.read_text(encoding="utf-8"), str(worker), "exec")

    marker = paths.state / "knowledge-smoke.json"
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "docling_ir": True,
                "docling_worker": True,
                "pdfium_render": True,
                "pikepdf": True,
                "canonical_zstd": True,
                "import_worker_spawn": True,
                "lancedb": True,
                "paddle_worker_resource": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_simple_pdf(path: Path, text: str) -> None:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    )
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(payload)
