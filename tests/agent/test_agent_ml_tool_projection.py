from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import (
    ArtifactService,
    RegisterArtifactInput,
    build_artifact_uri,
)
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ArtifactKind


_FIXTURE_ROOT = FIXTURES_ROOT / "ml_foundation"
_TRAIN_FIXTURE = _FIXTURE_ROOT / "grouped_lifecycle_v1.csv"
_APPLY_FIXTURE = _FIXTURE_ROOT / "grouped_lifecycle_apply_v1.csv"


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


def test_agent_ml_tools_project_bounded_evidence_and_real_apply_identity(
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
            source_path=str(_TRAIN_FIXTURE.resolve()),
            name="Grouped customer lifecycle",
        )
    )
    apply_dataset = datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(_APPLY_FIXTURE.resolve()),
            project_id=training_dataset.project_id,
            name="New customer scoring batch",
        )
    )
    context = ToolExecutionContext(
        thread_id="foundation-agent-ml-projection",
        dataset_ids=(training_dataset.id, apply_dataset.id),
    )

    binding_outcome = tools.execute(
        "data.feature.select",
        {
            "dataset_id": training_dataset.id,
            "model_key": "classification.logistic_regression",
            "role_bindings": [
                {
                    "role": "feature",
                    "columns": [
                        "orders_30d",
                        "avg_response_hours",
                        "support_tickets",
                        "plan_tier",
                    ],
                },
                {"role": "target", "columns": ["will_churn"]},
                {"role": "group", "columns": ["customer_id"]},
            ],
        },
        context,
    )
    binding_id = binding_outcome.value["binding_id"]

    train_outcome = tools.execute(
        "model.train",
        {
            "binding_id": binding_id,
            "models": ["classification.logistic_regression"],
            "run_name": "Grouped churn risk",
        },
        context,
    )
    assert train_outcome.value["async_state"] == "completed"
    trained_model = train_outcome.value["trained_models"][0]
    assert trained_model["dataset_id"] == training_dataset.id
    assert trained_model["training_scope"] == {
        "evaluation_model": "holdout_train_split",
        "apply_model": "all_eligible_rows",
    }
    assert trained_model["evaluation_facts_authority"] == "ml_task_result"
    evaluation_task_id = trained_model["evaluation_task_id"]

    query_outcome = tools.execute(
        "model.task.query",
        {
            "task_ids": train_outcome.value["task_ids"],
            "include_logs": True,
            "max_log_entries": 50,
        },
        context,
    )
    evaluation_task = next(
        task
        for task in query_outcome.value["tasks"]
        if task["task_id"] == evaluation_task_id
    )
    evaluation = evaluation_task["result"]
    assert evaluation["split_facts"]["realized_strategy"] == "group_hash_holdout.v1"
    assert evaluation["split_facts"]["group_overlap_count"] == 0
    assert evaluation["preparation_facts"]["fit_scope"] == "outer_train_split"
    assert evaluation["comparison"]["verdict"] in {
        "candidate_better",
        "baseline_better",
        "tied",
    }
    assert len(evaluation["evaluation"]["prediction_digest"]) == 64
    assert len(evaluation["baseline_evaluation"]["prediction_digest"]) == 64
    report = next(
        artifact
        for artifact in evaluation_task["artifacts"]
        if artifact["artifact_kind"] == "evaluation_report"
    )
    assert report["ready_to_open"] is True
    assert "ml_task_artifact_id" in report

    serialized_projection = json.dumps(query_outcome.value, sort_keys=True)
    assert str(paths.home) not in serialized_projection
    assert "absolute_path" not in serialized_projection
    assert "artifact_path" not in serialized_projection
    assert "preview_rows" not in serialized_projection
    assert "confusion_matrix" not in serialized_projection

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
    result_dataset = datasets.get_dataset(apply_outcome.value["result_dataset_id"])
    assert result_dataset.derived_from_dataset_id == apply_dataset.id
    resolved_apply_artifact = artifacts.resolve_uri(
        build_artifact_uri(apply_outcome.value["artifact_id"])
    )
    assert resolved_apply_artifact.metadata_payload["training_dataset_id"] == training_dataset.id
    assert resolved_apply_artifact.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
    assert resolved_apply_artifact.metadata_payload["source_artifact_ids"] == []

    apply_query = tools.execute(
        "model.task.query",
        {"task_ids": [apply_outcome.value["ml_task_id"]]},
        context,
    ).value["tasks"][0]
    assert apply_query["request"]["input_sources"] == [
        {
            "source_kind": "user_file",
            "dataset_id": apply_dataset.id,
        }
    ]
    assert apply_query["result"]["source_dataset_ids"] == [apply_dataset.id]
    assert apply_query["result"]["result_dataset_id"] == result_dataset.id
    assert "absolute_path" not in json.dumps(apply_query, sort_keys=True)

    source_artifact = artifacts.register_artifact(
        RegisterArtifactInput(
            title="External scoring file",
            absolute_path=str(_APPLY_FIXTURE.resolve()),
            kind=ArtifactKind.DATASET,
            mime_type="text/csv",
        )
    )
    artifact_apply = tools.execute(
        "model.apply",
        {
            "trained_model_id": trained_model["trained_model_id"],
            "input_sources": [build_artifact_uri(source_artifact.id)],
        },
        context,
    ).value
    assert artifact_apply["source_dataset_ids"] == []
    assert artifact_apply["source_artifact_ids"] == [source_artifact.id]
    artifact_result_dataset = datasets.get_dataset(artifact_apply["result_dataset_id"])
    assert artifact_result_dataset.derived_from_dataset_id is None
    storage.engine.dispose()
