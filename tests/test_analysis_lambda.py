from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.analysis_lambda import AnalysisLambdaDataset, AnalysisLambdaInput, AnalysisLambdaService
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService


def _build_runtime(monkeypatch, tmp_path: Path, *, lambda_limits: dict | None = None):
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
    analysis_lambda_service = AnalysisLambdaService(paths, limits=lambda_limits)
    registry = AgentToolRegistry(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=data_cleaning_service,
        data_transform_service=data_transform_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
        analysis_lambda_service=analysis_lambda_service,
        preprocessing_worker_runner=worker_runner,
    )
    return dataset_service, registry, None, analysis_lambda_service


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


def _register_sales_dataset(dataset_service: DatasetService, tmp_path: Path):
    return dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(_write_sales_csv(tmp_path).resolve()), name="Sales")
    )


def _lambda_input(dataset, code: str) -> AnalysisLambdaInput:
    return AnalysisLambdaInput(
        code=code,
        datasets=[
            AnalysisLambdaDataset(
                alias="sales",
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                source_path=dataset.source_path,
            )
        ],
        params={},
        manifest={"objective": "summarize sales"},
    )


def test_analysis_lambda_service_returns_dict_and_supported_artifacts(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _registry, _conversation_store, lambda_service = _build_runtime(monkeypatch, tmp_path)
    dataset = _register_sales_dataset(dataset_service, tmp_path)
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

    result = lambda_service.run_lambda(_lambda_input(dataset, code))

    assert result.output["metrics"]["total"] == 45.0
    assert result.output["mean"] == 15.0
    assert "artifact://lambda_artifact_" in result.output["markdown"]
    assert result.output["bytes_uri"].startswith("artifact://lambda_artifact_")
    assert result.output["figure_uri"].startswith("artifact://lambda_artifact_")
    assert len(result.artifacts) == 4
    for artifact in result.artifacts:
        assert Path(artifact.absolute_path).exists()
        assert artifact.placeholder_id.startswith("lambda_artifact_")


def test_analysis_lambda_service_accepts_bytesio_artifact_and_ref_output(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _registry, _conversation_store, lambda_service = _build_runtime(monkeypatch, tmp_path)
    dataset = _register_sales_dataset(dataset_service, tmp_path)
    code = '''
import io

def analyze(ctx, inputs, params):
    buf = io.BytesIO()
    buf.write(b"note")
    buf.seek(0)
    artifact = ctx.artifact.create(buf, name="analysis_note.txt")
    return {"artifact": artifact, "markdown": f"[note]({artifact.uri})"}
'''

    result = lambda_service.run_lambda(_lambda_input(dataset, code))

    assert result.output["artifact"]["kind"] == "file"
    assert result.output["artifact"]["uri"].startswith("artifact://lambda_artifact_")
    assert result.output["markdown"].startswith("[note](artifact://lambda_artifact_")
    [artifact] = result.artifacts
    assert artifact.mime_type == "text/plain"
    assert Path(artifact.absolute_path).read_bytes() == b"note"


def test_analysis_lambda_service_accepts_read_handle_and_value_artifact(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _registry, _conversation_store, lambda_service = _build_runtime(monkeypatch, tmp_path)
    dataset = _register_sales_dataset(dataset_service, tmp_path)
    code = '''
def analyze(ctx, inputs, params):
    sales = inputs["sales"].read()
    summary = sales.groupby("region", as_index=False)["amount"].sum()
    artifact = ctx.artifact.create(name="region_summary", kind="table", value=summary)
    return {"artifact": artifact, "rows": len(summary)}
'''

    result = lambda_service.run_lambda(_lambda_input(dataset, code))

    assert result.output["rows"] == 2
    assert result.output["artifact"]["kind"] == "table"
    assert result.output["artifact"]["uri"].startswith("artifact://lambda_artifact_")
    [artifact] = result.artifacts
    assert artifact.kind == "table"
    assert artifact.mime_type == "text/csv"


def test_analysis_lambda_service_rejects_non_dict_output(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _registry, _conversation_store, lambda_service = _build_runtime(monkeypatch, tmp_path)
    dataset = _register_sales_dataset(dataset_service, tmp_path)
    input_data = _lambda_input(dataset, "def analyze(ctx, inputs, params):\n    return ['not', 'a', 'dict']\n")

    with pytest.raises(ValidationError, match="must return a dict"):
        lambda_service.run_lambda(input_data)


def test_analysis_lambda_service_times_out_bad_code(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _registry, _conversation_store, lambda_service = _build_runtime(
        monkeypatch,
        tmp_path,
        lambda_limits={"timeout_seconds": 1},
    )
    dataset = _register_sales_dataset(dataset_service, tmp_path)
    input_data = _lambda_input(dataset, "def analyze(ctx, inputs, params):\n    while True:\n        pass\n")

    with pytest.raises(ValidationError, match="timed out"):
        lambda_service.run_lambda(input_data)


def test_agent_registry_rejects_unregistered_tool(monkeypatch, tmp_path: Path) -> None:
    _dataset_service, registry, conversation_store, _lambda_service = _build_runtime(monkeypatch, tmp_path)
    arguments = {
        "code": "def analyze(ctx, inputs, params):\n    return {}\n",
        "datasets": {"sales": "dataset-1"},
    }

    with pytest.raises(ValidationError, match="not registered"):
        registry.execute(
            "analysis.lambda",
            arguments,
            _tool_context(conversation_store, "analysis.lambda", arguments),
        )
