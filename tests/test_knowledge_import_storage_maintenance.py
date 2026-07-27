from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_content_store import KnowledgeContentStore
from xenix.services.knowledge_import_storage_maintenance import (
    KnowledgeImportStorageMaintenance,
    KnowledgeImportStorageMaintenanceError,
)
from xenix.services.storage.layout import knowledge_root, knowledge_staging_root


def _runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    return paths, KnowledgeContentStore(paths)


def _snapshot(store: KnowledgeContentStore, tmp_path: Path, name: str, text: str):
    source = tmp_path / name
    source.write_text(text, encoding="utf-8")
    return store.snapshot_source(source)


def _canonical(store: KnowledgeContentStore, identity: str):
    return store.write_canonical_bundle(
        envelope={"canonical_generation_id": identity},
        docling_document={"name": identity, "texts": []},
    )


def _write_source_cas(root: Path, payload: bytes) -> tuple[Path, Path]:
    digest = hashlib.sha256(payload).hexdigest()
    directory = root / "objects" / "source" / digest[:2] / digest[2:4] / digest
    directory.mkdir(parents=True)
    source = directory / "source.txt"
    source.write_bytes(payload)
    return directory, source


def test_cleanup_preserves_references_and_reclaims_definite_import_orphans(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, store = _runtime(monkeypatch, tmp_path)
    root = knowledge_root(paths)
    referenced_source = _snapshot(store, tmp_path, "live.数据", "live source")
    orphan_source = _snapshot(store, tmp_path, "orphan.txt", "orphan source")
    referenced_canonical = _canonical(store, "live-generation")
    orphan_canonical = _canonical(store, "orphan-generation")

    staging = knowledge_staging_root(paths)
    source_stage = staging / f"source-{'a' * 32}.tmp"
    source_stage.write_bytes(b"partial source")
    canonical_stage = staging / f"canonical-{'b' * 32}"
    canonical_stage.mkdir()
    (canonical_stage / "canonical-envelope.json.zst").write_bytes(b"partial")

    vector_stage = staging / f"vector-{'c' * 32}"
    vector_stage.mkdir()
    (vector_stage / "keep.txt").write_text("keep", encoding="utf-8")
    unknown_stage = staging / "source-not-a-uuid.tmp"
    unknown_stage.write_text("keep", encoding="utf-8")
    unknown_canonical_stage = staging / f"canonical-{'d' * 32}"
    unknown_canonical_stage.mkdir()
    (unknown_canonical_stage / "unknown.bin").write_bytes(b"keep")
    index_sentinel = root / "indexes" / "do-not-touch" / "keep.txt"
    index_sentinel.parent.mkdir(parents=True)
    index_sentinel.write_text("keep", encoding="utf-8")

    maintenance = KnowledgeImportStorageMaintenance(root)
    result = maintenance.cleanup(
        referenced_source_paths=[referenced_source.path],
        referenced_canonical_paths=[referenced_canonical.relative_path],
    )

    assert result.source_cas_quarantined == 1
    assert result.canonical_bundles_quarantined == 1
    assert result.source_staging_quarantined == 1
    assert result.canonical_staging_quarantined == 1
    assert result.trash_deleted == 4
    assert result.trash_remaining == 0
    assert referenced_source.path.is_file()
    assert referenced_canonical.path.is_dir()
    assert not orphan_source.path.parent.exists()
    assert not orphan_canonical.path.exists()
    assert not source_stage.exists()
    assert not canonical_stage.exists()
    assert (vector_stage / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert unknown_stage.read_text(encoding="utf-8") == "keep"
    assert (unknown_canonical_stage / "unknown.bin").read_bytes() == b"keep"
    assert index_sentinel.read_text(encoding="utf-8") == "keep"

    repeated = maintenance.cleanup(
        referenced_source_paths=[referenced_source.path],
        referenced_canonical_paths=[referenced_canonical.relative_path],
    )

    assert repeated.source_cas_quarantined == 0
    assert repeated.canonical_bundles_quarantined == 0
    assert repeated.source_staging_quarantined == 0
    assert repeated.canonical_staging_quarantined == 0
    assert repeated.trash_deleted == 0
    assert repeated.trash_remaining == 0


def test_cleanup_retains_unknown_and_link_like_shapes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, _store = _runtime(monkeypatch, tmp_path)
    root = knowledge_root(paths)

    corrupt_digest = "e" * 64
    corrupt_source = (
        root
        / "objects"
        / "source"
        / corrupt_digest[:2]
        / corrupt_digest[2:4]
        / corrupt_digest
    )
    corrupt_source.mkdir(parents=True)
    (corrupt_source / "source.txt").write_bytes(b"not the path digest")
    unknown_canonical = (
        root / "objects" / "canonical" / "ff" / "ff" / ("f" * 64)
    )
    unknown_canonical.mkdir(parents=True)
    (unknown_canonical / "keep.txt").write_text("keep", encoding="utf-8")

    link_payload = b"link target must survive"
    link_digest = hashlib.sha256(link_payload).hexdigest()
    link_parent = (
        root
        / "objects"
        / "source"
        / link_digest[:2]
        / link_digest[2:4]
    )
    link_parent.mkdir(parents=True, exist_ok=True)
    linked_source = link_parent / link_digest
    source_target = tmp_path / "outside-source-cas"
    source_target.mkdir()
    (source_target / "source.txt").write_bytes(link_payload)

    linked_stage = knowledge_staging_root(paths) / f"canonical-{'1' * 32}"
    stage_target = tmp_path / "outside-stage"
    stage_target.mkdir()
    (stage_target / "manifest.json").write_bytes(b"partial")

    _redirect_directory(linked_source, source_target)
    _redirect_directory(linked_stage, stage_target)
    try:
        result = KnowledgeImportStorageMaintenance(root).cleanup(
            referenced_source_paths=[],
            referenced_canonical_paths=[],
        )

        assert result.source_cas_quarantined == 0
        assert result.canonical_bundles_quarantined == 0
        assert result.canonical_staging_quarantined == 0
        assert (corrupt_source / "source.txt").read_bytes() == b"not the path digest"
        assert (unknown_canonical / "keep.txt").read_text(encoding="utf-8") == "keep"
        assert linked_source.exists()
        assert linked_stage.exists()
        assert (source_target / "source.txt").read_bytes() == link_payload
        assert (stage_target / "manifest.json").read_bytes() == b"partial"
    finally:
        _remove_directory_link(linked_source)
        _remove_directory_link(linked_stage)


def test_out_of_bounds_reference_fails_closed_before_any_reclamation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, _store = _runtime(monkeypatch, tmp_path)
    root = knowledge_root(paths)
    orphan_directory, orphan_source = _write_source_cas(root, b"preserve on bad input")
    outside = tmp_path / "outside.txt"
    outside.write_text("user owned", encoding="utf-8")

    with pytest.raises(KnowledgeImportStorageMaintenanceError):
        KnowledgeImportStorageMaintenance(root).cleanup(
            referenced_source_paths=[outside],
            referenced_canonical_paths=[],
        )

    assert orphan_directory.is_dir()
    assert orphan_source.read_bytes() == b"preserve on bad input"
    assert outside.read_text(encoding="utf-8") == "user owned"
    assert not (root / ".import-trash").exists()


def test_cleanup_detaches_to_private_trash_before_best_effort_deletion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from xenix.services import knowledge_import_storage_maintenance as maintenance_module

    paths, _store = _runtime(monkeypatch, tmp_path)
    root = knowledge_root(paths)
    orphan_directory, _orphan_source = _write_source_cas(root, b"busy orphan")
    original_rmtree = maintenance_module.shutil.rmtree

    def busy_trash(path, *args, **kwargs):
        if Path(path).parent.name == ".import-trash":
            error = PermissionError("injected sharing violation")
            error.winerror = 32
            raise error
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(maintenance_module.shutil, "rmtree", busy_trash)
    maintenance = KnowledgeImportStorageMaintenance(root)
    first = maintenance.cleanup(
        referenced_source_paths=[],
        referenced_canonical_paths=[],
    )

    assert first.source_cas_quarantined == 1
    assert first.trash_deleted == 0
    assert first.trash_remaining == 1
    assert not orphan_directory.exists()
    trash_entries = tuple((root / ".import-trash").iterdir())
    assert len(trash_entries) == 1

    monkeypatch.setattr(maintenance_module.shutil, "rmtree", original_rmtree)
    repeated = maintenance.cleanup(
        referenced_source_paths=[],
        referenced_canonical_paths=[],
    )

    assert repeated.source_cas_quarantined == 0
    assert repeated.trash_deleted == 1
    assert repeated.trash_remaining == 0


def _redirect_directory(link: Path, target: Path) -> None:
    if os.name != "nt":
        link.symlink_to(target, target_is_directory=True)
        return
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        pytest.skip("Windows junctions are unavailable")
    assert bool(getattr(link, "is_junction", lambda: False)())


def _remove_directory_link(link: Path) -> None:
    if link.is_symlink():
        link.unlink()
    elif bool(getattr(link, "is_junction", lambda: False)()):
        link.rmdir()
