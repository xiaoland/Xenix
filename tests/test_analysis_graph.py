from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtSvg import QSvgRenderer

import xenix.services.analysis_graph as analysis_graph_module
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.analysis_graph import AnalysisGraphService, GraphDatasetInput
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ArtifactKind


def _build_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    worker_runner = InlinePreprocessingWorkerRunner()
    data_cleaning_service = DataCleaningService(paths, worker_runner=worker_runner)
    data_transform_service = DataQueryTransformService(paths, worker_runner=worker_runner)
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
        preprocessing_worker_runner=worker_runner,
    )
    return paths, dataset_service, artifact_service, registry, None


def _tool_context(_conversation_store, tool_name: str, arguments: dict) -> ToolExecutionContext:
    return ToolExecutionContext(
        thread_id="tool-test-thread",
        dataset_ids=(),
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
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": 420,
        "height": 260,
        "mark": "bar",
        "encoding": {
            "x": {"field": "region", "type": "nominal"},
            "y": {"field": "amount", "type": "quantitative"},
            "color": {"value": "#4c78a8"},
        },
        "title": "Revenue by region",
    }


def _point_spec() -> dict:
    return {
        "width": 420,
        "height": 260,
        "mark": "point",
        "encoding": {
            "x": {"field": "amount", "type": "quantitative"},
            "y": {"field": "score", "type": "quantitative"},
            "color": {"value": "#4c78a8"},
        },
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


def _vegalite_wordcloud_transform_spec() -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": 360,
        "height": 220,
        "mark": "text",
        "encoding": {
            "text": {"field": "word", "type": "nominal"},
        },
        "transform": [
            {
                "type": "wordcloud",
                "text": {"field": "word"},
                "fontSize": {"field": "datum.count"},
            }
        ],
        "title": "Legacy wordcloud transform",
    }


def test_analysis_graph_service_writes_svg_from_vegalite_spec(monkeypatch, tmp_path: Path) -> None:
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
    svg = output_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    empty_paths = [
        element
        for element in root.iter(f"{{{analysis_graph_module._SVG_NS}}}path")
        if not str(element.attrib.get("d") or "").strip()
    ]
    bar_paths = [
        str(element.attrib.get("d") or "")
        for element in root.iter(f"{{{analysis_graph_module._SVG_NS}}}path")
        if element.attrib.get("fill") == "#4c78a8"
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
    assert bar_paths
    assert all("h0" not in path for path in bar_paths)
    assert renderer.isValid()
    assert not any("Invalid path data" in message for message in qt_messages)


def test_analysis_graph_repairs_process_wide_svg_namespace_pollution(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    ET.register_namespace("svg", analysis_graph_module._SVG_NS)

    try:
        result = AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Sales",
                spec=_bar_spec(),
            )
        )
    finally:
        ET.register_namespace("", analysis_graph_module._SVG_NS)

    svg = Path(result.output_path).read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg")
    assert "<svg:svg" not in svg


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


def test_analysis_graph_rejects_vegalite_wordcloud_transform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_terms_csv(tmp_path)

    with pytest.raises(ValidationError, match="Use wordcloud_spec instead"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(
                source_path=str(source.resolve()),
                dataset_name="Terms",
                spec=_vegalite_wordcloud_transform_spec(),
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
        "mark": "image",
        "encoding": {"url": {"value": "https://example.invalid/image.png"}},
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


def test_analysis_graph_allows_vegalite_top_level_transform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = _point_spec()
    spec["transform"] = [{"filter": "datum.amount > 10"}]

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
    )

    assert Path(result.output_path).exists()
    assert result.graph_metadata["referenced_fields"] == ["amount", "score"]


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


def test_analysis_graph_rejects_spec_without_vegalite_view(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {"width": 420, "height": 260, "encoding": {"x": {"field": "region"}}}

    with pytest.raises(ValidationError, match="must include a Vega-Lite mark"):
        AnalysisGraphService(paths).graph_dataset(
            GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
        )


def test_analysis_graph_accepts_vegalite_layer_spec(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = _write_sales_csv(tmp_path)
    spec = {
        "width": 420,
        "height": 260,
        "layer": [
            {
                "mark": "bar",
                "encoding": {
                    "x": {"field": "region", "type": "nominal"},
                    "y": {"field": "amount", "type": "quantitative"},
                },
            },
            {
                "mark": "point",
                "encoding": {
                    "x": {"field": "region", "type": "nominal"},
                    "y": {"field": "score", "type": "quantitative"},
                },
            },
        ],
    }

    result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(source_path=str(source.resolve()), dataset_name="Sales", spec=spec)
    )

    assert Path(result.output_path).exists()
    assert result.graph_metadata["referenced_fields"] == ["amount", "region", "score"]


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
    assert isinstance(result.value, dict)
    resolved = artifact_service.resolve_uri(f"artifact://{result.value['artifact_id']}?view=image")

    assert result.value["dataset_id"] == dataset.id
    assert "artifact_link" not in result.value
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
    assert isinstance(result.value, dict)
    resolved = artifact_service.resolve_uri(f"artifact://{result.value['artifact_id']}?view=image")

    assert result.value["dataset_id"] == dataset.id
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
    assert "oneOf" not in schema
    assert "exactly one graph mode" in specs["analysis.graph"].description
    assert "dataset_id" in schema["properties"]
    assert "spec" in schema["properties"]
    assert "wordcloud_spec" in schema["properties"]
    assert "do not use this field for word clouds" in schema["properties"]["spec"]["description"]
    assert "data.query or data.transform first" in schema["properties"]["wordcloud_spec"]["description"]
    spec_schema = schema["properties"]["spec"]
    assert "required" not in spec_schema
    assert "mark" in spec_schema["properties"]
    assert "encoding" in spec_schema["properties"]
    assert "layer" in spec_schema["properties"]
    assert "Vega-Lite" in spec_schema["description"]
    wordcloud_schema = schema["properties"]["wordcloud_spec"]
    assert wordcloud_schema["properties"]["top_n"]["minimum"] == 20
    assert wordcloud_schema["properties"]["top_n"]["maximum"] == 80
    assert wordcloud_schema["properties"]["color_mode"]["enum"] == ["rank_tier", "field"]
    assert "operation" not in schema["properties"]
    assert "params" not in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "rows" not in schema["properties"]
