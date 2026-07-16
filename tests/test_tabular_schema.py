from pathlib import Path

import pandas as pd
import pytest

from xenix.exceptions import ValidationError
from xenix.services.storage.models import DatasetSourceFormat
from xenix.services.tabular import (
    apply_tabular_schema,
    load_tabular_frame,
    load_tabular_schema,
    resolve_tabular_column_index,
    resolve_tabular_schema,
    resolve_tabular_schema_for_loaded_frame,
    tabular_schema_tool_names,
)


def test_resolve_tabular_schema_generates_tool_names_for_loader_placeholders() -> None:
    schema = resolve_tabular_schema(["品项销售明细", "__UNNAMED__1", "Unnamed: 2"])

    assert [column.tool_name for column in schema.columns] == [
        "品项销售明细",
        "column_2",
        "column_3",
    ]
    assert schema.columns[1].name_source == "generated_loader_placeholder"
    assert schema.columns[2].name_source == "generated_loader_placeholder"


def test_resolve_tabular_schema_generates_tool_names_for_duplicates_and_unstable_names() -> None:
    schema = resolve_tabular_schema(["city", "city", "amount\nraw", ""])

    assert [column.tool_name for column in schema.columns] == [
        "column_1",
        "column_2",
        "column_3",
        "column_4",
    ]
    assert [column.name_source for column in schema.columns] == [
        "generated_duplicate_name",
        "generated_duplicate_name",
        "generated_unstable_name",
        "generated_empty_name",
    ]


@pytest.mark.parametrize(
    "loader_names",
    [
        ["city", "city.1"],
        ["city", "city_duplicated_0"],
    ],
)
def test_resolve_tabular_schema_normalizes_duplicate_loader_suffixes(loader_names: list[str]) -> None:
    schema = resolve_tabular_schema(loader_names)

    assert tabular_schema_tool_names(schema) == ["city", "column_2"]
    assert schema.columns[1].name_source == "generated_loader_duplicate"


def test_load_tabular_schema_keeps_csv_numeric_text_names_but_normalizes_xlsx_numeric_headers(
    tmp_path: Path,
) -> None:
    csv_source = tmp_path / "numeric-header.csv"
    csv_source.write_text("1,amount\nx,1\n", encoding="utf-8")
    xlsx_source = tmp_path / "numeric-header.xlsx"
    pd.DataFrame({1: ["x"], "amount": [1]}).to_excel(xlsx_source, index=False)

    csv_schema = load_tabular_schema(csv_source, source_format=DatasetSourceFormat.CSV)
    xlsx_schema = load_tabular_schema(xlsx_source, source_format=DatasetSourceFormat.XLSX)

    # CSV's text header is a valid source name; the pandas/XLSX numeric header
    # is loader-unstable and is projected to the canonical generated name.
    assert tabular_schema_tool_names(csv_schema) == ["1", "amount"]
    assert tabular_schema_tool_names(xlsx_schema) == ["column_1", "amount"]


def test_load_tabular_schema_selects_xlsx_sheet_by_name(tmp_path: Path) -> None:
    source = tmp_path / "multi-sheet.xlsx"
    with pd.ExcelWriter(source) as writer:
        pd.DataFrame({"first": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({2: ["x"], "amount": [3]}).to_excel(writer, sheet_name="Second", index=False)

    schema = load_tabular_schema(
        source,
        source_format=DatasetSourceFormat.XLSX,
        sheet_name="Second",
    )

    assert tabular_schema_tool_names(schema) == ["column_1", "amount"]


def test_loaded_xlsx_schema_reconciles_trailing_blank_header_columns(tmp_path: Path) -> None:
    source = tmp_path / "report.xlsx"
    pd.DataFrame(
        [
            ["品项销售明细", None, None],
            ["营业日期【2026/04/01-2026/04/30】", None, None],
            ["城市", "销售数量", "销售金额(元)"],
            ["佛山市", 1, 118],
        ]
    ).to_excel(source, header=False, index=False)

    frame = load_tabular_frame(source, DatasetSourceFormat.XLSX)
    schema = resolve_tabular_schema_for_loaded_frame(source, DatasetSourceFormat.XLSX, frame)

    assert tabular_schema_tool_names(schema) == ["品项销售明细", "column_2", "column_3"]
    assert apply_tabular_schema(frame, schema).columns == ["品项销售明细", "column_2", "column_3"]


def test_load_tabular_schema_uses_header_only_authority_for_malformed_csv(tmp_path: Path) -> None:
    source = tmp_path / "duplicate-headers.csv"
    source.write_text(
        "city,city,,amount\n"
        "north,south,west,1\n",
        encoding="utf-8",
    )

    schema = load_tabular_schema(source, source_format=DatasetSourceFormat.CSV)
    polars_derived = resolve_tabular_schema(["city", "city_duplicated_0", "__UNNAMED__2", "amount"])

    assert tabular_schema_tool_names(schema) == ["city", "column_2", "column_3", "amount"]
    assert tabular_schema_tool_names(schema) == tabular_schema_tool_names(polars_derived)


def test_apply_tabular_schema_renames_duplicate_labels_by_position() -> None:
    frame = pd.DataFrame([["a", "b"]], columns=["city", "city"])
    schema = resolve_tabular_schema(frame.columns)

    applied = apply_tabular_schema(frame, schema)

    assert applied.columns.tolist() == ["column_1", "column_2"]
    assert applied.iloc[0].tolist() == ["a", "b"]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (True, "data.clean.params.column_index must be a zero-based integer column index"),
        ("0", "data.clean.params.column_index must be a zero-based integer column index"),
        (-1, "data.clean.params.column_index index -1 is outside the available zero-based column range"),
        (2, "data.clean.params.column_index index 2 is outside the available zero-based column range"),
    ],
)
def test_resolve_tabular_column_index_is_strict_and_field_contextual(
    value: object,
    message: str,
) -> None:
    schema = resolve_tabular_schema(["city", "amount"])

    with pytest.raises(ValidationError, match=message):
        resolve_tabular_column_index(schema, value, "data.clean.params.column_index")


def test_resolve_tabular_column_index_returns_tool_name_without_selection_policy() -> None:
    schema = resolve_tabular_schema(["city", "amount"])

    assert resolve_tabular_column_index(schema, 1, "data.clean.params.column_index") == "amount"
