from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from sqlmodel import select

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.embedding_service import (
    EmbeddingBatch,
    EmbeddingProfile,
    EmbeddingValidationError,
)
from xenix.services.knowledge_semantic_service import KnowledgeSemanticService
from xenix.services.knowledge_projection import knowledge_unit_id
from xenix.services.knowledge_service import (
    MAX_KNOWLEDGE_UNIT_CHARS,
    KnowledgeRetrievalUnavailable,
    KnowledgeSemanticUnavailable,
    KnowledgeService,
)
from xenix.services.knowledge_vector_store import LanceKnowledgeVectorStore
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import KnowledgeUnitRow, KnowledgeVectorGenerationRow
from xenix.services.storage.repositories.knowledge import KnowledgeRepository
from tests.knowledge_test_support import seed_knowledge_text


class _EmbeddingSession:
    def __init__(
        self,
        owner: _EmbeddingService,
        profile: EmbeddingProfile,
        actual_dimensions: int,
    ) -> None:
        self._owner = owner
        self.profile = profile
        self._actual_dimensions = actual_dimensions

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._owner._embed_texts(
            texts,
            profile=self.profile,
            actual_dimensions=self._actual_dimensions,
        )


class _EmbeddingService:
    def __init__(self) -> None:
        self.profile: EmbeddingProfile | None = EmbeddingProfile(
            provider_key="test",
            model="meaning-v1",
            dimensions=None,
            profile_fingerprint="profile-v1",
        )
        self.calls: list[tuple[str, ...]] = []
        self.call_profiles: list[str] = []
        self.before_documents: Callable[[], None] | None = None
        self.fail_documents = False
        self.actual_dimensions = 2

    def freeze(self) -> _EmbeddingSession | None:
        if self.profile is None:
            return None
        return _EmbeddingSession(self, self.profile, self.actual_dimensions)

    def configured_profile(self) -> EmbeddingProfile | None:
        session = self.freeze()
        return session.profile if session is not None else None

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        session = self.freeze()
        if session is None:
            raise EmbeddingValidationError("not configured")
        return session.embed_texts(texts)

    def _embed_texts(
        self,
        texts: Sequence[str],
        *,
        profile: EmbeddingProfile,
        actual_dimensions: int,
    ) -> EmbeddingBatch:
        values = tuple(texts)
        self.calls.append(values)
        self.call_profiles.append(profile.profile_fingerprint)
        if any("规则正文" in value for value in values):
            if self.before_documents is not None:
                callback, self.before_documents = self.before_documents, None
                callback()
            if self.fail_documents:
                raise EmbeddingValidationError("document embedding failed")
        return EmbeddingBatch(
            profile=profile,
            vectors=tuple(
                self._vector(value, actual_dimensions=actual_dimensions)
                for value in values
            ),
        )

    @staticmethod
    def _vector(value: str, *, actual_dimensions: int) -> tuple[float, ...]:
        prefix = (1.0, 0.0) if "雨季" in value or "规则正文" in value else (0.0, 1.0)
        return prefix + (0.0,) * (actual_dimensions - len(prefix))


def _services(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    embedding = _EmbeddingService()
    semantic = KnowledgeSemanticService(
        storage.session_factory,
        embedding_service=embedding,
        vector_store=LanceKnowledgeVectorStore(paths),
    )
    knowledge = KnowledgeService(
        storage.session_factory,
        semantic_search=semantic,
    )
    return storage, embedding, semantic, knowledge


def _generation_rows(storage) -> list[KnowledgeVectorGenerationRow]:
    with storage.session_factory() as session:
        return list(session.exec(select(KnowledgeVectorGenerationRow)))


def test_semantic_search_builds_projection_and_recovers_lexical_miss(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="经营经验", text="规则正文：防水出行品按三期周均销量备货。")

    assert knowledge.lookup("雨季补货策略") == []
    semantic.rebuild_generation()
    result = knowledge.retrieve("雨季补货策略", mode="semantic")

    assert result.mode == "semantic"
    assert [match.title for match in result.matches] == ["经营经验"]
    rows = _generation_rows(storage)
    assert len(rows) == 1
    assert rows[0].dimensions == 2
    assert rows[0].unit_count == 1
    assert embedding.calls == [
        ("规则正文：防水出行品按三期周均销量备货。",),
        ("雨季补货策略",),
    ]


def test_semantic_generation_receives_only_bounded_units(monkeypatch, tmp_path: Path) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge,
        title="超长规则",
        text="规则正文：" + ("㍿" * 3_000) + "语义末尾锚点。",
    )

    semantic.rebuild_generation()
    generation = semantic.search("雨季策略", library_id="global", limit=5)

    document_batches = [
        call for call in embedding.calls if any("规则正文" in text for text in call)
    ]
    document_texts = [text for batch in document_batches for text in batch]
    assert len(document_texts) > 1
    assert all(
        0 < len(unicodedata.normalize("NFKC", text)) <= MAX_KNOWLEDGE_UNIT_CHARS
        for text in document_texts
    )
    assert _generation_rows(storage)[0].unit_count == len(document_texts)
    assert generation.unit_ids


def test_unchanged_corpus_reuses_published_generation(monkeypatch, tmp_path: Path) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期平均销量。")

    semantic.rebuild_generation(force=False)
    semantic.rebuild_generation(force=False)
    semantic.search("雨季策略", library_id="global", limit=5)
    semantic.search("雨季策略", library_id="global", limit=5)

    document_calls = [call for call in embedding.calls if "规则正文" in call[0]]
    assert len(document_calls) == 1
    assert len(_generation_rows(storage)) == 1


def test_republishing_same_projection_keeps_vector_status_and_search_aligned(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage, _embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    document = seed_knowledge_text(
        knowledge,
        title="规则",
        text="规则正文：采用三期平均销量。",
    )
    generation = semantic.rebuild_generation()

    repository = KnowledgeRepository()
    with storage.session_factory() as session:
        current = repository.list_current_units(session, library_id="global")
        assert len(current) == 1
        unit = current[0]
        replacement = KnowledgeUnitRow(
            id=knowledge_unit_id(
                document_id=document.id,
                canonical_generation_id=document.retrieval_generation_id or "",
                ordinal=unit.ordinal,
            ),
            document_id=document.id,
            canonical_generation_id=document.retrieval_generation_id or "",
            ordinal=unit.ordinal,
            text=unit.text,
            search_text=unit.search_text,
            locator_payload=unit.locator_payload,
        )
        repository.replace_units(
            session,
            document=document,
            units=[replacement],
        )
        session.commit()

    state = semantic.inspect_index()
    candidates = semantic.search("雨季策略", library_id="global", limit=5)

    assert state.ready is True
    assert state.generation_id == generation.id
    assert candidates.unit_ids == (replacement.id,)


def test_corpus_or_profile_change_creates_a_new_projection(monkeypatch, tmp_path: Path) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则甲", text="规则正文：甲类按三期平均销量。")
    semantic.rebuild_generation()

    seed_knowledge_text(knowledge, title="规则乙", text="规则正文：乙类按两期平均销量。")
    semantic.rebuild_generation()
    embedding.profile = EmbeddingProfile(
        provider_key="test",
        model="meaning-v2",
        dimensions=None,
        profile_fingerprint="profile-v2",
    )
    semantic.rebuild_generation()

    rows = _generation_rows(storage)
    assert len(rows) == 3
    assert {row.profile_fingerprint for row in rows} == {"profile-v1", "profile-v2"}
    assert {row.unit_count for row in rows} == {1, 2}


def test_provider_dimension_change_cannot_reuse_an_incompatible_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期平均销量。")
    semantic.rebuild_generation()

    embedding.actual_dimensions = 3
    semantic.rebuild_generation()

    assert {row.dimensions for row in _generation_rows(storage)} == {2, 3}


def test_failed_or_stale_build_is_not_published(monkeypatch, tmp_path: Path) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则甲", text="规则正文：甲类按三期平均销量。")
    embedding.fail_documents = True

    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.rebuild_generation()
    assert _generation_rows(storage) == []

    embedding.fail_documents = False
    embedding.before_documents = lambda: seed_knowledge_text(knowledge,
        title="规则乙",
        text="新增正文：乙类按两期平均销量。",
    )
    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.rebuild_generation()
    assert _generation_rows(storage) == []


def test_disabled_embedding_reports_not_configured(monkeypatch, tmp_path: Path) -> None:
    _storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期平均销量。")
    embedding.profile = None

    assert semantic.is_configured() is False
    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.search("雨季策略", library_id="global", limit=5)


def test_empty_corpus_is_unavailable_except_for_auto_keyword_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _storage, _embedding, semantic, knowledge = _services(monkeypatch, tmp_path)

    assert knowledge.retrieve("雨季策略", mode="auto").mode == "keyword"
    with pytest.raises(KnowledgeRetrievalUnavailable):
        knowledge.retrieve("雨季策略", mode="semantic")
    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.search("雨季策略", library_id="global", limit=5)


def test_one_rebuild_uses_one_frozen_embedding_profile(monkeypatch, tmp_path: Path) -> None:
    storage, embedding, semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期平均销量。")
    embedding.before_documents = lambda: setattr(
        embedding,
        "profile",
        EmbeddingProfile(
            provider_key="test",
            model="meaning-v2",
            dimensions=None,
            profile_fingerprint="profile-v2",
        ),
    )

    with pytest.raises(KnowledgeSemanticUnavailable):
        semantic.rebuild_generation()

    assert embedding.call_profiles == ["profile-v1"]
    assert _generation_rows(storage) == []


def test_lookup_never_builds_an_absent_vector_index(monkeypatch, tmp_path: Path) -> None:
    _storage, embedding, _semantic, knowledge = _services(monkeypatch, tmp_path)
    seed_knowledge_text(knowledge, title="规则", text="规则正文：采用三期平均销量。")

    result = knowledge.retrieve("雨季策略", mode="auto")

    assert result.mode == "keyword"
    assert embedding.calls == []
