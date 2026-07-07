from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
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


def _tool_context(
    conversation_store: ConversationStore,
    tool_name: str,
    arguments: dict,
) -> ToolExecutionContext:
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


def test_data_cleaning_service_no_ops_returns_source_without_cleaning(monkeypatch, tmp_path: Path) -> None:
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

    frame = pd.read_csv(source)
    assert len(frame.index) == 4
    assert frame.duplicated().sum() == 1
    assert frame["amount"].isna().sum() == 1
    assert frame["segment"].isna().sum() == 1
    assert result.output_path == str(source.resolve())
    assert result.report["row_count_before"] == 4
    assert result.report["row_count_after"] == 4
    assert result.report["rows_removed"] == 0
    assert result.report["operations"] == []
    assert result.report["no_op"] is True


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
            operations=[
                {"operation": "type.convert", "params": {"column": "amount", "target_type": "numeric"}},
                {"operation": "type.convert", "params": {"column": "active", "target_type": "boolean"}},
                {"operation": "text.trim", "params": {"columns": ["region"]}},
                {"operation": "text.lowercase", "params": {"columns": ["region"]}},
                {"operation": "missing.fill_constant", "params": {"columns": ["amount"], "value": 0}},
                {
                    "operation": "validation.non_negative",
                    "params": {"name": "amount_non_negative", "column": "amount", "action": "drop_rows"},
                },
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
            "operation": "validation.non_negative",
            "action": "drop_rows",
            "violations": 1,
            "rows_removed": 1,
        }
    ]
    assert [operation["operation"] for operation in result.report["operations"]] == [
        "type.convert",
        "type.convert",
        "text.trim",
        "text.lowercase",
        "missing.fill_constant",
    ]


def test_data_cleaning_service_normalizes_column_names(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "messy_columns.csv"
    source.write_text(
        " 产品 价格（元） ,Product Price,金额,金额 ,###\n"
        "10,20,30,40,50\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Normalized columns",
            operations=[
                {"operation": "schema.normalize_column_names", "params": {}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.columns.tolist() == ["产品_价格_元", "product_price", "金额", "金额_2", "column_5"]
    operation_report = result.report["operations"][0]
    assert operation_report["operation"] == "schema.normalize_column_names"
    assert operation_report["columns_changed"] == 4
    assert operation_report["mapping"][0] == {"old": " 产品 价格（元） ", "new": "产品_价格_元"}
    assert operation_report["generated_empty_names"] == [{"column_index": 4, "new": "column_5"}]
    assert operation_report["duplicate_collisions"] == [
        {"column_index": 3, "base_name": "金额", "resolved_name": "金额_2"}
    ]


def test_data_cleaning_service_drops_high_missing_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "missing_columns.csv"
    source.write_text(
        "id,mostly_missing,sometimes_missing,kept\n"
        "1,,x,a\n"
        "2,,,b\n"
        "3,,y,c\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Dropped sparse columns",
            operations=[
                {"operation": "missing.drop_high_missing_columns", "params": {"threshold": 0.5}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.columns.tolist() == ["id", "sometimes_missing", "kept"]
    operation_report = result.report["operations"][0]
    assert operation_report["dropped_columns"] == ["mostly_missing"]
    assert operation_report["columns_removed"] == 1
    assert operation_report["missing_ratios"]["mostly_missing"] == 1.0
    assert operation_report["missing_ratios"]["sometimes_missing"] == pytest.approx(1 / 3)


def test_data_cleaning_service_clips_iqr_outliers(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "outliers.csv"
    source.write_text("amount\n1\n2\n3\n100\n", encoding="utf-8")

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Clipped outliers",
            operations=[
                {"operation": "outlier.clip_iqr", "params": {"columns": ["amount"], "multiplier": 1.5}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    summary = result.report["operations"][0]["columns_summary"][0]
    assert frame["amount"].max() == summary["upper_bound"]
    assert summary["cells_clipped"] == 1
    assert summary["lower_bound"] == pytest.approx(-36.5)
    assert summary["upper_bound"] == pytest.approx(65.5)


def test_data_cleaning_service_one_hot_encodes_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "segments.csv"
    source.write_text(
        "id,segment\n"
        "1,A\n"
        "2,B\n"
        "3,A\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Encoded segments",
            operations=[
                {"operation": "encoding.one_hot", "params": {"columns": ["segment"], "max_categories": 10}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"id": 1, "segment_a": 1, "segment_b": 0},
        {"id": 2, "segment_a": 0, "segment_b": 1},
        {"id": 3, "segment_a": 1, "segment_b": 0},
    ]
    operation_report = result.report["operations"][0]
    assert operation_report["encoded_columns"] == ["segment"]
    assert operation_report["columns_summary"][0]["generated_columns"] == ["segment_a", "segment_b"]


def test_data_cleaning_service_one_hot_skips_high_cardinality_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "high_cardinality.csv"
    source.write_text(
        "id,segment\n"
        "1,A\n"
        "2,B\n"
        "3,C\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Skipped high cardinality",
            operations=[
                {"operation": "encoding.one_hot", "params": {"columns": ["segment"], "max_categories": 2}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame.columns.tolist() == ["id", "segment"]
    operation_report = result.report["operations"][0]
    assert operation_report["encoded_columns"] == []
    assert operation_report["skipped_columns"] == [
        {
            "column": "segment",
            "category_count": 3,
            "max_categories": 2,
            "reason": "too_many_categories",
        }
    ]
    assert "above max_categories=2" in result.report["warnings"][0]


def test_data_cleaning_service_scales_numeric_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "scale.csv"
    source.write_text(
        "amount,score,const\n"
        "1,1,5\n"
        "3,2,5\n"
        "5,3,5\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Scaled numeric columns",
            operations=[
                {"operation": "scaling.minmax", "params": {"columns": ["amount"], "feature_range": [0, 1]}},
                {"operation": "scaling.standard", "params": {"columns": ["score", "const"]}},
            ],
        )
    )

    frame = pd.read_csv(result.output_path)
    assert frame["amount"].tolist() == [0.0, 0.5, 1.0]
    assert frame["score"].tolist() == pytest.approx([-1.2247448714, 0.0, 1.2247448714])
    assert frame["const"].tolist() == [5, 5, 5]
    assert result.report["operations"][0]["columns_summary"][0]["original_min"] == 1.0
    assert result.report["operations"][1]["columns_summary"][1]["scaled"] is False
    assert "standard scaling left it unchanged" in result.report["warnings"][0]


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
        "operations": [
            {
                "operation": "duplicate.key_columns",
                "params": {"columns": ["customer_id"], "keep": "first"},
            }
        ],
    }
    context = _tool_context(store, "data.clean", arguments)

    result = registry.execute("data.clean", arguments, context)
    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")

    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert derived_dataset.project_id == source_dataset.project_id
    assert result.payload["row_count_before"] == 3
    assert result.payload["row_count_after"] == 2
    assert result.payload["cleaning_report"]["operations"][0]["operation"] == "duplicate.key_columns"
    assert resolved_artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert resolved_artifact.metadata_payload["derived_from_dataset_id"] == source_dataset.id
    assert "artifact_link" not in result.payload


def test_data_clean_tool_no_ops_reports_nothing_happened(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _cleaning_service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "customers.csv"
    source.write_text("customer_id,amount\n1,10\n", encoding="utf-8")
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Customers",
        )
    )
    arguments = {"dataset_id": source_dataset.id, "operations": []}
    context = _tool_context(store, "data.clean", arguments)

    result = registry.execute("data.clean", arguments, context)

    assert result.payload["dataset_id"] == source_dataset.id
    assert result.payload["cleaning_report"]["no_op"] is True
    assert "artifact_id" not in result.payload
    assert artifact_service.list_thread_artifacts(context.thread_id) == []
    assert "Nothing happened" in result.payload["message"]
    assert not hasattr(result, "content_blocks")


def test_data_clean_tool_rejects_legacy_policy_fields(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _cleaning_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "customers.csv"
    source.write_text("customer_id,amount\n1,10\n", encoding="utf-8")
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Customers",
        )
    )
    arguments = {"dataset_id": source_dataset.id, "duplicate_policy": {"mode": "exact_rows"}}
    context = _tool_context(store, "data.clean", arguments)

    with pytest.raises(ValidationError, match="duplicate_policy"):
        registry.execute("data.clean", arguments, context)


def test_data_clean_metadata_returns_operation_group_schemas(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _cleaning_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    arguments = {"groups": ["missing", "text"]}
    context = _tool_context(store, "data.clean.metadata", arguments)

    result = registry.execute("data.clean.metadata", arguments, context)

    assert result.payload["group_names"] == [
        "schema",
        "duplicates",
        "missing",
        "types",
        "text",
        "validation",
        "outliers",
        "encoding",
        "scaling",
    ]
    assert [group["group"] for group in result.payload["groups"]] == ["missing", "text"]
    operations = [
        operation["operation"]
        for group in result.payload["groups"]
        for operation in group["operations"]
    ]
    assert "missing.fill_constant" in operations
    assert "missing.drop_high_missing_columns" in operations
    assert "text.map_values" in operations

    all_result = registry.execute("data.clean.metadata", {}, context)
    all_operations = [
        operation["operation"]
        for group in all_result.payload["groups"]
        for operation in group["operations"]
    ]
    assert "schema.normalize_column_names" in all_operations
    assert "outlier.clip_iqr" in all_operations
    assert "encoding.one_hot" in all_operations
    assert "scaling.minmax" in all_operations
    assert "scaling.standard" in all_operations


def test_data_clean_tool_schema_stays_compact(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _cleaning_service, _artifact_service, registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "project_id" not in specs["data.peek"].parameters_schema["properties"]
    assert "project_id" not in specs["data.integrate"].parameters_schema["properties"]
    assert "source_path" not in specs["data.peek"].parameters_schema["properties"]
    assert "source_paths" not in specs["data.integrate"].parameters_schema["properties"]
    assert specs["data.integrate"].parameters_schema["required"] == ["dataset_ids"]
    assert "profile" not in specs["data.clean"].parameters_schema["properties"]
    assert "duplicate_policy" not in specs["data.clean"].parameters_schema["properties"]
    assert "drop_duplicates" not in specs["data.clean"].parameters_schema["properties"]
    assert "missing_policy" not in specs["data.clean"].parameters_schema["properties"]
    assert "operations" in specs["data.clean"].parameters_schema["properties"]
    operation_schema = specs["data.clean"].parameters_schema["properties"]["operations"]["items"]
    assert set(operation_schema["properties"]) == {"operation", "params"}
    assert "enum" not in operation_schema["properties"]["operation"]
    assert "data.clean.metadata" in specs
    assert specs["data.clean.metadata"].parameters_schema["properties"]["groups"]["items"] == {"type": "string"}
