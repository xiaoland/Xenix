from pathlib import Path

import pandas as pd
import pytest

from xenix.exceptions import ValidationError
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
from xenix.services.tabular import TabularRuntimeError


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
        dataset_ids=[],
    )


def _write_report_xlsx(tmp_path: Path) -> Path:
    source = tmp_path / "report.xlsx"
    pd.DataFrame(
        [
            ["品项销售明细", None, None],
            ["营业日期【2026/04/01-2026/04/30】", None, None],
            ["城市", "销售数量", "销售金额(元)"],
            ["佛山市", 1, 118],
        ]
    ).to_excel(source, header=False, index=False)
    return source


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


def test_profile_tools_are_not_agent_exposed(monkeypatch, tmp_path: Path) -> None:
    _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "data.peek" not in specs
    assert "analysis.profile" not in specs


def test_analysis_profile_service_surfaces_structured_runtime_error(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    source = _write_mixed_csv(tmp_path)

    def fail_load(*_args, **_kwargs):
        raise TabularRuntimeError(
            "Polars failed to read the dataset file.",
            error_details={
                "engine": "polars",
                "phase": "read",
                "package_versions": {
                    "polars": "1.42.1",
                    "polars-runtime-32": "1.41.2",
                },
            },
        )

    monkeypatch.setattr("xenix.services.analysis_profile.load_tabular_frame", fail_load)

    with caplog.at_level("ERROR", logger="xenix.services.analysis_profile"):
        with pytest.raises(ValidationError) as exc_info:
            AnalysisProfileService().profile_dataset(
                ProfileDatasetInput(
                    source_path=str(source.resolve()),
                    dataset_name="Sales",
                )
            )

    assert "Dataset profile could not load the tabular runtime" in caplog.text
    assert exc_info.value.error_code == "tabular_runtime_unavailable"
    assert exc_info.value.error_details["operation"] == "analysis.profile"
    assert exc_info.value.error_details["tabular"]["package_versions"]["polars-runtime-32"] == "1.41.2"
    assert any("data.query" in hint for hint in exc_info.value.repair_hints)
    assert exc_info.value.retryable is True


def test_data_query_uses_canonical_names_for_messy_xlsx(monkeypatch, tmp_path: Path) -> None:
    dataset_service, _artifact_service, registry, conversation_store = _build_runtime(monkeypatch, tmp_path)
    source = _write_report_xlsx(tmp_path)
    dataset = dataset_service.register_dataset(RegisterDatasetInput(source_path=str(source.resolve()), name="Report"))
    arguments = {
        "dataset_id": dataset.id,
        "sql": 'SELECT "column_2" FROM input LIMIT 3',
        "limit": 3,
    }

    result = registry.execute(
        "data.query",
        arguments,
        _tool_context(conversation_store, "data.query", arguments),
    )

    assert result.payload["columns"]["data"] == [["column_2", "str", 0]]
    assert result.payload["rows"]["data"] == [[None], ["销售数量"], ["1"]]


def test_data_query_schema_does_not_expose_profile_controls(monkeypatch, tmp_path: Path) -> None:
    _dataset_service, _artifact_service, registry, _conversation_store = _build_runtime(monkeypatch, tmp_path)
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "analysis.profile" not in specs
    assert "data.peek" not in specs
    schema = specs["data.query"].parameters_schema
    assert schema["required"] == ["sql"]
    assert "dataset_id" in schema["properties"]
    assert "source_path" not in schema["properties"]
    assert "target_columns" not in schema["properties"]
    assert "top_n" not in schema["properties"]
    assert "correlation_column_limit" not in schema["properties"]
    assert "rows" not in schema["properties"]
