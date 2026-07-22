from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from threading import Event, Thread

from sqlalchemy import text

from tests.knowledge_test_support import seed_knowledge_text
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.embedding_service import (
    EmbeddingBatch,
    EmbeddingSettings,
    embedding_profile_from_settings,
)
from xenix.services.knowledge_index_service import (
    KnowledgeIndexKind,
    KnowledgeIndexService,
)
from xenix.services.knowledge_semantic_service import KnowledgeSemanticService
from xenix.services.knowledge_service import KnowledgeService
from xenix.services.knowledge_vector_store import LanceKnowledgeVectorStore
from xenix.services.storage import StorageBootstrapService


class _SettingsSource:
    def __init__(self) -> None:
        self.settings = EmbeddingSettings(
            enabled=True,
            provider_key="test",
            base_url="https://embedding.example.test/v1",
            model="meaning-v1",
            dimensions=2,
            batch_size=8,
        )

    def load(self) -> EmbeddingSettings:
        return self.settings.model_copy(deep=True)


class _EmbeddingSession:
    def __init__(self, owner: _Embedding, settings: EmbeddingSettings) -> None:
        self._owner = owner
        self.profile = embedding_profile_from_settings(settings)

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        values = tuple(texts)
        self._owner.calls.append(values)
        if self._owner.fail:
            raise RuntimeError("provider failure")
        return EmbeddingBatch(
            profile=self.profile,
            vectors=tuple((1.0, 0.0) for _text in values),
        )


class _Embedding:
    def __init__(self, settings: _SettingsSource) -> None:
        self._settings = settings
        self.calls: list[tuple[str, ...]] = []
        self.fail = False

    def freeze(self):
        settings = self._settings.load()
        return _EmbeddingSession(self, settings) if settings.enabled else None

    def configured_profile(self):
        session = self.freeze()
        return session.profile if session is not None else None

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        session = self.freeze()
        assert session is not None
        return session.embed_texts(texts)


def test_manual_task_rebuilds_keyword_and_text_vector_indexes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage, settings, embedding, _semantic, knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )
    seed_knowledge_text(
        knowledge,
        title="经营规则",
        text="雨季雨具按三周平均销量备货。",
    )
    with storage.session_factory() as session:
        session.execute(text("DELETE FROM knowledge_unit_fts"))
        session.commit()

    before = indexes.status()
    task_id = indexes.enqueue_rebuild(
        (KnowledgeIndexKind.KEYWORD, KnowledgeIndexKind.TEXT_VECTOR),
        trigger="manual",
    )
    completed = indexes.rebuild_now(task_id)
    after = indexes.status()

    assert before.keyword_state == "needs_rebuild"
    assert completed.status == "succeeded"
    assert after.keyword_state == "ready"
    assert after.text_vector_state == "ready"
    assert knowledge.lookup("雨具三周")
    assert embedding.calls == [("雨季雨具按三周平均销量备货。",)]
    assert after.estimated_vector_requests == 1
    assert settings.load().api_key == ""


def test_corpus_notifications_coalesce_into_one_visible_vector_task(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, _settings, _embedding, _semantic, knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )
    seed_knowledge_text(knowledge, title="规则", text="规则正文：三周需求。")

    first = indexes.notify_corpus_changed()
    second = indexes.notify_corpus_changed()
    tasks = indexes.list_tasks()

    assert first == second
    assert len(tasks) == 1
    assert tasks[0].status == "queued"
    assert tasks[0].index_kinds == ("text_vector",)
    assert indexes.status().text_vector_state == "building"


def test_corpus_notification_skips_vector_rebuild_without_searchable_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, _settings, _embedding, _semantic, _knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )

    assert indexes.notify_corpus_changed() is None
    assert indexes.list_tasks() == []


def test_claimed_task_cannot_absorb_work_the_worker_did_not_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, _settings, _embedding, _semantic, knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )
    seed_knowledge_text(knowledge, title="规则", text="规则正文：三周需求。")
    first_id = indexes.enqueue_rebuild(
        (KnowledgeIndexKind.TEXT_VECTOR,),
        trigger="manual",
    )
    original_get = indexes._repository.get_index_task
    claim_read = Event()
    release_claim = Event()
    gated_once = False

    def gated_get(session, task_id):
        nonlocal gated_once
        row = original_get(session, task_id)
        if not gated_once and task_id == first_id:
            gated_once = True
            claim_read.set()
            assert release_claim.wait(5.0)
        return row

    monkeypatch.setattr(indexes._repository, "get_index_task", gated_get)
    completed: list[object] = []
    second_ids: list[str] = []
    claim_thread = Thread(
        target=lambda: completed.append(indexes.rebuild_now(first_id)),
        name="knowledge-index-claim-test",
    )
    claim_thread.start()
    assert claim_read.wait(5.0)
    enqueue_thread = Thread(
        target=lambda: second_ids.append(
            indexes.enqueue_rebuild(
                (KnowledgeIndexKind.KEYWORD,),
                trigger="manual",
            )
        ),
        name="knowledge-index-enqueue-test",
    )
    enqueue_thread.start()
    enqueue_thread.join(0.1)
    assert enqueue_thread.is_alive()

    release_claim.set()
    claim_thread.join(5.0)
    enqueue_thread.join(5.0)

    assert not claim_thread.is_alive()
    assert not enqueue_thread.is_alive()
    assert completed and completed[0].status == "succeeded"
    assert second_ids and second_ids[0] != first_id
    tasks = indexes.list_tasks()
    assert len(tasks) == 2
    by_id = {task.task_id: task for task in tasks}
    assert by_id[second_ids[0]].index_kinds == ("keyword",)
    assert by_id[second_ids[0]].status == "queued"
    assert by_id[first_id].index_kinds == ("text_vector",)
    assert by_id[first_id].status == "succeeded"


def test_embedding_confirmation_follows_vector_compatibility_not_credentials(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, settings, _embedding, _semantic, knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )
    seed_knowledge_text(knowledge, title="规则", text="规则正文：三周需求。")
    current = settings.load()

    assert indexes.embedding_change_requires_confirmation(
        current,
        current.model_copy(update={"api_key": "new-key", "batch_size": 99}),
    ) is False
    assert indexes.embedding_change_requires_confirmation(
        current,
        current.model_copy(update={"model": "meaning-v2"}),
    ) is True
    assert indexes.embedding_change_requires_confirmation(
        current,
        current.model_copy(update={"base_url": "https://other.example.test"}),
    ) is True
    assert indexes.embedding_change_requires_confirmation(
        current,
        current.model_copy(update={"dimensions": 3}),
    ) is True
    assert indexes.embedding_change_requires_confirmation(
        current,
        current.model_copy(update={"enabled": False}),
    ) is False


def test_old_vector_failure_does_not_override_a_later_successful_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, _settings, embedding, _semantic, knowledge, indexes = _services(
        monkeypatch,
        tmp_path,
    )
    seed_knowledge_text(knowledge, title="规则甲", text="规则甲使用三周需求。")
    embedding.fail = True
    failed_id = indexes.enqueue_rebuild(
        (KnowledgeIndexKind.TEXT_VECTOR,),
        trigger="manual",
    )
    assert indexes.rebuild_now(failed_id).status == "failed"
    assert indexes.status().text_vector_state == "needs_attention"

    embedding.fail = False
    successful_id = indexes.enqueue_rebuild(
        (KnowledgeIndexKind.TEXT_VECTOR,),
        trigger="manual",
    )
    assert indexes.rebuild_now(successful_id).status == "succeeded"
    seed_knowledge_text(knowledge, title="规则乙", text="规则乙使用两周需求。")

    status = indexes.status()
    assert status.text_vector_state == "needs_rebuild"
    assert status.error_code is None


def _services(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    settings = _SettingsSource()
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
    return storage, settings, embedding, semantic, knowledge, indexes
