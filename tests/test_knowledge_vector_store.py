from hashlib import sha256
import json
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_vector_store import (
    KnowledgeVectorRecord,
    KnowledgeVectorStoreError,
    LanceKnowledgeVectorStore,
)
from xenix.services.storage.layout import knowledge_indexes_root, knowledge_staging_root

_CORPUS_FINGERPRINT = "1" * 64
_OTHER_CORPUS_FINGERPRINT = "2" * 64
_PROFILE_FINGERPRINT = "a" * 64
_OTHER_PROFILE_FINGERPRINT = "b" * 64


def _store(monkeypatch, tmp_path: Path) -> tuple[LanceKnowledgeVectorStore, object]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    return LanceKnowledgeVectorStore(paths), paths


def _unit_ids_digest(unit_ids: list[str]) -> str:
    digest = sha256(b"xenix.knowledge.unit-ids.v1\0")
    for unit_id in unit_ids:
        encoded = unit_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def test_lance_generation_is_atomically_published_reopened_and_searched(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, paths = _store(monkeypatch, tmp_path)

    relative_path = store.write_generation(
        generation_id="a" * 32,
        records=[
            KnowledgeVectorRecord("rainwear", (1.0, 0.0, 0.0)),
            KnowledgeVectorRecord("sunscreen", (0.0, 1.0, 0.0)),
        ],
        dimensions=3,
        corpus_fingerprint=_CORPUS_FINGERPRINT,
        profile_fingerprint=_PROFILE_FINGERPRINT,
    )

    assert relative_path == f"indexes/{'a' * 32}"
    assert not (knowledge_staging_root(paths) / f"vector-{'a' * 32}").exists()
    generation_path = knowledge_indexes_root(paths) / ("a" * 32)
    assert generation_path.is_dir()
    manifest_bytes = (generation_path / "manifest.json").read_bytes()
    assert len(manifest_bytes) <= 4_096
    assert json.loads(manifest_bytes) == {
        "schema_version": 1,
        "generation_id": "a" * 32,
        "corpus_fingerprint": _CORPUS_FINGERPRINT,
        "profile_fingerprint": _PROFILE_FINGERPRINT,
        "dimensions": 3,
        "unit_count": 2,
        "unit_ids_sha256": _unit_ids_digest(["rainwear", "sunscreen"]),
    }
    assert store.generation_is_usable(
        relative_path,
        expected_generation_id="a" * 32,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["rainwear", "sunscreen"],
        expected_count=2,
        expected_dimensions=3,
    )
    assert store.search(
        relative_path,
        query_vector=(0.95, 0.05, 0.0),
        limit=1,
    ) == ["rainwear"]


def test_lance_generation_rejects_bad_vectors_and_private_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, _paths = _store(monkeypatch, tmp_path)

    with pytest.raises(KnowledgeVectorStoreError):
        store.write_generation(
            generation_id="bad/generation",
            records=[KnowledgeVectorRecord("unit", (1.0, 0.0))],
            dimensions=2,
            corpus_fingerprint=_CORPUS_FINGERPRINT,
            profile_fingerprint=_PROFILE_FINGERPRINT,
        )
    with pytest.raises(KnowledgeVectorStoreError):
        store.write_generation(
            generation_id="b" * 32,
            records=[KnowledgeVectorRecord("unit", (float("nan"), 0.0))],
            dimensions=2,
            corpus_fingerprint=_CORPUS_FINGERPRINT,
            profile_fingerprint=_PROFILE_FINGERPRINT,
        )
    with pytest.raises(KnowledgeVectorStoreError):
        store.search("../../private", query_vector=(1.0, 0.0), limit=1)


def test_missing_generation_is_not_usable(monkeypatch, tmp_path: Path) -> None:
    store, _paths = _store(monkeypatch, tmp_path)

    assert not store.generation_is_usable(
        f"indexes/{'c' * 32}",
        expected_generation_id="c" * 32,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit"],
        expected_count=1,
        expected_dimensions=2,
    )


def test_generation_binding_rejects_wrong_same_shape_path_or_manifest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, paths = _store(monkeypatch, tmp_path)
    generation_id = "d" * 32
    records = [
        KnowledgeVectorRecord("unit-1", (1.0, 0.0)),
        KnowledgeVectorRecord("unit-2", (0.0, 1.0)),
    ]
    relative_path = store.write_generation(
        generation_id=generation_id,
        records=records,
        dimensions=2,
        corpus_fingerprint=_CORPUS_FINGERPRINT,
        profile_fingerprint=_PROFILE_FINGERPRINT,
    )

    assert not store.generation_is_usable(
        relative_path,
        expected_generation_id="e" * 32,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit-1", "unit-2"],
        expected_count=2,
        expected_dimensions=2,
    )
    assert not store.generation_is_usable(
        relative_path,
        expected_generation_id=generation_id,
        expected_corpus_fingerprint=_OTHER_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit-1", "unit-2"],
        expected_count=2,
        expected_dimensions=2,
    )

    manifest_path = knowledge_indexes_root(paths) / generation_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["profile_fingerprint"] = _OTHER_PROFILE_FINGERPRINT
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not store.generation_is_usable(
        relative_path,
        expected_generation_id=generation_id,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit-1", "unit-2"],
        expected_count=2,
        expected_dimensions=2,
    )


def test_generation_binding_checks_lance_unit_ids_even_with_forged_manifest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, paths = _store(monkeypatch, tmp_path)
    generation_id = "f" * 32
    relative_path = store.write_generation(
        generation_id=generation_id,
        records=[
            KnowledgeVectorRecord("wrong-1", (1.0, 0.0)),
            KnowledgeVectorRecord("wrong-2", (0.0, 1.0)),
        ],
        dimensions=2,
        corpus_fingerprint=_CORPUS_FINGERPRINT,
        profile_fingerprint=_PROFILE_FINGERPRINT,
    )
    manifest_path = knowledge_indexes_root(paths) / generation_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unit_ids_sha256"] = _unit_ids_digest(["unit-1", "unit-2"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert not store.generation_is_usable(
        relative_path,
        expected_generation_id=generation_id,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit-1", "unit-2"],
        expected_count=2,
        expected_dimensions=2,
    )


def test_failure_after_lance_open_removes_stage_and_allows_retry(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from lancedb.table import LanceTable

    store, paths = _store(monkeypatch, tmp_path)
    generation_id = "9" * 32
    original_count_rows = LanceTable.count_rows

    def fail_count_rows(self, *args, **kwargs):
        raise RuntimeError("injected count failure")

    monkeypatch.setattr(LanceTable, "count_rows", fail_count_rows)
    with pytest.raises(KnowledgeVectorStoreError) as failure:
        store.write_generation(
            generation_id=generation_id,
            records=[KnowledgeVectorRecord("unit", (1.0, 0.0))],
            dimensions=2,
            corpus_fingerprint=_CORPUS_FINGERPRINT,
            profile_fingerprint=_PROFILE_FINGERPRINT,
        )
    assert str(failure.value) == "Knowledge vector storage is unavailable."
    assert str(tmp_path) not in str(failure.value)

    stage = knowledge_staging_root(paths) / f"vector-{generation_id}"
    assert not stage.exists()
    monkeypatch.setattr(LanceTable, "count_rows", original_count_rows)

    relative_path = store.write_generation(
        generation_id=generation_id,
        records=[KnowledgeVectorRecord("unit", (1.0, 0.0))],
        dimensions=2,
        corpus_fingerprint=_CORPUS_FINGERPRINT,
        profile_fingerprint=_PROFILE_FINGERPRINT,
    )
    assert store.generation_is_usable(
        relative_path,
        expected_generation_id=generation_id,
        expected_corpus_fingerprint=_CORPUS_FINGERPRINT,
        expected_profile_fingerprint=_PROFILE_FINGERPRINT,
        expected_unit_ids=["unit"],
        expected_count=1,
        expected_dimensions=2,
    )
