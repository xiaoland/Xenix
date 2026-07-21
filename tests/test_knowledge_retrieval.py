from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_service import KnowledgeService
from xenix.services.storage import StorageBootstrapService


def _service(monkeypatch, tmp_path: Path) -> KnowledgeService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return KnowledgeService(context.session_factory)


def test_cjk_keyword_lookup_returns_bounded_source_linked_unit(monkeypatch, tmp_path: Path) -> None:
    service = _service(monkeypatch, tmp_path)
    document = service.index_plain_text(
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


def test_reindex_replaces_old_generation_in_lookup(monkeypatch, tmp_path: Path) -> None:
    service = _service(monkeypatch, tmp_path)
    document = service.index_plain_text(title="规则", text="旧规则要求使用四周销量。")

    replacement = service.index_plain_text(
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
    first = service.index_plain_text(title="甲", text="会员日活动毛利率达标。")
    second = service.index_plain_text(title="乙", text="直播活动毛利率偏低。")

    matches = service.lookup("毛利率", document_ids=[second.id])

    assert [match.document_id for match in matches] == [second.id]
    assert first.id not in {match.document_id for match in matches}
