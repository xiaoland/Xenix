import json
from pathlib import Path
import time
from typing import Any

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import (
    AgentHarnessService,
    AgentToolRegistry,
    CompleteToolCallInput,
    ConversationStore,
    CreateAgentThreadInput,
    CreateToolCallInput,
    DatasetAttachmentInput,
    ProviderResponse,
    ProviderToolCall,
    StartTurnInput,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentProvider
from xenix.services.agent.tools import ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_inspection import InspectDatasetInput
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
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
        attached_dataset_id = self._find_content_block_value(messages, "dataset_id")
        binding_id = self._find_payload_value(messages, "binding_id")
        trained_model_id = self._find_trained_model_id(messages)
        apply_artifact_id = self._find_apply_artifact_id(messages)
        if dataset_id is None:
            if attached_dataset_id is None:
                raise AssertionError("FirstSliceProvider requires an attached dataset id.")
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will inspect the uploaded dataset."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-peek",
                        tool_name="data.peek",
                        arguments={"dataset_id": attached_dataset_id},
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
                                },
                                {
                                    "role": "target",
                                    "columns": ["target"],
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
        if apply_artifact_id is None:
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
            assistant_content_blocks=[
                {
                    "type": "markdown",
                    "text": f"Analysis complete. [Apply results](artifact://{apply_artifact_id})",
                }
            ],
            tool_calls=[],
        )

    def _find_payload_value(self, messages: list[Any], key: str) -> str | None:
        for payload in self._tool_result_payloads(messages):
            if isinstance(payload.get(key), str):
                return payload[key]
        return None

    def _find_content_block_value(self, messages: list[Any], key: str) -> str | None:
        for message in reversed(messages):
            for block in reversed(getattr(message, "content_blocks", []) or []):
                if isinstance(block, dict) and isinstance(block.get(key), str):
                    return block[key]
        return None

    def _find_trained_model_id(self, messages: list[Any]) -> str | None:
        for payload in self._tool_result_payloads(messages):
            trained_models = payload.get("trained_models")
            if isinstance(trained_models, list) and trained_models:
                model = trained_models[0]
                if isinstance(model, dict) and isinstance(model.get("trained_model_id"), str):
                    return model["trained_model_id"]
        return None

    def _find_apply_artifact_id(self, messages: list[Any]) -> str | None:
        for payload in self._tool_result_payloads(messages):
            if payload.get("async_state") == "completed" and isinstance(payload.get("artifact_id"), str):
                return payload["artifact_id"]
        return None

    def _tool_result_payloads(self, messages: list[Any]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for message in reversed(messages):
            raw_content = str(getattr(message, "content", "") or "")
            if raw_content:
                try:
                    parsed = json.loads(raw_content)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
                    payloads.append(parsed["result"])
                    continue
            for block in reversed(getattr(message, "content_blocks", []) or []):
                payload = block.get("payload") if isinstance(block, dict) else None
                if isinstance(payload, dict):
                    payloads.append(payload)
        return payloads

    def _rendered_text(self, messages: list[Any]) -> str:
        return "\n".join(
            str(block.get("text", ""))
            for message in messages
            for block in message.content_blocks
            if block.get("type") == "markdown"
        )


class SlowWorkerRunner:
    def run(self, entrypoint, task_dir: Path, *, cancel_requested=None) -> int:
        deadline = time.time() + 0.2
        while time.time() < deadline:
            if cancel_requested is not None and cancel_requested():
                return -15
            time.sleep(0.01)
        return 1


def _build_first_slice_runtime(monkeypatch, tmp_path: Path, *, worker_runner=None):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    data_cleaning_service = DataCleaningService(paths)
    data_transform_service = DataQueryTransformService(paths)
    ml_task_service = MLTaskService(context.session_factory, paths, worker_runner=worker_runner)
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


def _dataset_attachment(registry: AgentToolRegistry, source_path: Path) -> DatasetAttachmentInput:
    dataset_service = registry._dataset_service
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source_path.resolve()), name=source_path.stem)
    )
    inspection = dataset_service.inspect_source_file(InspectDatasetInput(source_path=dataset.source_path))
    return DatasetAttachmentInput(
        dataset_id=dataset.id,
        name=dataset.name,
        file_name=inspection.file_name,
        source_format=inspection.source_format.value,
        row_count=inspection.row_count,
        column_count=inspection.column_count,
        preview_columns=inspection.preview_columns,
    )


class ToolCaptureProvider:
    def __init__(self) -> None:
        self.tools_by_call: list[list[str]] = []

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        self.tools_by_call.append([tool.name for tool in tools])
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": "Ready."}],
            tool_calls=[],
        )


class HiddenToolCallProvider:
    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-hidden-train",
                    tool_name="model.train",
                    arguments={},
                )
            ],
        )


class PeekFromThreadFilesProvider:
    def __init__(self) -> None:
        self.tools_by_call: list[list[str]] = []

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        self.tools_by_call.append([tool.name for tool in tools])
        if self._find_payload_value(messages, "dataset_id") is not None:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "Inspected previous file."}],
                tool_calls=[],
            )
        dataset_id = self._find_content_block_value(messages, "dataset_id")
        if dataset_id is None:
            raise AssertionError("Expected a dataset attachment in provider messages.")
        return ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-peek-previous-file",
                    tool_name="data.peek",
                    arguments={"dataset_id": dataset_id},
                )
            ],
        )

    def _find_payload_value(self, messages: list[Any], key: str) -> str | None:
        for payload in self._tool_result_payloads(messages):
            if isinstance(payload.get(key), str):
                return payload[key]
        return None

    def _find_content_block_value(self, messages: list[Any], key: str) -> str | None:
        for message in reversed(messages):
            for block in reversed(getattr(message, "content_blocks", []) or []):
                if isinstance(block, dict) and isinstance(block.get(key), str):
                    return block[key]
        return None

    def _tool_result_payloads(self, messages: list[Any]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for message in reversed(messages):
            raw_content = str(getattr(message, "content", "") or "")
            if raw_content:
                try:
                    parsed = json.loads(raw_content)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
                    payloads.append(parsed["result"])
                    continue
            for block in reversed(getattr(message, "content_blocks", []) or []):
                payload = block.get("payload") if isinstance(block, dict) else None
                if isinstance(payload, dict):
                    payloads.append(payload)
        return payloads


def _tool_context() -> ToolExecutionContext:
    return ToolExecutionContext(
        thread_id="thread-id",
        turn_id="turn-id",
        tool_call_id="tool-call-id",
        dataset_ids=[],
    )


def _persisted_tool_context(context) -> ToolExecutionContext:
    conversations = ConversationStore(context.session_factory)
    thread = conversations.create_thread(CreateAgentThreadInput(title="Tool context"))
    turn, _user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Run a tool"}],
        )
    )
    _request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="data.peek",
            arguments_payload={},
        )
    )
    return ToolExecutionContext(
        thread_id=thread.id,
        turn_id=turn.id,
        tool_call_id=tool_call.id,
        dataset_ids=[],
    )


def _seed_tool_payload(context, tool_name: str, payload: dict[str, Any]) -> str:
    conversations = ConversationStore(context.session_factory)
    thread = conversations.create_thread(CreateAgentThreadInput(title="Seeded tool context"))
    turn, _user_message = conversations.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Prepare context"}],
        )
    )
    _request_message, tool_call = conversations.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name=tool_name,
            arguments_payload={},
        )
    )
    conversations.complete_tool_call(
        CompleteToolCallInput(
            tool_call_id=tool_call.id,
            result_payload=payload,
        )
    )
    conversations.end_turn(thread.id, turn.id)
    return thread.id


def test_agent_harness_hides_data_and_training_tools_without_context(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    provider = ToolCaptureProvider()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    harness.submit_user_turn(SubmitUserTurnInput(text="hello"))

    tool_names = provider.tools_by_call[0]
    assert not any(name.startswith("data.") for name in tool_names)
    assert not any(name.startswith("analysis.") for name in tool_names)
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names
    assert "model.apply" not in tool_names
    assert "model.metadata" in tool_names
    assert "model.task.query" in tool_names


def test_agent_harness_exposes_data_tools_when_file_is_attached(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    provider = ToolCaptureProvider()
    source_file = tmp_path / "source.csv"
    source_file.write_text("value\n1\n", encoding="utf-8")
    attachment = _dataset_attachment(registry, source_file)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    harness.submit_user_turn(
        SubmitUserTurnInput(
            text="inspect this file",
            dataset_attachments=[attachment],
        )
    )

    tool_names = provider.tools_by_call[0]
    assert "data.peek" in tool_names
    assert "data.integrate" not in tool_names
    assert "analysis.profile" not in tool_names
    assert "analysis.graph" in tool_names
    assert "analysis.lambda" not in tool_names
    assert "data.clean" in tool_names
    assert "data.clean.metadata" in tool_names
    assert "data.query" in tool_names
    assert "data.transform" in tool_names
    assert "data.feature.select" in tool_names
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names
    assert "model.apply" not in tool_names


def test_agent_harness_exposes_dataset_tools_after_dataset_payload(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    thread_id = _seed_tool_payload(context, "data.peek", {"dataset_id": "dataset-1"})
    provider = ToolCaptureProvider()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    harness.submit_user_turn(SubmitUserTurnInput(thread_id=thread_id, text="analyze it"))

    tool_names = provider.tools_by_call[0]
    assert "data.peek" in tool_names
    assert "data.integrate" not in tool_names
    assert "data.clean" in tool_names
    assert "data.clean.metadata" in tool_names
    assert "data.query" in tool_names
    assert "data.transform" in tool_names
    assert "data.feature.select" in tool_names
    assert "analysis.profile" not in tool_names
    assert "analysis.graph" in tool_names
    assert "analysis.lambda" not in tool_names


def test_agent_harness_exposes_and_uses_data_tools_after_prior_thread_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    source_file = tmp_path / "source.csv"
    source_file.write_text("value\n1\n", encoding="utf-8")
    attachment = _dataset_attachment(registry, source_file)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=ToolCaptureProvider(),
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )
    first_snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            text="keep this file available",
            dataset_attachments=[attachment],
        )
    )
    provider = PeekFromThreadFilesProvider()
    harness.set_provider(provider)

    second_snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=first_snapshot.thread.id,
            text="inspect the file I already attached",
        )
    )

    first_tool_list = provider.tools_by_call[0]
    assert "data.peek" in first_tool_list
    assert "data.integrate" not in first_tool_list
    assert "analysis.profile" not in first_tool_list
    assert "analysis.graph" in first_tool_list
    assert "analysis.lambda" not in first_tool_list
    assert "data.clean" in first_tool_list
    assert "data.clean.metadata" in first_tool_list
    assert "data.query" in first_tool_list
    assert "data.transform" in first_tool_list
    assert "data.feature.select" in first_tool_list
    assert second_snapshot.tool_calls[-1].tool_name == "data.peek"
    assert second_snapshot.tool_calls[-1].status.value == "succeeded"
    assert "source_path" not in second_snapshot.tool_calls[-1].result_payload["inspection"]


def test_agent_harness_exposes_training_tools_after_selection_payload(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    thread_id = _seed_tool_payload(context, "data.feature.select", {"binding_id": "binding-1"})
    provider = ToolCaptureProvider()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    harness.submit_user_turn(SubmitUserTurnInput(thread_id=thread_id, text="train now"))

    tool_names = provider.tools_by_call[0]
    assert not any(name.startswith("data.") for name in tool_names)
    assert not any(name.startswith("analysis.") for name in tool_names)
    assert "model.train" in tool_names
    assert "model.hyper_train" in tool_names
    assert "model.apply" not in tool_names


def test_agent_harness_exposes_apply_after_trained_model_payload(monkeypatch, tmp_path: Path) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    thread_id = _seed_tool_payload(
        context,
        "model.train",
        {"trained_models": [{"trained_model_id": "trained-model-1"}]},
    )
    provider = ToolCaptureProvider()
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=provider,
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )

    harness.submit_user_turn(SubmitUserTurnInput(thread_id=thread_id, text="apply it"))

    tool_names = provider.tools_by_call[0]
    assert "model.apply" in tool_names
    assert "model.train" not in tool_names
    assert "model.hyper_train" not in tool_names


def test_agent_harness_rejects_provider_tool_call_that_was_not_exposed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=HiddenToolCallProvider(),
        tool_registry=registry,
        conversation_store=ConversationStore(context.session_factory),
    )
    thread = harness.create_thread("Hidden tool call")

    with pytest.raises(ValidationError, match="not attached to this request"):
        harness.submit_user_turn(SubmitUserTurnInput(thread_id=thread.thread.id, text="train now"))

    snapshot = harness.get_thread_snapshot(thread.thread.id)
    assert snapshot.provider_requests[0].status.value == "failed"
    assert snapshot.tool_calls == []


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
    assert "analysis.profile" not in specs
    assert "analysis.graph" in specs
    assert "analysis.lambda" not in specs
    assert "data.peek" in specs
    assert "data.clean.metadata" in specs
    assert "data.feature.select" in specs
    assert "model.train" in specs
    assert "model.hyper_train" in specs
    assert "model.apply" in specs
    graph_schema = specs["analysis.graph"].parameters_schema
    assert graph_schema["required"] == ["dataset_id", "spec"]
    assert "spec" in graph_schema["properties"]
    assert "operation" not in graph_schema["properties"]
    assert "params" not in graph_schema["properties"]
    assert "enum" not in specs["model.metadata"].parameters_schema["properties"]["model_keys"]["items"]
    feature_select_schema = specs["data.feature.select"].parameters_schema
    assert "enum" not in feature_select_schema["properties"]["model_key"]
    role_binding_schema = feature_select_schema["properties"]["role_bindings"]["items"]
    assert set(role_binding_schema["properties"]) == {"role", "columns"}
    assert role_binding_schema["required"] == ["role", "columns"]
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


def test_agent_harness_model_tools_expose_task_query_tool(monkeypatch, tmp_path: Path) -> None:
    _context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)

    task_query_spec = next(spec for spec in registry.list_specs() if spec.name == "model.task.query")

    assert task_query_spec.provider_name == "model_task_query"
    assert task_query_spec.parameters_schema["required"] == ["task_ids"]
    assert "include_related" not in task_query_spec.parameters_schema["properties"]


def test_agent_harness_train_returns_background_receipt_after_grace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("xenix.services.agent.tools.MODEL_TRAIN_GRACE_SECONDS", 0.01)
    context, registry = _build_first_slice_runtime(monkeypatch, tmp_path, worker_runner=SlowWorkerRunner())
    tool_context = _persisted_tool_context(context)
    training_file = tmp_path / "slow-demand.csv"
    training_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n",
        encoding="utf-8",
    )
    attachment = _dataset_attachment(registry, training_file)
    dataset_result = registry.execute(
        "data.peek",
        {"dataset_id": attachment.dataset_id},
        tool_context,
    )
    binding_result = registry.execute(
        "data.feature.select",
        {
            "dataset_id": dataset_result.payload["dataset_id"],
            "model_key": "regression.linear",
            "role_bindings": [
                {"role": "feature", "columns": ["feature_a", "feature_b"]},
                {"role": "target", "columns": ["target"]},
            ],
        },
        tool_context,
    )

    result = registry.execute(
        "model.train",
        {
            "binding_id": binding_result.payload["binding_id"],
            "models": ["linear_regression"],
        },
        tool_context,
    )
    query_result = registry.execute(
        "model.task.query",
        {
            "task_ids": result.payload["task_ids"],
            "include_logs": True,
            "max_log_entries": 5,
        },
        tool_context,
    )

    assert result.payload["async_state"] == "running_background"
    assert result.payload["task_ids"]
    assert "can_cancel_task_ids" not in result.payload
    assert result.content_blocks[0]["text"] == "Model training running in background"
    assert query_result.payload["tasks"][0]["task_id"] == result.payload["task_ids"][0]
    assert "logs" in query_result.payload["tasks"][0]


def test_agent_harness_task_query_summarizes_completed_evaluation(monkeypatch, tmp_path: Path) -> None:
    _context, registry = _build_first_slice_runtime(monkeypatch, tmp_path)
    tool_context = _tool_context()
    training_file = tmp_path / "evaluated-demand.csv"
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
    attachment = _dataset_attachment(registry, training_file)
    dataset_result = registry.execute(
        "data.peek",
        {"dataset_id": attachment.dataset_id},
        tool_context,
    )
    binding_result = registry.execute(
        "data.feature.select",
        {
            "dataset_id": dataset_result.payload["dataset_id"],
            "model_key": "regression.linear",
            "role_bindings": [
                {"role": "feature", "columns": ["feature_a", "feature_b"]},
                {"role": "target", "columns": ["target"]},
            ],
        },
        tool_context,
    )

    result = registry.execute(
        "model.train",
        {
            "binding_id": binding_result.payload["binding_id"],
            "models": ["linear_regression"],
        },
        tool_context,
    )
    evaluation_task_id = next(
        task["task_id"]
        for task in result.payload["ml_tasks"]
        if task["task_type"] == "evaluate"
    )
    query_result = registry.execute(
        "model.task.query",
        {"task_ids": [evaluation_task_id]},
        tool_context,
    )

    assert result.payload["async_state"] == "completed"
    assert "evaluation: r2=" in result.content_blocks[0]["text"]
    evaluation = query_result.payload["tasks"][0]["result"]["evaluation"]
    assert {
        "r2",
        "mse",
        "rmse",
        "mae",
        "mape",
        "explained_variance",
        "residual_mean",
        "residual_std",
    }.issubset(evaluation["metrics"])
    markdown = query_result.content_blocks[0]["text"]
    assert "Primary metric: r2=" in markdown
    assert "Key metrics: r2=" in markdown
    assert "rmse=" in markdown


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
    attachment = _dataset_attachment(registry, training_file)
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
            dataset_attachments=[attachment],
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
    attachment = _dataset_attachment(registry, training_file)
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
            dataset_attachments=[attachment],
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
