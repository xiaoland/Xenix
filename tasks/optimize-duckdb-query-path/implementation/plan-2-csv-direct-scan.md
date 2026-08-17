# Plan-2 — CSV bindings scan through DuckDB (IH-2)

## Working set

- `src/xenix/services/data_transform.py` (`DataQueryTransformService`)
- `tests/test_data_transform_service.py`

## Pass 0 — type-inference alignment check (decision input)

Before mutating `_register_binding()`, run a throwaway comparison over a representative CSV corpus (numeric-only, leading-zero identifiers, mixed numeric/text, date-as-string, empty-cell numeric) printing `pd.read_csv(...).dtypes` versus `read_csv_auto(...)` `DESCRIBE`. Record the delta in the execution log.

Decision rule: if the delta is benign (numeric↔BIGINT/DOUBLE, string↔VARCHAR) proceed; if it is material (a date-looking string becomes `DATE`, or leading-zero identifiers become integers), stop and return to discussion per IH-2.

## Pass 1 — CSV binding view

1. Add `_register_csv_binding(connection, relation_name, path)` mirroring `_register_parquet_binding()`: resolve schema via `load_tabular_schema(path, DatasetSourceFormat.CSV)`, then `CREATE TEMP VIEW {relation_name} AS SELECT {loader_name AS tool_name, ...} FROM read_csv_auto('path') AS source`.
2. Route CSV in `_register_binding()` to `_register_csv_binding()`. Keep the `load_pandas_frame_with_schema` fallback for any non-CSV/non-parquet/non-xlsx format (unchanged).

Stop condition: CSV bindings produce the same column names and row counts as before, with DuckDB-inferred types.

## Pass 2 — focused tests

Extend `tests/test_data_transform_service.py`:

- CSV binding over numeric / null / string / date columns asserts inferred `type` and query result values;
- `column_reference: "indexes"` projects `c0, c1, ...` for a CSV binding;
- the `app.py` smoke shape (`SELECT SUM(value)`) returns 3.

## Pass 3 — verification

- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`
- `pdm run check`
- `pdm run smoke`
