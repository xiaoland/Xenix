# IH-2 — CSV bindings scan through DuckDB directly

- status: `superseded` (see [findings](../evidence/findings.md))

## Address and Object

`src/xenix/services/data_transform.py`, class `DataQueryTransformService`:

- `_register_binding()` — route `DatasetSourceFormat.CSV` to a new `_register_csv_binding()` instead of the `_load_frame_with_schema()` + `connection.register()` fallback.
- Add `_register_csv_binding(connection, relation_name, path)`, mirroring `_register_parquet_binding()`.

## State Diff

`From -> To`:

- From: `loaded = self._load_frame_with_schema(path)` (full `pd.read_csv` + `resolve_tabular_schema` + `apply_tabular_schema`) then `connection.register(relation_name, loaded.frame)` (pandas → Arrow upload).
- To: `CREATE TEMP VIEW {relation_name} AS SELECT {loader_name AS tool_name, ...} FROM read_csv_auto('path') AS source`, with the canonical schema from `load_tabular_schema(path, CSV)` (header-only `pd.read_csv(path, nrows=0)`).

## Blast Radius

- CSV-bound `data.query` / `data.transform` SQL **type inference** moves from pandas `read_csv` inference to DuckDB `read_csv_auto` inference. Known deltas: DuckDB auto-detects `DATE`/`TIMESTAMP` (pandas leaves such columns as `object`), and leading-zero / mixed-type inference can differ.
- The `type` string for CSV columns changes accordingly (already covered by IH-1's DuckDB-type mapping).
- Consumers: `agent/tools.py`, `llm/xenix_table_text.py`, `app.py` smoke, and the Agent skills that write SQL over CSV (`xenix-data-analysis`, `xenix-data-preprocessing`).
- **Not affected:** `data.clean` (operates on pandas frames), dataset inspection (Polars), parquet/xlsx bindings, storage.

## Invariants

- Canonical column-name resolution is unchanged (still `load_tabular_schema` → `tool_name` projection), so `column_reference: "names" | "indexes"` and `_create_indexed_binding_view()` behave identically.
- Row counts and row values for deterministic columns are unchanged (same rows scanned).
- Numeric aggregation over numeric columns still works — specifically the `app.py` smoke `SELECT SUM(value) AS total FROM input` over a CSV binding still returns `3`.
- SQL authority boundary is unchanged: user SQL still cannot call file-scan functions or read direct paths.

## Verification

- New focused tests: CSV binding with numeric / null / string / date columns assert inferred types and query results; `column_reference: "indexes"` still projects `c0, c1, ...`.
- **Pre-implementation type-inference alignment check:** compare `pd.read_csv` dtypes vs `read_csv_auto` schema on a representative CSV corpus (numeric, leading-zero identifiers, mixed types, date-as-string, empty-cell numeric). The delta is recorded in the execution log and is the decision input for the return-to-discussion trigger.
- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`, `pdm run check`, `pdm run smoke`

## prerequisite Evidence IDs

- Code audit (2026-08-16): CSV bindings currently fall through to `_load_frame_with_schema` → `pd.read_csv` + `register()`; parquet bindings already scan directly via `read_parquet`.

## return-to-discussion triggers

- If the type-inference delta materially changes query semantics for a realistic CSV (date-as-string becoming `DATE`, leading-zero identifiers, or mixed-type columns), pause and return to discussion to choose between accepting DuckDB inference and pinning an explicit column schema.
