# Verification Ledger

## Latest Authoritative Verification

2026-07-08, after commit `542561f Refine dataset tools and lazy exports`:

- `pdm run python -m pytest -q`
- Result: 304 passed, 3 warnings in 271.21s.
- Warnings:
  - sklearn `SVC(probability=True)` deprecation warning.
  - sklearn `MLPClassifier` convergence warnings.

Note: `pdm run pytest` timed out once in this session after 244 seconds and left pytest wrapper child processes. Direct `pdm run python -m pytest -q` completed successfully. Treat the direct pytest result as the verification authority for the commit.

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
- `dataset://` activation lazily exports/reuses workbook artifacts.
- Service-owned link activation returns promptly from the UI thread and closes progress on success/failure.
- Service-link progress is non-modal and retranslated on language switch.
- Dataset export tests fail if export regresses to Pandas `DataFrame.to_csv()` or `to_excel()`.

## Historical Verification

Detailed older command logs are preserved in `archive/2026-07-implementation-history/execution.md`.
