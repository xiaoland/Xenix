# Structure DSL Draft

## Purpose

`data.peek` should establish a provider-facing, executable structure boundary for real-world tabular files.

The tool should not own semantic parsing such as deciding that a row is "the real header". It should present macroscopic dataset structure as mechanical evidence. The model/user owns interpretation.

Provider-facing spreadsheet structure has one authoritative representation: JSON DSL. No provider-facing Markdown table should be emitted by the tool.

## Candidate Shape

```json
{
  "structure": {
    "format": "xlsx",
    "sheet": {"index": 0, "name": "品项销售明细"},
    "coordinate_system": {
      "rows": "spreadsheet_1_based",
      "columns": "position_0_based"
    },
    "declared_dimensions": {"rows": 1, "columns": 1},
    "observed_dimensions": {"rows": 486123, "columns": 50},
    "layout_evidence": [
      "declared_dimension_mismatch",
      "leading_sparse_rows",
      "dense_rows_after_sparse_rows"
    ],
    "row_windows": [
      {
        "row": 1,
        "non_empty_count": 1,
        "observed_width": 1,
        "cells": ["品项销售明细"]
      },
      {
        "row": 2,
        "non_empty_count": 1,
        "observed_width": 1,
        "cells": ["营业日期【2026/04/01-2026/04/30】；门店【已选109个】；..."]
      },
      {
        "row": 3,
        "non_empty_count": 50,
        "observed_width": 50,
        "cells": ["城市", "机构编码", "门店名称", "营业日期"]
      }
    ],
    "columns": [
      {
        "index": 0,
        "tool_name": "品项销售明细",
        "source_name": "品项销售明细",
        "name_source": "preserved_source_name",
        "sample_values": ["营业日期【2026/04/01-...】", "城市", "佛山市"]
      },
      {
        "index": 1,
        "tool_name": "column_2",
        "source_name": "Unnamed: 1",
        "loader_name": "__UNNAMED__1",
        "name_source": "generated_loader_placeholder",
        "sample_values": ["", "机构编码", "C7"]
      }
    ],
    "type_evidence": [
      {
        "column_index": 22,
        "tool_name": "column_23",
        "numeric_like_ratio": 0.99,
        "text_samples": ["销售数量"],
        "placeholder_samples": []
      }
    ]
  }
}
```

## Field Notes

- `layout_evidence` contains mechanical labels only.
- `row_windows` preserves coordinates and compact cell samples. For XLSX files with suspicious declared dimensions, collect this through a bounded reader. Options include openpyxl after `reset_dimensions()` for cheap physical row evidence, or Polars/calamine with `read_options={"n_rows": N}` when row samples should align with loader column names. Do not require full-table profiling just to build row windows.
- `columns[*].tool_name` is the downstream executable authority.
- `source_name` and `loader_name` are evidence only.
- `type_evidence` reports parse-like facts without choosing a cleaning operation.
- The DSL should be bounded for token safety.

## Pre-Execution Decisions

1. `structure` should be present for `data.peek` whenever a compact structure reader can build it. For CSV/XLSX this should be part of the normal provider-facing contract, with empty or partial fields only when inspection fails gracefully.
2. Row windows should include leading rows plus the first dense row window when that differs from the leading rows. Trailing rows are not Phase 1 unless needed for a repairable failure.
3. `observed_dimensions.rows` means physical spreadsheet/source rows when available, including title/filter/header-like rows. Existing `inspection.row_count` may remain the loaded dataframe/data-row count; do not silently equate the two.
