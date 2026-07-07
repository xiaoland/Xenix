# Execution Notes

## Implemented Slice

- Added a thin tabular schema resolver in `src/xenix/services/tabular.py`.
- `tool_name` is now the executable column authority for placeholder, duplicate, empty, and unstable names.
- `data.peek` includes a JSON structure DSL with row windows, layout evidence, canonical columns, and compact provider projection.
- `data.query` and `data.transform` use the same canonical schema projection.
- CSV query/transform keeps pandas type inference for existing numeric SQL behavior.
- XLS/XLSX query/transform uses Polars/calamine plus a temporary CSV table registered with DuckDB as `all_varchar=true`, avoiding pandas full-read slowness and mixed-type cast failures.
- Harness can replay a compact tool-owned provider projection instead of serializing the full persisted tool `result_payload`.
- Agent Harness Unit TDD now records that provider-facing tool results are LLM lookup/planning surfaces, not human-facing presentation.

## Verification

- `pdm run pytest tests/test_tabular_schema.py tests/test_analysis_profile.py tests/test_data_transform.py tests/test_agent_harness_foundation.py`
  - Result: 31 passed.
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
