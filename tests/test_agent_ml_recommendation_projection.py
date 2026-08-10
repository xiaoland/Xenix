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


MODEL_KEY = "recommendation.collaborative_top_k"
PARAMS = {
    "top_k": 3,
    "min_user_interactions": 4,
    "min_item_interactions": 2,
    "positive_rating_threshold": 4.0,
}
USER_VALUES = tuple(f"rt-r-private-member-{index:02d}" for index in range(8))
ITEM_VALUES = tuple(f"rt-r-private-offering-{index:02d}" for index in range(7))
COLD_USER = "rt-r-private-cold-member"


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


def _write_clean_room_sources(tmp_path: Path) -> tuple[Path, Path]:
    ratings = [5.0, 4.0, 2.0, 5.0, 4.5]
    interactions = [
        {
            "member_key": user,
            "offering_key": ITEM_VALUES[(user_index + offset) % len(ITEM_VALUES)],
            "preference": ratings[offset],
            "event_time": f"2026-02-{offset + 1:02d}T12:00:00Z",
        }
        for user_index, user in enumerate(USER_VALUES)
        for offset in range(5)
    ]
    source_dir = tmp_path / "clean-room-inputs"
    source_dir.mkdir()
    training_path = source_dir / "recommendation_training.csv"
    apply_path = source_dir / "recommendation_apply.csv"
    pd.DataFrame(interactions).to_csv(training_path, index=False)
    pd.DataFrame(
        {"member_key": [USER_VALUES[0], COLD_USER]}
    ).to_csv(apply_path, index=False)
    return training_path, apply_path


def _artifact_by_kind(task: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(
        artifact
        for artifact in task["artifacts"]
        if artifact["artifact_kind"] == kind
    )


def test_agent_recommendation_projection_is_bounded_private_and_lineage_truthful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    training_path, apply_path = _write_clean_room_sources(tmp_path)
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
                name="Clean-room recommendation history",
            )
        )
        apply_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(apply_path.resolve()),
                project_id=training_dataset.project_id,
                name="Known and cold recommendation users",
            )
        )
        context = ToolExecutionContext(
            thread_id="agent-recommendation-projection",
            dataset_ids=(training_dataset.id, apply_dataset.id),
        )

        family_metadata = tools.execute(
            "model.metadata",
            {"model_family": "recommendation"},
            context,
        ).value
        family_entry = next(
            model
            for model in family_metadata["models"]
            if model["model_key"] == MODEL_KEY
        )
        assert "param_schema" not in family_entry
        assert all("param_schema" not in model for model in family_metadata["models"])

        detail_metadata = tools.execute(
            "model.metadata",
            {"model_key": MODEL_KEY},
            context,
        ).value
        assert detail_metadata["model_keys"] == [MODEL_KEY]
        detail = detail_metadata["models"][0]
        assert detail["model_family"] == "recommendation"
        assert detail["model_task_kind"] == "recommender"
        assert detail["evaluation_kind"] == "ranking"
        assert detail["apply_mode"] == "rows"
        assert detail["supports_evaluation"] is True
        assert detail["supports_apply"] is True
        assert "param_grid_schema" not in detail
        param_schema = detail["param_schema"]
        assert param_schema["type"] == "object"
        assert set(param_schema["properties"]) == set(PARAMS)
        assert all(
            "properties" not in field_schema and "items" not in field_schema
            for field_schema in param_schema["properties"].values()
        )

        binding = tools.execute(
            "data.feature.select",
            {
                "dataset_id": training_dataset.id,
                "model_key": MODEL_KEY,
                "role_bindings": [
                    {"role": "user", "columns": ["member_key"]},
                    {"role": "item", "columns": ["offering_key"]},
                    {"role": "rating", "columns": ["preference"]},
                    {"role": "time", "columns": ["event_time"]},
                ],
            },
            context,
        ).value
        assert binding["dataset_id"] == training_dataset.id
        assert binding["model_family"] == "recommendation"
        assert binding["model_task_kind"] == "recommender"

        training = tools.execute(
            "model.train",
            {
                "binding_id": binding["binding_id"],
                "models": [MODEL_KEY],
                "params_by_model": {MODEL_KEY: PARAMS},
                "run_name": "Clean-room collaborative ranking",
            },
            context,
        ).value
        assert training["async_state"] == "completed"
        trained_model = training["trained_models"][0]
        assert trained_model["model_key"] == MODEL_KEY
        assert trained_model["dataset_id"] == training_dataset.id
        assert trained_model["evaluation_kind"] == "ranking"
        assert trained_model["apply_mode"] == "rows"
        assert trained_model["training_scope"] == {
            "evaluation_model": "per_user_holdout_training_interactions",
            "apply_model": "all_admitted_interactions",
        }
        assert trained_model["evaluation_facts_authority"] == "ml_task_result"

        query = tools.execute(
            "model.task.query",
            {"task_ids": training["task_ids"]},
            context,
        ).value
        fit_task = next(task for task in query["tasks"] if task["task_type"] == "fit")
        evaluation_task = next(
            task for task in query["tasks"] if task["task_type"] == "evaluate"
        )

        fit_result = fit_task["result"]
        split = fit_result["recommendation_split_facts"]
        preparation = fit_result["recommendation_preparation_facts"]
        assert split["policy_key"] == "latest_positive_per_user.v1"
        assert split["eligible_user_count"] == len(USER_VALUES)
        assert split["holdout_interaction_count"] == len(USER_VALUES)
        assert split["user_overlap_count"] == len(USER_VALUES)
        assert preparation["policy_key"] == "explicit_rating_mean_duplicates.v1"
        assert preparation["source_row_count"] == len(USER_VALUES) * 5
        assert preparation["admitted_interaction_count"] == len(USER_VALUES) * 5
        assert preparation["time_column_present"] is True
        assert fit_result["result_dataset_id"]
        fit_dataset = datasets.get_dataset(fit_result["result_dataset_id"])
        assert fit_dataset.derived_from_dataset_id == training_dataset.id
        assert fit_dataset.ml_task_id == fit_task["task_id"]

        for artifact_kind in ("training_report", "export_file"):
            public_artifact = _artifact_by_kind(fit_task, artifact_kind)
            assert public_artifact["ready_to_open"] is True
            assert public_artifact["artifact_id"]
            assert artifacts.resolve_uri(
                build_artifact_uri(public_artifact["artifact_id"])
            ).exists is True

        evaluation = evaluation_task["result"]
        recommendation = evaluation["recommendation_evaluation"]
        assert evaluation["evaluation_kind"] == "ranking"
        assert evaluation["evaluation"]["primary_metric_name"] == "ndcg_at_k"
        assert evaluation["baseline_evaluation"]["primary_metric_name"] == "ndcg_at_k"
        assert evaluation["comparison"]["primary_metric_name"] == "ndcg_at_k"
        assert recommendation["split"] == split
        assert recommendation["preparation"] == preparation
        assert recommendation["candidate"]["policy_key"] == (
            "item_neighborhood_explicit_rating.v1"
        )
        assert recommendation["baseline"]["policy_key"] == (
            "global_popularity_unseen.v1"
        )
        assert recommendation["candidate"]["seen_item_violation_count"] == 0
        assert recommendation["baseline"]["seen_item_violation_count"] == 0
        assert evaluation["evaluation"]["metrics"]["ndcg_at_k"] == pytest.approx(
            recommendation["candidate"]["ndcg_at_k"]
        )
        assert evaluation["baseline_evaluation"]["metrics"][
            "ndcg_at_k"
        ] == pytest.approx(recommendation["baseline"]["ndcg_at_k"])
        assert len(recommendation["evidence_digest"]) == 64

        evaluation_report = _artifact_by_kind(evaluation_task, "evaluation_report")
        assert evaluation_report["ready_to_open"] is True
        assert evaluation_report["artifact_id"]
        assert artifacts.resolve_uri(
            build_artifact_uri(evaluation_report["artifact_id"])
        ).exists is True

        applied = tools.execute(
            "model.apply",
            {
                "trained_model_id": trained_model["trained_model_id"],
                "input_sources": [apply_dataset.id],
            },
            context,
        ).value
        assert applied["async_state"] == "completed"
        assert applied["training_dataset_id"] == training_dataset.id
        assert applied["source_dataset_ids"] == [apply_dataset.id]
        assert applied["source_artifact_ids"] == []
        assert applied["result_dataset_id"]
        assert applied["artifact_id"]
        result_dataset = datasets.get_dataset(applied["result_dataset_id"])
        assert result_dataset.derived_from_dataset_id == apply_dataset.id
        assert result_dataset.ml_task_id == applied["ml_task_id"]
        applied_rows = pd.read_parquet(result_dataset.source_path)
        cold_rows = applied_rows.loc[applied_rows["user_id"] == COLD_USER]
        assert len(cold_rows) == PARAMS["top_k"]
        assert set(cold_rows["strategy"]) == {"popularity_cold_start"}

        resolved_apply = artifacts.resolve_uri(build_artifact_uri(applied["artifact_id"]))
        assert resolved_apply.exists is True
        assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
        assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
        assert resolved_apply.metadata_payload["source_artifact_ids"] == []
        assert resolved_apply.metadata_payload["result_dataset_id"] == result_dataset.id

        apply_query = tools.execute(
            "model.task.query",
            {"task_ids": [applied["ml_task_id"]]},
            context,
        ).value["tasks"][0]
        assert apply_query["request"]["input_sources"] == [
            {"source_kind": "user_file", "dataset_id": apply_dataset.id}
        ]
        assert apply_query["result"]["source_dataset_ids"] == [apply_dataset.id]
        assert apply_query["result"]["result_dataset_id"] == result_dataset.id

        provider_projection = json.dumps(
            {
                "family_metadata": family_metadata,
                "detail_metadata": detail_metadata,
                "binding": binding,
                "training": training,
                "query": query,
                "applied": applied,
                "apply_query": apply_query,
            },
            sort_keys=True,
        )
        for forbidden in (
            str(paths.home),
            str(tmp_path),
            "absolute_path",
            "source_path",
            "artifact_path",
            "preview_rows",
            "raw_rows",
            "holdout_interactions",
            "rt-r-private-member-",
            "rt-r-private-offering-",
            COLD_USER,
        ):
            assert forbidden not in provider_projection
    finally:
        storage.engine.dispose()
