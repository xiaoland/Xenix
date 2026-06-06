from pathlib import Path

import pytest

import xenix.services.analysis_graph as analysis_graph_module
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
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


def _bar_spec() -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "mark": "bar",
        "encoding": {
            "x": {"field": "region", "type": "nominal"},
            "y": {"aggregate": "sum", "field": "amount", "type": "quantitative"},
        },
        "title": "Revenue by region",
    }


def test_analysis_graph_service_writes_svg_from_vega_lite_spec(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Sales",
            spec=_bar_spec(),
        )
    )

    output_path = Path(result.output_path)
    assert output_path.exists()
    assert output_path.suffix == ".svg"
    assert result.graph_metadata["renderer"] == "vl-convert-python"
    assert result.graph_metadata["spec_format"] == "vega-lite"
    assert result.graph_metadata["title"] == "Revenue by region"
    assert result.graph_metadata["referenced_fields"] == ["amount", "region"]
    assert result.graph_metadata["row_count"] == 4
    assert result.graph_metadata["truncated"] is False
    assert "<svg" in output_path.read_text(encoding="utf-8")


def test_analysis_graph_service_supports_vega_lite_transform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "transform": [{"filter": "datum.amount >= 15"}],
        "mark": "line",
        "encoding": {
            "x": {"field": "date", "type": "temporal"},
            "y": {"aggregate": "sum", "field": "amount", "type": "quantitative"},
            "color": {"field": "region", "type": "nominal"},
        },
    }

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
    )

    assert Path(result.output_path).exists()
    assert result.graph_metadata["referenced_fields"] == ["amount", "date", "region"]
    assert result.graph_metadata["warnings"] == []


def test_analysis_graph_rejects_spec_owned_data_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "data": {"url": "https://example.invalid/sales.csv"},
        "mark": "bar",
        "encoding": {"x": {"field": "region"}, "y": {"field": "amount"}},
    }

    with pytest.raises(ValidationError, match="Xenix injects the registered dataset"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_rejects_unknown_fields_with_available_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "mark": "point",
        "encoding": {
            "x": {"field": "missing_amount", "type": "quantitative"},
            "y": {"field": "score", "type": "quantitative"},
        },
    }

    with pytest.raises(ValidationError, match="missing_amount.*Available columns: region, amount, score, date"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_rejects_large_aggregate_chart_without_preaggregation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setattr(analysis_graph_module, "_MAX_RENDER_ROWS", 3)
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)

    with pytest.raises(ValidationError, match="Use data.query or data.transform to pre-aggregate"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=_bar_spec())
        )


def test_analysis_graph_truncates_large_row_level_chart(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setattr(analysis_graph_module, "_MAX_RENDER_ROWS", 3)
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "mark": "point",
        "encoding": {
            "x": {"field": "amount", "type": "quantitative"},
            "y": {"field": "score", "type": "quantitative"},
        },
    }

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
    )

    assert result.graph_metadata["truncated"] is True
    assert result.graph_metadata["rendered_row_count"] == 3
    assert "Rendered the first 3 rows" in result.graph_metadata["warnings"][0]


def test_analysis_graph_tool_registers_image_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_sales_csv(tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    arguments = {
        "dataset_id": dataset.id,
        "spec": _bar_spec(),
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
    assert resolved.title == "Revenue by region"
    assert Path(resolved.absolute_path).exists()
    assert resolved.metadata_payload["dataset_id"] == dataset.id
    assert resolved.metadata_payload["analysis_graph"]["renderer"] == "vl-convert-python"


def test_analysis_graph_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.graph" in specs
    schema = specs["analysis.graph"].parameters_schema
    assert schema["required"] == ["dataset_id", "spec"]
    assert "dataset_id" in schema["properties"]
    assert "spec" in schema["properties"]
    assert "operation" not in schema["properties"]
    assert "params" not in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "rows" not in schema["properties"]
