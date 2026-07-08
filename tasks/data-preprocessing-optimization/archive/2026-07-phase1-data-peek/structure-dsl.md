# Structure DSL Draft

## Purpose

`data.peek` should establish a compact executable inspection/schema boundary for real-world tabular files.

The tool should not own semantic parsing such as deciding that a row is "the real header". It should present macroscopic dataset structure as mechanical evidence. The model/user owns interpretation.

Spreadsheet inspection and structure should have one authoritative tool-result representation. No Markdown table should be emitted by the tool unless Markdown is deliberately the best machine-readable result shape for that specific tool.

Longer-term dataset direction: raw `.xlsx` / `.xls` / `.csv` imports should be separated from app-owned `dataset` records. A dataset should represent one tabular imported result, such as one sheet, with its actual table content stored under AppData in an app-owned format such as CSV or a better future format. `data.peek` should inspect that dataset-shaped table, not leak workbook/file adapter details into the normal contract.

## Candidate Shape

```json
{
  "inspection": {
    "row_count": 486122,
    "column_count": 50,
    "coordinate_system": "rows are spreadsheet_1_based; columns are position_0_based",
    "columns": {
      "_schema": {"tool_name": 0, "position": 1, "samples": 2},
      "data": [
        ["品项销售明细", 0, ["品项销售明细", "营业日期【2026/04/01-...】", "城市", "佛山市"]],
        ["column_2", 1, ["", "机构编码", "C7"]]
      ]
    },
    "row_windows": {
      "_schema": {"row": 0, "non_empty": 1, "width": 2, "cells": 3},
      "data": [
        [1, 1, 1, ["品项销售明细"]],
        [2, 1, 1, ["营业日期【2026/04/01-2026/04/30】；门店【已选109个】；..."]],
        [3, 50, 50, ["城市", "机构编码", "门店名称", "营业日期"]]
      ]
    }
  }
}
```

## Field Notes

- Do not include `format` or `sheet` in the normal `dataset` inspection contract once dataset import separates raw workbook/files from app-owned tabular datasets.
- Do not include `layout_evidence`; labels such as sparse/dense mix semantic interpretation into the tool result.
- `row_windows` preserves coordinates and compact cell samples without interpreting which row is the true header.
- `columns.data[*][tool_name]` is the downstream executable authority.
- Do not expose `source_name`, `loader_name`, or `name_source` to the LLM-facing result unless a specific repair flow proves it needs them. Loader facts belong inside the loader boundary.
- The DSL should be bounded for token safety.
- The DSL must not publish `candidate_header_row` or equivalent semantic header claims. Dense-row evidence is allowed; the interpretation remains with the model/user.

## Pre-Execution Decisions

1. `inspection` should be present for `data.peek` whenever a compact structure reader can build it. For imported datasets this should be part of the normal tool-result contract, with empty or partial fields only when inspection fails gracefully.
2. Row windows should include leading rows plus the first dense row window when that differs from the leading rows. Trailing rows are not Phase 1 unless needed for a repairable failure.
3. `observed_dimensions.rows` means physical spreadsheet/source rows when available, including title/filter/header-like rows. Existing `inspection.row_count` may remain the loaded dataframe/data-row count; do not silently equate the two.
