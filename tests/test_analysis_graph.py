from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtSvg import QSvgRenderer

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
        dataset_ids=[],
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
        "$schema": "https://vega.github.io/schema/vega/v6.json",
        "width": 420,
        "height": 260,
        "scales": [
            {
                "name": "x",
                "type": "band",
                "domain": {"field": "region"},
                "range": "width",
                "padding": 0.1,
            },
            {
                "name": "y",
                "type": "linear",
                "domain": {"field": "amount"},
                "range": "height",
                "nice": True,
                "zero": True,
            },
        ],
        "axes": [{"orient": "bottom", "scale": "x"}, {"orient": "left", "scale": "y"}],
        "marks": [
            {
                "type": "rect",
                "encode": {
                    "enter": {
                        "x": {"scale": "x", "field": "region"},
                        "width": {"scale": "x", "band": 1},
                        "y": {"scale": "y", "field": "amount"},
                        "y2": {"scale": "y", "value": 0},
                        "fill": {"value": "#4c78a8"},
                    }
                },
            }
        ],
        "title": "Revenue by region",
    }


def _point_spec() -> dict:
    return {
        "width": 420,
        "height": 260,
        "scales": [
            {
                "name": "x",
                "type": "linear",
                "domain": {"field": "amount"},
                "range": "width",
                "nice": True,
                "zero": True,
            },
            {
                "name": "y",
                "type": "linear",
                "domain": {"field": "score"},
                "range": "height",
                "nice": True,
                "zero": True,
            },
        ],
        "axes": [{"orient": "bottom", "scale": "x"}, {"orient": "left", "scale": "y"}],
        "marks": [
            {
                "type": "symbol",
                "encode": {
                    "enter": {
                        "x": {"scale": "x", "field": "amount"},
                        "y": {"scale": "y", "field": "score"},
                        "size": {"value": 80},
                        "fill": {"value": "#4c78a8"},
                    }
                },
            }
        ],
    }


def _write_terms_csv(tmp_path: Path) -> Path:
    source = tmp_path / "terms.csv"
    source.write_text(
        "\n".join(
            [
                "word,count",
                "sales,40",
                "margin,28",
                "north,22",
                "retail,18",
                "growth,15",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def _wordcloud_spec() -> dict:
    return {
        "title": "Term cloud",
        "width": 360,
        "height": 220,
    }


def _write_many_terms_csv(tmp_path: Path, total_terms: int = 95) -> Path:
    source = tmp_path / "many-terms.csv"
    rows = ["word,count"]
    rows.extend(f"term_{index},{total_terms - index + 1}" for index in range(1, total_terms + 1))
    rows.append("")
    source.write_text("\n".join(rows), encoding="utf-8")
    return source


def _write_semantic_terms_csv(tmp_path: Path) -> Path:
    source = tmp_path / "semantic-terms.csv"
    source.write_text(
        "\n".join(
            [
                "word,count,source",
                "sales,40,reviews",
                "margin,28,reviews",
                "north,22,surveys",
                "retail,18,surveys",
                "growth,15,reviews",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def _semantic_wordcloud_spec() -> dict:
    return {
        "width": 360,
        "height": 220,
        "title": "Term cloud",
        "color_mode": "field",
        "color_field": "source",
        "palette": ["#1f4e79", "#c06c4e"],
    }


def _wordcloud_missing_count_spec() -> dict:
    spec = _wordcloud_spec()
    spec["count_field"] = "frequency"
    return spec


def _vega_wordcloud_spec() -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega/v6.json",
        "width": 360,
        "height": 220,
        "marks": [
            {
                "type": "text",
                "encode": {
                    "enter": {
                        "text": {"field": "word"},
                    }
                },
                "transform": [
                    {
                        "type": "wordcloud",
                        "text": {"field": "word"},
                        "fontSize": {"field": "datum.count"},
                    }
                ],
            }
        ],
        "title": "Legacy Vega cloud",
    }


def test_analysis_graph_service_writes_svg_from_vega_profile_spec(monkeypatch, tmp_path: Path) -> None:
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
    assert result.graph_metadata["spec_format"] == "vega"
    assert result.graph_metadata["title"] == "Revenue by region"
    assert result.graph_metadata["referenced_fields"] == ["amount", "region"]
    assert result.graph_metadata["row_count"] == 4
    assert result.graph_metadata["truncated"] is False
    svg = output_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    empty_paths = [
        element
        for element in root.iter(f"{{{analysis_graph_module._SVG_NS}}}path")
        if not str(element.attrib.get("d") or "").strip()
    ]
    qt_messages: list[str] = []

    def collect_qt_message(_mode, _context, message: str) -> None:
        qt_messages.append(message)

    previous_handler = qInstallMessageHandler(collect_qt_message)
    try:
        renderer = QSvgRenderer(str(output_path))
    finally:
        qInstallMessageHandler(previous_handler)

    assert "<svg" in svg
    assert empty_paths == []
    assert renderer.isValid()
    assert not any("Invalid path data" in message for message in qt_messages)


def test_analysis_graph_service_renders_wordcloud_from_wordcloud_spec(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Terms",
            wordcloud_spec=_wordcloud_spec(),
        )
    )
    svg = Path(result.output_path).read_text(encoding="utf-8")

    assert Path(result.output_path).exists()
    assert result.graph_metadata["spec_format"] == "wordcloud"
    assert result.graph_metadata["referenced_fields"] == ["count", "word"]
    assert result.graph_metadata["wordcloud_options"]["font_size_range"] == [12, 56]
    assert "sales" in svg
    assert "<title>sales: 40</title>" in svg
    assert "Term cloud" in svg
    assert "ERROR" not in svg


def test_analysis_graph_wordcloud_title_keeps_single_full_background_rect(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Terms",
            wordcloud_spec=_wordcloud_spec(),
        )
    )
    root = ET.fromstring(Path(result.output_path).read_text(encoding="utf-8"))

    background_rects = [
        element
        for element in root.iter(f"{{{analysis_graph_module._SVG_NS}}}rect")
        if element.attrib.get("width") == "100%" and element.attrib.get("height") == "100%"
    ]

    assert len(background_rects) == 1


def test_analysis_graph_wordcloud_trims_to_top_80_terms(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_many_terms_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Terms",
            wordcloud_spec=_wordcloud_spec(),
        )
    )

    assert result.graph_metadata["rendered_row_count"] == 80
    assert result.graph_metadata["wordcloud_options"]["font_size_range"] == [10, 42]
    assert any("top 80 terms" in warning for warning in result.graph_metadata["warnings"])


def test_analysis_graph_wordcloud_uses_dense_font_range_for_medium_term_count(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_many_terms_csv(tmp_path, total_terms=45)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Terms",
            wordcloud_spec=_wordcloud_spec(),
        )
    )

    assert result.graph_metadata["rendered_row_count"] == 45
    assert result.graph_metadata["wordcloud_options"]["font_size_range"] == [10, 42]


def test_analysis_graph_wordcloud_supports_semantic_color_field(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_semantic_terms_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(source.resolve()),
            dataset_name="Semantic terms",
            wordcloud_spec=_semantic_wordcloud_spec(),
        )
    )
    svg = Path(result.output_path).read_text(encoding="utf-8")

    assert Path(result.output_path).exists()
    assert result.graph_metadata["referenced_fields"] == ["count", "source", "word"]
    assert result.graph_metadata["wordcloud_options"]["color_mode"] == "field"
    assert "#1f4e79" in svg
    assert "#c06c4e" in svg
    assert "<title>sales: 40 | source: reviews</title>" in svg


def test_analysis_graph_wordcloud_missing_count_field_returns_structured_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    with pytest.raises(ValidationError, match="count field 'frequency' was not found") as exc_info:
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Terms",
                wordcloud_spec=_wordcloud_missing_count_spec(),
            )
        )
    assert getattr(exc_info.value, "error_code", None) == "wordcloud_count_field_missing"
    assert getattr(exc_info.value, "error_details", {}).get("requested_field") == "frequency"
    assert any("data.query or data.transform" in hint for hint in getattr(exc_info.value, "repair_hints", []))


def test_analysis_graph_rejects_vega_wordcloud_transform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    with pytest.raises(ValidationError, match="Use wordcloud_spec instead"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Terms",
                spec=_vega_wordcloud_spec(),
            )
        )


def test_analysis_graph_requires_exactly_one_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    with pytest.raises(ValidationError, match="exactly one of spec or wordcloud_spec"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Terms",
                spec=_bar_spec(),
                wordcloud_spec=_wordcloud_spec(),
            )
        )


def test_analysis_graph_ignores_user_authored_data_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = _bar_spec()
    spec["data"] = [
        {
            "name": "llm_data",
            "url": "https://example.invalid/sales.csv",
            "values": [{"region": "Wrong", "amount": 999}],
            "transform": [{"type": "filter", "expr": "datum.amount > 100"}],
        }
    ]
    spec["datasets"] = {"llm_data": [{"region": "Wrong", "amount": 999}]}

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
    )
    svg = Path(result.output_path).read_text(encoding="utf-8")

    assert Path(result.output_path).exists()
    assert "Wrong" not in svg
    assert result.graph_metadata["referenced_fields"] == ["amount", "region"]


def test_analysis_graph_rejects_external_urls(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "marks": [
            {
                "type": "image",
                "encode": {"enter": {"url": {"value": "https://example.invalid/image.png"}}},
            }
        ],
    }

    with pytest.raises(ValidationError, match="External data or resource URLs"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_rejects_unknown_fields_with_available_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "marks": [
            {
                "type": "symbol",
                "encode": {
                    "enter": {
                        "x": {"field": "missing_amount"},
                        "y": {"field": "score"},
                    }
                },
            }
        ],
    }

    with pytest.raises(ValidationError, match="missing_amount.*Available columns: region, amount, score, date"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_rejects_non_mark_level_transform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = _point_spec()
    spec["transform"] = [{"type": "filter", "expr": "datum.amount > 10"}]

    with pytest.raises(ValidationError, match="only supports Vega mark-level transform"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_truncates_large_row_level_chart(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    monkeypatch.setattr(analysis_graph_module, "_MAX_RENDER_ROWS", 3)
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=_point_spec())
    )

    assert result.graph_metadata["truncated"] is True
    assert result.graph_metadata["rendered_row_count"] == 3
    assert "Rendered the first 3 rows" in result.graph_metadata["warnings"][0]


def test_analysis_graph_rejects_complex_mark_dataflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "marks": [
            {
                "type": "group",
                "from": {"facet": {"name": "region_groups", "groupby": "region"}},
                "marks": [{"type": "rect"}],
            }
        ],
    }

    with pytest.raises(ValidationError, match="does not support Vega facet dataflow"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_rejects_complex_scale_domain(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = _bar_spec()
    spec["scales"][0]["domain"] = {"fields": [{"field": "region"}]}

    with pytest.raises(ValidationError, match="does not support complex Vega scale domains"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


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


def test_analysis_graph_tool_registers_wordcloud_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_terms_csv(tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Terms")
    )
    arguments = {
        "dataset_id": dataset.id,
        "wordcloud_spec": _wordcloud_spec(),
    }

    result = registry.execute(
        "analysis.graph",
        arguments,
        _tool_context(conversation_store, "analysis.graph", arguments),
    )
    resolved = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}?view=image")

    assert result.payload["dataset_id"] == dataset.id
    assert resolved.kind is ArtifactKind.IMAGE
    assert resolved.mime_type == "image/svg+xml"
    assert resolved.metadata_payload["analysis_graph"]["spec_format"] == "wordcloud"
    assert resolved.metadata_payload["analysis_graph"]["renderer"] == "wordcloud"
    assert Path(resolved.absolute_path).exists()


def test_analysis_graph_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.graph" in specs
    schema = specs["analysis.graph"].parameters_schema
    assert schema["required"] == ["dataset_id"]
    assert schema["oneOf"] == [{"required": ["spec"]}, {"required": ["wordcloud_spec"]}]
    assert "dataset_id" in schema["properties"]
    assert "spec" in schema["properties"]
    assert "wordcloud_spec" in schema["properties"]
    assert "Do not use this field for word clouds" in schema["properties"]["spec"]["description"]
    assert "data.query or data.transform first" in schema["properties"]["wordcloud_spec"]["description"]
    spec_schema = schema["properties"]["spec"]
    assert spec_schema["required"] == ["marks"]
    assert spec_schema["properties"]["marks"]["minItems"] == 1
    assert "not for word clouds" in spec_schema["properties"]["marks"]["description"]
    wordcloud_schema = schema["properties"]["wordcloud_spec"]
    assert wordcloud_schema["properties"]["top_n"]["minimum"] == 20
    assert wordcloud_schema["properties"]["top_n"]["maximum"] == 80
    assert wordcloud_schema["properties"]["color_mode"]["enum"] == ["rank_tier", "field"]
    assert "operation" not in schema["properties"]
    assert "params" not in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "rows" not in schema["properties"]
