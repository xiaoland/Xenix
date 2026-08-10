from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult, FitTaskResult
from xenix.services.ml.registry import get_model_catalog_entry, list_model_keys
from xenix.services.ml.types import ApplyMode, EvaluationKind, ModelFamily, ModelTaskKind
from xenix.services.ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus
from xenix.services.trained_model_metadata import parse_trained_model_metadata


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ml_text_discovery"
DISCOVERY_PATH = FIXTURE_ROOT / "bilingual_discovery_corpus_v1.csv"
RETRIEVAL_PATH = FIXTURE_ROOT / "bilingual_retrieval_twin_v1.csv"
APPLY_PATH = FIXTURE_ROOT / "bilingual_discovery_apply_v1.csv"

FIXTURE_SHA256 = {
    DISCOVERY_PATH.name: "5f6a6937cfc0fc7a37e1535c7cbfc02d2415486318b1a579c2df83bb8e0416d4",
    RETRIEVAL_PATH.name: "4042ae0f81e4ddf58c88992559fa67f7e42639a64732f4be72a217b7996b46cc",
    APPLY_PATH.name: "94ecdcf683357cd381e27f641daead9a84e710f3b15b285e8526e57977bd046b",
}

# These opaque labels are test-private truth. They deliberately do not occur in
# the registered source data and must never become a production training role.
_PRIVATE_THEMES = ("theta-river", "theta-lantern", "theta-garden")
_RELEVANCE_BY_THEME = dict(
    zip(_PRIVATE_THEMES, ("rel-01", "rel-02", "rel-03"), strict=True)
)

# Each family crosses business groups. Taken together with the business-group
# edges, the families create four components that each contain all three hidden
# themes. The final family includes the intentionally empty source document.
_TEMPLATE_FAMILIES = tuple(
    tuple(f"svc-doc-{base + theme_offset + 3 * group_offset:03d}" for group_offset in range(3))
    for base in (1, 10, 19, 28)
    for theme_offset in range(3)
)

_URL_PATTERN = re.compile(r"https?://[A-Za-z0-9.-]+(?:/[^\s；，]*)?")
_EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\b")
_NUMBER_PATTERN = re.compile(r"\b\d+\b")
_TOKEN_PATTERN = re.compile(r"[a-z]+|[\u4e00-\u9fff]")

_ACTIVE_CLUSTER_KEY = "text.clustering.multilingual_kmeans_tfidf"
_ACTIVE_TOPIC_KEY = "text.topic_modeling.multilingual_lda"
_ACTIVE_RETRIEVAL_KEY = "text.similarity.multilingual_tfidf_cosine"
_LEGACY_KEYS = {
    "text.clustering.kmeans_tfidf",
    "text.topic_modeling.lda",
    "text.similarity.tfidf_cosine",
}
_COMMON_PARAMS = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 5000,
    "custom_dictionary_dataset_ids": [],
    "stopword_dataset_ids": [],
}
_MODEL_CASES = (
    (
        _ACTIVE_CLUSTER_KEY,
        DISCOVERY_PATH,
        [
            {"role": "text", "columns": ["text"]},
            {"role": "group", "columns": ["business_group"]},
        ],
        {**_COMMON_PARAMS, "n_clusters": 3, "displayed_term_count": 6},
    ),
    (
        _ACTIVE_TOPIC_KEY,
        DISCOVERY_PATH,
        [
            {"role": "text", "columns": ["text"]},
            {"role": "group", "columns": ["business_group"]},
        ],
        {**_COMMON_PARAMS, "topic_count": 3, "displayed_term_count": 6},
    ),
    (
        _ACTIVE_RETRIEVAL_KEY,
        RETRIEVAL_PATH,
        [
            {"role": "text", "columns": ["text"]},
            {"role": "document_id", "columns": ["document_id"]},
            {"role": "relevance_group", "columns": ["relevance_group"]},
        ],
        {**_COMMON_PARAMS, "top_k": 5, "minimum_similarity": 0.0},
    ),
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _private_theme(document_id: str) -> str:
    ordinal = int(document_id.rsplit("-", maxsplit=1)[1])
    return _PRIVATE_THEMES[(ordinal - 1) % len(_PRIVATE_THEMES)]


def _fixture_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _URL_PATTERN.sub(" url ", normalized)
    normalized = _EMAIL_PATTERN.sub(" email ", normalized)
    normalized = _NUMBER_PATTERN.sub(" number ", normalized)
    return set(_TOKEN_PATTERN.findall(normalized))


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right)


def _connected_components(rows: list[dict[str, str]]) -> list[set[str]]:
    present_ids = {row["document_id"] for row in rows}
    adjacency: dict[str, set[str]] = defaultdict(set)

    by_business_group: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_business_group[row["business_group"]].append(row["document_id"])
    edge_groups = list(by_business_group.values()) + [
        [document_id for document_id in family if document_id in present_ids]
        for family in _TEMPLATE_FAMILIES
    ]
    for edge_group in edge_groups:
        for left, right in combinations(edge_group, 2):
            adjacency[left].add(right)
            adjacency[right].add(left)

    components: list[set[str]] = []
    remaining = set(present_ids)
    while remaining:
        frontier = [remaining.pop()]
        component: set[str] = set()
        while frontier:
            document_id = frontier.pop()
            component.add(document_id)
            unseen = adjacency[document_id] & remaining
            remaining.difference_update(unseen)
            frontier.extend(unseen)
        components.append(component)
    return components


class _InlineWorkerRunner:
    max_dispatch_threads = 1

    def run(
        self,
        entrypoint: Any,
        task_dir: Path,
        *,
        cancel_requested: Any | None = None,
    ) -> int:
        if cancel_requested is not None and cancel_requested():
            return -15
        entrypoint(str(task_dir))
        return 0


@dataclass
class _Runtime:
    storage: Any
    datasets: DatasetService
    tasks: MLTaskService
    ml: MLService
    artifacts: ArtifactService


@dataclass(frozen=True)
class _CompletedLifecycle:
    training_dataset: Any
    apply_dataset: Any
    fit_task: Any
    fit_payload: dict[str, Any]
    fit_result: FitTaskResult
    fit_frame: pd.DataFrame
    trained_model: Any
    evaluation_task_id: str
    evaluation: EvaluateTaskResult
    apply_task: Any
    apply_payload: dict[str, Any]
    apply_frame: pd.DataFrame
    registered_source_digests: dict[Path, str]


def _runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Runtime:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    return _Runtime(
        storage=storage,
        datasets=datasets,
        tasks=tasks,
        ml=MLService(paths, storage.session_factory, datasets, tasks),
        artifacts=ArtifactService(storage.session_factory),
    )


def _register(
    datasets: DatasetService,
    source: Path,
    *,
    project_id: str | None = None,
) -> Any:
    return datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            project_id=project_id,
            name=source.stem,
        )
    )


def _wait_for_terminal(
    tasks: MLTaskService,
    task_id: str,
    *,
    timeout: float = 60.0,
) -> Any:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        task = tasks.get_ml_task(task_id)
        if task.status in {
            MLTaskStatus.SUCCEEDED,
            MLTaskStatus.FAILED,
            MLTaskStatus.CANCELLED,
        }:
            return task
        sleep(0.02)
    raise AssertionError(f"ML task {task_id} did not finish within {timeout} seconds")


def _wait_for_evaluation_id(
    ml: MLService,
    trained_model_id: str,
    *,
    timeout: float = 60.0,
) -> str:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        trained_model = ml.get_trained_model(trained_model_id)
        metadata = parse_trained_model_metadata(
            trained_model.metadata_payload if trained_model is not None else None
        )
        if metadata is not None and metadata.evaluation_ml_task_id:
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("Text discovery model did not receive an evaluation task reference")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_prediction_digest(values: list[int | None]) -> str:
    canonical = [
        {"type": "null", "value": None}
        if value is None
        else {"type": "int", "value": int(value)}
        for value in values
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assert_public_artifact(
    runtime: _Runtime,
    task_id: str,
    artifact_kind: MLTaskArtifactKind,
) -> Any:
    artifact = next(
        item
        for item in runtime.tasks.list_ml_task_artifacts(task_id)
        if item.artifact_kind is artifact_kind
    )
    assert artifact.artifact_id
    assert runtime.artifacts.resolve_uri(build_artifact_uri(artifact.artifact_id)).exists is True
    return artifact


def _run_lifecycle(
    runtime: _Runtime,
    *,
    model_key: str,
    training_fixture: Path,
    role_bindings: list[dict[str, Any]],
    params: dict[str, Any],
) -> _CompletedLifecycle:
    training_dataset = _register(runtime.datasets, training_fixture)
    apply_dataset = _register(
        runtime.datasets,
        APPLY_PATH,
        project_id=training_dataset.project_id,
    )
    registered_source_digests = {
        Path(dataset.source_path): _sha256_file(Path(dataset.source_path))
        for dataset in (training_dataset, apply_dataset)
    }
    binding = runtime.ml.create_column_binding(
        CreateColumnBindingInput(
            dataset_id=training_dataset.id,
            model_key=model_key,
            role_bindings=role_bindings,
        )
    )
    fit_task = runtime.ml.fit_with_evaluate(
        FitWithEvaluateInput(
            binding_id=binding.id,
            run_name=f"Independent RT-T2 acceptance: {model_key}",
            model_key=model_key,
            params=params,
        )
    )
    completed_fit = _wait_for_terminal(runtime.tasks, fit_task.id)
    assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
    fit_payload = completed_fit.result_payload or {}
    fit_result = FitTaskResult.model_validate(fit_payload)
    fit_dataset = runtime.datasets.get_dataset(fit_payload["result_dataset_id"])
    assert fit_dataset.derived_from_dataset_id == training_dataset.id
    assert fit_dataset.ml_task_id == fit_task.id
    fit_frame = pd.read_parquet(fit_dataset.source_path)

    trained_model = runtime.ml.get_trained_model_by_ml_task(fit_task.id)
    assert trained_model is not None
    assert trained_model.dataset_id == training_dataset.id
    evaluation_task_id = _wait_for_evaluation_id(runtime.ml, trained_model.id)
    completed_evaluation = _wait_for_terminal(runtime.tasks, evaluation_task_id)
    assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, (
        completed_evaluation.error_summary
    )
    evaluation = EvaluateTaskResult.model_validate(completed_evaluation.result_payload)

    apply_task = runtime.ml.apply(
        ApplyWithFilesInput(
            trained_model_id=trained_model.id,
            input_sources=[
                ApplySourceInput(
                    source_path=apply_dataset.source_path,
                    dataset_id=apply_dataset.id,
                )
            ],
        )
    )
    completed_apply = _wait_for_terminal(runtime.tasks, apply_task.id)
    assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
    apply_payload = completed_apply.result_payload or {}
    apply_dataset_result = runtime.datasets.get_dataset(apply_payload["result_dataset_id"])
    assert apply_dataset_result.derived_from_dataset_id == apply_dataset.id
    assert apply_dataset_result.ml_task_id == apply_task.id
    apply_frame = pd.read_parquet(apply_dataset_result.source_path)

    _assert_public_artifact(runtime, fit_task.id, MLTaskArtifactKind.EXPORT_FILE)
    _assert_public_artifact(runtime, fit_task.id, MLTaskArtifactKind.TRAINING_REPORT)
    _assert_public_artifact(runtime, evaluation_task_id, MLTaskArtifactKind.EVALUATION_REPORT)
    apply_artifact = _assert_public_artifact(
        runtime,
        apply_task.id,
        MLTaskArtifactKind.APPLY_RESULT,
    )
    assert apply_artifact.ready_to_open is True
    resolved_apply = runtime.artifacts.resolve_uri(build_artifact_uri(apply_artifact.artifact_id))
    assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
    assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
    assert resolved_apply.metadata_payload["result_dataset_id"] == apply_dataset_result.id

    metadata = parse_trained_model_metadata(trained_model.metadata_payload)
    assert metadata is not None
    assert metadata.training_params == params
    assert metadata.supports_evaluation is True
    assert metadata.supports_apply is True
    assert metadata.apply_mode == ApplyMode.ROWS.value
    assert all(
        _sha256_file(path) == digest
        for path, digest in registered_source_digests.items()
    )
    return _CompletedLifecycle(
        training_dataset=training_dataset,
        apply_dataset=apply_dataset,
        fit_task=fit_task,
        fit_payload=fit_payload,
        fit_result=fit_result,
        fit_frame=fit_frame,
        trained_model=trained_model,
        evaluation_task_id=evaluation_task_id,
        evaluation=evaluation,
        apply_task=apply_task,
        apply_payload=apply_payload,
        apply_frame=apply_frame,
        registered_source_digests=registered_source_digests,
    )


def _assert_fact_privacy(*facts: Any) -> None:
    serialized = json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
    for forbidden in (
        "absolute_path",
        "source_path",
        "artifact_path",
        "svc-doc-",
        "svc-biz-",
        "svc-query-",
        "rel-01",
        "rel-02",
        "rel-03",
        ".example",
        "@example.com",
    ):
        assert forbidden not in serialized


def _assert_input_columns_preserved(output: pd.DataFrame, source: pd.DataFrame) -> None:
    # CSV export/finalization represents an empty string as Parquet null. Compare
    # the public tabular value semantics while keeping every non-empty byte exact.
    for column in source.columns:
        assert output[column].fillna("").astype(str).tolist() == (
            source[column].fillna("").astype(str).tolist()
        )


def _retrieval_diagnostics_oracle(
    result: pd.DataFrame,
    source: pd.DataFrame,
    *,
    query_position_column: str,
) -> dict[str, Any]:
    eligible_source = source.loc[source["text"].fillna("").astype(str).str.strip().ne("")].reset_index(
        drop=True
    )
    source_positions = {
        str(document_id): position
        for position, document_id in enumerate(eligible_source["document_id"].tolist())
    }
    safe_rows: list[list[int | float]] = []
    grouped_ranks: dict[int, list[int]] = defaultdict(list)
    grouped_matches: dict[int, list[str]] = defaultdict(list)
    self_violations = 0
    for row in result.to_dict(orient="records"):
        if query_position_column == "query_document_id":
            query_position = source_positions[str(row[query_position_column])]
            query_id = str(row[query_position_column])
        else:
            query_position = int(row[query_position_column]) - 1
            query_id = str(row["document_id"])
        matched_id = str(row["matched_document_id"])
        rank = int(row["rank"])
        grouped_ranks[query_position].append(rank)
        grouped_matches[query_position].append(matched_id)
        self_violations += int(query_id == matched_id)
        safe_rows.append(
            [
                query_position,
                source_positions[matched_id],
                rank,
                round(float(row["similarity"]), 12),
            ]
        )
    return {
        "indexed_document_count": len(eligible_source.index),
        "inspected_query_count": (
            len(eligible_source.index)
            if query_position_column == "query_document_id"
            else len(_read_rows(APPLY_PATH))
        ),
        "query_with_results_count": len(grouped_ranks),
        "maximum_effective_top_k": max(map(len, grouped_ranks.values()), default=0),
        "result_row_count": len(result.index),
        "self_match_violation_count": self_violations,
        "duplicate_match_violation_count": sum(
            len(values) - len(set(values)) for values in grouped_matches.values()
        ),
        "rank_sequence_violation_count": sum(
            ranks != list(range(1, len(ranks) + 1)) for ranks in grouped_ranks.values()
        ),
        "index_identity_digest": _json_digest(
            [
                hashlib.sha256(str(value).encode("utf-8")).hexdigest()
                for value in eligible_source["document_id"].tolist()
            ]
        ),
        "result_digest": _json_digest(safe_rows),
    }


def _retrieval_ranking_oracle(
    result: pd.DataFrame,
    source: pd.DataFrame,
    *,
    top_k: int,
) -> dict[str, Any]:
    eligible = source.loc[source["text"].fillna("").astype(str).str.strip().ne("")].reset_index(
        drop=True
    )
    relevance_by_id = dict(
        zip(eligible["document_id"], eligible["relevance_group"], strict=True)
    )
    by_query = {
        str(query_id): frame.sort_values("rank", kind="stable")
        for query_id, frame in result.groupby("query_document_id", sort=False)
    }
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    for query_id, query_group in relevance_by_id.items():
        relevant = {
            document_id
            for document_id, relevance_group in relevance_by_id.items()
            if document_id != query_id and relevance_group == query_group
        }
        if not relevant:
            continue
        ranked = by_query.get(query_id, pd.DataFrame())
        hits = (
            [int(str(value) in relevant) for value in ranked["matched_document_id"].tolist()[:top_k]]
            if not ranked.empty
            else []
        )
        recalls.append(sum(hits) / len(relevant))
        reciprocal_ranks.append(
            next((1.0 / rank for rank, hit in enumerate(hits, start=1) if hit), 0.0)
        )
        dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits, start=1))
        ideal = sum(
            1.0 / math.log2(rank + 1)
            for rank in range(1, min(len(relevant), top_k) + 1)
        )
        ndcgs.append(dcg / ideal if ideal else 0.0)
    return {
        "evaluated_query_count": len(recalls),
        "recall_at_k": sum(recalls) / len(recalls),
        "mrr_at_k": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "ndcg_at_k": sum(ndcgs) / len(ndcgs),
    }


def test_text_discovery_fixture_bytes_and_schema_are_frozen() -> None:
    for path in (DISCOVERY_PATH, RETRIEVAL_PATH, APPLY_PATH):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == FIXTURE_SHA256[path.name]

    discovery_rows = _read_rows(DISCOVERY_PATH)
    retrieval_rows = _read_rows(RETRIEVAL_PATH)
    apply_rows = _read_rows(APPLY_PATH)

    assert list(discovery_rows[0]) == ["document_id", "business_group", "text"]
    assert list(retrieval_rows[0]) == [
        "document_id",
        "business_group",
        "text",
        "relevance_group",
    ]
    assert list(apply_rows[0]) == ["document_id", "text"]
    assert len(discovery_rows) == len(retrieval_rows) == 36
    assert len(apply_rows) == 7
    assert len({row["document_id"] for row in discovery_rows}) == 36
    assert len({row["document_id"] for row in apply_rows}) == 7

    fixture_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (DISCOVERY_PATH, RETRIEVAL_PATH, APPLY_PATH)
    )
    assert not any(private_theme in fixture_text for private_theme in _PRIVATE_THEMES)
    assert not any(prefix in fixture_text for prefix in ("NOTE-", "ASK-", "CAMPUS-"))


def test_discovery_fixture_has_group_safe_cross_theme_components() -> None:
    rows = _read_rows(DISCOVERY_PATH)
    rows_by_id = {row["document_id"]: row for row in rows}

    business_group_counts = Counter(row["business_group"] for row in rows)
    assert business_group_counts == Counter({f"svc-biz-{index:02d}": 3 for index in range(1, 13)})

    themes_by_business_group: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        themes_by_business_group[row["business_group"]].add(_private_theme(row["document_id"]))
    assert all(themes == set(_PRIVATE_THEMES) for themes in themes_by_business_group.values())

    # This is a fixture-quality check, not the product's near-duplicate threshold.
    # It proves that entity/number masking leaves strong bilingual template overlap.
    for family in _TEMPLATE_FAMILIES:
        non_empty = [document_id for document_id in family if rows_by_id[document_id]["text"].strip()]
        assert len({rows_by_id[document_id]["business_group"] for document_id in family}) == 3
        assert len({_private_theme(document_id) for document_id in family}) == 1
        for left, right in combinations(non_empty, 2):
            assert _jaccard(
                _fixture_tokens(rows_by_id[left]["text"]),
                _fixture_tokens(rows_by_id[right]["text"]),
            ) >= 0.78

    all_components = _connected_components(rows)
    eligible_rows = [row for row in rows if row["text"].strip()]
    eligible_components = _connected_components(eligible_rows)

    assert sorted(map(len, all_components)) == [9, 9, 9, 9]
    assert sorted(map(len, eligible_components)) == [8, 9, 9, 9]
    assert all(
        {_private_theme(document_id) for document_id in component} == set(_PRIVATE_THEMES)
        for component in eligible_components
    )
    assert [row["document_id"] for row in rows if not row["text"].strip()] == ["svc-doc-036"]


def test_retrieval_twin_adds_only_admitted_opaque_relevance_truth() -> None:
    discovery_rows = _read_rows(DISCOVERY_PATH)
    retrieval_rows = _read_rows(RETRIEVAL_PATH)

    assert [
        {key: row[key] for key in ("document_id", "business_group", "text")}
        for row in retrieval_rows
    ] == discovery_rows
    assert Counter(row["relevance_group"] for row in retrieval_rows) == Counter(
        {"rel-01": 12, "rel-02": 12, "rel-03": 12}
    )
    assert all(
        row["relevance_group"] == _RELEVANCE_BY_THEME[_private_theme(row["document_id"])]
        for row in retrieval_rows
    )


def test_apply_fixture_covers_semantic_oov_and_empty_boundaries() -> None:
    rows = _read_rows(APPLY_PATH)
    by_id = {row["document_id"]: row["text"] for row in rows}

    assert [document_id for document_id, text in by_id.items() if not text.strip()] == [
        "svc-query-005",
        "svc-query-006",
    ]
    oov_text = by_id["svc-query-004"].casefold()
    assert all(token in oov_text for token in ("cryonebula", "xenoglyph", "量子果园"))
    masked_entity_text = by_id["svc-query-007"]
    assert "9090" in masked_entity_text
    assert "https://future.example" in masked_entity_text
    assert "unseen@example.com" in masked_entity_text


def test_active_catalog_is_raw_text_authority_without_removing_legacy_keys() -> None:
    keys = set(list_model_keys())
    assert {
        _ACTIVE_CLUSTER_KEY,
        _ACTIVE_TOPIC_KEY,
        _ACTIVE_RETRIEVAL_KEY,
        *_LEGACY_KEYS,
    } <= keys

    expected = {
        _ACTIVE_CLUSTER_KEY: (
            EvaluationKind.TEXT_CLUSTERING,
            ModelTaskKind.TEXT_ANALYZER,
            {"n_clusters", "displayed_term_count"},
        ),
        _ACTIVE_TOPIC_KEY: (
            EvaluationKind.TOPIC_MODELING,
            ModelTaskKind.TEXT_ANALYZER,
            {"topic_count", "displayed_term_count"},
        ),
        _ACTIVE_RETRIEVAL_KEY: (
            EvaluationKind.RETRIEVAL,
            ModelTaskKind.RETRIEVER,
            {"top_k", "minimum_similarity"},
        ),
    }
    common_params = {
        "preparation_profile",
        "phrase_mode",
        "max_features",
        "custom_dictionary_dataset_ids",
        "stopword_dataset_ids",
    }
    for model_key, (evaluation_kind, task_kind, specific_params) in expected.items():
        catalog = get_model_catalog_entry(model_key)
        assert catalog.model_family is ModelFamily.TEXT_ANALYSIS
        assert catalog.model_task_kind is task_kind
        assert catalog.evaluation_kind is evaluation_kind
        assert catalog.supports_evaluation is True
        assert catalog.supports_apply is True
        assert catalog.apply_mode is ApplyMode.ROWS
        assert catalog.supports_hyperparameter_tuning is False
        assert set(catalog.param_schema["properties"]) == common_params | specific_params


@pytest.mark.parametrize(
    ("model_key", "training_fixture", "role_bindings", "params"),
    _MODEL_CASES,
    ids=("clustering", "topic", "retrieval-with-truth"),
)
def test_active_text_discovery_real_lifecycles_are_recomputable_and_public(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    model_key: str,
    training_fixture: Path,
    role_bindings: list[dict[str, Any]],
    params: dict[str, Any],
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        completed = _run_lifecycle(
            runtime,
            model_key=model_key,
            training_fixture=training_fixture,
            role_bindings=role_bindings,
            params=params,
        )
        assert completed.fit_result.model_key == model_key
        assert completed.fit_result.params == params
        assert completed.evaluation.model_key == model_key
        assert completed.evaluation.baseline_evaluation is None
        assert completed.evaluation.comparison is None

        if model_key == _ACTIVE_CLUSTER_KEY:
            _assert_cluster_lifecycle(completed)
        elif model_key == _ACTIVE_TOPIC_KEY:
            _assert_topic_lifecycle(completed)
        else:
            _assert_retrieval_lifecycle(completed, relevance_truth=True)

        for path, digest in completed.registered_source_digests.items():
            assert _sha256_file(path) == digest
        assert all(
            _sha256_file(path) == FIXTURE_SHA256[path.name]
            for path in (DISCOVERY_PATH, RETRIEVAL_PATH, APPLY_PATH)
        )
    finally:
        runtime.storage.engine.dispose()


def _assert_cluster_lifecycle(completed: _CompletedLifecycle) -> None:
    source = pd.read_parquet(completed.training_dataset.source_path)
    assert completed.fit_frame.columns.tolist() == [*source.columns, "cluster_label"]
    _assert_input_columns_preserved(completed.fit_frame, source)
    eligible_mask = source["text"].fillna("").astype(str).str.strip().ne("")
    labels = [int(value) for value in completed.fit_frame.loc[eligible_mask, "cluster_label"]]
    facts = completed.fit_result.text_clustering_evaluation
    evaluated = completed.evaluation.text_clustering_evaluation
    assert facts is not None and evaluated is not None
    assert facts.model_dump(mode="json") == evaluated.model_dump(mode="json")
    assert facts.quality.assignment_digest == _canonical_prediction_digest(labels)

    counts = Counter(labels)
    expected_sizes = {
        label: (count, count / len(labels))
        for label, count in sorted(counts.items())
    }
    assert {
        item.cluster_label: (item.row_count, item.share)
        for item in facts.sizes
    } == expected_sizes
    assert facts.quality.realized_cluster_count == len(counts)
    assert facts.quality.minimum_cluster_share == pytest.approx(
        min(counts.values()) / len(labels)
    )
    assert facts.quality.maximum_cluster_share == pytest.approx(
        max(counts.values()) / len(labels)
    )
    assert facts.quality.degenerate_cluster_count == sum(
        count < 2 or count / len(labels) < 0.02 for count in counts.values()
    )
    assert facts.isolation.partition_group_overlap_count == 0
    assert facts.stability.resample_group_overlap_count == 0
    assert facts.stability.successful_run_count + facts.stability.failed_run_count == 5
    assert completed.evaluation.evaluation is not None
    assert completed.evaluation.evaluation.primary_metric_name == "cosine_silhouette"
    assert completed.evaluation.evaluation.primary_metric_value == pytest.approx(
        facts.quality.cosine_silhouette
    )
    assert completed.evaluation.evaluation.details["assignment_digest"] == (
        facts.quality.assignment_digest
    )

    apply_source = pd.read_parquet(completed.apply_dataset.source_path)
    assert completed.apply_frame.columns.tolist() == [*apply_source.columns, "cluster_label"]
    _assert_input_columns_preserved(completed.apply_frame, apply_source)
    apply_labels = [
        None if pd.isna(value) else int(value)
        for value in completed.apply_frame["cluster_label"].tolist()
    ]
    apply_facts = completed.apply_payload["text_clustering_apply_facts"]
    assert apply_facts["assigned_row_count"] == sum(value is not None for value in apply_labels)
    assert apply_facts["unassigned_row_count"] == sum(value is None for value in apply_labels)
    assert apply_facts["assignment_digest"] == _canonical_prediction_digest(apply_labels)
    assert apply_facts["stable_label_mapping_digest"] == (
        facts.stability.stable_label_mapping_digest
    )
    assert evaluated.stability.stable_label_mapping_digest == (
        facts.stability.stable_label_mapping_digest
    )
    assert completed.apply_payload["row_count"] == len(apply_source.index)
    assert completed.apply_payload["prediction_column_name"] == "cluster_label"
    _assert_fact_privacy(
        facts.model_dump(mode="json"),
        evaluated.model_dump(mode="json"),
        apply_facts,
    )


def _topic_profile_identity_digest(facts: Any) -> str:
    return _json_digest(
        [
            {
                "topic_label": profile.topic_label,
                "terms": [term.term for term in profile.top_terms],
            }
            for profile in facts.profiles
        ]
    )


def _assert_topic_output(
    output: pd.DataFrame,
    source: pd.DataFrame,
    *,
    topic_count: int,
) -> None:
    topic_columns = [f"topic_{index}_share" for index in range(1, topic_count + 1)]
    assert output.columns.tolist() == [
        *source.columns,
        "dominant_topic",
        "topic_score",
        *topic_columns,
    ]
    _assert_input_columns_preserved(output, source)
    eligible_mask = source["text"].fillna("").astype(str).str.strip().ne("")
    for position in output.index[eligible_mask]:
        shares = [float(output.at[position, column]) for column in topic_columns]
        dominant = int(output.at[position, "dominant_topic"])
        assert sum(shares) == pytest.approx(1.0)
        assert dominant == max(range(1, topic_count + 1), key=lambda label: shares[label - 1])
        assert float(output.at[position, "topic_score"]) == pytest.approx(max(shares))
    assert output.loc[~eligible_mask, ["dominant_topic", "topic_score", *topic_columns]].isna().all().all()


def _assert_topic_lifecycle(completed: _CompletedLifecycle) -> None:
    facts = completed.fit_result.text_topic_evaluation
    evaluated = completed.evaluation.text_topic_evaluation
    assert facts is not None and evaluated is not None
    assert facts.model_dump(mode="json") == evaluated.model_dump(mode="json")
    assert facts.topic_label_identity_digest == _topic_profile_identity_digest(facts)
    assert evaluated.topic_label_identity_digest == facts.topic_label_identity_digest
    assert facts.split.group_overlap_count == 0
    assert facts.isolation.partition_group_overlap_count == 0
    assert facts.split.train_row_count + facts.split.holdout_row_count == (
        facts.split.eligible_row_count
    )
    assert facts.quality.train_document_count == facts.split.train_row_count
    assert facts.quality.heldout_document_count == facts.split.holdout_row_count
    assert sum(item.dominant_document_count for item in facts.prevalence) == (
        facts.split.holdout_row_count
    )
    assert sum(item.mean_prevalence for item in facts.prevalence) == pytest.approx(1.0)
    assert facts.quality.heldout_perplexity > 0.0
    assert math.isfinite(facts.quality.heldout_perplexity)
    assert -1.0 <= facts.quality.mean_coherence <= 1.0
    assert 0.0 <= facts.quality.term_diversity <= 1.0
    assert facts.stability.successful_run_count + facts.stability.failed_run_count == 5
    assert completed.evaluation.evaluation is not None
    assert completed.evaluation.evaluation.primary_metric_name == "heldout_perplexity"
    assert completed.evaluation.evaluation.primary_metric_value == pytest.approx(
        facts.quality.heldout_perplexity
    )
    assert completed.evaluation.evaluation.details == {
        "dominant_topic_digest": facts.quality.dominant_topic_digest,
        "topic_label_identity_digest": facts.topic_label_identity_digest,
    }

    training_source = pd.read_parquet(completed.training_dataset.source_path)
    _assert_topic_output(completed.fit_frame, training_source, topic_count=3)
    apply_source = pd.read_parquet(completed.apply_dataset.source_path)
    _assert_topic_output(completed.apply_frame, apply_source, topic_count=3)
    apply_facts = completed.apply_payload["text_topic_apply_facts"]
    assert apply_facts["assigned_row_count"] == 5
    assert apply_facts["unassigned_row_count"] == 2
    assert apply_facts["topic_label_identity_digest"] == facts.topic_label_identity_digest
    assert completed.apply_payload["row_count"] == len(apply_source.index)
    assert completed.apply_payload["prediction_column_name"] == "dominant_topic"
    _assert_fact_privacy(
        facts.model_dump(mode="json"),
        evaluated.model_dump(mode="json"),
        apply_facts,
    )


def _assert_retrieval_lifecycle(
    completed: _CompletedLifecycle,
    *,
    relevance_truth: bool,
) -> None:
    fixed_columns = [
        "query_document_id",
        "query_text",
        "matched_document_id",
        "matched_text",
        "rank",
        "similarity",
    ]
    assert completed.fit_frame.columns.tolist() == fixed_columns
    facts = completed.fit_result.text_retrieval_evaluation
    evaluated = completed.evaluation.text_retrieval_evaluation
    assert facts is not None and evaluated is not None
    assert facts.model_dump(mode="json") == evaluated.model_dump(mode="json")
    training_source = pd.read_parquet(completed.training_dataset.source_path)
    diagnostics = _retrieval_diagnostics_oracle(
        completed.fit_frame,
        training_source,
        query_position_column="query_document_id",
    )
    for key, value in diagnostics.items():
        assert getattr(facts.diagnostics, key) == value
    assert facts.diagnostics.requested_top_k == 5

    raw_text_by_id = dict(
        zip(training_source["document_id"], training_source["text"], strict=True)
    )
    assert all(
        row["query_text"] == raw_text_by_id[row["query_document_id"]]
        and row["matched_text"] == raw_text_by_id[row["matched_document_id"]]
        for row in completed.fit_frame.to_dict(orient="records")
    )
    if relevance_truth:
        assert facts.mode == "relevance_evaluated"
        assert facts.ranking is not None
        ranking = _retrieval_ranking_oracle(
            completed.fit_frame,
            training_source,
            top_k=5,
        )
        assert facts.ranking.evaluated_query_count == ranking["evaluated_query_count"]
        assert facts.ranking.recall_at_k == pytest.approx(ranking["recall_at_k"])
        assert facts.ranking.mrr_at_k == pytest.approx(ranking["mrr_at_k"])
        assert facts.ranking.ndcg_at_k == pytest.approx(ranking["ndcg_at_k"])
        assert completed.evaluation.evaluation is not None
        assert completed.evaluation.evaluation.primary_metric_name == "ndcg_at_k"
        assert completed.evaluation.evaluation.primary_metric_value == pytest.approx(
            ranking["ndcg_at_k"]
        )
    else:
        assert facts.mode == "index_diagnostic"
        assert facts.ranking is None
        assert completed.evaluation.evaluation is None

    apply_source = pd.read_parquet(completed.apply_dataset.source_path)
    assert completed.apply_frame.columns.tolist() == [
        *apply_source.columns,
        "source_file",
        "input_row_number",
        "matched_document_id",
        "matched_text",
        "rank",
        "similarity",
    ]
    assert set(completed.apply_frame["source_file"]) == {
        Path(completed.apply_dataset.source_path).name
    }
    assert all("/" not in value and "\\" not in value for value in completed.apply_frame["source_file"])
    assert set(completed.apply_frame["input_row_number"]) <= {1, 2, 3, 4, 7}
    apply_diagnostics = _retrieval_diagnostics_oracle(
        completed.apply_frame,
        training_source,
        query_position_column="input_row_number",
    )
    apply_facts = completed.apply_payload["text_retrieval_apply_facts"]
    for key, value in apply_diagnostics.items():
        assert apply_facts["diagnostics"][key] == value
    assert apply_facts["diagnostics"]["requested_top_k"] == 5
    assert completed.apply_payload["prediction_column_name"] == "matched_document_id"
    _assert_fact_privacy(
        facts.model_dump(mode="json"),
        evaluated.model_dump(mode="json"),
        apply_facts,
    )


def test_retrieval_without_admitted_truth_publishes_only_index_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        completed = _run_lifecycle(
            runtime,
            model_key=_ACTIVE_RETRIEVAL_KEY,
            training_fixture=DISCOVERY_PATH,
            role_bindings=[
                {"role": "text", "columns": ["text"]},
                {"role": "document_id", "columns": ["document_id"]},
            ],
            params={**_COMMON_PARAMS, "top_k": 5, "minimum_similarity": 0.0},
        )
        _assert_retrieval_lifecycle(completed, relevance_truth=False)
    finally:
        runtime.storage.engine.dispose()


def test_exact_retrieval_rejects_more_than_two_thousand_source_rows_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    oversized_source = tmp_path / "oversized_retrieval.csv"
    oversized_source.write_text(
        "document_id,text\n"
        + "".join(
            f"boundary-{index},small boundary text {index}；边界文本 {index}\n"
            for index in range(2001)
        ),
        encoding="utf-8",
    )
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        dataset = _register(runtime.datasets, oversized_source)
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=dataset.id,
                model_key=_ACTIVE_RETRIEVAL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["text"]},
                    {"role": "document_id", "columns": ["document_id"]},
                ],
            )
        )
        with pytest.raises(
            ValidationError,
            match=r"supports at most 2,000 source rows in v1",
        ):
            runtime.ml.fit_with_evaluate(
                FitWithEvaluateInput(
                    binding_id=binding.id,
                    model_key=_ACTIVE_RETRIEVAL_KEY,
                    params={**_COMMON_PARAMS, "top_k": 5, "minimum_similarity": 0.0},
                )
            )
        assert runtime.ml.list_dataset_tasks(dataset.id) == []
    finally:
        runtime.storage.engine.dispose()
