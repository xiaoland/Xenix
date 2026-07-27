from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_service import (
    KnowledgeRetrievalUnavailable,
    KnowledgeSemanticCandidates,
    KnowledgeSemanticUnavailable,
    KnowledgeService,
)
from xenix.services.storage import StorageBootstrapService
from tests.knowledge_test_support import seed_knowledge_text


class _SemanticSearch:
    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.unit_ids: list[str] = []
        self.error: Exception | None = None
        self.configuration_error: Exception | None = None
        self.calls: list[tuple[str, str, int]] = []
        self.current = True
        self.current_checks: list[tuple[str, str]] = []

    def is_configured(self) -> bool:
        if self.configuration_error is not None:
            raise self.configuration_error
        return self.configured

    def search(
        self,
        query: str,
        *,
        library_id: str,
        limit: int,
    ) -> KnowledgeSemanticCandidates:
        self.calls.append((query, library_id, limit))
        if self.error is not None:
            raise self.error
        return KnowledgeSemanticCandidates(
            unit_ids=tuple(self.unit_ids[:limit]),
            corpus_fingerprint="fake-corpus",
            profile_fingerprint="fake-profile",
            generation_id="fake-generation",
        )

    def is_current(
        self,
        candidates: KnowledgeSemanticCandidates,
        *,
        library_id: str,
    ) -> bool:
        self.current_checks.append((candidates.corpus_fingerprint, library_id))
        return self.current


def _service(
    monkeypatch,
    tmp_path: Path,
    *,
    semantic_search=None,
) -> KnowledgeService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return KnowledgeService(
        context.session_factory,
        semantic_search=semantic_search,
    )


def test_cjk_keyword_lookup_returns_bounded_source_linked_unit(monkeypatch, tmp_path: Path) -> None:
    service = _service(monkeypatch, tmp_path)
    document = seed_knowledge_text(service,
        title="华东雨季备货规则",
        text="8—9 月华东门店仅雨具按 3 周平均销量建立目标库存。\n\n防晒用品沿用常规库存策略。",
    )

    matches = service.lookup("华东雨季雨具备货")

    assert len(matches) == 1
    assert matches[0].document_id == document.id
    assert matches[0].title == "华东雨季备货规则"
    assert "3 周平均销量" in matches[0].quote
    assert matches[0].locator == {"passage": 1}
    assert matches[0].citation_id == f"knowledge:{matches[0].unit_id}"


def test_document_listing_returns_logical_summaries_scoped_to_one_library(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = _service(monkeypatch, tmp_path)
    seed_knowledge_text(service, title="全局规则", text="雨具使用三周需求。")
    seed_knowledge_text(
        service,
        title="未来知识库规则",
        text="雨具使用五周需求。",
        library_id="future-library",
    )

    summaries = service.list_documents()

    assert len(summaries) == 1
    assert summaries[0].title == "全局规则"
    assert summaries[0].source_format == "unknown"
    assert summaries[0].content_state == "ready"
    assert summaries[0].updated_at >= summaries[0].imported_at


def test_keyword_excerpt_is_centered_on_a_match_near_the_unit_tail(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = _service(monkeypatch, tmp_path)
    seed_knowledge_text(service,
        title="长规则",
        text=("前置经营背景。" * 900) + "超长末尾检索锚点要求保留三周需求。",
    )

    match = service.lookup("超长末尾检索锚点")[0]

    assert "超长末尾检索锚点" in match.quote
    assert len(match.quote) <= 1600
    assert match.quote.startswith("…")


def test_reindex_replaces_old_generation_in_lookup(monkeypatch, tmp_path: Path) -> None:
    service = _service(monkeypatch, tmp_path)
    document = seed_knowledge_text(service, title="规则", text="旧规则要求使用四周销量。")

    replacement = seed_knowledge_text(service,
        title="规则",
        text="新规则要求使用三周销量。",
        document_id=document.id,
    )

    assert service.lookup("四周") == []
    matches = service.lookup("三周")
    assert len(matches) == 1
    assert matches[0].document_generation_id == replacement.canonical_generation_id


def test_document_filter_limits_lookup(monkeypatch, tmp_path: Path) -> None:
    service = _service(monkeypatch, tmp_path)
    first = seed_knowledge_text(service, title="甲", text="会员日活动毛利率达标。")
    second = seed_knowledge_text(service, title="乙", text="直播活动毛利率偏低。")

    matches = service.lookup("毛利率", document_ids=[second.id])

    assert [match.document_id for match in matches] == [second.id]
    assert first.id not in {match.document_id for match in matches}


def test_library_scope_is_enforced_by_keyword_and_final_candidate_resolution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    semantic = _SemanticSearch()
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    global_document = seed_knowledge_text(service,
        title="全局规则",
        text="雨具采用三周平均需求。",
    )
    private_document = seed_knowledge_text(service,
        title="隔离规则",
        text="雨具采用五周平均需求。",
        library_id="future-library",
    )
    global_unit = service.lookup("雨具", library_id="global")[0]
    private_unit = service.lookup("雨具", library_id="future-library")[0]

    assert [match.document_id for match in service.lookup("雨具", library_id="global")] == [
        global_document.id
    ]
    assert [
        match.document_id
        for match in service.lookup("雨具", library_id="future-library")
    ] == [private_document.id]

    semantic.unit_ids = [private_unit.unit_id, global_unit.unit_id]
    result = service.retrieve("补货周期", mode="semantic", library_id="global")

    assert [match.document_id for match in result.matches] == [global_document.id]


def test_semantic_mode_recovers_a_lexical_miss(monkeypatch, tmp_path: Path) -> None:
    semantic = _SemanticSearch()
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service,
        title="运营指引",
        text="防水出行品类按照最近三期周均销量设定目标量，并扣减现存数量。",
    )
    unit = service.lookup("防水出行")[0]
    semantic.unit_ids = [unit.unit_id]

    assert service.lookup("雨季商品补货规则") == []
    result = service.retrieve("雨季商品补货规则", mode="semantic")

    assert result.mode == "semantic"
    assert [match.unit_id for match in result.matches] == [unit.unit_id]
    assert semantic.calls == [("雨季商品补货规则", "global", 20)]


def test_hybrid_rrf_rewards_evidence_found_by_both_legs(monkeypatch, tmp_path: Path) -> None:
    semantic = _SemanticSearch()
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    exact = seed_knowledge_text(service, title="精确政策", text="雨具安全库存采用三周需求。")
    related = seed_knowledge_text(service, title="相关经验", text="降水季节应提前准备防水商品。")
    exact_unit = service.lookup("三周需求", document_ids=[exact.id])[0]
    related_unit = service.lookup("防水商品", document_ids=[related.id])[0]
    semantic.unit_ids = [related_unit.unit_id, exact_unit.unit_id]

    result = service.retrieve("雨具三周需求", mode="hybrid", top_k=2)

    assert result.mode == "hybrid"
    assert [match.unit_id for match in result.matches] == [
        exact_unit.unit_id,
        related_unit.unit_id,
    ]


def test_hybrid_keeps_a_result_when_only_one_ranker_finds_it(monkeypatch, tmp_path: Path) -> None:
    semantic = _SemanticSearch()
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="经验", text="防水出行品按三期周均销量备货。")
    unit = service.lookup("防水出行")[0]
    semantic.unit_ids = [unit.unit_id]

    semantic_only = service.retrieve("雨季补货策略", mode="hybrid")
    semantic.unit_ids = []
    keyword_only = service.retrieve("防水出行", mode="hybrid")

    assert [match.unit_id for match in semantic_only.matches] == [unit.unit_id]
    assert [match.unit_id for match in keyword_only.matches] == [unit.unit_id]


def test_auto_falls_back_honestly_but_explicit_semantic_does_not(
    monkeypatch,
    tmp_path: Path,
) -> None:
    semantic = _SemanticSearch()
    semantic.error = KnowledgeSemanticUnavailable()
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="规则", text="雨具补货使用三周需求。")

    automatic = service.retrieve("雨具补货", mode="auto")

    assert automatic.mode == "keyword"
    assert len(automatic.matches) == 1
    with pytest.raises(KnowledgeRetrievalUnavailable) as error:
        service.retrieve("雨具补货", mode="semantic")
    assert error.value.available_modes == ["keyword"]


def test_disabled_semantic_search_never_runs_for_auto(monkeypatch, tmp_path: Path) -> None:
    semantic = _SemanticSearch(configured=False)
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="规则", text="雨具补货使用三周需求。")

    result = service.retrieve("雨具补货", mode="auto")

    assert result.mode == "keyword"
    assert semantic.calls == []


def test_unexpected_configuration_failure_is_not_silently_downgraded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    semantic = _SemanticSearch()
    semantic.configuration_error = RuntimeError("invalid private setting")
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="规则", text="雨具补货使用三周需求。")

    with pytest.raises(RuntimeError, match="invalid private setting"):
        service.retrieve("雨具补货", mode="auto")
    with pytest.raises(RuntimeError, match="invalid private setting"):
        service.retrieve("雨具补货", mode="semantic")
    assert semantic.calls == []


def test_candidate_snapshot_change_falls_back_only_for_auto(monkeypatch, tmp_path: Path) -> None:
    semantic = _SemanticSearch()
    semantic.current = False
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="规则", text="雨具补货使用三周需求。")
    semantic.unit_ids = [service.lookup("三周需求")[0].unit_id]

    automatic = service.retrieve("雨具补货", mode="auto")

    assert automatic.mode == "keyword"
    with pytest.raises(KnowledgeRetrievalUnavailable):
        service.retrieve("雨具补货", mode="semantic")
    assert semantic.current_checks == [
        ("fake-corpus", "global"),
        ("fake-corpus", "global"),
    ]


def test_unexpected_semantic_search_failure_is_not_silently_downgraded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    semantic = _SemanticSearch()
    semantic.error = RuntimeError("programming defect")
    service = _service(monkeypatch, tmp_path, semantic_search=semantic)
    seed_knowledge_text(service, title="规则", text="雨具补货使用三周需求。")

    with pytest.raises(RuntimeError, match="programming defect"):
        service.retrieve("雨具补货", mode="auto")
