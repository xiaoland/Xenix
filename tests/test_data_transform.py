import sqlite3
from pathlib import Path

import duckdb
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
from xenix.services.dataset_export_service import DatasetExportService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.dataset_inspection import detect_source_format, load_dataframe
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService
import xenix.services.data_transform as data_transform_module


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


def _register_report_xlsx(dataset_service: DatasetService, tmp_path: Path):
    source = tmp_path / "report.xlsx"
    pd.DataFrame(
        [
            ["品项销售明细", None, None],
            ["营业日期【2026/04/01-2026/04/30】", None, None],
            ["城市", "销售数量", "销售金额(元)"],
            ["佛山市", 1, 118],
        ]
    ).to_excel(source, header=False, index=False)
    return dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Report")
    )


def _read_dataset_frame(path: str | Path) -> pd.DataFrame:
    source_path = Path(path)
    return load_dataframe(source_path, detect_source_format(source_path))


def test_data_integrate_tool_uses_dataset_ids_and_returns_artifact_id(monkeypatch, tmp_path: Path) -> None:
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
    assert _read_dataset_frame(derived_dataset.source_path)["order_id"].tolist() == [1, 2]
    assert result.payload["input_dataset_ids"] == [orders.id, more_orders.id]
    assert "dataset_uri" not in result.payload
    assert "artifact_uri" not in result.payload
    artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    assert artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert artifact.metadata_payload["dataset_export"]["dataset_id"] == derived_dataset.id
    assert Path(artifact.absolute_path).suffix == ".xlsx"
    assert pd.read_excel(artifact.absolute_path)["order_id"].tolist() == [1, 2]
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
    assert result.total_row_count == 2
    assert result.truncated is False
    assert result.validation_summary["read_only"] is True
    assert result.validation_summary["bindings"] == ["orders"]


def test_data_transform_service_materializes_parquet(monkeypatch, tmp_path: Path) -> None:
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

    frame = _read_dataset_frame(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "total_amount": 25.0},
        {"customer_id": 2, "total_amount": 5.0},
    ]
    assert result.row_count == 2
    assert Path(result.output_path).suffix == ".parquet"
    assert result.transform_report["sql"].startswith("SELECT customer_id")
    assert result.transform_report["bindings"] == [{"alias": "input", "dataset_id": "customers-id"}]


def test_data_transform_service_does_not_fetch_full_output_dataframe(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "orders.csv"
    source.write_text("order_id,amount\n1,10\n2,20\n", encoding="utf-8")
    real_connect = duckdb.connect

    class CursorProxy:
        def __init__(self, cursor, sql: object) -> None:
            self._cursor = cursor
            self._sql = str(sql)

        def fetchdf(self):
            normalized = " ".join(self._sql.split()).lower()
            if normalized == "select * from output":
                raise AssertionError("transform must not fetch the full output relation into pandas")
            return self._cursor.fetchdf()

        def __getattr__(self, name: str):
            return getattr(self._cursor, name)

    class ConnectionProxy:
        def __init__(self, connection) -> None:
            self._connection = connection

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._connection.__exit__(exc_type, exc, tb)

        def execute(self, sql, *args, **kwargs):
            return CursorProxy(self._connection.execute(sql, *args, **kwargs), sql)

        def __getattr__(self, name: str):
            return getattr(self._connection, name)

    def connect_proxy(*args, **kwargs):
        return ConnectionProxy(real_connect(*args, **kwargs))

    monkeypatch.setattr(data_transform_module.duckdb, "connect", connect_proxy)

    result = service.transform(
        DataTransformInput(
            bindings=[
                DatasetSqlBinding(
                    alias="input",
                    dataset_id="orders-id",
                    source_path=str(source.resolve()),
                )
            ],
            sql="SELECT * FROM input ORDER BY order_id",
            name="Orders copy",
        )
    )

    assert _read_dataset_frame(result.output_path)["amount"].tolist() == [10, 20]


def test_data_transform_tool_does_not_leave_dataset_or_output_when_output_validation_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, dataset_service, service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "order_id,amount\n1,10\n2,20\n",
    )

    def fail_validation(_self, _output_path: Path) -> None:
        raise ValidationError("Synthetic output validation failure.")

    monkeypatch.setattr(DataQueryTransformService, "_validate_transform_output", fail_validation)
    arguments = {
        "dataset_id": dataset.id,
        "sql": "SELECT * FROM input",
        "name": "Broken transform",
    }

    with pytest.raises(ValidationError, match="Synthetic output validation failure"):
        registry.execute("data.transform", arguments, _tool_context(store, "data.transform", arguments))

    transformed_dir = paths.temp / "datasets" / "transformed"
    assert not list(transformed_dir.glob("broken-transform-*.parquet"))
    with sqlite3.connect(paths.state / "xenix.db") as connection:
        derived_count = connection.execute(
            "SELECT COUNT(*) FROM dataset WHERE derived_from_dataset_id = ?",
            (dataset.id,),
        ).fetchone()[0]
    assert derived_count == 0


def test_data_transform_tool_discards_dataset_when_export_artifact_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, dataset_service, _service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "order_id,amount\n1,10\n2,20\n",
    )

    def fail_export(_self, *_args, **_kwargs) -> None:
        raise RuntimeError("Synthetic export artifact failure.")

    monkeypatch.setattr(DatasetExportService, "materialize_dataset_export_artifact", fail_export)
    arguments = {
        "dataset_id": dataset.id,
        "sql": "SELECT * FROM input",
        "name": "Broken export",
    }

    with pytest.raises(RuntimeError, match="Synthetic export artifact failure"):
        registry.execute("data.transform", arguments, _tool_context(store, "data.transform", arguments))

    with sqlite3.connect(paths.state / "xenix.db") as connection:
        derived_count = connection.execute(
            "SELECT COUNT(*) FROM dataset WHERE derived_from_dataset_id = ?",
            (dataset.id,),
        ).fetchone()[0]
    assert derived_count == 0
    assert not list((paths.state / "datasets" / "derived").glob("*.parquet"))


def test_data_transform_tool_requires_output_relation_for_multi_statement_scripts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, dataset_service, _service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "order_id,amount\n1,10\n2,20\n",
    )
    arguments = {
        "dataset_id": dataset.id,
        "sql": "CREATE TEMP TABLE stage AS SELECT * FROM input",
        "name": "No output",
    }

    with pytest.raises(ValidationError, match="must leave a final relation named output"):
        registry.execute("data.transform", arguments, _tool_context(store, "data.transform", arguments))

    with sqlite3.connect(_paths.state / "xenix.db") as connection:
        derived_count = connection.execute(
            "SELECT COUNT(*) FROM dataset WHERE derived_from_dataset_id = ?",
            (dataset.id,),
        ).fetchone()[0]
    assert derived_count == 0


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
    assert result.payload["total_row_count"] == 3
    assert result.payload["truncated"] is True
    assert list(result.payload) == ["columns", "rows", "returned_row_count", "total_row_count", "truncated"]
    assert result.payload["columns"] == {
        "_schema": {"name": 0, "type": 1, "index": 2},
        "data": [["order_id", "int64", 0], ["amount", "int64", 1]],
    }
    assert result.payload["rows"] == {
        "_schema": {"order_id": 0, "amount": 1},
        "data": [[3, 30], [2, 20]],
    }
    assert "bindings" not in result.payload
    assert "input_dataset_ids" not in result.payload
    assert "limit" not in result.payload
    assert "validation_summary" not in result.payload
    assert not hasattr(result, "content_blocks")


def test_data_query_tool_uses_bindings_when_dataset_id_is_also_present(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    ignored = _register_csv(
        dataset_service,
        tmp_path,
        "ignored",
        "order_id,amount\n1,10\n",
    )
    orders = _register_csv(
        dataset_service,
        tmp_path,
        "orders",
        "order_id,amount\n2,20\n",
    )
    arguments = {
        "dataset_id": ignored.id,
        "bindings": [{"alias": "orders", "dataset_id": orders.id}],
        "sql": "SELECT order_id, amount FROM orders",
    }

    result = registry.execute("data.query", arguments, _tool_context(store, "data.query", arguments))

    assert result.payload["rows"]["_schema"] == {"order_id": 0, "amount": 1}
    assert result.payload["rows"]["data"] == [[2, 20]]
    assert result.payload["total_row_count"] == 1


def test_data_query_tool_accepts_canonical_names_for_messy_xlsx(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    dataset = _register_report_xlsx(dataset_service, tmp_path)
    arguments = {
        "dataset_id": dataset.id,
        "sql": 'SELECT "column_2" FROM input LIMIT 3',
        "limit": 3,
    }

    result = registry.execute("data.query", arguments, _tool_context(store, "data.query", arguments))

    assert result.payload["columns"] == {
        "_schema": {"name": 0, "type": 1, "index": 2},
        "data": [["column_2", "str", 0]],
    }
    assert result.payload["rows"] == {
        "_schema": {"column_2": 0},
        "data": [[None], ["销售数量"], ["1"]],
    }
    assert result.payload["total_row_count"] == 3


def test_data_transform_tool_registers_derived_dataset_and_returns_artifact_id(monkeypatch, tmp_path: Path) -> None:
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
    frame = _read_dataset_frame(derived_dataset.source_path)

    assert derived_dataset.derived_from_dataset_id == dataset.id
    assert "dataset_uri" not in result.payload
    assert "artifact_uri" not in result.payload
    artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    assert artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert artifact.metadata_payload["dataset_export"]["source_path"] == derived_dataset.source_path
    assert pd.read_excel(artifact.absolute_path).to_dict(orient="records") == [
        {"customer_id": 1, "total_amount": 25},
        {"customer_id": 2, "total_amount": 5},
    ]
    assert result.payload["row_count"] == 2
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "total_amount": 25.0},
        {"customer_id": 2, "total_amount": 5.0},
    ]
    assert (
        result.payload["transform_report"]["validation_summary"]["requires_output_relation"]
        == "output"
    )


def test_data_transform_tool_records_multi_input_lineage_in_result(monkeypatch, tmp_path: Path) -> None:
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

    assert derived_dataset.derived_from_dataset_id is None
    assert result.payload["input_dataset_ids"] == [orders.id, customers.id]
    assert "dataset_uri" not in result.payload
    artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    assert artifact.metadata_payload["input_dataset_ids"] == [orders.id, customers.id]
