from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


FIXTURE = FIXTURES_ROOT / "ml_cf_service" / "weekly_panel_v1.csv"


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


def test_agent_forecast_workflow_projects_bounded_evidence_and_public_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    ml = MLService(paths, storage.session_factory, datasets, tasks)
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
            source_path=str(FIXTURE.resolve()),
            name="Weekly regional demand",
        )
    )
    context = ToolExecutionContext(
        thread_id="agent-forecast-projection",
        dataset_ids=(training_dataset.id,),
    )

    binding = tools.execute(
        "data.feature.select",
        {
            "dataset_id": training_dataset.id,
            "model_key": "forecasting.holt_winters",
            "role_bindings": [
                {"role": "time", "column_indexes": [0]},
                {"role": "target", "column_indexes": [2]},
                {"role": "group", "column_indexes": [1]},
            ],
        },
        context,
    ).value
    assert binding["model_family"] == "forecasting"
    assert binding["model_task_kind"] == "forecaster"

    params = {
        "horizon": 4,
        "seasonal_period": 4,
        "frequency": "weekly",
        "interval_level": 0.8,
        "rolling_windows": 3,
        "damped_trend": False,
    }
    training = tools.execute(
        "model.train",
        {
            "binding_id": binding["binding_id"],
            "models": ["forecasting.holt_winters"],
            "params_by_model": {"forecasting.holt_winters": params},
            "run_name": "Weekly demand forecast",
        },
        context,
    ).value
    assert training["async_state"] == "completed"
    trained_model = training["trained_models"][0]
    assert trained_model["apply_mode"] == "future_horizon"
    assert trained_model["supports_evaluation"] is True
    assert trained_model["supports_apply"] is True
    assert trained_model["forecast_options"] == {
        "values": {
            "frequency": "weekly",
            "horizon": 4,
            "interval_level": 0.8,
            "rolling_windows": 3,
            "seasonal_period": 4,
        },
        "parameter_count": 5,
        "parameters_truncated": False,
    }
    assert trained_model["training_scope"] == {
        "evaluation_model": "chronological_training_prefixes",
        "apply_model": "all_observed_history",
    }
    assert trained_model["evaluation_facts_authority"] == "ml_task_result"

    query = tools.execute(
        "model.task.query",
        {"task_ids": training["task_ids"]},
        context,
    ).value
    evaluation_task = next(
        task for task in query["tasks"] if task["task_id"] == trained_model["evaluation_task_id"]
    )
    forecast = evaluation_task["result"]["forecast_evaluation"]
    assert forecast["split"]["policy_key"] == "rolling_origin.v1"
    assert forecast["split"]["rolling_windows"] == 3
    assert len(forecast["split"]["folds"]) == 3
    assert forecast["split"]["future_overlap_count"] == 0
    assert forecast["preparation"]["policy_key"] == "regular_forecast_panel.v1"
    assert forecast["preparation"]["group_count"] == 2
    assert len(forecast["per_group"]) == 2
    assert all(set(group) == {"group_index", "metrics", "baseline_metrics"} for group in forecast["per_group"])
    assert forecast["intervals"]["method"] == "residual_quantile.v1"
    assert forecast["intervals"]["coverage_guaranteed"] is False
    assert evaluation_task["result"]["comparison"]["primary_metric_name"] == "mae"
    evaluation_report = next(
        artifact
        for artifact in evaluation_task["artifacts"]
        if artifact["artifact_kind"] == "evaluation_report"
    )
    assert evaluation_report["ready_to_open"] is True
    assert evaluation_report["artifact_id"]
    assert artifacts.resolve_uri(build_artifact_uri(evaluation_report["artifact_id"])).exists is True

    projected_json = json.dumps(
        {"training": training, "query": query},
        sort_keys=True,
    )
    for forbidden in (
        "absolute_path",
        "source_path",
        "transcript",
        "north",
        "south",
    ):
        assert forbidden not in projected_json

    applied = tools.execute(
        "model.apply",
        {
            "trained_model_id": trained_model["trained_model_id"],
            "horizon": 4,
        },
        context,
    ).value
    assert applied["async_state"] == "completed"
    assert applied["training_dataset_id"] == training_dataset.id
    assert applied["source_dataset_ids"] == [training_dataset.id]
    assert applied["source_artifact_ids"] == []
    assert applied["row_count"] == 8
    result_dataset = datasets.get_dataset(applied["result_dataset_id"])
    assert result_dataset.derived_from_dataset_id == training_dataset.id
    resolved_apply = artifacts.resolve_uri(build_artifact_uri(applied["artifact_id"]))
    assert resolved_apply.exists is True
    assert resolved_apply.metadata_payload["result_dataset_id"] == result_dataset.id

    apply_query = tools.execute(
        "model.task.query",
        {"task_ids": [applied["ml_task_id"]]},
        context,
    ).value["tasks"][0]
    assert apply_query["request"]["forecast_horizon"] == 4
    assert apply_query["result"]["summary"] == {
        "row_count": 8,
        "input_file_count": 0,
        "prediction_column_name": "forecast",
        "apply_mode": "future_horizon",
        "horizon": 4,
        "group_count": 2,
    }
    assert apply_query["result"]["result_dataset_id"] == result_dataset.id
    assert "source_path" not in json.dumps(apply_query, sort_keys=True)

    with pytest.raises(ValidationError, match="exactly one input mode"):
        tools.execute(
            "model.apply",
            {
                "trained_model_id": trained_model["trained_model_id"],
                "input_rows": {
                    "header_index_map": {"orders": 0},
                    "data": [[1.0]],
                },
                "horizon": 4,
            },
            context,
        )

    storage.engine.dispose()
