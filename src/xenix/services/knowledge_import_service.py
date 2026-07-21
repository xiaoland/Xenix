from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from charset_normalizer import from_bytes
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from ..config import AppPaths
from ..exceptions import ValidationError
from .artifact_service import ArtifactService, RegisterArtifactInput
from .knowledge_content_store import KnowledgeContentStore
from .knowledge_service import KnowledgeService, KnowledgeUnitInput
from .paddle_ocr_service import PaddleOcrService
from .storage.models import ArtifactKind, KnowledgeImportRow, generate_id, utc_now

SUPPORTED_KNOWLEDGE_SUFFIXES = frozenset({".txt", ".docx", ".doc", ".pptx", ".ppt", ".pdf"})


@dataclass(frozen=True)
class FileProbeResult:
    source_path: Path
    source_format: str
    needs_normalization: bool


@dataclass(frozen=True)
class KnowledgeImportResult:
    import_id: str
    document_id: str
    source_artifact_id: str | None
    source_sha256: str
    canonical_path: str | None
    reused_existing: bool


@dataclass(frozen=True)
class KnowledgeImportView:
    import_id: str
    file_name: str
    source_format: str
    status: str
    document_id: str | None
    reused_existing: bool
    error_summary: str | None


class FileProbe:
    def probe(self, path: Path) -> FileProbeResult:
        source = path.expanduser().resolve()
        if not source.is_file():
            raise ValidationError("Knowledge source must be an existing local file.")
        suffix = source.suffix.casefold()
        if suffix not in SUPPORTED_KNOWLEDGE_SUFFIXES:
            raise ValidationError("Supported Knowledge formats are TXT, DOCX, DOC, PPTX, PPT, and PDF.")
        header = source.read_bytes()[:16]
        if suffix == ".pdf" and not header.startswith(b"%PDF-"):
            raise ValidationError("The selected .pdf file does not have a PDF signature.")
        if suffix in {".doc", ".ppt"} and not header.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValidationError(f"The selected {suffix} file is not a legacy Microsoft Office document.")
        if suffix in {".docx", ".pptx"}:
            _verify_ooxml(source, suffix)
        if suffix == ".txt" and b"\x00" in header:
            raise ValidationError("The selected TXT file appears to be binary.")
        return FileProbeResult(
            source_path=source,
            source_format=suffix.lstrip("."),
            needs_normalization=suffix in {".doc", ".ppt"},
        )


class FormatNormalizer:
    def __init__(self, executable: Path | None = None) -> None:
        self._executable = executable

    def normalize(self, probe: FileProbeResult, *, work_dir: Path) -> Path:
        if not probe.needs_normalization:
            return probe.source_path
        executable = self._executable or _find_libreoffice()
        if executable is None:
            raise ValidationError(
                "Importing legacy DOC/PPT requires LibreOffice. Install LibreOffice and retry."
            )
        target_suffix = ".docx" if probe.source_format == "doc" else ".pptx"
        filter_name = "docx:Office Open XML Text" if target_suffix == ".docx" else "pptx:Impress MS PowerPoint 2007 XML"
        profile = work_dir / "libreoffice-profile"
        local_source = work_dir / f"source.{probe.source_format}"
        shutil.copyfile(probe.source_path, local_source)
        command = [
            str(executable),
            "--headless",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to",
            filter_name,
            "--outdir",
            str(work_dir),
            str(local_source),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        output = work_dir / f"source{target_suffix}"
        if completed.returncode != 0 or not output.is_file():
            raise ValidationError("LibreOffice could not normalize the legacy Office document.")
        _verify_ooxml(output, target_suffix)
        return output


class ParserRouter:
    def __init__(self, ocr_service: PaddleOcrService | None = None) -> None:
        self._ocr = ocr_service

    def parse(self, path: Path, *, source_format: str, work_dir: Path):
        if source_format == "txt":
            return _plain_text_docling_document(path)
        document = _docling_convert(path, source_format=source_format)
        if source_format == "pdf":
            missing_pages = _pdf_pages_needing_ocr(path)
            if missing_pages and self._ocr is None:
                raise ValidationError(
                    "This PDF contains scanned pages. Install local PaddleOCR and retry."
                )
            if missing_pages:
                _append_paddle_ocr_pages(
                    document,
                    pdf_path=path,
                    page_indexes=missing_pages,
                    work_dir=work_dir,
                    ocr_service=self._ocr,
                )
        return document


class Canonicalizer:
    def canonical_bytes(
        self,
        document: Any,
        *,
        generation_id: str,
        source_sha256: str,
        source_format: str,
    ) -> bytes:
        payload = {
            "envelope": {
                "schema_version": 1,
                "canonical_generation_id": generation_id,
                "source_sha256": source_sha256,
                "source_format": source_format,
                "content_ir": "DoclingDocument",
            },
            "docling_document": _sanitize_docling_payload(document.export_to_dict()),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def knowledge_units(self, document: Any) -> list[KnowledgeUnitInput]:
        units: list[KnowledgeUnitInput] = []
        for item, level in document.iterate_items():
            text = str(getattr(item, "text", "") or "").strip()
            if not text and hasattr(item, "export_to_markdown"):
                try:
                    text = str(item.export_to_markdown(doc=document)).strip()
                except Exception:
                    text = ""
            if not text:
                continue
            locator: dict[str, Any] = {
                "self_ref": str(getattr(item, "self_ref", "")),
                "level": level,
            }
            provenance = list(getattr(item, "prov", ()) or ())
            if provenance:
                page_no = getattr(provenance[0], "page_no", None)
                if page_no is not None:
                    locator["page"] = int(page_no)
            units.append(KnowledgeUnitInput(text=text, locator=locator))
        if not units:
            fallback = str(document.export_to_text()).strip()
            if fallback:
                units.append(KnowledgeUnitInput(text=fallback, locator={"document": True}))
        return units


class KnowledgeImportService:
    """Synchronous public import facade; UI dispatches calls off the GUI thread."""

    def __init__(
        self,
        *,
        paths: AppPaths,
        session_factory: sessionmaker,
        knowledge_service: KnowledgeService,
        artifact_service: ArtifactService,
        normalizer: FormatNormalizer | None = None,
        ocr_service: PaddleOcrService | None = None,
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._knowledge = knowledge_service
        self._artifacts = artifact_service
        self._store = KnowledgeContentStore(paths)
        self._probe = FileProbe()
        self._normalizer = normalizer or FormatNormalizer()
        self._parser = ParserRouter(ocr_service)
        self._canonicalizer = Canonicalizer()
        self._import_lock = threading.Lock()

    def import_file(self, source_path: Path) -> KnowledgeImportResult:
        with self._import_lock:
            return self._import_file_serialized(source_path)

    def _import_file_serialized(self, source_path: Path) -> KnowledgeImportResult:
        probe = self._probe.probe(source_path)
        row = self._create_import(probe)
        try:
            snapshot = self._store.snapshot_source(probe.source_path)
            existing = self._knowledge.get_document_by_source_sha256(snapshot.sha256)
            if existing is not None:
                self._finish_import(
                    row.id,
                    status="succeeded",
                    document_id=existing.id,
                    source_artifact_id=existing.source_artifact_id,
                    source_sha256=snapshot.sha256,
                    canonical_path=existing.canonical_path,
                    reused_existing=True,
                )
                return KnowledgeImportResult(
                    import_id=row.id,
                    document_id=existing.id,
                    source_artifact_id=existing.source_artifact_id,
                    source_sha256=snapshot.sha256,
                    canonical_path=existing.canonical_path,
                    reused_existing=True,
                )

            with tempfile.TemporaryDirectory(prefix="xenix-knowledge-import-") as temp:
                normalized = self._normalizer.normalize(probe, work_dir=Path(temp))
                routed_format = normalized.suffix.casefold().lstrip(".")
                document_ir = self._parser.parse(
                    normalized,
                    source_format=routed_format,
                    work_dir=Path(temp),
                )
                units = self._canonicalizer.knowledge_units(document_ir)
                if not units:
                    raise ValidationError("The document did not contain searchable text.")
                generation_id = generate_id()
                canonical_bytes = self._canonicalizer.canonical_bytes(
                    document_ir,
                    generation_id=generation_id,
                    source_sha256=snapshot.sha256,
                    source_format=probe.source_format,
                )
                canonical_path = self._store.write_canonical(snapshot.sha256, canonical_bytes)

            source_artifact = self._artifacts.register_artifact(
                RegisterArtifactInput(
                    title=probe.source_path.name,
                    absolute_path=str(snapshot.path),
                    kind=ArtifactKind.FILE,
                    mime_type=mimetypes.guess_type(probe.source_path.name)[0],
                    metadata_payload={
                        "knowledge_source_sha256": snapshot.sha256,
                        "original_file_name": probe.source_path.name,
                    },
                )
            )
            document = self._knowledge.index_document(
                title=probe.source_path.stem,
                units=units,
                source_artifact_id=source_artifact.id,
                canonical_generation_id=generation_id,
                source_sha256=snapshot.sha256,
                source_format=probe.source_format,
                canonical_path=str(canonical_path),
            )
            self._finish_import(
                row.id,
                status="succeeded",
                document_id=document.id,
                source_artifact_id=source_artifact.id,
                source_sha256=snapshot.sha256,
                canonical_path=str(canonical_path),
            )
            return KnowledgeImportResult(
                import_id=row.id,
                document_id=document.id,
                source_artifact_id=source_artifact.id,
                source_sha256=snapshot.sha256,
                canonical_path=str(canonical_path),
                reused_existing=False,
            )
        except Exception as exc:
            self._finish_import(
                row.id,
                status="failed",
                error_code=type(exc).__name__,
                error_summary=str(exc)[:1000],
            )
            raise

    def list_imports(self) -> list[KnowledgeImportView]:
        with self._session_factory() as session:
            rows = list(
                session.exec(
                    select(KnowledgeImportRow).order_by(KnowledgeImportRow.created_at.desc())
                )
            )
        return [
            KnowledgeImportView(
                import_id=row.id,
                file_name=row.original_file_name,
                source_format=row.source_format,
                status=row.status,
                document_id=row.document_id,
                reused_existing=row.reused_existing,
                error_summary=row.error_summary,
            )
            for row in rows
        ]

    def _create_import(self, probe: FileProbeResult) -> KnowledgeImportRow:
        row = KnowledgeImportRow(
            original_file_name=probe.source_path.name,
            source_format=probe.source_format,
            status="running",
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def _finish_import(self, import_id: str, *, status: str, **values: Any) -> None:
        with self._session_factory() as session:
            row = session.get(KnowledgeImportRow, import_id)
            if row is None:
                return
            row.status = status
            row.updated_at = utc_now()
            for key, value in values.items():
                setattr(row, key, value)
            session.add(row)
            session.commit()


def _plain_text_docling_document(path: Path):
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    payload = path.read_bytes()
    match = from_bytes(payload).best()
    if match is None:
        raise ValidationError("TXT encoding could not be detected.")
    text = str(match).replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    document = DoclingDocument(name=path.stem)
    for paragraph in (part.strip() for part in text.split("\n\n")):
        if paragraph:
            document.add_text(DocItemLabel.TEXT, paragraph)
    return document


def _docling_convert(path: Path, *, source_format: str):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = None
    if source_format == "pdf":
        options = {InputFormat.PDF: PdfFormatOption(pipeline_options=PdfPipelineOptions(do_ocr=False))}
    result = DocumentConverter(format_options=options).convert(path)
    status = str(getattr(result.status, "value", result.status)).lower()
    if status not in {"success", "partial_success"}:
        raise ValidationError(f"Docling could not parse the {source_format.upper()} document.")
    return result.document


def _verify_ooxml(path: Path, suffix: str) -> None:
    required = "word/document.xml" if suffix == ".docx" else "ppt/presentation.xml"
    try:
        with ZipFile(path) as package:
            if required not in package.namelist():
                raise ValidationError(f"The selected {suffix} file has the wrong Office package type.")
    except BadZipFile as exc:
        raise ValidationError(f"The selected {suffix} file is not a valid Office package.") from exc


def _find_libreoffice() -> Path | None:
    command = shutil.which("soffice") or shutil.which("libreoffice")
    candidates = [
        Path(command) if command else None,
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    return next((path for path in candidates if path is not None and path.is_file()), None)


def _sanitize_docling_payload(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_docling_payload(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_docling_payload(item, key=key) for item in value]
    if isinstance(value, str) and key in {"path", "uri"}:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate.name
    return value


def _pdf_pages_needing_ocr(path: Path) -> list[int]:
    import pypdfium2

    document = pypdfium2.PdfDocument(path)
    try:
        missing: list[int] = []
        for index in range(len(document)):
            page = document[index]
            try:
                text_page = page.get_textpage()
                text = text_page.get_text_range().strip()
            finally:
                page.close()
            if len(text) < 8:
                missing.append(index)
        return missing
    finally:
        document.close()


def _append_paddle_ocr_pages(
    document: Any,
    *,
    pdf_path: Path,
    page_indexes: list[int],
    work_dir: Path,
    ocr_service: PaddleOcrService,
) -> None:
    import pypdfium2
    from docling_core.types.doc import BoundingBox, DocItemLabel, ProvenanceItem

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
            payload = ocr_service.recognize(image_path, output_path=output_path)
            for text, bbox in _paddle_text_boxes(payload):
                if not text.strip():
                    continue
                document.add_text(
                    DocItemLabel.TEXT,
                    text.strip(),
                    prov=ProvenanceItem(
                        page_no=page_index + 1,
                        bbox=BoundingBox(l=bbox[0], t=bbox[1], r=bbox[2], b=bbox[3]),
                        charspan=(0, len(text.strip())),
                    ),
                )
    finally:
        pdf.close()


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
