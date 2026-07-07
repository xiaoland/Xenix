# Execution Notes

## Implemented Slice

### Phase 1 Follow-Up

- Converged ordinary tool results around canonical `result_payload`.
- Removed ordinary `ToolExecutionResult.content_blocks` and `ToolExecutionResult.provider_payload` from the production result contract.
- Harness no longer writes `provider_payload.tool_result` for completed tool calls.
- `ConversationStore` replays completed tool calls from `AgentToolCallRow.result_payload` directly.
- `data.peek` now returns compact `inspection` with `row_count`, `column_count`, coordinate-system text, compact `columns`, and compact `row_windows`.
- `data.peek` no longer returns `structure`, `format`, `sheet`, `layout_evidence`, loader/source/name-source fields, profile markdown, or a separate provider projection.
- Repeated LLM-facing rows now use `_schema` plus `data` arrays for `data.peek` columns and row windows.
- `data.transform` writes transform output to a temp file, validates that output, then moves it to the final transformed dataset path. Failed output validation no longer leaves a final transformed CSV or derived dataset row.
- Agent Harness Unit TDD now records canonical result replay and the compact table pattern.
- Product TDD now records observability/debug/audit material in tool output as an anti-pattern.

### Earlier Phase 1

- Added a thin tabular schema resolver in `src/xenix/services/tabular.py`.
- `tool_name` is now the executable column authority for placeholder, duplicate, empty, and unstable names.
- `data.query` and `data.transform` use the same canonical schema projection.
- CSV query/transform keeps pandas type inference for existing numeric SQL behavior.
- XLS/XLSX query/transform uses Polars/calamine plus a temporary CSV table registered with DuckDB as `all_varchar=true`, avoiding pandas full-read slowness and mixed-type cast failures.

## Verification

- `pdm run pytest`
  - Result: 299 passed, 3 warnings.
- Real XLSX `data.peek` / query smoke after follow-up:
  - Source: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`
  - `data.peek` with `analysis=false` returned payload keys `analysis`, `dataset_id`, and `inspection`.
  - `inspection` keys were `column_count`, `columns`, `coordinate_system`, `row_count`, and `row_windows`.
  - Payload was about 4,517 JSON characters.
  - `columns` used `_schema: {"tool_name": 0, "position": 1, "samples": 2}`.
  - First two executable column rows were `品项销售明细` at position 0 and `column_2` at position 1.
  - `row_windows` used `_schema: {"row": 0, "non_empty": 1, "width": 2, "cells": 3}`.
  - `SELECT "column_2" FROM input LIMIT 3` returned `NULL`, `机构编码`, and `C7`.
- `pdm run pytest tests/test_tabular_schema.py tests/test_analysis_profile.py tests/test_data_transform.py tests/test_agent_harness_foundation.py`
  - Result: 32 passed after adding transform atomicity coverage.
- Real XLSX query smoke:
  - Source: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`
  - SQL: `SELECT "column_23" FROM input LIMIT 5`
  - Result: succeeded in about 25.84s.
  - Rows included `NULL`, `销售数量`, `1`, `2`, `1`.
- Real XLSX `data.peek` smoke:
  - `analysis=false`
  - Result: succeeded in about 24.37s.
  - Structure DSL exposed row 3 as a 50-column dense row and `column_2` / `column_3` canonical names for Polars placeholders.
  - Provider compact payload did not include markdown.
