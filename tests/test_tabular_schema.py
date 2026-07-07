from xenix.services.tabular import resolve_tabular_schema


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
