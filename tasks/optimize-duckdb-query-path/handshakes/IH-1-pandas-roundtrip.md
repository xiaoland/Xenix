# IH-1 — Remove the pandas round-trip from query/transform result materialization

- status: `superseded` (see [findings](../evidence/findings.md))

## Address and Object

`src/xenix/services/data_transform.py`, class `DataQueryTransformService`:

- `query()` (result `SELECT` at the `LIMIT {limit}` execution) — drop `.fetchdf()`.
- `_records()` — replace the pandas `astype(object).where(pd.notna, None).to_json(orient="records", date_format="iso")` path.
- `_columns()` — replace `frame.dtypes` iteration with DuckDB cursor-description mapping.
- `_output_columns()` — replace the one-row `.fetchdf()` with cursor-description mapping.

## State Diff

`From -> To`:

- Result materialization: `execute(sql).fetchdf()` → `cursor = execute(sql)`, then derive columns from `cursor.description` and rows from `cursor.fetchall()`.
- `_records`: pandas `astype(object) + where + to_json + json.loads` → a `_records_from_cursor(rows, columns)` normalization producing JSON-safe Python values directly (no pandas, no Arrow→pandas copy).
- `_columns` / `_output_columns`: `str(pandas_dtype)` (e.g. `int64`, `object`, `datetime64[ns]`) → `str(duckdb_type)` (e.g. `INTEGER`, `BIGINT`, `VARCHAR`, `DOUBLE`, `BOOLEAN`, `TIMESTAMP`, `DATE`, `DECIMAL(18,3)`).

Normalization contract (the exact `To`):

- `NULL` → `None`; integer types → `int`; `FLOAT`/`DOUBLE` → `float` with `nan`/`inf` → `None`.
- `DECIMAL` → `float` (JSON-safe); `VARCHAR` → `str`; `BOOLEAN` → `bool`.
- `TIMESTAMP` → ISO string; `DATE` → `"YYYY-MM-DD"`; `TIME` → ISO string.
- `BLOB`/list/struct/map/enum/uuid/interval → JSON-safe fallback (`str` or list); these are not produced by current query results but are guarded.

## Blast Radius

- The `type` string in `DataQueryResult.columns` and `DataTransformResult.columns` changes from pandas dtype names to DuckDB type names — visible in the LLM-facing Xenix Table Text `schema:` block and the `data.transform` payload `columns`. This applies to **all** bindings (parquet, xlsx, csv) and transform output, not only CSV.
- Consumers:
  - `src/xenix/services/agent/tools.py` — `_query_columns_payload` / `_query_rows_payload` (project `type` and row dicts into the Agent payload).
  - `src/xenix/services/llm/xenix_table_text.py` — `_render_data_query` and `_markdown_alignment` (render `type`; numeric alignment keys off substrings `int/float/double/decimal/numeric/number`, which DuckDB names still satisfy).
  - `src/xenix/app.py` — `_run_smoke_checks` asserts `rows[0]["total"] == 3`.

## Invariants

- Row shape stays `list[dict[str, Any]]` keyed by column name; column order matches `columns`.
- Rows stay JSON-serializable: no `NaN`/`inf`/`datetime`/`Decimal`/numpy scalar leaks; NULL and non-finite floats → `None`; date/time → ISO string.
- `returned_row_count`, `total_row_count`, `truncated`, `limit`, and `validation_summary` are unchanged in computation and value.
- Numeric aggregate values (SUM/COUNT/AVG/…) are bit-identical to today for the same SQL.
- `data.query` still renders as valid Xenix Table Text.

## Verification

- New focused tests pin: numeric/null/boolean/date serialization (`NaN`→`None`, datetime→ISO, bool→`true/false`), column name+type order, and that INTEGER/DOUBLE/DECIMAL types stay numeric-aligned in the XTT renderer.
- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`, `pdm run check`, `pdm run smoke`

## prerequisite Evidence IDs

- Probed pandas serialization contract (2026-08-16): `NaN`/`NaT`/`None`/`inf` → `null`; `datetime64[us]` → `"2024-01-01T00:00:00.000"`.

## return-to-discussion triggers

- If any consumer or test depends on an exact pandas dtype string (`object`, `datetime64[ns]`, …), or a real query produces a type (DECIMAL/LIST/BLOB/STRUCT) without a safe JSON mapping, pause and return to discussion before proceeding.
