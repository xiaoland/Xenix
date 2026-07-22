from __future__ import annotations

import json
import time
from pathlib import Path

import msoffcrypto
import pikepdf
import pytest
from docx import Document
from PIL import Image
from sqlmodel import select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService
from xenix.services.knowledge_content_store import KnowledgeContentStore
from xenix.services.knowledge_derivation_service import KnowledgeDerivationService
from xenix.services.knowledge_import_service import KnowledgeImportService
from xenix.services.knowledge_pipeline import FormatNormalizer
from xenix.services.knowledge_service import MAX_KNOWLEDGE_UNIT_CHARS, KnowledgeService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    ArtifactRow,
    KnowledgeCanonicalGenerationRow,
    KnowledgeDerivationRow,
    KnowledgeDocumentRow,
    KnowledgeImportRow,
    KnowledgeUnitRow,
)


def _runtime(
    monkeypatch,
    tmp_path: Path,
    *,
    ocr_service=None,
    retrieval_ready_notifier=None,
    start_worker=True,
):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    derivation = KnowledgeDerivationService(
        paths=paths,
        session_factory=storage.session_factory,
        retrieval_ready_notifier=retrieval_ready_notifier,
        start_worker=start_worker,
    )
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        normalizer=FormatNormalizer(),
        ocr_service=ocr_service,
        canonical_ready_notifier=derivation.enqueue_generation,
        start_worker=start_worker,
    )
    return paths, storage, importer, derivation, KnowledgeService(storage.session_factory)


def test_admission_is_durable_before_snapshot_and_reopen_requires_source_reselection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, first, first_derivation, _knowledge = _runtime(
        monkeypatch,
        tmp_path,
        start_worker=False,
    )
    source = tmp_path / "rule.txt"
    source.write_text("雨具安全库存按三周平均需求计算。", encoding="utf-8")

    receipt = first.enqueue_file(source)
    source.unlink()
    first.shutdown()
    first_derivation.shutdown()
    reopened = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        start_worker=False,
    )
    try:
        view = {item.import_id: item for item in reopened.list_imports()}[receipt.import_id]
        assert view.status == "needs_attention"
        assert view.phase == "source_reselection_required"
        assert view.error_code == "knowledge_source_reselection_required"
        assert view.retryable is True
        with storage.session_factory() as session:
            row = session.get(KnowledgeImportRow, receipt.import_id)
            assert row is not None
            persisted = json.dumps(row.model_dump(mode="json"), ensure_ascii=False)
        assert str(source.resolve()) not in persisted
    finally:
        reopened.shutdown()


@pytest.mark.parametrize("mutation", ["tamper_bytes", "replace_artifact_path"])
def test_recovery_rejects_a_source_snapshot_that_no_longer_matches_its_cas_identity(
    monkeypatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    paths, storage, first, first_derivation, _knowledge = _runtime(
        monkeypatch,
        tmp_path,
        start_worker=False,
    )
    source = tmp_path / "rule.txt"
    source.write_text("原始渠道库存规则", encoding="utf-8")
    receipt = first.enqueue_file(source)
    assert first._prepare_source_snapshot(receipt.import_id) is not None
    with storage.session_factory() as session:
        import_row = session.get(KnowledgeImportRow, receipt.import_id)
        assert import_row is not None and import_row.source_artifact_id
        artifact = session.get(ArtifactRow, import_row.source_artifact_id)
        assert artifact is not None
        snapshot_path = Path(artifact.absolute_path)
        if mutation == "tamper_bytes":
            snapshot_path.write_text("被替换的内容", encoding="utf-8")
        else:
            replacement = tmp_path / "same-bytes.txt"
            replacement.write_bytes(source.read_bytes())
            artifact.absolute_path = str(replacement)
            session.add(artifact)
            session.commit()
    first.shutdown()
    first_derivation.shutdown()

    reopened = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        start_worker=False,
    )
    try:
        view = {item.import_id: item for item in reopened.list_imports()}[receipt.import_id]
        assert view.status == "needs_attention"
        assert view.phase == "source_reselection_required"
        assert view.error_code == "knowledge_source_reselection_required"
        assert view.retryable is True
    finally:
        reopened.shutdown()


def test_queue_cancel_and_retry_create_distinct_attempts(monkeypatch, tmp_path: Path) -> None:
    _paths, _storage, importer, derivation, _knowledge = _runtime(
        monkeypatch,
        tmp_path,
        start_worker=False,
    )
    source = tmp_path / "rule.txt"
    source.write_text("渠道库存规则", encoding="utf-8")
    receipt = importer.enqueue_file(source)

    assert importer.cancel_import(receipt.import_id) is True
    retry = importer.retry_import(receipt.import_id, source_path=source)
    views = {item.import_id: item for item in importer.list_imports()}

    assert views[receipt.import_id].status == "cancelled"
    assert views[retry.import_id].attempt_number == 2
    assert retry.import_id != receipt.import_id
    importer.shutdown()
    derivation.shutdown()


def test_startup_reclaims_bundle_published_before_database_commit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, importer, derivation, _knowledge = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "rule.txt"
    source.write_text("崩溃前已冻结但尚未提交的知识。", encoding="utf-8")
    published: list[Path] = []
    write_bundle = importer._store.write_canonical_bundle

    class InjectedCrash(Exception):
        pass

    def publish_then_crash(**kwargs):
        stored = write_bundle(**kwargs)
        published.append(stored.path)
        raise InjectedCrash

    monkeypatch.setattr(importer._store, "write_canonical_bundle", publish_then_crash)
    receipt = importer.enqueue_file(source)
    with pytest.raises(ValidationError):
        importer.wait_for_import(receipt.import_id, timeout=60)
    assert published and published[0].is_dir()
    importer.shutdown()
    derivation.shutdown()

    reopened = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        start_worker=False,
    )
    try:
        assert not published[0].exists()
        with storage.session_factory() as session:
            row = session.get(KnowledgeImportRow, receipt.import_id)
            assert row is not None and row.status == "failed"
            artifact = session.get(ArtifactRow, row.source_artifact_id)
            assert artifact is not None and Path(artifact.absolute_path).is_file()
    finally:
        reopened.shutdown()


def test_encrypted_pdf_password_is_transient_and_retryable(monkeypatch, tmp_path: Path) -> None:
    _paths, storage, importer, derivation, knowledge = _runtime(monkeypatch, tmp_path)
    clear = tmp_path / "clear.pdf"
    encrypted = tmp_path / "encrypted.pdf"
    _write_simple_pdf(clear, "Rain inventory uses three week demand")
    with pikepdf.Pdf.open(clear) as document:
        document.save(encrypted, encryption=pikepdf.Encryption(owner="owner", user="transient-pass-4821"))

    with pytest.raises(ValidationError) as error:
        importer.import_file(encrypted, timeout=60)
    assert error.value.error_code == "knowledge_password_required"
    failed = importer.list_imports()[0]
    result = importer.wait_for_import(
        importer.retry_import(failed.import_id, password="transient-pass-4821").import_id,
        timeout=60,
    )

    assert result.canonical_ready is True
    _wait_for_retrieval(knowledge, "three week demand", result.document_id)
    with storage.session_factory() as session:
        persisted = json.dumps(
            [row.model_dump(mode="json") for row in session.exec(select(KnowledgeImportRow))],
            ensure_ascii=False,
        )
    assert "transient-pass-4821" not in persisted
    assert str(encrypted.resolve()) not in persisted
    importer.shutdown()
    derivation.shutdown()


def test_encrypted_docx_decrypts_in_attempt_only(monkeypatch, tmp_path: Path) -> None:
    _paths, _storage, importer, derivation, knowledge = _runtime(monkeypatch, tmp_path)
    clear = tmp_path / "clear.docx"
    encrypted = tmp_path / "secret.docx"
    document = Document()
    document.add_paragraph("会员渠道毛利率不得低于百分之十八。")
    document.save(clear)
    with clear.open("rb") as source, encrypted.open("wb") as output:
        msoffcrypto.OfficeFile(source).encrypt("secret", output)

    with pytest.raises(ValidationError) as error:
        importer.import_file(encrypted, timeout=60)
    assert error.value.error_code == "knowledge_password_required"
    failed_id = importer.list_imports()[0].import_id
    result = importer.wait_for_import(
        importer.retry_import(failed_id, password="secret").import_id,
        timeout=120,
    )

    _wait_for_retrieval(knowledge, "会员渠道毛利率", result.document_id)
    importer.shutdown()
    derivation.shutdown()


def test_image_without_ocr_is_canonical_ready_but_not_retrieval_ready(monkeypatch, tmp_path: Path) -> None:
    paths, storage, importer, derivation, knowledge = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "field.png"
    Image.new("RGB", (120, 80), "white").save(source)

    result = importer.import_file(source, timeout=60)

    assert result.canonical_ready is True
    _wait_for_derivation_status(derivation, result.import_id, "succeeded")
    assert knowledge.lookup("field") == []
    with storage.session_factory() as session:
        generation = session.get(KnowledgeCanonicalGenerationRow, result.canonical_generation_id)
        document = session.get(KnowledgeDocumentRow, result.document_id)
    assert generation is not None and generation.warnings_payload == ["ocr_projection_unavailable"]
    assert document is not None and document.retrieval_status == "unavailable"
    bundle = KnowledgeContentStore(paths).read_canonical_bundle(generation.relative_path)
    assert bundle.envelope["projections"] == [{"kind": "ocr_text", "status": "unavailable"}]
    importer.shutdown()
    derivation.shutdown()


def test_completed_derivation_notifies_the_library_index_coordinator(
    monkeypatch,
    tmp_path: Path,
) -> None:
    notifications: list[str] = []
    _paths, _storage, importer, derivation, knowledge = _runtime(
        monkeypatch,
        tmp_path,
        retrieval_ready_notifier=notifications.append,
    )
    source = tmp_path / "rule.txt"
    source.write_text("雨季库存按三周需求计算。", encoding="utf-8")

    try:
        result = importer.import_file(source, timeout=60)
        _wait_for_retrieval(knowledge, "雨季三周需求", result.document_id)
        deadline = time.monotonic() + 10
        while not notifications and time.monotonic() < deadline:
            time.sleep(0.02)
        assert notifications == ["global"]
    finally:
        importer.shutdown()
        derivation.shutdown()


def test_png_and_jpeg_with_ocr_publish_searchable_projection(monkeypatch, tmp_path: Path) -> None:
    class FakeOcr:
        def is_ready(self) -> bool:
            return True

        def recognize(self, image_path: Path, *, output_path: Path, timeout: int = 300) -> dict:
            return {
                "protocol": 1,
                "rec_texts": ["门店陈列每周检查两次"],
                "rec_polys": [[[1, 1], [80, 1], [80, 20], [1, 20]]],
            }

    _paths, _storage, importer, derivation, knowledge = _runtime(
        monkeypatch,
        tmp_path,
        ocr_service=FakeOcr(),
    )
    for suffix, image_format in ((".png", "PNG"), (".jpg", "JPEG")):
        source = tmp_path / f"field{suffix}"
        Image.new("RGB", (120, 80), "white").save(source, image_format)
        result = importer.import_file(source, timeout=60)
        assert result.canonical_ready is True
        _wait_for_retrieval(knowledge, "门店陈列检查", result.document_id)
    importer.shutdown()
    derivation.shutdown()


def test_long_docling_item_is_published_as_bounded_searchable_units(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, storage, importer, derivation, knowledge = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "long-rule.txt"
    source.write_text(
        "库存规则。" + ("连续正文" * 5_000) + "超长末尾检索锚点。",
        encoding="utf-8",
    )

    result = importer.import_file(source, timeout=60)
    _wait_for_retrieval(knowledge, "超长末尾检索锚点", result.document_id)

    with storage.session_factory() as session:
        rows = list(
            session.exec(
                select(KnowledgeUnitRow)
                .where(KnowledgeUnitRow.document_id == result.document_id)
                .order_by(KnowledgeUnitRow.ordinal)
            )
        )
    assert len(rows) > 1
    assert all(0 < len(row.text) <= MAX_KNOWLEDGE_UNIT_CHARS for row in rows)
    assert [row.locator_payload["split_part"] for row in rows] == list(
        range(1, len(rows) + 1)
    )
    assert {row.locator_payload["split_parts"] for row in rows} == {len(rows)}
    importer.shutdown()
    derivation.shutdown()


def test_unsupported_suffix_is_rejected_and_spoofed_image_fails_after_admission(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, _storage, importer, derivation, _knowledge = _runtime(monkeypatch, tmp_path)
    pptx = tmp_path / "slides.pptx"
    pptx.write_bytes(b"PK\x03\x04not-a-supported-presentation")
    spoofed = tmp_path / "fake.png"
    spoofed.write_text("not an image", encoding="utf-8")

    with pytest.raises(ValidationError):
        importer.enqueue_file(pptx)
    receipt = importer.enqueue_file(spoofed)
    with pytest.raises(ValidationError) as error:
        importer.wait_for_import(receipt.import_id, timeout=30)
    assert error.value.error_code == "knowledge_format_mismatch"
    assert len(importer.list_imports()) == 1
    importer.shutdown()
    derivation.shutdown()


def test_derivation_failure_keeps_canonical_ready_and_can_retry_independently(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    derivation = KnowledgeDerivationService(
        paths=paths,
        session_factory=storage.session_factory,
        start_worker=False,
    )
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        normalizer=FormatNormalizer(),
        canonical_ready_notifier=derivation.enqueue_generation,
    )
    source = tmp_path / "rule.txt"
    source.write_text("库存规则正文", encoding="utf-8")
    receipt = importer.enqueue_file(source)
    job = _wait_for_derivation_job(derivation, storage.session_factory, receipt.import_id)
    with storage.session_factory() as session:
        generation = session.get(KnowledgeCanonicalGenerationRow, job.canonical_generation_id)
    assert generation is not None
    (KnowledgeContentStore(paths).resolve_relative_path(generation.relative_path) / "docling-document.json.zst").write_bytes(b"bad")

    try:
        result = derivation.derive_now(job.id)
        assert result.retrieval_ready is False
        failed = {item.import_id: item for item in importer.list_imports()}[receipt.import_id]
        assert failed.status == "canonical_ready"
        assert failed.phase == "completed"

        retry_job_id = derivation.retry_for_import(receipt.import_id)
        with storage.session_factory() as session:
            jobs = list(
                session.exec(
                    select(KnowledgeDerivationRow)
                    .where(KnowledgeDerivationRow.import_id == receipt.import_id)
                    .order_by(KnowledgeDerivationRow.attempt_number)
                )
            )
        assert len(jobs) == 2
        assert jobs[1].attempt_number == 2
        assert jobs[1].id == retry_job_id
        assert jobs[1].retry_of == jobs[0].id
        assert jobs[1].status == "queued"
        unchanged = {item.import_id: item for item in importer.list_imports()}[receipt.import_id]
        assert unchanged.phase == "completed"
        assert unchanged.error_code is None
        assert unchanged.retryable is False
    finally:
        importer.shutdown()
        derivation.shutdown()


def _wait_for_derivation_job(
    derivation: KnowledgeDerivationService,
    session_factory,
    import_id: str,
    timeout: float = 30,
) -> KnowledgeDerivationRow:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = derivation.status_for_import(import_id)
        if view is not None:
            with session_factory() as session:
                row = session.get(KnowledgeDerivationRow, view.job_id)
                if row is not None:
                    return row
        time.sleep(0.02)
    raise AssertionError("canonical publication did not enqueue derivation")


def _wait_for_derivation_status(
    derivation: KnowledgeDerivationService,
    import_id: str,
    status: str,
    timeout: float = 30,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = derivation.status_for_import(import_id)
        if view is not None and view.status == status:
            return
        time.sleep(0.02)
    raise AssertionError(f"derivation did not reach {status}")


def _wait_for_retrieval(
    knowledge: KnowledgeService,
    query: str,
    document_id: str,
    timeout: float = 30,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if document_id in {match.document_id for match in knowledge.lookup(query)}:
            return
        time.sleep(0.02)
    raise AssertionError("derivation did not publish searchable Units")


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
