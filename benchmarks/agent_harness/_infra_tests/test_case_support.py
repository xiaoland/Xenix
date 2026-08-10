from __future__ import annotations

from types import SimpleNamespace

from xenix.services.llm.messages import DatasetBlock

from benchmarks.agent_harness._infra.case_support import (
    registered_source_ids_for_digest,
    sha256_file,
    source_dataset_ids_for_external_digest,
)


def test_registered_source_identity_uses_complete_final_attachment_snapshot(tmp_path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_text("key\nfirst\n", encoding="utf-8")
    second_path.write_text("key\nsecond\n", encoding="utf-8")
    datasets = {
        "dataset-first": SimpleNamespace(source_path=str(first_path)),
        "dataset-second": SimpleNamespace(source_path=str(second_path)),
    }
    services = SimpleNamespace(
        datasets=SimpleNamespace(get_dataset=lambda dataset_id: datasets[dataset_id])
    )
    early_snapshot = _snapshot("dataset-first")
    final_snapshot = _snapshot("dataset-first", "dataset-second")

    assert registered_source_ids_for_digest(
        snapshot=early_snapshot,
        services=services,
        digest=sha256_file(second_path),
    ) == set()
    assert registered_source_ids_for_digest(
        snapshot=final_snapshot,
        services=services,
        digest=sha256_file(second_path),
    ) == {"dataset-second"}


def test_registered_source_identity_fails_closed_after_registered_copy_changes(tmp_path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text("key\noriginal\n", encoding="utf-8")
    original_digest = sha256_file(source_path)
    services = SimpleNamespace(
        datasets=SimpleNamespace(
            get_dataset=lambda _dataset_id: SimpleNamespace(source_path=str(source_path))
        )
    )
    snapshot = _snapshot("dataset-source")
    source_path.write_text("key\nchanged\n", encoding="utf-8")

    assert registered_source_ids_for_digest(
        snapshot=snapshot,
        services=services,
        digest=original_digest,
    ) == set()


def test_external_source_identity_survives_registered_parquet_materialization(tmp_path) -> None:
    external_path = tmp_path / "attached.csv"
    materialized_path = tmp_path / "registered.parquet"
    external_path.write_text("key\nsource\n", encoding="utf-8")
    materialized_path.write_bytes(b"PAR1-materialized-content")
    services = SimpleNamespace(
        datasets=SimpleNamespace(
            get_dataset=lambda _dataset_id: SimpleNamespace(
                source_path=str(materialized_path)
            ),
            resolve_dataset_source_presentation=lambda _dataset_id: SimpleNamespace(
                open_path=str(external_path)
            ),
        )
    )

    assert registered_source_ids_for_digest(
        snapshot=_snapshot("dataset-source"),
        services=services,
        digest=sha256_file(external_path),
    ) == set()
    assert source_dataset_ids_for_external_digest(
        snapshot=_snapshot("dataset-source"),
        services=services,
        digest=sha256_file(external_path),
    ) == {"dataset-source"}


def _snapshot(*dataset_ids: str) -> SimpleNamespace:
    blocks = [DatasetBlock(dataset_id=dataset_id).to_json() for dataset_id in dataset_ids]
    message = SimpleNamespace(
        kind="user",
        content_payload={"blocks": blocks},
    )
    return SimpleNamespace(messages=[message])
