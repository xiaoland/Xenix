import json
import re
from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tools import (
    MAX_CLEANING_REPORT_COLUMN_NAME_CHARS,
    MAX_CLEANING_REPORT_WARNING_CHARS,
    AgentToolRegistry,
    ToolExecutionContext,
)
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import CleanDatasetInput, DataCleaningService
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.dataset_inspection import detect_source_format, load_dataframe
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService


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
    return paths, dataset_service, data_cleaning_service, artifact_service, registry, None


def _read_dataset_frame(path: str | Path) -> pd.DataFrame:
    source_path = Path(path)
    return load_dataframe(source_path, detect_source_format(source_path))


def _xtt_metadata(value: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}: (.+)$", value, re.MULTILINE)
    assert match is not None, f"missing XTT metadata field {key!r}: {value}"
    return match.group(1)


def _tool_context(
    _conversation_store,
    tool_name: str,
    arguments: dict,
) -> ToolExecutionContext:
    return ToolExecutionContext(
        thread_id="tool-test-thread",
        dataset_ids=(),
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

    frame = _read_dataset_frame(result.output_path)
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


def test_data_cleaning_service_resolves_zero_based_column_indexes_and_rejects_mixed_references(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "indexed-columns.csv"
    source.write_text(
        "customer_id,amount,segment\n"
        "1,, north \n"
        "2,20,south\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Indexed columns",
            operations=[
                {"operation": "missing.fill_constant", "params": {"column_indexes": [1], "value": 0}},
                {"operation": "text.trim", "params": {"column_indexes": [2]}},
                {"operation": "validation.non_negative", "params": {"column_index": 1}},
            ],
        )
    )

    frame = _read_dataset_frame(result.output_path)
    assert frame.to_dict(orient="records") == [
        {"customer_id": 1, "amount": 0.0, "segment": "north"},
        {"customer_id": 2, "amount": 20.0, "segment": "south"},
    ]

    with pytest.raises(ValidationError, match="column_indexes or column_names, not both"):
        cleaning_service.clean_dataset(
            CleanDatasetInput(
                source_path=str(source.resolve()),
                name="Mixed columns",
                operations=[
                    {
                        "operation": "text.trim",
                        "params": {"column_indexes": [2], "column_names": ["segment"]},
                    }
                ],
            )
        )


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

    frame = _read_dataset_frame(result.output_path)
    # The source schema is canonicalized by position before operations.  The
    # duplicate/empty headers therefore arrive at the cleaning operation as
    # deterministic tool names and remain stable in its report.
    assert frame.columns.tolist() == ["产品_价格_元", "product_price", "column_3", "column_4", "column_5"]
    operation_report = result.report["operations"][0]
    assert operation_report["operation"] == "schema.normalize_column_names"
    assert operation_report["columns_changed"] == 3
    assert operation_report["mapping"][0] == {"old": "产品 价格（元）", "new": "产品_价格_元"}
    assert operation_report["generated_empty_names"] == [{"column_index": 4, "new": "column_5"}]
    assert operation_report["duplicate_collisions"] == []


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

    frame = _read_dataset_frame(result.output_path)
    assert frame.columns.tolist() == ["id", "sometimes_missing", "kept"]
    operation_report = result.report["operations"][0]
    assert operation_report["dropped_columns"] == ["mostly_missing"]
    assert operation_report["columns_removed"] == 1
    assert operation_report["missing_ratios"]["mostly_missing"] == 1.0
    assert operation_report["missing_ratios"]["sometimes_missing"] == pytest.approx(1 / 3)


def test_data_cleaning_canonicalizes_malformed_headers_before_index_operations(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "malformed-headers.csv"
    source.write_text("record_id,,备注\n1, ,良好\n", encoding="utf-8")

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Canonical headers",
            operations=[
                {"operation": "text.trim", "params": {"column_indexes": [1]}},
            ],
        )
    )

    frame = _read_dataset_frame(result.output_path)
    assert frame.columns.tolist() == ["record_id", "column_2", "备注"]
    assert result.report["operations"][0]["column"] == "column_2"


@pytest.mark.parametrize(
    ("boundary_operation", "boundary_params"),
    [
        (
            "missing.drop_high_missing_columns",
            {"threshold": 0.5},
        ),
        (
            "encoding.one_hot",
            {"columns": ["segment"], "max_categories": 10},
        ),
    ],
)
def test_data_cleaning_service_rejects_stale_indexes_after_column_set_boundary(
    monkeypatch,
    tmp_path: Path,
    boundary_operation: str,
    boundary_params: dict,
) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / f"stale-index-{boundary_operation.split('.')[0]}.csv"
    source.write_text(
        "id,mostly_missing,segment,amount\n"
        "1,,A,10\n"
        "2,,B,20\n"
        "3,,A,30\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match=r"column_index\(es\).*new data.query/data.clean call"):
        cleaning_service.clean_dataset(
            CleanDatasetInput(
                source_path=str(source.resolve()),
                name="Stale index rejection",
                operations=[
                    {"operation": boundary_operation, "params": boundary_params},
                    {"operation": "text.trim", "params": {"column_indexes": [1]}},
                ],
            )
        )


def test_data_cleaning_service_allows_name_references_after_column_set_boundary(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, cleaning_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "name-after-boundary.csv"
    source.write_text(
        "id,mostly_missing,segment,amount\n"
        "1,,A,10\n"
        "2,,B,20\n"
        "3,,A,30\n",
        encoding="utf-8",
    )

    result = cleaning_service.clean_dataset(
        CleanDatasetInput(
            source_path=str(source.resolve()),
            name="Name references after boundary",
            operations=[
                {
                    "operation": "missing.drop_high_missing_columns",
                    "params": {"threshold": 0.5},
                },
                {"operation": "text.trim", "params": {"columns": ["segment"]}},
            ],
        )
    )

    assert _read_dataset_frame(result.output_path).columns.tolist() == ["id", "segment", "amount"]


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

    frame = _read_dataset_frame(result.output_path)
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

    frame = _read_dataset_frame(result.output_path)
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

    frame = _read_dataset_frame(result.output_path)
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

    frame = _read_dataset_frame(result.output_path)
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
    assert isinstance(result.value, str)
    derived_dataset = dataset_service.get_dataset(_xtt_metadata(result.value, "dataset_id"))

    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert derived_dataset.project_id == source_dataset.project_id
    assert "dataset_uri" not in result.value
    assert "artifact_uri" not in result.value
    artifact = artifact_service.resolve_uri(f"artifact://{_xtt_metadata(result.value, 'artifact_id')}")
    assert artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert artifact.metadata_payload["dataset_export"]["dataset_id"] == derived_dataset.id
    assert pd.read_excel(artifact.absolute_path).fillna("").to_dict(orient="records") == [
        {"customer_id": 1, "amount": 10, "segment": "A"},
        {"customer_id": 2, "amount": "", "segment": "B"},
    ]
    assert "row_count_before: 3" in result.value
    assert "row_count_after: 2" in result.value
    assert "operations: [duplicate.key_columns]" in result.value
    assert artifact.metadata_payload["cleaning_report"]["operations"][0]["columns"] == ["customer_id"]
    assert "artifact_link" not in result.value


def test_data_clean_tool_compacts_report_but_keeps_next_step_facts_and_full_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, dataset_service, _cleaning_service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    long_column = "constant_" + ("x" * 100)
    source = tmp_path / "compact-report.csv"
    source.write_text(
        f"segment,{long_column}\n"
        "A,5\n"
        "B,5\n"
        "A,5\n",
        encoding="utf-8",
    )
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Compact report source",
        )
    )
    arguments = {
        "dataset_id": source_dataset.id,
        "name": "Compact report result",
        "operations": [
            {
                "operation": "encoding.one_hot",
                "params": {"columns": ["segment"]},
            },
            {
                "operation": "scaling.minmax",
                "params": {"columns": [long_column], "feature_range": [2, 4]},
            },
        ],
    }
    context = _tool_context(store, "data.clean", arguments)

    result = registry.execute("data.clean", arguments, context)
    assert isinstance(result.value, str)
    assert "operations: [encoding.one_hot, scaling.minmax]" in result.value
    bounded_warning_report = registry._compact_cleaning_report(
        {"warnings": ["warning-" + ("x" * (MAX_CLEANING_REPORT_WARNING_CHARS + 20))]}
    )
    assert len(bounded_warning_report["warnings"][0]) == MAX_CLEANING_REPORT_WARNING_CHARS
    assert bounded_warning_report["warnings"][0].endswith("…")
    assert len(result.value.encode("utf-8")) < 16_000

    artifact = artifact_service.resolve_uri(f"artifact://{_xtt_metadata(result.value, 'artifact_id')}")
    full_report = artifact.metadata_payload["cleaning_report"]
    assert full_report["operations"][1]["columns"] == [long_column]
    assert full_report["operations"][0]["columns_summary"][0]["generated_columns"] == [
        "segment_a",
        "segment_b",
    ]


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

    assert isinstance(result.value, dict)
    assert result.value["dataset_id"] == source_dataset.id
    assert result.value["cleaning_report"]["no_op"] is True
    assert "artifact_id" not in result.value
    assert "Nothing happened" in result.value["message"]


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


def test_data_clean_metadata_returns_compact_operation_catalog(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _cleaning_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    arguments = {"groups": ["missing", "text"]}
    context = _tool_context(store, "data.clean.metadata", arguments)

    result = registry.execute("data.clean.metadata", arguments, context)

    assert result.value["column_reference"] == {
        "index_base": 0,
        "single": "column_index preferred; column_name fallback; choose one",
        "multiple": "column_indexes preferred; column_names fallback; choose one",
    }
    assert result.value["group_names"] == [
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
    assert [group["group"] for group in result.value["groups"]] == ["missing", "text"]
    operations = [
        operation["operation"]
        for group in result.value["groups"]
        for operation in group["operations"]
    ]
    assert "missing.fill_constant" in operations
    assert "missing.drop_high_missing_columns" in operations
    assert "text.map_values" in operations
    missing_fill_mean = next(
        operation
        for group in result.value["groups"]
        for operation in group["operations"]
        if operation["operation"] == "missing.fill_mean"
    )
    assert missing_fill_mean["params"] == ["multiple_columns"]
    assert all(
        set(operation) == {"operation", "summary", "params"}
        for group in result.value["groups"]
        for operation in group["operations"]
    )
    assert all(group["summary"] for group in result.value["groups"])
    assert result.value["groups"][0]["summary"] == "Fill/drop missing"
    assert result.value["groups"][1]["summary"] == "Clean text"

    partial_result = registry.execute(
        "data.clean.metadata",
        {"groups": ["schema", "duplicate", "missing"]},
        context,
    )
    assert [group["group"] for group in partial_result.value["groups"]] == ["schema", "missing"]
    assert partial_result.value["invalid_groups"] == [
        {"group": "duplicate", "error_code": "unknown_group"}
    ]
    assert partial_result.value["operation_count"] == (
        len(partial_result.value["groups"][0]["operations"])
        + len(partial_result.value["groups"][1]["operations"])
    )

    all_invalid_result = registry.execute(
        "data.clean.metadata",
        {"groups": ["duplicate"]},
        context,
    )
    assert all_invalid_result.value["groups"] == []
    assert all_invalid_result.value["invalid_groups"] == [
        {"group": "duplicate", "error_code": "unknown_group"}
    ]
    assert all_invalid_result.value["operation_count"] == 0

    all_result = registry.execute("data.clean.metadata", {}, context)
    all_operations = [
        operation["operation"]
        for group in all_result.value["groups"]
        for operation in group["operations"]
    ]
    assert "schema.normalize_column_names" in all_operations
    assert "outlier.clip_iqr" in all_operations
    assert "encoding.one_hot" in all_operations
    assert "scaling.minmax" in all_operations
    assert "scaling.standard" in all_operations
    all_iqr_operation = next(
        operation
        for group in all_result.value["groups"]
        for operation in group["operations"]
        if operation["operation"] == "outlier.clip_iqr"
    )
    assert all_iqr_operation["summary"] == "Clip outliers by IQR"
    metadata_size = len(json.dumps(all_result.value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert metadata_size < 4_096
    assert metadata_size < 11_200


def test_data_tools_resolve_indexes_for_unicode_query_and_role_binding(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _cleaning_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "unicode-churn.csv"
    source.write_text(
        '"Account Balance (Yuan)","Days Since Last Transaction",'
        '"Last Month’s Trading Commission (Yuan)","Total Trading Commission (Yuan)",'
        '"Years with This Brokerage","Customer Churn (Yes/No)"\n'
        "22686.5,297,149.25,2029.85,0,0\n",
        encoding="utf-8",
    )
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Unicode churn")
    )

    query_arguments = {
        "dataset_id": dataset.id,
        "column_reference": "indexes",
        "sql": "SELECT c2 AS last_month_commission, c5 AS churn FROM input",
    }
    query_result = registry.execute(
        "data.query",
        query_arguments,
        _tool_context(store, "data.query", query_arguments),
    )
    assert isinstance(query_result.value, str)
    assert "| 1 | 149.25 | 0 |" in query_result.value

    binding_arguments = {
        "dataset_id": dataset.id,
        "role_bindings": [
            {"role": "feature", "column_indexes": [0, 1, 2, 3, 4]},
            {"role": "target", "column_indexes": [5]},
        ],
    }
    binding_result = registry.execute(
        "data.feature.select",
        binding_arguments,
        _tool_context(store, "data.feature.select", binding_arguments),
    )
    bindings_by_role = {
        item["role"]: item["columns"] for item in binding_result.value["role_bindings"]
    }
    assert bindings_by_role == {
        "feature": [
            "Account Balance (Yuan)",
            "Days Since Last Transaction",
            "Last Month’s Trading Commission (Yuan)",
            "Total Trading Commission (Yuan)",
            "Years with This Brokerage",
        ],
        "target": ["Customer Churn (Yes/No)"],
    }


def test_data_clean_tool_schema_stays_compact(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _cleaning_service, _artifact_service, registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "data.peek" not in specs
    assert "project_id" not in specs["data.query"].parameters_schema["properties"]
    assert "project_id" not in specs["data.integrate"].parameters_schema["properties"]
    assert "source_path" not in specs["data.query"].parameters_schema["properties"]
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
    assert specs["data.clean.metadata"].parameters_schema["properties"]["groups"]["items"] == {
        "type": "string",
        "enum": [
            "schema",
            "duplicates",
            "missing",
            "types",
            "text",
            "validation",
            "outliers",
            "encoding",
            "scaling",
        ],
    }
    assert specs["data.query"].parameters_schema["properties"]["column_reference"]["enum"] == [
        "names",
        "indexes",
    ]
    assert specs["data.transform"].parameters_schema["properties"]["column_reference"]["enum"] == [
        "names",
        "indexes",
    ]
    role_binding_schema = specs["data.feature.select"].parameters_schema["properties"]["role_bindings"]["items"]
    assert role_binding_schema["required"] == ["role"]
    assert role_binding_schema["properties"]["column_indexes"] == {
        "type": "array",
        "items": {"type": "integer", "minimum": 0},
        "description": (
            "Preferred zero-based dataset column indexes returned by data.query. "
            "Use either column_indexes or columns, never both."
        ),
    }
