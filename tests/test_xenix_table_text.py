from xenix.services.agent.xenix_table_text import render_xenix_table_tool_result


def test_xenix_table_text_renders_data_query_compact_table_payload() -> None:
    text = render_xenix_table_tool_result(
        tool_name="data.query",
        status="succeeded",
        payload={
            "columns": {
                "_schema": {"name": 0, "type": 1, "index": 2},
                "data": [["order_id", "int64", 0], ["customer", "string", 1], ["amount", "float64", 2]],
            },
            "rows": {
                "_schema": {"order_id": 0, "customer": 1, "amount": 2},
                "data": [[1001, "Alice", 128.5], [1002, "Bob|B", None]],
            },
            "returned_row_count": 2,
            "total_row_count": 1280,
            "truncated": True,
        },
    )

    assert text is not None
    assert "shape: 2 rows × 3 columns" in text
    assert "returned_rows: 2" in text
    assert "total_rows: 1280" in text
    assert "truncated: true" in text
    assert "null: ∅" in text
    assert "schema:\n  order_id: int64\n  customer: string\n  amount: float64" in text
    assert "| # | order_id | customer | amount |" in text
    assert "| 2 | 1002 | Bob\\|B | ∅ |" in text


def test_xenix_table_text_uses_records_block_for_wide_rows() -> None:
    text = render_xenix_table_tool_result(
        tool_name="data.query",
        status="succeeded",
        payload={
            "columns": {
                "_schema": {"name": 0, "type": 1, "index": 2},
                "data": [[f"field_{index}", "string", index] for index in range(9)],
            },
            "rows": {
                "_schema": {f"field_{index}": index for index in range(9)},
                "data": [[f"value {index}" for index in range(9)]],
            },
            "returned_row_count": 1,
            "total_row_count": 1,
            "truncated": False,
        },
    )

    assert text is not None
    assert "records:\n\n[1]\nfield_0 = \"value 0\"" in text
    assert "| # |" not in text


def test_xenix_table_text_renders_generated_dataset_preview() -> None:
    text = render_xenix_table_tool_result(
        tool_name="data.transform",
        status="succeeded",
        payload={
            "dataset_id": "dataset-1",
            "artifact_id": "artifact-1",
            "summary": "Transformed dataset created. Rows: 3.",
            "input_dataset_ids": ["source-1"],
            "row_count": 3,
            "inspection": {
                "row_count": 3,
                "column_count": 2,
                "columns": [
                    {"name": "region", "kind": "text", "nullable": False},
                    {"name": "amount", "kind": "numeric", "nullable": True},
                ],
                "preview_columns": ["region", "amount"],
                "preview_rows": [["north", "30"], ["south", ""]],
            },
        },
    )

    assert text is not None
    assert text.startswith("tool: data.transform\ndataset_id: dataset-1\nartifact_id: artifact-1\n")
    assert "input_dataset_ids: [source-1]" in text
    assert "row_count: 3" in text
    assert "shape: 2 rows × 2 columns" in text
    assert "total_rows: 3" in text
    assert "truncated: true" in text
    assert "schema:\n  region: text\n  amount: numeric" in text
    assert "| 2 | south | ∅ |" in text
    assert "use dataset_id for follow-up tools and artifact_id for the user-openable workbook" in text


def test_xenix_table_text_does_not_render_non_tabular_or_failed_results() -> None:
    assert (
        render_xenix_table_tool_result(
            tool_name="data.clean.metadata",
            status="succeeded",
            payload={"groups": []},
        )
        is None
    )
    assert (
        render_xenix_table_tool_result(
            tool_name="data.query",
            status="failed",
            payload={"error": "bad sql"},
            error_summary="bad sql",
        )
        is None
    )
