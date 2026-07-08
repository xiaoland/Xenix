# Verification Ledger

## Latest Authoritative Verification

2026-07-08, after commit `542561f Refine dataset tools and lazy exports`:

- `pdm run python -m pytest -q`
- Result: 304 passed, 3 warnings in 271.21s.
- Warnings:
  - sklearn `SVC(probability=True)` deprecation warning.
  - sklearn `MLPClassifier` convergence warnings.

Note: `pdm run pytest` timed out once in this session after 244 seconds and left pytest wrapper child processes. Direct `pdm run python -m pytest -q` completed successfully. Treat the direct pytest result as the verification authority for the commit.

## Current Uncommitted Slice Verification

2026-07-08, `08-eager-derived-export-artifacts`:

- `git diff --check`
- Result: passed.
- `pdm run pytest tests/test_services.py::test_dataset_export_service_materializes_workbook_artifact tests/test_services.py::test_link_router_rejects_dataset_scheme tests/test_services.py::test_dataset_service_discards_unreferenced_dataset tests/test_data_transform.py::test_data_integrate_tool_uses_dataset_ids_and_returns_artifact_id tests/test_data_transform.py::test_data_transform_tool_discards_dataset_when_export_artifact_fails tests/test_data_transform.py::test_data_transform_tool_registers_derived_dataset_and_returns_artifact_id tests/test_data_transform.py::test_data_transform_tool_records_multi_input_lineage_in_result tests/test_data_cleaning.py::test_data_clean_tool_registers_derived_dataset_and_artifact tests/test_data_tokenization.py::test_data_tokenize_tool_registers_derived_dataset_and_artifact tests/test_main.py::test_main_window_opens_service_link_off_ui_thread tests/test_main.py::test_main_window_service_link_activation_failure_closes_progress`
- Result: 11 passed in 10.23s.
- `pdm run python -m compileall -q src/xenix`
- Result: passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_main.py -q`
- Result: 100 passed in 39.98s.

## Focused Verification From The Main Slice

- `pdm run pytest tests/test_services.py -q`: 15 passed after Polars dataset export and lazy dataset export coverage.
- `pdm run pytest tests/test_data_transform.py -q`: transform/query contract coverage passed in the full suite.
- `pdm run pytest tests/test_main.py -q`: 53 passed after async service-link activation and non-modal progress.
- `pdm run pytest tests/test_i18n.py -q`: 5 passed after service-link progress i18n.
- `pdm run python -m compileall -q src/xenix`: passed after relevant implementation slices.

## Coverage Claims

- Provider tool specs no longer expose `data.peek`.
- `data.query` returns compact `columns`, `rows`, `returned_row_count`, and `truncated`.
- `data.query` accepts both `bindings` and `dataset_id`; `bindings` wins.
- Workbook import can register multiple app-owned Parquet datasets.
- `data.transform` can materialize Parquet derived datasets from explicit `output`.
- Failed transform validation does not leave a durable derived dataset row or final output file.
- ML dataset loading supports Parquet-backed registered datasets.
- Current local code removes lazy dataset activation and replaces generated dataset completion with eager workbook export artifact creation.
- Service-owned link activation returns promptly from the UI thread and closes progress on success/failure.
- Service-link progress is non-modal and retranslated on language switch.
- Dataset export tests fail if export regresses to Pandas `DataFrame.to_csv()` or `to_excel()`.

## Historical Verification

Detailed older command logs are preserved in `archive/2026-07-implementation-history/execution.md`.
