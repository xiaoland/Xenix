from __future__ import annotations

import json
from pathlib import Path

import pytest
from docling_core.types.doc import DoclingDocument, ImageRef
from PIL import Image

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.knowledge_canonical import CanonicalIdentity, Canonicalizer
from xenix.services.knowledge_content_store import (
    CanonicalBundleIdentity,
    KnowledgeContentStore,
)


def _store(monkeypatch, tmp_path: Path) -> KnowledgeContentStore:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    return KnowledgeContentStore(ensure_app_dirs(get_app_paths()))


def test_canonical_bundle_is_addressed_by_envelope_and_verified_on_reuse(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    document = {"schema_name": "DoclingDocument", "version": "1", "name": "rule"}
    first = store.write_canonical_bundle(
        envelope={"canonical_generation_id": "generation-a"},
        docling_document=document,
    )
    repeated = store.write_canonical_bundle(
        envelope={"canonical_generation_id": "generation-a"},
        docling_document=document,
    )
    second = store.write_canonical_bundle(
        envelope={"canonical_generation_id": "generation-b"},
        docling_document=document,
    )

    assert repeated == first
    assert second.path != first.path
    assert first.path.is_dir() and second.path.is_dir()
    assert store.read_canonical_bundle(first.relative_path).envelope["canonical_generation_id"] == "generation-a"


def test_existing_canonical_target_is_reopened_and_tamper_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    stored = store.write_canonical_bundle(
        envelope={"canonical_generation_id": "generation-a"},
        docling_document={"name": "rule"},
    )
    (stored.path / "docling-document.json.zst").write_bytes(b"tampered")

    with pytest.raises(ValidationError) as error:
        store.write_canonical_bundle(
            envelope={"canonical_generation_id": "generation-a"},
            docling_document={"name": "rule"},
        )

    assert error.value.error_code == "knowledge_canonical_integrity_failed"


def test_canonicalizer_externalizes_embedded_docling_images_and_binds_asset_bytes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    document = DoclingDocument(name="illustrated-rule")
    document.add_picture(image=ImageRef.from_pil(Image.new("RGB", (8, 6), "navy"), dpi=72))
    material = Canonicalizer().freeze(
        document,
        identity=CanonicalIdentity(
            library_id="global",
            document_id="document-a",
            import_id="import-a",
            canonical_generation_id="generation-a",
            source_artifact_id="artifact-a",
            source_sha256="a" * 64,
            source_format="docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            display_name="illustrated.docx",
            title="illustrated",
            attempt_number=1,
        ),
        pipeline={"parser": "docling"},
        warnings=[],
    )

    stored = store.write_canonical_bundle(
        envelope=material.envelope,
        docling_document=material.docling_document,
        assets=material.assets,
    )
    reopened = store.read_canonical_bundle(stored.relative_path)

    encoded_ir = json.dumps(reopened.docling_document, sort_keys=True)
    assert "data:image" not in encoded_ir
    assert len(reopened.envelope["assets"]) == 1
    descriptor = reopened.envelope["assets"][0]
    assert reopened.docling_document["pictures"][0]["image"]["uri"] == descriptor["relative_path"]
    asset_path = stored.path.joinpath(*descriptor["relative_path"].split("/"))
    assert asset_path.is_file()

    asset_path.write_bytes(b"tampered")
    with pytest.raises(ValidationError) as error:
        store.read_canonical_bundle(stored.relative_path)
    assert error.value.error_code == "knowledge_canonical_integrity_failed"


def test_source_snapshot_reuse_verifies_existing_bytes(monkeypatch, tmp_path: Path) -> None:
    store = _store(monkeypatch, tmp_path)
    source = tmp_path / "rule.txt"
    source.write_text("same bytes", encoding="utf-8")
    first = store.snapshot_source(source)
    first.path.write_text("bad bytes!", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        store.snapshot_source(source)

    assert error.value.error_code == "knowledge_source_integrity_failed"


def test_source_snapshot_canonicalizes_jpeg_suffix_aliases(monkeypatch, tmp_path: Path) -> None:
    store = _store(monkeypatch, tmp_path)
    jpg = tmp_path / "photo.jpg"
    jpeg = tmp_path / "photo.jpeg"
    jpg.write_bytes(b"same jpeg payload")
    jpeg.write_bytes(jpg.read_bytes())

    first = store.snapshot_source(jpg)
    second = store.snapshot_source(jpeg)

    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert first.path.name == "source.jpg"
    assert list(first.path.parent.iterdir()) == [first.path]


def test_canonical_reader_rejects_a_valid_bundle_with_the_wrong_database_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    stored = store.write_canonical_bundle(
        envelope={
            "canonical_generation_id": "generation-b",
            "document": {"id": "document-b", "library_id": "global"},
            "import": {"id": "import-b"},
            "source": {
                "artifact_id": "artifact-b",
                "sha256": "b" * 64,
                "format": "txt",
            },
        },
        docling_document={"name": "valid-bundle"},
    )

    with pytest.raises(ValidationError) as error:
        store.read_canonical_bundle(
            stored.relative_path,
            expected_envelope_sha256=stored.envelope_sha256,
            expected_content_ir_sha256=stored.content_ir_sha256,
            expected_identity=CanonicalBundleIdentity(
                document_id="document-a",
                import_id="import-a",
                canonical_generation_id="generation-a",
                source_artifact_id="artifact-a",
                library_id="global",
                source_sha256="a" * 64,
                source_format="txt",
            ),
        )

    assert error.value.error_code == "knowledge_canonical_integrity_failed"


def test_source_snapshot_cancellation_removes_staging_and_does_not_publish(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    source = tmp_path / "large.txt"
    source.write_bytes(b"a" * (3 * 1024 * 1024))
    checks = 0

    class Cancelled(Exception):
        pass

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks == 3:
            raise Cancelled

    with pytest.raises(Cancelled):
        store.snapshot_source(source, check_cancelled=check_cancelled)

    root = store._root
    assert not tuple((root / "staging").glob("source-*.tmp"))
    assert not tuple((root / "objects" / "source").rglob("source.*"))


def test_source_snapshot_enforces_worker_byte_limit_without_publishing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    source = tmp_path / "grew-after-admission.txt"
    source.write_bytes(b"a" * (2 * 1024 * 1024))

    with pytest.raises(ValidationError) as error:
        store.snapshot_source(source, maximum_bytes=1024 * 1024)

    assert error.value.error_code == "knowledge_source_size_unsupported"
    assert not tuple((store._root / "staging").glob("source-*.tmp"))
    assert not tuple((store._root / "objects" / "source").rglob("source.*"))


@pytest.mark.parametrize("relative", ["../private", "C:/private", "", "/absolute"])
def test_canonical_reader_rejects_uncontained_paths(monkeypatch, tmp_path: Path, relative: str) -> None:
    store = _store(monkeypatch, tmp_path)

    with pytest.raises(ValidationError):
        store.read_canonical_bundle(relative)


def test_legacy_canonical_locator_is_readable_only_inside_owned_storage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _store(monkeypatch, tmp_path)
    digest = "c" * 64
    legacy = (
        store._root
        / "objects"
        / digest[:2]
        / digest[2:4]
        / digest
        / "docling-document.json.zst"
    )
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy")
    outside = tmp_path / "docling-document.json.zst"
    outside.write_bytes(b"private")

    assert store.resolve_legacy_canonical_path(str(legacy)) == legacy.resolve()
    with pytest.raises(ValidationError):
        store.resolve_legacy_canonical_path(str(outside))
