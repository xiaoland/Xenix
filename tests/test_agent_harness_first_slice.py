from pathlib import Path
from typing import Any

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import (
    AgentHarnessService,
    AgentToolRegistry,
    ConversationStore,
    ProviderResponse,
    ProviderToolCall,
    SubmitUserTurnInput,
)
from xenix.services.agent.providers import AgentProvider
from xenix.services.artifact_service import ArtifactService
from xenix.services.dataset_service import DatasetService
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import ProjectService
from xenix.services.storage import StorageBootstrapService
from xenix.services.work_item_service import WorkItemService


class FirstSliceProvider:
    def __init__(self, inference_path: Path) -> None:
        self._inference_path = inference_path

    def complete(self, messages: list[Any], tools: list[Any]) -> ProviderResponse:
        dataset_id = self._find_payload_value(messages, "dataset_id")
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
        if trained_model_id is None:
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will train a linear regression model."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-train",
                        tool_name="model.train",
                        arguments={
                            "dataset_id": dataset_id,
                            "feature_columns": ["feature_a", "feature_b"],
                            "target_columns": ["target"],
                            "models": ["regression.linear"],
                            "params_by_model": {"regression.linear": {"fit_intercept": True}},
                            "run_name": "Harness demand analysis",
                        },
                    )
                ],
            )
        if artifact_link is None or "Prediction results" not in self._rendered_text(messages):
            return ProviderResponse(
                assistant_content_blocks=[{"type": "markdown", "text": "I will run prediction with the trained model."}],
                tool_calls=[
                    ProviderToolCall(
                        provider_call_id="call-infer",
                        tool_name="model.inference",
                        arguments={
                            "dataset_id": dataset_id,
                            "feature_columns": ["feature_a", "feature_b"],
                            "trained_model_id": trained_model_id,
                            "input_files": [str(self._inference_path.resolve())],
                        },
                    )
                ],
            )
        return ProviderResponse(
            assistant_content_blocks=[{"type": "markdown", "text": f"Analysis complete. {artifact_link}"}],
            tool_calls=[
                ProviderToolCall(
                    provider_call_id="call-end",
                    tool_name="turn_end",
                    arguments={},
                )
            ],
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


def test_agent_harness_first_slice_runs_from_file_to_prediction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    artifact_service = ArtifactService(context.session_factory)
    registry = AgentToolRegistry(
        paths=paths,
        project_service=project_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
    )

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
    inference_file = tmp_path / "predict.csv"
    inference_file.write_text("feature_a,feature_b\n11,9\n12,10\n", encoding="utf-8")
    harness = AgentHarnessService(
        session_factory=context.session_factory,
        provider=FirstSliceProvider(inference_file),
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
        "model.train",
        "model.inference",
        "turn_end",
    ]
    prediction_artifacts = [artifact for artifact in snapshot.artifacts if artifact.kind.value == "prediction"]
    assert len(prediction_artifacts) == 1
    assert Path(prediction_artifacts[0].absolute_path).read_text(encoding="utf-8").splitlines()[0].endswith("prediction")
