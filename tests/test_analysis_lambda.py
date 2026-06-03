from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.analysis_lambda import AnalysisLambdaService
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ArtifactKind


def _build_runtime(monkeypatch, tmp_path: Path, *, lambda_limits: dict | None = None):
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
        analysis_lambda_service=AnalysisLambdaService(paths, limits=lambda_limits),
    )
    conversation_store = ConversationStore(context.session_factory)
    return dataset_service, artifact_service, registry, conversation_store


def _tool_context(conversation_store: ConversationStore, tool_name: str, arguments: dict) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Run a custom analysis."}],
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
                "region,amount",
                "North,10",
                "South,20",
                "North,15",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def test_analysis_lambda_returns_dict_and_registers_supported_artifacts(monkeypatch, tmp_path: Path) -> None:
    dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )
    code = '''
import numpy as np
from scipy import stats

def analyze(ctx, inputs, params):
    sales = inputs["sales"]
    summary = sales.groupby("region", as_index=False)["amount"].sum()
    table_artifact = ctx.artifact.create("Region summary", summary)
    svg_artifact = ctx.artifact.create(
        "Inline trend",
        "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20'></svg>",
        media_type="image/svg+xml",
    )
    bytes_artifact = ctx.artifact.create("Raw note", b"hello", media_type="text/plain")
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.bar(summary["region"], summary["amount"])
    figure_artifact = ctx.artifact.create(fig, name="Region chart")
    return {
        "markdown": f"![Trend]({svg_artifact.uri}) [Table]({table_artifact.uri})",
        "metrics": {"total": np.float64(sales["amount"].sum())},
        "mean": stats.describe(sales["amount"]).mean,
        "bytes_uri": bytes_artifact.uri,
        "figure_uri": figure_artifact.uri,
    }
'''
    arguments = {
        "code": code,
        "datasets": {"sales": dataset.id},
        "params": {},
        "manifest": {"objective": "summarize sales by region"},
    }
    context = _tool_context(conversation_store, "analysis.lambda", arguments)

    result = registry.execute("analysis.lambda", arguments, context)

    output = result.payload["result"]["output"]
    assert output["metrics"]["total"] == 45.0
    assert output["mean"] == 15.0
    assert "lambda_artifact_" not in output["markdown"]
    assert "artifact://" in output["markdown"]
    assert "lambda_artifact_" not in output["bytes_uri"]
    assert "lambda_artifact_" not in output["figure_uri"]
    assert result.content_blocks == [{"type": "markdown", "text": output["markdown"]}]
    assert len(result.payload["artifacts"]) == 4

    artifacts = artifact_service.list_thread_artifacts(context.thread_id)
    assert len(artifacts) == 4
    kinds = {artifact.kind for artifact in artifacts}
    assert ArtifactKind.IMAGE in kinds
    assert ArtifactKind.FILE in kinds
    for artifact in artifacts:
        assert Path(artifact.absolute_path).exists()
        assert artifact.metadata_payload["analysis_lambda"]["placeholder_id"].startswith("lambda_artifact_")


def test_analysis_lambda_accepts_bytesio_artifact_and_ref_output(monkeypatch, tmp_path: Path) -> None:
    dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )
    code = '''
import io

def analyze(ctx, inputs, params):
    buf = io.BytesIO()
    buf.write(b"note")
    buf.seek(0)
    artifact = ctx.artifact.create(buf, name="analysis_note.txt")
    return {"artifact": artifact, "markdown": f"[note]({artifact.uri})"}
'''
    arguments = {
        "code": code,
        "datasets": {"sales": dataset.id},
    }
    context = _tool_context(conversation_store, "analysis.lambda", arguments)

    result = registry.execute("analysis.lambda", arguments, context)

    output = result.payload["result"]["output"]
    assert output["artifact"]["kind"] == "file"
    assert "lambda_artifact_" not in output["artifact"]["uri"]
    assert "lambda_artifact_" not in output["markdown"]
    [artifact] = artifact_service.list_thread_artifacts(context.thread_id)
    assert artifact.mime_type == "text/plain"
    assert Path(artifact.absolute_path).read_bytes() == b"note"


def test_analysis_lambda_accepts_read_handle_and_value_artifact(monkeypatch, tmp_path: Path) -> None:
    dataset_service, artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )
    code = '''
def analyze(ctx, inputs, params):
    sales = inputs["sales"].read()
    summary = sales.groupby("region", as_index=False)["amount"].sum()
    artifact = ctx.artifact.create(name="region_summary", kind="table", value=summary)
    return {"artifact": artifact, "rows": len(summary)}
'''
    arguments = {
        "code": code,
        "datasets": {"sales": dataset.id},
    }
    context = _tool_context(conversation_store, "analysis.lambda", arguments)

    result = registry.execute("analysis.lambda", arguments, context)

    output = result.payload["result"]["output"]
    assert output["rows"] == 2
    assert output["artifact"]["kind"] == "table"
    assert output["artifact"]["uri"].startswith("artifact://")
    [artifact] = artifact_service.list_thread_artifacts(context.thread_id)
    assert artifact.kind is ArtifactKind.FILE
    assert artifact.mime_type == "text/csv"


def test_analysis_lambda_rejects_non_dict_output(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )
    arguments = {
        "code": "def analyze(ctx, inputs, params):\n    return ['not', 'a', 'dict']\n",
        "datasets": {"sales": dataset.id},
    }

    with pytest.raises(ValidationError, match="must return a dict"):
        registry.execute(
            "analysis.lambda",
            arguments,
            _tool_context(conversation_store, "analysis.lambda", arguments),
        )


def test_analysis_lambda_times_out_bad_code(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _artifact_service, registry, conversation_store = _build_runtime(
        monkeypatch,
        tmp_path,
        lambda_limits={"timeout_seconds": 1},
    )
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )
    arguments = {
        "code": "def analyze(ctx, inputs, params):\n    while True:\n        pass\n",
        "datasets": {"sales": dataset.id},
    }

    with pytest.raises(ValidationError, match="timed out"):
        registry.execute(
            "analysis.lambda",
            arguments,
            _tool_context(conversation_store, "analysis.lambda", arguments),
        )


def test_analysis_lambda_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.lambda" in specs
    schema = specs["analysis.lambda"].parameters_schema
    assert schema["required"] == ["code", "datasets"]
    assert "code" in schema["properties"]
    assert "datasets" in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "reusable" not in schema["properties"]
    description = specs["analysis.lambda"].description
    assert "Supported imports" in description
    assert "seaborn" in description
    assert "xgboost" in description
    assert "inputs[alias].read()" in description
    assert "value=..." in description
