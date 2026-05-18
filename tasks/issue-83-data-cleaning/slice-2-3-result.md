# Issue 83 Slice 2-3 Result

## Objective & Hypothesis

- Objective: Implement read-only dataset querying and derived-dataset transformation through LLM-facing tools.
- Hypothesis: A shared DuckDB-backed service can safely power `data.query` and `data.transform` when SQL is limited to single SELECT/CTE statements over registered dataset bindings.

## Guardrails Touched

- `data.duckdb` is not exposed as an LLM tool.
- `data.query` is read-only and returns bounded rows plus summary metadata.
- `data.transform` creates a new derived dataset artifact and leaves source datasets intact.
- DuckDB runs as an internal in-memory execution engine.
- Runtime extension downloads are outside the default execution path.

## Implementation Notes

- Added `duckdb>=1.5.2` as a runtime dependency.
- Added `DataQueryTransformService` as the DuckDB-backed service boundary.
- Added `DuckDbSqlValidator` for single SELECT/CTE validation, mutation keyword rejection, file scan function rejection, direct file path rejection, and binding alias validation.
- Added LLM-facing `data.query`:
  - accepts `dataset_id` for a single `input` binding or `bindings` for multi-input queries
  - returns bounded rows, columns, truncation state, input bindings, and validation summary
  - creates no dataset artifact by default
- Added LLM-facing `data.transform`:
  - accepts `dataset_id` for a single `input` binding or `bindings` for multi-input transforms
  - materializes output CSV files under `artifacts/datasets/transformed/`
  - registers generated dataset artifacts
  - sets `derived_from_dataset_id` for single-input transforms
  - records multi-input dataset ids in artifact metadata
- Added a smoke-test DuckDB in-memory query so packaged smoke covers DuckDB import and execution.

## Verification

- Command: `pdm run pytest tests/test_data_transform.py tests/test_data_cleaning.py tests/test_agent_harness_first_slice.py tests/test_main.py::test_smoke_test_bootstraps_runtime_in_fresh_app_home -q`
- Result: `15 passed`.
- Command: `pdm run check`
- Result: passed.
- Command: `pdm run pytest tests/test_data_transform.py -q`
- Result: `7 passed`.
- Command: `pdm run pytest -q`
- Result: `83 passed`.
- Command: `pdm run smoke`
- Result: passed.
- Command: `pdm run package`
- Result: passed; PyInstaller loaded `_pyinstaller_hooks_contrib` `hook-duckdb.py`.
- Command: `pdm run smoke-package`
- Result: passed.

## Files Changed

- `pyproject.toml`
- `pdm.lock`
- `src/xenix/services/data_transform.py`
- `src/xenix/services/agent/tools.py`
- `src/xenix/app.py`
- `tests/test_data_transform.py`
- `tests/test_data_cleaning.py`
- `tests/test_agent_harness_first_slice.py`
- `docs/10-prd/product-scope.md`
- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/20-product-tdd/storage-ownership.md`
- `docs/40-deployment/development.md`
- `docs/40-deployment/runtime-state.md`
- `tasks/issue-83-data-cleaning/implementation-plan.md`

## Deferred Items

- First-class multi-parent dataset lineage remains deferred. Multi-input transform lineage is recorded in artifact metadata for now.
- Dynamic cleaning tool family loading remains Slice 4.
