# IH-4 — Remove the dead CSV binding path

- status: `consumed` (implemented 2026-08-16; `pdm run check` passed, direct behavioral verification passed, 149 tests collect)

## Address and Object

- `src/xenix/services/data_transform.py`, class `DataQueryTransformService`:
  - `_register_binding()` — replace the pandas CSV `else` fallback with an explicit rejection of non-parquet/non-xlsx sources.
  - remove `_load_frame()` and `_load_frame_with_schema()` (no remaining callers).
  - remove the now-unused `load_pandas_frame_with_schema` (and `LoadedPandasFrame`) imports.
- `src/xenix/app.py` `_run_smoke_checks()` — bind a parquet instead of a raw CSV for the DuckDB smoke query.

## State Diff

`From -> To`:

- From: `_register_binding()` loads any non-parquet/non-xlsx source (CSV/unknown) via `pd.read_csv` + `register()`; `_load_frame()` / `_load_frame_with_schema()` are unreachable in production.
- To: `_register_binding()` handles parquet and xlsx/xls explicitly and raises `ValidationError` for anything else; the dead helpers and import are removed; the smoke query binds a parquet.

## Blast Radius

- CSV-bound `data.query` / `data.transform` (today only the `app.py` smoke) now raises instead of loading via pandas. No registered Dataset is CSV (imports are always parquet), so production is unaffected.
- `app.py` smoke moves from a CSV binding to a parquet binding; it still exercises DuckDB query over a binding.

## Invariants

- Parquet and xlsx/xls bindings are unchanged (names, types, values, `column_reference` indexes mode).
- `data.clean`, tokenization, and ML — which call `load_pandas_frame_with_schema` directly — are untouched; that helper remains in `tabular.py`.
- `data.query` / `data.transform` validation and result contract are unchanged.

## Verification

- New tests: parquet and xlsx bindings still query correctly; a CSV binding raises `ValidationError`; the removed helpers/imports leave the module importable and lint-clean.
- `pdm run pytest --direct tests/test_data_transform_service.py`, `pdm run test`, `pdm run check`, `pdm run smoke`.

## prerequisite Evidence IDs

- Source grep: `DatasetRow.source_format` is `PARQUET` at all 3 sites; `register_dataset` always writes parquet; `_load_frame` has no callers and `_load_frame_with_schema` is reachable only from it and the CSV fallback.

## return-to-discussion triggers

- If a future feature re-adds raw-CSV bindings, revisit this rejection with a deliberate, type-safe CSV path instead of restoring the old pandas fallback.
