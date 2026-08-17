from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


CLUSTER_KEY = "text.clustering.multilingual_kmeans_tfidf"
TOPIC_KEY = "text.topic_modeling.multilingual_lda"
RETRIEVAL_KEY = "text.similarity.multilingual_tfidf_cosine"
PRIVATE_SENTINEL = "rt-t2-sentinel@example.invalid"
CLUSTER_PARAMS = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 500,
    "n_clusters": 3,
    "displayed_term_count": 5,
    "custom_dictionary_dataset_ids": [],
    "stopword_dataset_ids": [],
}
TOPIC_PARAMS = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 500,
    "topic_count": 3,
    "displayed_term_count": 5,
    "custom_dictionary_dataset_ids": [],
    "stopword_dataset_ids": [],
}
RETRIEVAL_PARAMS = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 500,
    "top_k": 3,
    "minimum_similarity": 0.01,
    "custom_dictionary_dataset_ids": [],
    "stopword_dataset_ids": [],
}


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


def _write_independent_sources(tmp_path: Path) -> tuple[Path, Path, pd.DataFrame, pd.DataFrame]:
    themes = (
        ("rt-t2-private-relevance-cuisine", "aurora cuisine broth noodle 牛肉面 汤底"),
        ("rt-t2-private-relevance-service", "harbor service support patient 服务 热情"),
        ("rt-t2-private-relevance-delivery", "meteor delivery parcel timely 配送 包装"),
    )
    group_terms = (
        "acacia",
        "birch",
        "cedar",
        "dogwood",
        "elmwood",
        "firwood",
        "gingko",
        "hazel",
        "ironwood",
        "juniper",
        "kapok",
        "larch",
        "magnolia",
        "nutmeg",
        "oakwood",
        "poplar",
        "quince",
        "redwood",
    )
    rows: list[dict[str, str]] = []
    for theme_index, (relevance, theme_text) in enumerate(themes):
        for group_offset in range(6):
            group_index = theme_index * 6 + group_offset
            business_group = f"rt-t2-private-business-{group_index:02d}"
            group_term = group_terms[group_index]
            for side, qualifier in enumerate(("clear reliable", "focused consistent")):
                rows.append(
                    {
                        "document_id": f"rt-t2-private-document-{theme_index}-{group_offset}-{side}",
                        "business_group": business_group,
                        "relevance_group": relevance,
                        "text": (
                            f"{PRIVATE_SENTINEL} {theme_text} {group_term} {qualifier} "
                            f"independent observation {theme_index}-{group_offset}-{side}"
                        ),
                    }
                )
    training = pd.DataFrame(rows)
    apply = pd.DataFrame(
        [
            {
                "document_id": "rt-t2-private-apply-cuisine",
                "business_group": "rt-t2-private-apply-group-a",
                "relevance_group": "rt-t2-private-apply-relevance-a",
                "text": f"{PRIVATE_SENTINEL} aurora cuisine noodle broth 新鲜 牛肉面",
            },
            {
                "document_id": "rt-t2-private-apply-service",
                "business_group": "rt-t2-private-apply-group-b",
                "relevance_group": "rt-t2-private-apply-relevance-b",
                "text": f"{PRIVATE_SENTINEL} harbor patient support 服务 热情",
            },
            {
                "document_id": "rt-t2-private-apply-delivery",
                "business_group": "rt-t2-private-apply-group-c",
                "relevance_group": "rt-t2-private-apply-relevance-c",
                "text": f"{PRIVATE_SENTINEL} meteor timely parcel 配送 包装",
            },
        ]
    )
    source_dir = tmp_path / "independent-agent-text-discovery"
    source_dir.mkdir()
    training_path = source_dir / "private_discovery_training.csv"
    apply_path = source_dir / "private_discovery_apply.csv"
    training.to_csv(training_path, index=False)
    apply.to_csv(apply_path, index=False)
    return training_path, apply_path, training, apply


def _train_and_query(
    tools: AgentToolRegistry,
    context: ToolExecutionContext,
    *,
    dataset_id: str,
    model_key: str,
    role_bindings: list[dict[str, Any]],
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    binding = tools.execute(
        "data.feature.select",
        {
            "dataset_id": dataset_id,
            "model_key": model_key,
            "role_bindings": role_bindings,
        },
        context,
    ).value
    training = tools.execute(
        "model.train",
        {
            "binding_id": binding["binding_id"],
            "models": [model_key],
            "params_by_model": {model_key: params},
            "run_name": f"Independent projection {model_key}",
        },
        context,
    ).value
    assert training["async_state"] == "completed"
    query = tools.execute(
        "model.task.query",
        {"task_ids": training["task_ids"]},
        context,
    ).value
    return binding, training, query


def _task(query: dict[str, Any], task_type: str) -> dict[str, Any]:
    return next(task for task in query["tasks"] if task["task_type"] == task_type)


def _artifact_by_kind(task: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(artifact for artifact in task["artifacts"] if artifact["artifact_kind"] == kind)


def _assert_no_vocabulary_payload(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if "vocabulary" in str(key):
                assert key in {"vocabulary_digest", "out_of_vocabulary_row_count"}
                assert not isinstance(nested, (list, dict))
            _assert_no_vocabulary_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_vocabulary_payload(nested)


def test_agent_text_discovery_projection_is_typed_private_and_lineage_truthful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    training_path, apply_path, private_training, private_apply = _write_independent_sources(tmp_path)
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    task_service = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    ml = MLService(paths, storage.session_factory, datasets, task_service)
    artifacts = ArtifactService(storage.session_factory)
    tools = AgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=Mock(),
        data_transform_service=Mock(),
        ml_service=ml,
        artifact_service=artifacts,
    )

    try:
        training_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(training_path.resolve()),
                name="Independent raw text discovery corpus",
            )
        )
        apply_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(apply_path.resolve()),
                project_id=training_dataset.project_id,
                name="Independent raw text discovery apply batch",
            )
        )
        context = ToolExecutionContext(
            thread_id="agent-text-discovery-projection",
            dataset_ids=(training_dataset.id, apply_dataset.id),
        )

        family_metadata = tools.execute(
            "model.metadata",
            {"model_family": "text_analysis"},
            context,
        ).value
        assert {CLUSTER_KEY, TOPIC_KEY, RETRIEVAL_KEY} <= set(family_metadata["model_keys"])
        assert all("param_schema" not in model for model in family_metadata["models"])

        metadata: dict[str, dict[str, Any]] = {}
        expected = {
            CLUSTER_KEY: ("text_analyzer", "text_clustering", set(CLUSTER_PARAMS)),
            TOPIC_KEY: ("text_analyzer", "topic_modeling", set(TOPIC_PARAMS)),
            RETRIEVAL_KEY: ("retriever", "retrieval", set(RETRIEVAL_PARAMS)),
        }
        for model_key, (task_kind, evaluation_kind, param_names) in expected.items():
            detail_response = tools.execute(
                "model.metadata",
                {"model_key": model_key},
                context,
            ).value
            assert detail_response["model_keys"] == [model_key]
            detail = detail_response["models"][0]
            metadata[model_key] = detail_response
            assert detail["model_task_kind"] == task_kind
            assert detail["evaluation_kind"] == evaluation_kind
            assert detail["supports_evaluation"] is True
            assert detail["supports_apply"] is True
            assert detail["supports_hyperparameter_tuning"] is False
            assert detail["result_contract"] == {
                "train_result_kinds": ["model", "table", "metrics", "report"],
                "apply_result_kinds": ["table"],
                "preview_kinds": ["model", "table", "file"],
            }
            schema = detail["param_schema"]
            assert set(schema["properties"]) == param_names
            assert len(schema["properties"]) in {7, 8}
            assert all("properties" not in field for field in schema["properties"].values())

        topic_binding, topic_training, topic_query = _train_and_query(
            tools,
            context,
            dataset_id=training_dataset.id,
            model_key=TOPIC_KEY,
            role_bindings=[
                {"role": "text", "columns": ["text"]},
                {"role": "group", "columns": ["business_group"]},
            ],
            params=TOPIC_PARAMS,
        )
        topic_fit = _task(topic_query, "fit")
        topic_evaluate = _task(topic_query, "evaluate")
        topic_fit_facts = topic_fit["result"]["text_topic_evaluation"]
        topic_evaluation = topic_evaluate["result"]["text_topic_evaluation"]
        assert topic_binding["model_task_kind"] == "text_analyzer"
        assert topic_training["trained_models"][0]["training_scope"] == {
            "evaluation_model": "connected_group_train_split",
            "apply_model": "all_eligible_rows",
        }
        assert topic_fit_facts == topic_evaluation
        assert topic_evaluation["split"]["group_overlap_count"] == 0
        assert topic_evaluation["isolation"]["partition_group_overlap_count"] == 0
        assert topic_evaluation["quality"]["heldout_perplexity"] > 0
        assert topic_evaluation["stability"]["requested_run_count"] == 5
        assert len(topic_evaluation["topic_label_identity_digest"]) == 64
        assert len(topic_evaluation["profiles"]) == 3
        assert all(len(profile["top_terms"]) <= TOPIC_PARAMS["displayed_term_count"] for profile in topic_evaluation["profiles"])
        assert PRIVATE_SENTINEL not in json.dumps(topic_evaluation, ensure_ascii=False)
        assert "<email>" not in json.dumps(topic_evaluation, ensure_ascii=False)
        assert topic_evaluate["result"]["evaluation"]["primary_metric_name"] == "heldout_perplexity"

        topic_fit_dataset = datasets.get_dataset(topic_fit["result"]["result_dataset_id"])
        assert topic_fit_dataset.derived_from_dataset_id == training_dataset.id
        assert topic_fit_dataset.ml_task_id == topic_fit["task_id"]
        for task, artifact_kind in (
            (topic_fit, "training_report"),
            (topic_fit, "export_file"),
            (topic_evaluate, "evaluation_report"),
        ):
            public_artifact = _artifact_by_kind(task, artifact_kind)
            assert public_artifact["ready_to_open"] is True
            assert artifacts.resolve_uri(build_artifact_uri(public_artifact["artifact_id"])).exists is True

        topic_trained = topic_training["trained_models"][0]
        topic_apply = tools.execute(
            "model.apply",
            {
                "trained_model_id": topic_trained["trained_model_id"],
                "input_sources": [apply_dataset.id],
            },
            context,
        ).value
        assert topic_apply["async_state"] == "completed"
        assert topic_apply["source_dataset_ids"] == [apply_dataset.id]
        assert topic_apply["artifact_id"]
        topic_apply_dataset = datasets.get_dataset(topic_apply["result_dataset_id"])
        assert topic_apply_dataset.derived_from_dataset_id == apply_dataset.id
        assert topic_apply_dataset.ml_task_id == topic_apply["ml_task_id"]
        topic_apply_artifact = artifacts.resolve_uri(build_artifact_uri(topic_apply["artifact_id"]))
        assert topic_apply_artifact.metadata_payload["training_dataset_id"] == training_dataset.id
        assert topic_apply_artifact.metadata_payload["result_dataset_id"] == topic_apply_dataset.id
        topic_apply_query = tools.execute(
            "model.task.query",
            {"task_ids": [topic_apply["ml_task_id"]]},
            context,
        ).value["tasks"][0]
        topic_apply_facts = topic_apply_query["result"]["text_topic_apply_facts"]
        assert topic_apply["text_topic_apply_facts"] == topic_apply_facts
        assert (
            topic_apply_facts["topic_label_identity_digest"]
            == topic_evaluation["topic_label_identity_digest"]
        )
        assert topic_apply_facts["assigned_row_count"] == len(private_apply.index)

        cluster_binding, cluster_training, cluster_query = _train_and_query(
            tools,
            context,
            dataset_id=training_dataset.id,
            model_key=CLUSTER_KEY,
            role_bindings=[
                {"role": "text", "columns": ["text"]},
                {"role": "group", "columns": ["business_group"]},
            ],
            params=CLUSTER_PARAMS,
        )
        cluster_fit = _task(cluster_query, "fit")
        cluster_evaluate = _task(cluster_query, "evaluate")
        cluster_fit_facts = cluster_fit["result"]["text_clustering_evaluation"]
        cluster_evaluation = cluster_evaluate["result"]["text_clustering_evaluation"]
        assert cluster_binding["model_task_kind"] == "text_analyzer"
        assert cluster_fit_facts == cluster_evaluation
        cluster_label_identity = cluster_evaluation["stability"]["stable_label_mapping_digest"]
        assert len(cluster_label_identity) == 64
        assert cluster_evaluation["stability"]["requested_run_count"] == 5
        assert cluster_evaluation["stability"]["resample_group_overlap_count"] == 0
        assert PRIVATE_SENTINEL not in json.dumps(cluster_evaluation, ensure_ascii=False)
        cluster_fit_dataset = datasets.get_dataset(cluster_fit["result"]["result_dataset_id"])
        assert cluster_fit_dataset.derived_from_dataset_id == training_dataset.id

        cluster_apply = tools.execute(
            "model.apply",
            {
                "trained_model_id": cluster_training["trained_models"][0]["trained_model_id"],
                "input_sources": [apply_dataset.id],
            },
            context,
        ).value
        cluster_apply_query = tools.execute(
            "model.task.query",
            {"task_ids": [cluster_apply["ml_task_id"]]},
            context,
        ).value["tasks"][0]
        assert (
            cluster_apply_query["result"]["text_clustering_apply_facts"]["stable_label_mapping_digest"]
            == cluster_label_identity
        )
        cluster_apply_dataset = datasets.get_dataset(cluster_apply["result_dataset_id"])
        assert cluster_apply_dataset.derived_from_dataset_id == apply_dataset.id
        assert cluster_apply["artifact_id"]

        retrieval_roles = [
            {"role": "text", "columns": ["text"]},
            {"role": "document_id", "columns": ["document_id"]},
            {"role": "relevance_group", "columns": ["relevance_group"]},
        ]
        retrieval_binding, retrieval_training, retrieval_query = _train_and_query(
            tools,
            context,
            dataset_id=training_dataset.id,
            model_key=RETRIEVAL_KEY,
            role_bindings=retrieval_roles,
            params=RETRIEVAL_PARAMS,
        )
        retrieval_fit = _task(retrieval_query, "fit")
        retrieval_evaluate = _task(retrieval_query, "evaluate")
        retrieval_facts = retrieval_evaluate["result"]["text_retrieval_evaluation"]
        assert retrieval_binding["model_task_kind"] == "retriever"
        assert retrieval_facts["mode"] == "relevance_evaluated"
        assert retrieval_facts["ranking"] is not None
        assert set(retrieval_facts["ranking"]) >= {"recall_at_k", "mrr_at_k", "ndcg_at_k"}
        assert retrieval_facts["diagnostics"]["self_match_violation_count"] == 0
        assert retrieval_facts["diagnostics"]["duplicate_match_violation_count"] == 0
        assert retrieval_evaluate["result"]["evaluation"]["primary_metric_name"] == "ndcg_at_k"
        retrieval_fit_dataset = datasets.get_dataset(retrieval_fit["result"]["result_dataset_id"])
        assert retrieval_fit_dataset.derived_from_dataset_id == training_dataset.id
        assert retrieval_training["trained_models"][0]["evaluation_facts_authority"] == "ml_task_result"

        no_truth_binding, no_truth_training, no_truth_query = _train_and_query(
            tools,
            context,
            dataset_id=training_dataset.id,
            model_key=RETRIEVAL_KEY,
            role_bindings=[
                {"role": "text", "columns": ["text"]},
                {"role": "document_id", "columns": ["document_id"]},
            ],
            params=RETRIEVAL_PARAMS,
        )
        no_truth_evaluate = _task(no_truth_query, "evaluate")
        no_truth_facts = no_truth_evaluate["result"]["text_retrieval_evaluation"]
        assert no_truth_binding["model_task_kind"] == "retriever"
        assert no_truth_facts["mode"] == "index_diagnostic"
        assert no_truth_facts["ranking"] is None
        assert no_truth_evaluate["result"]["evaluation"] is None
        assert "recall_at_k" not in json.dumps(no_truth_query, sort_keys=True)
        no_truth_fit = _task(no_truth_query, "fit")
        no_truth_dataset = datasets.get_dataset(no_truth_fit["result"]["result_dataset_id"])
        assert no_truth_dataset.derived_from_dataset_id == training_dataset.id
        assert no_truth_training["trained_models"][0]["evaluation_kind"] == "retrieval"

        provider_projection = json.dumps(
            {
                "family_metadata": family_metadata,
                "metadata": metadata,
                "topic_binding": topic_binding,
                "topic_training": topic_training,
                "topic_query": topic_query,
                "topic_apply": topic_apply,
                "topic_apply_query": topic_apply_query,
                "cluster_binding": cluster_binding,
                "cluster_training": cluster_training,
                "cluster_query": cluster_query,
                "cluster_apply": cluster_apply,
                "cluster_apply_query": cluster_apply_query,
                "retrieval_binding": retrieval_binding,
                "retrieval_training": retrieval_training,
                "retrieval_query": retrieval_query,
                "no_truth_binding": no_truth_binding,
                "no_truth_training": no_truth_training,
                "no_truth_query": no_truth_query,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        forbidden = [
            str(paths.home),
            str(tmp_path),
            "absolute_path",
            "source_path",
            "artifact_path",
            "preview_rows",
            "raw_rows",
            PRIVATE_SENTINEL,
            *private_training["document_id"].astype(str).tolist(),
            *private_training["business_group"].astype(str).tolist(),
            *private_training["relevance_group"].astype(str).unique().tolist(),
            *private_training["text"].astype(str).tolist(),
            *private_apply["document_id"].astype(str).tolist(),
            *private_apply["business_group"].astype(str).tolist(),
            *private_apply["relevance_group"].astype(str).tolist(),
            *private_apply["text"].astype(str).tolist(),
        ]
        for value in forbidden:
            assert value not in provider_projection
        assert "<email>" not in provider_projection
        _assert_no_vocabulary_payload(
            {
                "topic_query": topic_query,
                "cluster_query": cluster_query,
                "retrieval_query": retrieval_query,
                "no_truth_query": no_truth_query,
                "topic_apply_query": topic_apply_query,
                "cluster_apply_query": cluster_apply_query,
            }
        )
    finally:
        storage.engine.dispose()
