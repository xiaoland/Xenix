from pathlib import Path

import pandas as pd

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import CleanDatasetInput, DataCleaningService
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
    return paths, dataset_service, data_cleaning_service, artifact_service, registry, conversation_store


def _tool_context(conversation_store: ConversationStore, arguments: dict) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Clean this dataset."}],
        )
    )
    _tool_message, tool_call = conversation_store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name="data.clean",
            arguments_payload=arguments,
        )
    )
    return ToolExecutionContext(
        thread_id=thread.id,
        turn_id=turn.id,
        tool_call_id=tool_call.id,
        attached_files=[],
    )


def test_data_cleaning_service_preserves_default_cleaning_behavior(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "customers.csv"
    source.write_text(
        "customer_id,amount,segment\n"
        "1,10,A\n"
        "1,10,A\n"
        "2,,B\n"
        "3,30,\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Customers cleaned",
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "amount": 10.0, "segment": "A"},
        {"customer_id": 2, "amount": 20.0, "segment": "B"},
        {"customer_id": 3, "amount": 30.0, "segment": "A"},
    ]
    assert result.report["row_count_before"] == 4
    assert result.report["row_count_after"] == 3
    assert result.report["rows_removed"] == 1
    assert result.report["operations"][0]["operation"] == "duplicates"


def test_data_cleaning_service_applies_atomic_operations(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "orders.csv"
    source.write_text(
        "order_id,amount,region,active\n"
        "1,10, north ,Y\n"
        "2,-5,north,N\n"
        "3,, SOUTH ,yes\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Orders cleaned",
            duplicate_policy={"mode": "none"},
            type_corrections=[
                {"column": "amount", "target_type": "numeric"},
                {"column": "active", "target_type": "boolean"},
            ],
            text_standardization=[
                {
                    "columns": ["region"],
                    "trim": True,
                    "lowercase": True,
                    "collapse_whitespace": True,
                }
            ],
            missing_policy={
                "default_numeric": "constant",
                "default_text": "mode",
                "fill_values": {"amount": 0},
            },
            validation_rules=[
                {
                    "name": "amount_non_negative",
                    "column": "amount",
                    "rule": "non_negative",
                    "action": "drop_rows",
                }
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"order_id": 1, "amount": 10.0, "region": "north", "active": True},
        {"order_id": 3, "amount": 0.0, "region": "south", "active": True},
    ]
    assert result.report["row_count_after"] == 2
    assert result.report["validation_rules"] == [
        {
            "name": "amount_non_negative",
            "column": "amount",
            "rule": "non_negative",
            "action": "drop_rows",
            "violations": 1,
            "rows_removed": 1,
        }
    ]


def test_data_clean_tool_registers_derived_dataset_and_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _cleaning_service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "customers.csv"
    source.write_text(
        "customer_id,amount,segment\n"
        "1,10,A\n"
        "1,10,A\n"
        "2,,B\n",
        encoding="utf-8",
    )
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Customers",
        )
    )
    arguments = {
        "dataset_id": source_dataset.id,
        "name": "Customers cleaned",
        "duplicate_policy": {"mode": "key_columns", "columns": ["customer_id"], "keep": "first"},
    }
    context = _tool_context(store, arguments)

    result = registry.execute("data.clean", arguments, context)
    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")

    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert derived_dataset.project_id == source_dataset.project_id
    assert result.payload["row_count_before"] == 3
    assert result.payload["row_count_after"] == 2
    assert result.payload["cleaning_report"]["operations"][0]["mode"] == "key_columns"
    assert resolved_artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert resolved_artifact.metadata_payload["derived_from_dataset_id"] == source_dataset.id
    assert "artifact://" in result.payload["artifact_link"]


def test_data_clean_tool_schema_stays_compact(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _cleaning_service, _artifact_service, registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "project_id" not in specs["data.peek"].parameters_schema["properties"]
    assert "project_id" not in specs["data.integrate"].parameters_schema["properties"]
    assert "profile" not in specs["data.clean"].parameters_schema["properties"]
    assert "duplicate_policy" in specs["data.clean"].parameters_schema["properties"]
    assert "drop_duplicates" in specs["data.clean"].parameters_schema["properties"]
