from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.analysis_profile import AnalysisProfileService, ProfileDatasetInput
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


def _build_runtime(monkeypatch, tmp_path: Path):
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
    conversation_store = ConversationStore(context.session_factory)
    return dataset_service, artifact_service, registry, conversation_store


def _tool_context(conversation_store: ConversationStore, tool_name: str, arguments: dict) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Profile this dataset."}],
        )
    )
    _tool_message, tool_call = conversation_store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name=tool_name,
            arguments_payload=arguments,
        )
    )
    return ToolExecutionContext(
        thread_id=thread.id,
        turn_id=turn.id,
        tool_call_id=tool_call.id,
        attached_files=[],
    )


def _write_mixed_csv(tmp_path: Path) -> Path:
    source = tmp_path / "sales.csv"
    source.write_text(
        "\n".join(
            [
                "region,amount,score,active,date",
                "North,10,1.5,1,2026-01-01",
                "South,20,2.5,0,2026-01-02",
                "North,,2.0,1,2026-01-03",
                "South,20,3.0,0,2026-01-04",
                "South,20,3.0,0,2026-01-04",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def test_analysis_profile_service_builds_bounded_markdown_report(tmp_path: Path) -> None:
    source = _write_mixed_csv(tmp_path)

    result = AnalysisProfileService().profile_dataset(
        ProfileDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Sales",
            target_columns=["amount"],
            top_n=2,
            correlation_column_limit=3,
        )
    )

    assert result.profile["basic_info"] == {
        "row_count": 5,
        "column_count": 5,
        "duplicate_row_count": 1,
    }
    assert result.profile["field_type_summary"]["continuous_numeric"]["columns"] == ["amount", "score"]
    assert result.profile["field_type_summary"]["binary"]["columns"] == ["active"]
    assert result.profile["field_type_summary"]["non_numeric"]["columns"] == ["region"]
    assert result.profile["field_type_summary"]["datetime"]["columns"] == ["date"]
    assert result.profile["datetime_statistics"] == [
        {
            "column": "date",
            "min": "2026-01-01T00:00:00",
            "max": "2026-01-04T00:00:00",
            "span_days": 3,
        }
    ]
    assert result.profile["target_group_statistics"]
    assert "# Dataset profile: Sales" in result.markdown
    assert "| Duplicate rows | 1 |" in result.markdown
    assert "## Numeric statistics" in result.markdown
    assert "## Target group statistics" in result.markdown


def test_analysis_profile_tool_returns_markdown_without_artifact(monkeypatch, tmp_path: Path) -> None:
    dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_mixed_csv(tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    arguments = {"dataset_id": dataset.id, "target_columns": ["amount"], "top_n": 2}
    context = _tool_context(conversation_store, "analysis.profile", arguments)

    result = registry.execute(
        "analysis.profile",
        arguments,
        context,
    )

    assert result.payload["dataset_id"] == dataset.id
    assert "# Dataset profile: Sales" in result.payload["markdown"]
    assert "artifact_id" not in result.payload
    assert "artifact_link" not in result.payload
    assert result.content_blocks[0]["type"] == "markdown"
    assert "# Dataset profile: Sales" in result.content_blocks[0]["text"]
    assert artifact_service.list_thread_artifacts(context.thread_id) == []


def test_analysis_profile_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.profile" in specs
    schema = specs["analysis.profile"].parameters_schema
    assert schema["required"] == ["dataset_id"]
    assert "dataset_id" in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "rows" not in schema["properties"]
