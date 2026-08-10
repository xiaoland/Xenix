from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


FIXTURES = Path(__file__).parent / "fixtures" / "ml_cf_service"
TRAIN_PATH = FIXTURES / "segment_train.csv"
APPLY_PATH = FIXTURES / "segment_apply.csv"
FEATURES = [
    "visits_90d",
    "avg_order_value",
    "return_rate",
    "channel",
    "entity_id",
]


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


def test_agent_clustering_projection_is_bounded_private_and_lineage_truthful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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

    training_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(TRAIN_PATH.resolve()),
            name="Segment training fixture",
        )
    )
    apply_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(APPLY_PATH.resolve()),
            project_id=training_dataset.project_id,
            name="Unseen category segment fixture",
        )
    )
    context = ToolExecutionContext(
        thread_id="offline-agent-clustering-projection",
        dataset_ids=(training_dataset.id, apply_dataset.id),
    )

    binding_outcome = tools.execute(
        "data.feature.select",
        {
            "dataset_id": training_dataset.id,
            "model_key": "clustering.kmeans",
            "role_bindings": [{"role": "feature", "columns": FEATURES}],
        },
        context,
    )
    binding_id = binding_outcome.value["binding_id"]

    train_outcome = tools.execute(
        "model.train",
        {
            "binding_id": binding_id,
            "models": ["clustering.kmeans"],
            "params_by_model": {
                "clustering.kmeans": {
                    "n_clusters": 3,
                    "n_init": 20,
                    "max_iter": 300,
                    "random_state": 42,
                }
            },
            "run_name": "Bounded clustering projection",
        },
        context,
    )
    assert train_outcome.value["async_state"] == "completed"
    trained_model = train_outcome.value["trained_models"][0]
    assert trained_model["model_key"] == "clustering.kmeans"
    assert trained_model["supports_evaluation"] is True
    assert trained_model["supports_apply"] is True
    assert trained_model["apply_mode"] == "rows"

    query_outcome = tools.execute(
        "model.task.query",
        {
            "task_ids": train_outcome.value["task_ids"],
            "include_logs": True,
            "max_log_entries": 50,
        },
        context,
    )
    queried_tasks = query_outcome.value["tasks"]
    fit_task = next(task for task in queried_tasks if task["task_type"] == "fit")
    evaluation_task = next(
        task for task in queried_tasks if task["task_type"] == "evaluate"
    )

    assignment_dataset_id = fit_task["result"]["result_dataset_id"]
    assert assignment_dataset_id
    assignment_dataset = datasets.get_dataset(assignment_dataset_id)
    assert assignment_dataset.derived_from_dataset_id == training_dataset.id
    fit_report = next(
        artifact
        for artifact in fit_task["artifacts"]
        if artifact["artifact_kind"] == "training_report"
    )
    assert fit_report["ready_to_open"] is True
    assert fit_report["artifact_id"]

    evaluation = evaluation_task["result"]
    clustering = evaluation["clustering_evaluation"]
    assert clustering["protocol"] == "clustering_trustworthiness.v1"
    assert clustering["quality"]["cluster_count"] == 3
    assert clustering["quality"]["evaluated_row_count"] == 78
    assert clustering["stability"]["run_count"] == 5
    assert len(clustering["stability"]["seeds"]) == 5
    assert clustering["null_baseline"]["run_count"] == 16
    assert clustering["size_fact_count"] == len(clustering["sizes"])
    assert clustering["profile_count"] == len(clustering["profiles"])
    assert len(clustering["sizes"]) <= 24
    assert len(clustering["profiles"]) <= 12
    assert all(len(profile["numeric"]) <= 12 for profile in clustering["profiles"])
    assert all(len(profile["categorical"]) <= 12 for profile in clustering["profiles"])
    assert clustering["label_map"]["entry_count"] == len(
        clustering["label_map"]["entries"]
    )
    entity_profiles = [
        fact
        for profile in clustering["profiles"]
        for fact in profile["categorical"]
        if fact["feature"] == "entity_id"
    ]
    channel_profiles = [
        fact
        for profile in clustering["profiles"]
        for fact in profile["categorical"]
        if fact["feature"] == "channel"
    ]
    assert entity_profiles
    assert all(fact["value_suppressed"] is True for fact in entity_profiles)
    assert all(fact["top_value"] is None for fact in entity_profiles)
    assert all(fact["top_value_share"] is None for fact in entity_profiles)
    assert all(
        fact["suppression_reason"] == "high_cardinality_identifier_like"
        for fact in entity_profiles
    )
    assert channel_profiles
    assert all(fact["value_suppressed"] is False for fact in channel_profiles)
    assert all(fact["top_value"] for fact in channel_profiles)

    evaluation_report = next(
        artifact
        for artifact in evaluation_task["artifacts"]
        if artifact["artifact_kind"] == "evaluation_report"
    )
    assert evaluation_report["ready_to_open"] is True
    assert evaluation_report["artifact_id"]

    apply_outcome = tools.execute(
        "model.apply",
        {
            "trained_model_id": trained_model["trained_model_id"],
            "input_sources": [apply_dataset.id],
        },
        context,
    )
    assert apply_outcome.value["async_state"] == "completed"
    assert apply_outcome.value["training_dataset_id"] == training_dataset.id
    assert apply_outcome.value["source_dataset_ids"] == [apply_dataset.id]
    assert apply_outcome.value["source_artifact_ids"] == []
    assert apply_outcome.value["result_dataset_id"]
    assert apply_outcome.value["artifact_id"]
    apply_result_dataset = datasets.get_dataset(apply_outcome.value["result_dataset_id"])
    assert apply_result_dataset.derived_from_dataset_id == apply_dataset.id
    resolved_apply = artifacts.resolve_uri(
        build_artifact_uri(apply_outcome.value["artifact_id"])
    )
    assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
    assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
    assert resolved_apply.metadata_payload["result_dataset_id"] == apply_result_dataset.id

    apply_query = tools.execute(
        "model.task.query",
        {"task_ids": [apply_outcome.value["ml_task_id"]]},
        context,
    ).value["tasks"][0]
    assert apply_query["request"]["input_sources"] == [
        {"source_kind": "user_file", "dataset_id": apply_dataset.id}
    ]
    assert apply_query["result"]["result_dataset_id"] == apply_result_dataset.id
    assert apply_query["result"]["source_dataset_ids"] == [apply_dataset.id]

    serialized_projection = json.dumps(
        {
            "binding": binding_outcome.value,
            "training": train_outcome.value,
            "query": query_outcome.value,
            "apply": apply_outcome.value,
            "apply_query": apply_query,
        },
        sort_keys=True,
    )
    assert str(paths.home) not in serialized_projection
    assert "absolute_path" not in serialized_projection
    assert "source_path" not in serialized_projection
    assert "artifact_path" not in serialized_projection
    assert "preview_rows" not in serialized_projection
    assert "raw_rows" not in serialized_projection
    assert "E001" not in serialized_projection
    assert "E078" not in serialized_projection
    assert "A001" not in serialized_projection
    assert "A009" not in serialized_projection
    storage.engine.dispose()
