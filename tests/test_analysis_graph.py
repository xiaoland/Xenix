from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.analysis_graph import AnalysisGraphService, GraphDatasetInput
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ArtifactKind


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
    return paths, dataset_service, artifact_service, registry, conversation_store


def _tool_context(conversation_store: ConversationStore, tool_name: str, arguments: dict) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Draw this dataset."}],
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


def _write_sales_csv(tmp_path: Path) -> Path:
    source = tmp_path / "sales.csv"
    source.write_text(
        "\n".join(
            [
                "region,amount,score,date",
                "North,10,1.5,2026-01-01",
                "South,20,2.5,2026-01-02",
                "North,15,2.0,2026-01-03",
                "West,30,3.0,2026-01-04",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def test_analysis_graph_service_writes_svg_bar_count(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Sales",
            operation="bar_count",
            params={"column": "region", "top_n": 2},
        )
    )

    output_path = Path(result.output_path)
    assert output_path.exists()
    assert output_path.suffix == ".svg"
    assert result.graph_metadata["operation"] == "bar_count"
    assert result.graph_metadata["columns"] == ["region"]
    assert "<svg" in output_path.read_text(encoding="utf-8")


def test_analysis_graph_service_supports_core_graph_operations(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    service = AnalysisGraphService(paths)

    cases = [
        ("scatter", {"x": "amount", "y": "score"}, ["amount", "score"]),
        ("line", {"x": "date", "y": "amount"}, ["date", "amount"]),
        ("correlation_heatmap", {"columns": ["amount", "score"]}, ["amount", "score"]),
    ]
    for operation, params, columns in cases:
        result = service.graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Sales",
                operation=operation,
                params=params,
            )
        )

        output_path = Path(result.output_path)
        assert output_path.exists()
        assert "<svg" in output_path.read_text(encoding="utf-8")
        assert result.graph_metadata["operation"] == operation
        assert result.graph_metadata["columns"] == columns


def test_analysis_graph_line_drops_invalid_datetime_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = tmp_path / "line.csv"
    source.write_text(
        "\n".join(
            [
                "date,amount",
                "not-a-date,10",
                "2026-01-02,20",
                "2026-01-03,30",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Line",
            operation="line",
            params={"x": "date", "y": "amount"},
        )
    )

    assert result.graph_metadata["point_count"] == 2
    assert Path(result.output_path).exists()


def test_analysis_graph_tool_registers_image_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_sales_csv(tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    arguments = {
        "dataset_id": dataset.id,
        "operation": "histogram",
        "params": {"column": "amount", "bins": 4, "title": "Amount distribution"},
    }

    result = registry.execute(
        "analysis.graph",
        arguments,
        _tool_context(conversation_store, "analysis.graph", arguments),
    )
    resolved = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}?view=image")

    assert result.payload["dataset_id"] == dataset.id
    assert "artifact_link" not in result.payload
    assert result.content_blocks == []
    assert resolved.kind is ArtifactKind.IMAGE
    assert resolved.mime_type == "image/svg+xml"
    assert Path(resolved.absolute_path).exists()
    assert resolved.metadata_payload["dataset_id"] == dataset.id
    assert resolved.metadata_payload["analysis_graph"]["operation"] == "histogram"


def test_analysis_graph_tool_uses_default_title_for_blank_title(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_sales_csv(tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    arguments = {
        "dataset_id": dataset.id,
        "operation": "bar_count",
        "params": {"column": "region", "title": "   "},
    }

    result = registry.execute(
        "analysis.graph",
        arguments,
        _tool_context(conversation_store, "analysis.graph", arguments),
    )
    resolved = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}?view=image")

    assert resolved.title == "Sales bar_count"
    assert "artifact_link" not in result.payload


def test_analysis_graph_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.graph" in specs
    schema = specs["analysis.graph"].parameters_schema
    assert schema["required"] == ["dataset_id", "operation"]
    assert "dataset_id" in schema["properties"]
    assert "operation" in schema["properties"]
    assert "params" in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "rows" not in schema["properties"]
