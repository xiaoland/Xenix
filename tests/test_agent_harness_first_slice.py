from pathlib import Path
from typing import Any

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import (
    AgentHarnessService,
    AgentToolRegistry,
    ConversationStore,
    ProviderResponse,
    ProviderToolCall,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentProvider
from xenix.services.agent.tools import ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


class FirstSliceProvider:
    def __init__(
        self,
        apply_path: Path | None = None,
        apply_rows: dict[str, Any] | None = None,
    ) -> None:
        self._apply_path = apply_path
        self._apply_rows = apply_rows

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        dataset_id = self._find_payload_value(messages, "dataset_id")
        binding_id = self._find_payload_value(messages, "binding_id")
        trained_model_id = self._find_trained_model_id(messages)
        artifact_link = self._find_payload_value(messages, "artifact_link")
        if dataset_id is None:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will inspect the uploaded dataset."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-peek",
                        tool_name="data.peek",
                        arguments={"name": "Harness Demand"},
                    )
                ],
            )
        if binding_id is None:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will bind the training columns."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-select",
                        tool_name="data.feature.select",
                        arguments={
                            "dataset_id": dataset_id,
                            "model_key": "regression.linear",
                            "role_bindings": [
                                {
                                    "role": "feature",
                                    "columns": ["feature_a", "feature_b"],
                                    "role_kind": "many_columns",
                                },
                                {
                                    "role": "target",
                                    "columns": ["target"],
                                    "role_kind": "single_column",
                                },
                            ],
                        },
                    )
                ],
            )
        if trained_model_id is None:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will train a linear regression model."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-train",
                        tool_name="model.train",
                        arguments={
                            "binding_id": binding_id,
                            "models": ["linear_regression"],
                            "params_by_model": {"linear_regression": {"fit_intercept": True}},
                            "run_name": "Harness demand analysis",
                        },
                    )
                ],
            )
        if artifact_link is None or "Apply results" not in self._rendered_text(messages):
            apply_arguments = {"trained_model_id": trained_model_id}
            if self._apply_rows is not None:
                apply_arguments["input_rows"] = self._apply_rows
            else:
                if self._apply_path is None:
                    raise AssertionError("FirstSliceProvider requires apply input data.")
                apply_arguments["input_files"] = [str(self._apply_path.resolve())]
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will apply the trained model."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-apply",
                        tool_name="model.apply",
                        arguments=apply_arguments,
                    )
                ],
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": f"Analysis complete. {artifact_link}"}],
            tool_calls=[],
        )

    def _find_payload_value(self, messages: list[Any], key: str) -> str | None:
        for message in reversed(messages):
            for block in reversed(message.content_blocks):
                payload = block.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get(key), str):
                    return payload[key]
        return None

    def _find_trained_model_id(self, messages: list[Any]) -> str | None:
        for message in reversed(messages):
            for block in reversed(message.content_blocks):
                payload = block.get("payload")
                if not isinstance(payload, dict):
                    continue
                trained_models = payload.get("trained_models")
                if isinstance(trained_models, list) and trained_models:
                    model = trained_models[0]
                    if isinstance(model, dict) and isinstance(model.get("trained_model_id"), str):
                        return model["trained_model_id"]
        return None

    def _rendered_text(self, messages: list[Any]) -> str:
        return "\n".join(
            str(block.get("text", ""))
            for message in messages
            for block in message.content_blocks
            if block.get("type") == "markdown"
        )


def _build_first_slice_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    data_cleaning_service = DataCleaningService(paths)
    data_transform_service = DataQueryTransformService(paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        ml_task_service,
    )
    artifact_service = ArtifactService(context.session_factory)
    registry = AgentToolRegistry(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=data_cleaning_service,
        data_transform_service=data_transform_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
    )
    return context, registry


def _tool_context() -> ToolExecutionContext:
    return ToolExecutionContext(
        thread_id="thread-id",
        turn_id="turn-id",
        tool_call_id="tool-call-id",
        attached_files=[],
    )


def test_agent_harness_model_metadata_exposes_catalog_without_train_enums(monkeypatch, tmp_path: Path) -> None:
    _context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    specs = {spec.name: spec for spec in registry.list_specs()}
    result = registry.execute(
        "model.metadata",
        {
            "model_keys": [
                "linear_regression",
                "random_forest",
                "decision_tree",
                "gradient_boosting",
            ],
            "include_param_schema": True,
            "include_param_grid_schema": True,
        },
        _tool_context(),
    )

    assert "model.metadata" in specs
    metadata_key_enum = specs["model.metadata"].parameters_schema["properties"]["model_keys"]["items"]["enum"]
    assert "regression.linear" in metadata_key_enum
    assert "model_family" in specs["model.metadata"].parameters_schema["properties"]
    assert "model_task_kind" in specs["model.metadata"].parameters_schema["properties"]
    assert "evaluation_kind" in specs["model.metadata"].parameters_schema["properties"]
    assert "enum" not in specs["model.train"].parameters_schema["properties"]["models"]["items"]
    apply_schema = specs["model.apply"].parameters_schema
    assert apply_schema["required"] == ["trained_model_id"]
    assert "input_rows" in apply_schema["properties"]
    assert set(apply_schema["properties"]["input_rows"]["required"]) == {"header_index_map", "data"}
    assert result.payload["model_keys"] == [
        "regression.linear",
        "regression.gradient_boosting",
        "regression.random_forest",
        "regression.decision_tree",
    ]
    assert result.payload["models"][0]["supports_hyperparameter_tuning"] is True
    assert result.payload["models"][0]["evaluation_kind"] == "regression"
    assert result.payload["models"][0]["model_family"] == "supervised"
    assert result.payload["models"][0]["model_task_kind"] == "predictor"
    assert [role["name"] for role in result.payload["models"][0]["train_role_schema"]["roles"]] == ["feature", "target"]
    assert [role["name"] for role in result.payload["models"][0]["apply_role_schema"]["roles"]] == ["feature"]
    assert result.payload["models"][0]["result_contract"]["apply_result_kinds"] == ["table"]
    assert "param_schema" in result.payload["models"][0]
    assert "param_grid_schema" in result.payload["models"][0]
    clustering_result = registry.execute(
        "model.metadata",
        {"model_family": "clustering"},
        _tool_context(),
    )
    assert clustering_result.payload["model_keys"] == ["clustering.kmeans", "clustering.dbscan"]
    predictor_result = registry.execute(
        "model.metadata",
        {"model_task_kind": "predictor"},
        _tool_context(),
    )
    assert "regression.linear" in predictor_result.payload["model_keys"]
    assert "classification.logistic_regression" in predictor_result.payload["model_keys"]
    assert "clustering.kmeans" not in predictor_result.payload["model_keys"]
    summary_result = registry.execute(
        "model.metadata",
        {"evaluation_kind": "summary"},
        _tool_context(),
    )
    assert "association.apriori_apyori" in summary_result.payload["model_keys"]
    assert "recommendation.item_similarity" in summary_result.payload["model_keys"]
    with pytest.raises(ValidationError, match="Unknown model_family"):
        registry.execute("model.metadata", {"model_family": "unknown"}, _tool_context())
    with pytest.raises(ValidationError, match="Unknown model_task_kind"):
        registry.execute("model.metadata", {"model_task_kind": "unknown"}, _tool_context())
    with pytest.raises(ValidationError, match="Unknown evaluation_kind"):
        registry.execute("model.metadata", {"evaluation_kind": "unknown"}, _tool_context())
    xgboost_result = registry.execute("model.metadata", {"model_keys": ["xgboost"]}, _tool_context())
    assert xgboost_result.payload["model_keys"] == ["regression.xgboost"]


def test_agent_tool_registry_owns_tool_presentation(monkeypatch, tmp_path: Path) -> None:
    _context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    data_presentation = registry.tool_presentation("data.peek")
    unknown_presentation = registry.tool_presentation("unknown.tool")

    assert data_presentation.icon_key == "table"
    assert data_presentation.pending_summary == "Inspecting dataset..."
    assert data_presentation.summary_for("failed") == "Failed to inspect dataset"
    assert unknown_presentation.icon_key == "tool"


def test_agent_harness_hyper_train_validates_tuning_capability_before_execution(monkeypatch, tmp_path: Path) -> None:
    _context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    with pytest.raises(ValidationError, match="hyperparameter_tuning support"):
        registry.execute(
            "model.hyper_train",
            {
                "binding_id": "missing-binding",
                "param_grids_by_model": {"kmeans": {}},
            },
            _tool_context(),
        )


def test_agent_harness_first_slice_runs_from_file_to_apply_result(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    training_file = tmp_path / "demand.csv"
    training_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    apply_file = tmp_path / "apply.csv"
    apply_file.write_text("feature_a,feature_b\n11,9\n12,10\n", encoding="utf-8")
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=FirstSliceProvider(apply_file),
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="Analyze this dataset, train a model, and predict the attached future rows.",
            file_paths=[str(training_file.resolve())],
        )
    )

    assert len(snapshot.turns) == 1
    assert snapshot.turns[0].status.value == "ended"
    assert [tool.tool_name for tool in snapshot.tool_calls] == [
        "data.peek",
        "data.feature.select",
        "model.train",
        "model.apply",
    ]
    apply_artifacts = [artifact for artifact in snapshot.artifacts if artifact.kind.value == "file"]
    assert len(apply_artifacts) == 1
    assert Path(apply_artifacts[0].absolute_path).read_text(encoding="utf-8").splitlines()[0].endswith("prediction")


def test_agent_harness_first_slice_runs_inline_rows_to_apply_result(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    training_file = tmp_path / "demand.csv"
    training_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=FirstSliceProvider(
            apply_rows={
                "header_index_map": {"feature_b": 0, "feature_a": 1},
                "data": [[9, 11], [10, 12]],
            },
        ),
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="Analyze this dataset, train a model, and predict the inline future rows.",
            file_paths=[str(training_file.resolve())],
        )
    )

    assert len(snapshot.turns) == 1
    assert snapshot.turns[0].status.value == "ended"
    assert [tool.tool_name for tool in snapshot.tool_calls] == [
        "data.peek",
        "data.feature.select",
        "model.train",
        "model.apply",
    ]
    apply_artifacts = [artifact for artifact in snapshot.artifacts if artifact.kind.value == "file"]
    assert len(apply_artifacts) == 1
    prediction_lines = Path(apply_artifacts[0].absolute_path).read_text(encoding="utf-8").splitlines()
    assert prediction_lines[0].endswith("prediction")
    assert prediction_lines[1].startswith("11,9,")
