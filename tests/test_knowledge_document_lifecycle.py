from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import select

from tests.knowledge_test_support import seed_knowledge_text
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.artifact_service import ArtifactService
from xenix.services.embedding_service import (
    EmbeddingBatch,
    EmbeddingSettings,
    embedding_profile_from_settings,
)
from xenix.services.knowledge_derivation_service import KnowledgeDerivationService
from xenix.services.knowledge_document_lifecycle_service import (
    KnowledgeDocumentBusy,
    KnowledgeDocumentLifecycleService,
)
from xenix.services.knowledge_import_service import KnowledgeImportService
from xenix.services.knowledge_import_worker import InlineKnowledgeImportWorkerRunner
from xenix.services.knowledge_index_service import KnowledgeIndexService
from xenix.services.knowledge_semantic_service import KnowledgeSemanticService
from xenix.services.knowledge_service import KnowledgeService
from xenix.services.knowledge_vector_store import LanceKnowledgeVectorStore
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import knowledge_import_task_root
from xenix.services.storage.models import (
    ArtifactRow,
    KnowledgeCanonicalGenerationRow,
    KnowledgeDerivationRow,
    KnowledgeDocumentRow,
    KnowledgeImportRow,
    KnowledgeUnitRow,
    KnowledgeVectorGenerationRow,
)


class _EmbeddingSettings:
    def __init__(self) -> None:
        self.value = EmbeddingSettings(
            enabled=True,
            provider_key="test",
            base_url="https://embedding.example.test/v1",
            model="meaning-v1",
            dimensions=2,
            batch_size=20,
        )

    def load(self) -> EmbeddingSettings:
        return self.value.model_copy(deep=True)


class _EmbeddingSession:
    def __init__(self, settings: EmbeddingSettings) -> None:
        self.profile = embedding_profile_from_settings(settings)

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            profile=self.profile,
            vectors=tuple((1.0, 0.0) for _text in texts),
        )


class _Embedding:
    def __init__(self, settings: _EmbeddingSettings) -> None:
        self._settings = settings

    def freeze(self) -> _EmbeddingSession | None:
        settings = self._settings.load()
        return _EmbeddingSession(settings) if settings.enabled else None

    def configured_profile(self):
        session = self.freeze()
        return session.profile if session is not None else None

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        session = self.freeze()
        assert session is not None
        return session.embed_texts(texts)


def _runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    artifacts = ArtifactService(storage.session_factory)
    knowledge = KnowledgeService(storage.session_factory)
    return paths, storage, artifacts, knowledge


def test_remove_imported_document_clears_search_and_owned_lineage_but_not_user_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, artifacts, knowledge = _runtime(monkeypatch, tmp_path)
    derivation = KnowledgeDerivationService(
        paths=paths,
        session_factory=storage.session_factory,
    )
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
        worker_runner=InlineKnowledgeImportWorkerRunner(paths),
        canonical_ready_notifier=derivation.enqueue_generation,
    )
    lifecycle = KnowledgeDocumentLifecycleService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
        content_cleanup=importer.cleanup_storage_orphans,
    )
    source = tmp_path / "经营规则.txt"
    source.write_text("华东雨季雨具按三周平均销量备货。", encoding="utf-8")
    original_bytes = source.read_bytes()
    try:
        imported = importer.import_file(source)
        assert _wait_for_document(knowledge, "雨具三周", imported.document_id)
        with storage.session_factory() as session:
            artifact = session.get(ArtifactRow, imported.source_artifact_id)
            generation = session.get(
                KnowledgeCanonicalGenerationRow,
                imported.canonical_generation_id,
            )
            assert artifact is not None
            assert generation is not None
            source_snapshot = Path(artifact.absolute_path)
            canonical_bundle = Path(imported.canonical_path or "")
        task_root = knowledge_import_task_root(paths, imported.import_id)
        assert source_snapshot.is_file()
        assert canonical_bundle.is_dir()
        assert task_root.is_dir()

        receipt = lifecycle.remove_document(imported.document_id)

        assert receipt.document_id == imported.document_id
        assert receipt.removed_import_count == 1
        assert knowledge.list_documents() == []
        assert knowledge.lookup("雨具三周") == []
        assert source.read_bytes() == original_bytes
        assert not source_snapshot.exists()
        assert not canonical_bundle.exists()
        assert not task_root.exists()
        with storage.session_factory() as session:
            for model in (
                KnowledgeDocumentRow,
                KnowledgeUnitRow,
                KnowledgeImportRow,
                KnowledgeCanonicalGenerationRow,
                KnowledgeDerivationRow,
            ):
                assert list(session.exec(select(model))) == []
            assert session.get(ArtifactRow, imported.source_artifact_id) is None
            assert (
                session.exec(
                    text("SELECT count(*) FROM knowledge_unit_fts")
                ).one()[0]
                == 0
            )
            assert session.exec(text("PRAGMA foreign_key_check")).all() == []

        reimported = importer.import_file(source)
        assert reimported.document_id != imported.document_id
        assert reimported.reused_existing is False
        assert _wait_for_document(knowledge, "雨具三周", reimported.document_id)
    finally:
        importer.shutdown()
        derivation.shutdown()


def test_remove_rejects_active_document_work_without_partial_mutation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, artifacts, knowledge = _runtime(monkeypatch, tmp_path)
    document = seed_knowledge_text(
        knowledge,
        title="仍在处理",
        text="三周平均需求。",
    )
    with storage.session_factory() as session:
        session.add(
            KnowledgeImportRow(
                id="a" * 32,
                library_id="global",
                original_file_name="busy.txt",
                source_format="txt",
                status="running",
                phase="parsing",
                planned_document_id=document.id,
                document_id=document.id,
            )
        )
        session.commit()
    lifecycle = KnowledgeDocumentLifecycleService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
    )

    with pytest.raises(KnowledgeDocumentBusy) as exc_info:
        lifecycle.remove_document(document.id)

    assert exc_info.value.error_code == "knowledge_document_busy"
    assert [item.document_id for item in knowledge.list_documents()] == [document.id]
    assert knowledge.lookup("三周平均需求")
    with storage.session_factory() as session:
        row = session.get(KnowledgeDocumentRow, document.id)
        assert row is not None and row.active
        assert session.get(KnowledgeImportRow, "a" * 32) is not None


def test_remove_preserves_source_cas_until_last_library_reference_is_removed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, artifacts, knowledge = _runtime(monkeypatch, tmp_path)
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
        worker_runner=InlineKnowledgeImportWorkerRunner(paths),
    )
    lifecycle = KnowledgeDocumentLifecycleService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
        content_cleanup=importer.cleanup_storage_orphans,
    )
    source = tmp_path / "共享来源.txt"
    source.write_text("共享来源中的跨库库存规则。", encoding="utf-8")
    try:
        imported = importer.import_file(source)
        with storage.session_factory() as session:
            artifact = session.get(ArtifactRow, imported.source_artifact_id)
            assert artifact is not None
            source_snapshot = Path(artifact.absolute_path)
        other = seed_knowledge_text(
            knowledge,
            title="另一知识库的共享来源",
            text="另一知识库仍使用共享来源中的跨库库存规则。",
            source_artifact_id=imported.source_artifact_id,
            library_id="other-library",
        )

        lifecycle.remove_document(imported.document_id)

        assert source_snapshot.is_file()
        with storage.session_factory() as session:
            assert session.get(ArtifactRow, imported.source_artifact_id) is not None
        assert [
            match.document_id
            for match in knowledge.lookup(
                "跨库库存规则",
                library_id="other-library",
            )
        ] == [other.id]

        lifecycle.remove_document(other.id, library_id="other-library")

        assert not source_snapshot.exists()
        with storage.session_factory() as session:
            assert session.get(ArtifactRow, imported.source_artifact_id) is None
            assert session.exec(text("PRAGMA foreign_key_check")).all() == []
    finally:
        importer.shutdown()


def test_remove_invalidates_whole_library_vectors_and_rebuilds_remaining_corpus(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, artifacts, _knowledge = _runtime(monkeypatch, tmp_path)
    settings = _EmbeddingSettings()
    embedding = _Embedding(settings)
    semantic = KnowledgeSemanticService(
        storage.session_factory,
        embedding_service=embedding,
        vector_store=LanceKnowledgeVectorStore(paths),
    )
    knowledge = KnowledgeService(
        storage.session_factory,
        semantic_search=semantic,
    )
    indexes = KnowledgeIndexService(
        session_factory=storage.session_factory,
        semantic_service=semantic,
        embedding_service=embedding,
        embedding_settings_source=settings,
        start_worker=False,
    )
    removed = seed_knowledge_text(
        knowledge,
        title="删除规则",
        text="删除目标使用三周平均需求。",
    )
    remaining = seed_knowledge_text(
        knowledge,
        title="保留规则",
        text="保留目标使用五周平均需求。",
    )
    initial_generation = semantic.rebuild_generation()
    lifecycle = KnowledgeDocumentLifecycleService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=artifacts,
        index_service=indexes,
    )
    try:
        receipt = lifecycle.remove_document(removed.id)

        assert receipt.invalidated_vector_generation_count == 1
        assert receipt.vector_rebuild_task_id is not None
        assert all(
            match.document_id != removed.id
            for match in knowledge.lookup("三周平均需求")
        )
        assert [match.document_id for match in knowledge.lookup("五周平均需求")] == [
            remaining.id
        ]
        with storage.session_factory() as session:
            assert list(session.exec(select(KnowledgeVectorGenerationRow))) == []
        assert not (
            paths.artifacts
            / "knowledge"
            / "indexes"
            / initial_generation.id
        ).exists()

        completed = indexes.rebuild_now(receipt.vector_rebuild_task_id)
        assert completed.status == "succeeded"
        state = semantic.inspect_index()
        assert state.ready
        assert state.unit_count == 1
        result = knowledge.retrieve("任意语义查询", mode="semantic")
        assert [match.document_id for match in result.matches] == [remaining.id]
    finally:
        indexes.shutdown()


def _wait_for_document(
    knowledge: KnowledgeService,
    query: str,
    document_id: str,
) -> bool:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if any(match.document_id == document_id for match in knowledge.lookup(query)):
            return True
        time.sleep(0.02)
    return False
