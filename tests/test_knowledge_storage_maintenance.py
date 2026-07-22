from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
from threading import Event, Thread

import pytest
from sqlmodel import select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.embedding_service import EmbeddingBatch, EmbeddingProfile
from xenix.services.knowledge_semantic_service import KnowledgeSemanticService
from xenix.services.knowledge_service import KnowledgeSemanticUnavailable, KnowledgeService
from xenix.services.knowledge_storage_maintenance import KnowledgeStorageMaintenance
from xenix.services.knowledge_vector_store import (
    KnowledgeVectorRecord,
    KnowledgeVectorStoreError,
    LanceKnowledgeVectorStore,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import knowledge_indexes_root, knowledge_staging_root
from xenix.services.storage.models import KnowledgeVectorGenerationRow
from tests.knowledge_test_support import seed_knowledge_text

_CORPUS = "c" * 64
_PROFILE = "p" * 64


def _runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    store = LanceKnowledgeVectorStore(paths)
    return paths, storage, store


def _metadata(
    storage,
    *,
    generation_id: str,
    relative_path: str | None = None,
    dimensions: int = 2,
    unit_count: int = 1,
) -> None:
    with storage.session_factory() as session:
        session.add(
            KnowledgeVectorGenerationRow(
                id=generation_id,
                library_id="global",
                corpus_fingerprint=_CORPUS,
                profile_fingerprint=_PROFILE,
                provider_key="test",
                model="meaning-v1",
                dimensions=dimensions,
                distance_metric="cosine",
                relative_path=relative_path or f"indexes/{generation_id}",
                unit_count=unit_count,
            )
        )
        session.commit()


def _metadata_ids(storage) -> set[str]:
    with storage.session_factory() as session:
        return set(session.exec(select(KnowledgeVectorGenerationRow.id)))


def _write_valid_generation(
    store: LanceKnowledgeVectorStore,
    generation_id: str,
) -> str:
    return store.write_generation(
        generation_id=generation_id,
        records=[KnowledgeVectorRecord("unit-1", (1.0, 0.0))],
        dimensions=2,
        corpus_fingerprint=_CORPUS,
        profile_fingerprint=_PROFILE,
    )


def _write_corrupt_generation(paths, generation_id: str) -> Path:
    path = knowledge_indexes_root(paths) / generation_id
    path.mkdir()
    (path / "manifest.json").write_text("{}", encoding="utf-8")
    return path


class _ChangingEmbedding:
    def __init__(self) -> None:
        self.profile = EmbeddingProfile(
            provider_key="test",
            model="meaning-v1",
            dimensions=None,
            profile_fingerprint=_PROFILE,
        )
        self.before_documents = None

    def freeze(self):
        return self

    def embed_texts(self, texts):
        values = tuple(texts)
        if any("规则正文" in value for value in values) and self.before_documents:
            callback, self.before_documents = self.before_documents, None
            callback()
        return EmbeddingBatch(
            profile=self.profile,
            vectors=tuple((1.0, 0.0) for _value in values),
        )


def test_stale_semantic_build_reclaims_unpublished_final_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, store = _runtime(monkeypatch, tmp_path)
    embedding = _ChangingEmbedding()
    semantic = KnowledgeSemanticService(
        storage.session_factory,
        embedding_service=embedding,
        vector_store=store,
    )
    knowledge = KnowledgeService(storage.session_factory, semantic_search=semantic)
    seed_knowledge_text(knowledge, title="规则甲", text="规则正文：甲类采用三期均值。")
    embedding.before_documents = lambda: seed_knowledge_text(knowledge,
        title="规则乙",
        text="新增正文：乙类采用两期均值。",
    )

    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.rebuild_generation(library_id="global")

    assert _metadata_ids(storage) == set()
    assert store.list_definite_generation_paths() == ()
    assert store.list_quarantined() == ()
    assert not any(
        child.name != ".vector-trash"
        for child in knowledge_indexes_root(paths).iterdir()
    )


def test_first_semantic_use_reconciles_a_crash_final_orphan(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, store = _runtime(monkeypatch, tmp_path)
    orphan_id = "x" * 32
    orphan_path = knowledge_indexes_root(paths) / orphan_id
    _write_valid_generation(store, orphan_id)

    semantic = KnowledgeSemanticService(
        storage.session_factory,
        embedding_service=_ChangingEmbedding(),
        vector_store=LanceKnowledgeVectorStore(paths),
    )
    knowledge = KnowledgeService(storage.session_factory, semantic_search=semantic)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期均值。")

    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.search("雨季策略", library_id="global", limit=5)

    assert not orphan_path.exists()
    assert orphan_id not in _metadata_ids(storage)


def test_cleanup_only_reclaims_proven_vector_orphans_and_old_vector_staging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, store = _runtime(monkeypatch, tmp_path)
    orphan_id = "o" * 32
    orphan_path = knowledge_indexes_root(paths) / orphan_id
    _write_valid_generation(store, orphan_id)

    indexes_sentinel = knowledge_indexes_root(paths) / ("s" * 32)
    indexes_sentinel.mkdir()
    (indexes_sentinel / "keep.txt").write_text("keep", encoding="utf-8")
    staging = knowledge_staging_root(paths)
    old_vector_stage = staging / "vector-old-stage"
    current_vector_stage = staging / "vector-current-stage"
    source_stage = staging / "source-keep.tmp"
    canonical_stage = staging / "canonical-keep"
    for path in (old_vector_stage, current_vector_stage, source_stage, canonical_stage):
        path.mkdir()
    os.utime(old_vector_stage, (1_000.0, 1_000.0))
    os.utime(current_vector_stage, (9_990.0, 9_990.0))

    result = KnowledgeStorageMaintenance(
        storage.session_factory,
        vector_store=store,
        stale_staging_seconds=100.0,
        clock=lambda: 10_000.0,
    ).cleanup()

    assert result.orphan_generations_quarantined == 1
    assert result.stale_staging_quarantined == 1
    assert not orphan_path.exists()
    assert not old_vector_stage.exists()
    assert current_vector_stage.is_dir()
    assert source_stage.is_dir()
    assert canonical_stage.is_dir()
    assert (indexes_sentinel / "keep.txt").read_text(encoding="utf-8") == "keep"


def _redirect_directory(link: Path, target: Path, *, kind: str) -> None:
    link.rmdir()
    if kind == "symlink":
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks are unavailable: {exc}")
        return
    if os.name != "nt":
        pytest.skip("Windows junction coverage")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        pytest.skip("directory junctions are unavailable")
    assert getattr(link, "is_junction")()


def _remove_directory_link(link: Path) -> None:
    if link.is_symlink():
        link.unlink()
    elif bool(getattr(link, "is_junction", lambda: False)()):
        link.rmdir()


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("root_name", ["indexes", "staging"])
def test_redirected_vector_roots_are_rejected_without_blocking_keyword_use(
    monkeypatch,
    tmp_path: Path,
    caplog,
    kind: str,
    root_name: str,
) -> None:
    paths, storage, store = _runtime(monkeypatch, tmp_path)
    root = (
        knowledge_indexes_root(paths)
        if root_name == "indexes"
        else knowledge_staging_root(paths)
    )
    redirected = paths.artifacts / f"redirected-{root_name}-{kind}"
    redirected.mkdir()
    victim = redirected / (
        "v" * 32 if root_name == "indexes" else f"vector-{'v' * 32}"
    )
    victim.mkdir()
    marker = victim / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    _redirect_directory(root, redirected, kind=kind)
    try:
        with pytest.raises(KnowledgeVectorStoreError):
            store.list_definite_generation_paths()

        semantic = KnowledgeSemanticService(
            storage.session_factory,
            embedding_service=_ChangingEmbedding(),
            vector_store=LanceKnowledgeVectorStore(paths),
        )
        knowledge = KnowledgeService(storage.session_factory, semantic_search=semantic)
        seed_knowledge_text(knowledge, title="词法规则", text="保留关键字证据。")
        with caplog.at_level(logging.WARNING):
            with pytest.raises(KnowledgeSemanticUnavailable):
                semantic.search("语义问题", library_id="global", limit=5)

        assert [match.title for match in knowledge.lookup("关键字")] == ["词法规则"]
        assert marker.read_text(encoding="utf-8") == "keep"
        assert "Knowledge vector maintenance was deferred." in caplog.messages
    finally:
        _remove_directory_link(root)
        root.mkdir(exist_ok=True)


def test_cleanup_removes_missing_corrupt_and_unsafe_metadata_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, store = _runtime(monkeypatch, tmp_path)
    healthy_id = "h" * 32
    corrupt_id = "c" * 32
    missing_id = "m" * 32
    unsafe_id = "u" * 32
    _write_valid_generation(store, healthy_id)
    _metadata(storage, generation_id=healthy_id)
    corrupt_path = _write_corrupt_generation(paths, corrupt_id)
    _metadata(storage, generation_id=corrupt_id)
    _metadata(storage, generation_id=missing_id)
    outside_sentinel = paths.artifacts / "do-not-delete.txt"
    outside_sentinel.write_text("keep", encoding="utf-8")
    _metadata(
        storage,
        generation_id=unsafe_id,
        relative_path="../../do-not-delete.txt",
    )

    result = KnowledgeStorageMaintenance(
        storage.session_factory,
        vector_store=store,
    ).cleanup()

    assert result.metadata_scanned == 4
    assert result.healthy_metadata == 1
    assert result.missing_metadata_deleted == 1
    assert result.corrupt_metadata_deleted == 2
    assert result.metadata_retained == 0
    assert _metadata_ids(storage) == {healthy_id}
    assert (knowledge_indexes_root(paths) / healthy_id).is_dir()
    assert not corrupt_path.exists()
    assert outside_sentinel.read_text(encoding="utf-8") == "keep"


def test_sharing_violation_retries_then_completes_cleanup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from xenix.services import knowledge_vector_store as vector_module

    paths, storage, store = _runtime(monkeypatch, tmp_path)
    generation_id = "r" * 32
    generation_path = _write_corrupt_generation(paths, generation_id)
    _metadata(storage, generation_id=generation_id)
    original_replace = vector_module.os.replace
    attempts = 0

    def replace_after_retry(source, target):
        nonlocal attempts
        if Path(source) == generation_path:
            attempts += 1
            if attempts == 1:
                error = PermissionError("injected sharing violation")
                error.winerror = 32
                raise error
        return original_replace(source, target)

    monkeypatch.setattr(vector_module.os, "replace", replace_after_retry)
    result = KnowledgeStorageMaintenance(
        storage.session_factory,
        vector_store=store,
    ).cleanup()

    assert attempts == 2
    assert result.corrupt_metadata_deleted == 1
    assert _metadata_ids(storage) == set()
    assert not generation_path.exists()


def test_persistent_sharing_violation_preserves_metadata_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from xenix.services import knowledge_vector_store as vector_module

    paths, storage, store = _runtime(monkeypatch, tmp_path)
    generation_id = "b" * 32
    generation_path = _write_corrupt_generation(paths, generation_id)
    _metadata(storage, generation_id=generation_id)
    attempts = 0

    def always_busy(source, target):
        nonlocal attempts
        if Path(source) == generation_path:
            attempts += 1
            error = PermissionError("injected sharing violation")
            error.winerror = 32
            raise error
        raise AssertionError("cleanup touched an unexpected path")

    monkeypatch.setattr(vector_module.os, "replace", always_busy)
    result = KnowledgeStorageMaintenance(
        storage.session_factory,
        vector_store=store,
    ).cleanup()

    assert attempts == 3
    assert result.metadata_retained == 1
    assert result.corrupt_metadata_deleted == 0
    assert _metadata_ids(storage) == {generation_id}
    assert generation_path.is_dir()


def test_private_trash_deletion_is_best_effort_after_readiness_is_removed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from xenix.services import knowledge_vector_store as vector_module

    paths, storage, store = _runtime(monkeypatch, tmp_path)
    generation_id = "t" * 32
    generation_path = _write_corrupt_generation(paths, generation_id)
    _metadata(storage, generation_id=generation_id)
    original_rmtree = vector_module.shutil.rmtree

    def busy_trash(path, *args, **kwargs):
        if Path(path).parent.name == ".vector-trash":
            error = PermissionError("injected sharing violation")
            error.winerror = 32
            raise error
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(vector_module.shutil, "rmtree", busy_trash)
    result = KnowledgeStorageMaintenance(
        storage.session_factory,
        vector_store=store,
    ).cleanup()

    assert result.corrupt_metadata_deleted == 1
    assert result.trash_remaining == 1
    assert _metadata_ids(storage) == set()
    assert not generation_path.exists()

    monkeypatch.setattr(vector_module.shutil, "rmtree", original_rmtree)
    for token in store.list_quarantined():
        assert store.delete_quarantined(token)


def test_vector_store_instances_share_one_runtime_lifecycle_lock(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, _storage, first = _runtime(monkeypatch, tmp_path)
    second = LanceKnowledgeVectorStore(paths)
    holder_entered = Event()
    release_holder = Event()
    waiter_entered = Event()

    def hold_lifecycle() -> None:
        with first.lifecycle():
            holder_entered.set()
            assert release_holder.wait(timeout=5)

    def wait_for_lifecycle() -> None:
        assert holder_entered.wait(timeout=5)
        with second.lifecycle():
            waiter_entered.set()

    holder = Thread(target=hold_lifecycle)
    waiter = Thread(target=wait_for_lifecycle)
    holder.start()
    waiter.start()
    assert holder_entered.wait(timeout=5)
    assert not waiter_entered.wait(timeout=0.1)
    release_holder.set()
    holder.join(timeout=5)
    waiter.join(timeout=5)

    assert not holder.is_alive()
    assert not waiter.is_alive()
    assert waiter_entered.is_set()
