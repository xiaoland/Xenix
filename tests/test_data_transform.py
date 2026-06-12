from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_transform import (
    DataQueryInput,
    DataQueryTransformService,
    DataTransformInput,
    DatasetSqlBinding,
)
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
    return paths, dataset_service, data_transform_service, artifact_service, registry, conversation_store


def _tool_context(conversation_store: ConversationStore, tool_name: str, arguments: dict) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Query this dataset."}],
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


def _register_csv(dataset_service: DatasetService, tmp_path: Path, name: str, content: str):
    source = tmp_path / f"{name}.csv"
    source.write_text(content, encoding="utf-8")
    return dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name=name)
    )


def test_data_integrate_tool_uses_dataset_ids_and_registers_generated_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    orders = _register_csv(dataset_service, tmp_path, "orders", "order_id,amount\n1,10\n")
    more_orders = _register_csv(dataset_service, tmp_path, "more-orders", "order_id,amount\n2,20\n")
    arguments = {"dataset_ids": [orders.id, more_orders.id], "name": "All orders"}

    result = registry.execute(
        "data.integrate",
        arguments,
        _tool_context(store, "data.integrate", arguments),
    )

    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    assert pd.read_csv(derived_dataset.source_path)["order_id"].tolist() == [1, 2]
    assert result.payload["input_dataset_ids"] == [orders.id, more_orders.id]
    assert resolved_artifact.metadata_payload["input_dataset_ids"] == [orders.id, more_orders.id]
    assert "source_path" not in result.payload["inspection"]


def test_data_query_service_runs_read_only_select(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "orders.csv"
    source.write_text(
        "order_id,region,amount\n"
        "1,north,10\n"
        "2,north,20\n"
        "3,south,5\n",
        encoding="utf-8",
    )

    result = service.query(
        DataQueryInput(
            bindings=[
                DatasetSqlBinding(
                    alias="orders",
                    dataset_id="orders-id",
                    source_path=str(source.resolve()),
                )
            ],
            sql=(
                "WITH totals AS ("
                " SELECT region, SUM(amount) AS total_amount FROM orders GROUP BY region"
                ") SELECT * FROM totals ORDER BY total_amount DESC"
            ),
            limit=2,
        )
    )

    assert result.rows == [
        {"region": "north", "total_amount": 30.0},
        {"region": "south", "total_amount": 5.0},
    ]
    assert result.returned_row_count == 2
    assert result.truncated is False
    assert result.validation_summary["read_only"] is True
    assert result.validation_summary["bindings"] == ["orders"]


def test_data_transform_service_materializes_csv(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "customers.csv"
    source.write_text(
        "customer_id,amount\n"
        "1,10\n"
        "1,15\n"
        "2,5\n",
        encoding="utf-8",
    )

    result = service.transform(
        DataTransformInput(
            bindings=[
                DatasetSqlBinding(
                    alias="input",
                    dataset_id="customers-id",
                    source_path=str(source.resolve()),
                )
            ],
            sql="SELECT customer_id, SUM(amount) AS total_amount FROM input GROUP BY customer_id ORDER BY customer_id",
            name="Customer totals",
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "total_amount": 25.0},
        {"customer_id": 2, "total_amount": 5.0},
    ]
    assert result.row_count == 2
    assert result.transform_report["sql"].startswith("SELECT customer_id")
    assert result.transform_report["bindings"] == [{"alias": "input", "dataset_id": "customers-id"}]


def test_duckdb_sql_validator_rejects_mutation_and_file_scans(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "orders.csv"
    source.write_text("id,value\n1,2\n", encoding="utf-8")
    binding = DatasetSqlBinding(alias="input", dataset_id="orders-id", source_path=str(source.resolve()))

    with pytest.raises(ValidationError, match="unsupported statement keyword"):
        service.query(DataQueryInput(bindings=[binding], sql="UPDATE input SET value = 3", limit=10))

    with pytest.raises(ValidationError, match="single statement"):
        service.query(DataQueryInput(bindings=[binding], sql="SELECT * FROM input; SELECT * FROM input", limit=10))

    with pytest.raises(ValidationError, match="file scan function"):
        service.query(DataQueryInput(bindings=[binding], sql="SELECT * FROM read_csv('orders.csv')", limit=10))

    with pytest.raises(ValidationError, match="direct file paths"):
        service.query(DataQueryInput(bindings=[binding], sql="SELECT * FROM 'orders.csv'", limit=10))


def test_data_query_and_transform_tools_are_registered(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _service, _artifact_service, registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "data.query" in specs
    assert "data.transform" in specs
    assert "data.duckdb" not in specs
    assert "sql" in specs["data.query"].parameters_schema["required"]
    assert "sql" in specs["data.transform"].parameters_schema["required"]


def test_data_query_tool_returns_bounded_rows(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "order_id,amount\n1,10\n2,20\n3,30\n",
    )
    arguments = {
        "dataset_id": dataset.id,
        "sql": "SELECT * FROM input ORDER BY amount DESC",
        "limit": 2,
    }

    result = registry.execute("data.query", arguments, _tool_context(store, "data.query", arguments))

    assert result.payload["returned_row_count"] == 2
    assert result.payload["truncated"] is True
    assert result.payload["rows"] == [
        {"order_id": 3, "amount": 30},
        {"order_id": 2, "amount": 20},
    ]
    assert result.payload["bindings"] == [{"alias": "input", "dataset_id": dataset.id}]
    assert "Query returned 2 row(s)" in result.content_blocks[0]["text"]


def test_data_transform_tool_registers_derived_dataset_and_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_csv(
        dataset_service,
        tmp_path,
        "customers",
        "customer_id,amount\n1,10\n1,15\n2,5\n",
    )
    arguments = {
        "dataset_id": dataset.id,
        "sql": "SELECT customer_id, SUM(amount) AS total_amount FROM input GROUP BY customer_id ORDER BY customer_id",
        "name": "Customer totals",
    }

    result = registry.execute(
        "data.transform",
        arguments,
        _tool_context(store, "data.transform", arguments),
    )
    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    frame = pd.read_csv(derived_dataset.source_path)

    assert derived_dataset.derived_from_dataset_id == dataset.id
    assert result.payload["row_count"] == 2
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "total_amount": 25.0},
        {"customer_id": 2, "total_amount": 5.0},
    ]
    assert resolved_artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert resolved_artifact.metadata_payload["derived_from_dataset_id"] == dataset.id
    assert resolved_artifact.metadata_payload["input_dataset_ids"] == [dataset.id]
    assert resolved_artifact.metadata_payload["transform_report"]["validation_summary"]["read_only"] is True


def test_data_transform_tool_records_multi_input_lineage_in_artifact_metadata(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    orders = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "customer_id,amount\n1,10\n2,5\n",
    )
    customers = _register_csv(
        dataset_service,
        tmp_path,
        "customers",
        "customer_id,segment\n1,A\n2,B\n",
    )
    arguments = {
        "bindings": [
            {"alias": "orders", "dataset_id": orders.id},
            {"alias": "customers", "dataset_id": customers.id},
        ],
        "sql": (
            "SELECT customers.segment, SUM(orders.amount) AS total_amount "
            "FROM orders JOIN customers USING (customer_id) "
            "GROUP BY customers.segment ORDER BY customers.segment"
        ),
        "name": "Segment totals",
    }

    result = registry.execute(
        "data.transform",
        arguments,
        _tool_context(store, "data.transform", arguments),
    )
    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")

    assert derived_dataset.derived_from_dataset_id is None
    assert resolved_artifact.metadata_payload["input_dataset_ids"] == [orders.id, customers.id]
    assert result.payload["input_dataset_ids"] == [orders.id, customers.id]
