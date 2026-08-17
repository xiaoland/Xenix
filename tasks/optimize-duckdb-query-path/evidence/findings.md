# Findings — DuckDB query-path investigation

Environment: duckdb **1.5.4**, pandas **3.0.3** (pyproject floor is `>=2.3.0`), polars 1.42.1. All probes run against the project venv.

## 1. Type inference: pandas vs DuckDB `read_csv_auto`

Representative CSV (`probe_type_alignment.py`):

| column | pandas 3.0.3 | duckdb `read_csv_auto` | delta |
| --- | --- | --- | --- |
| `id` | int64 | BIGINT | — |
| `zip_code` ("001") | int64 (**drops leading zero**) | VARCHAR (**preserves**) | DuckDB better |
| `amount` (has empty cell) | float64 | BIGINT (empty→NULL) | benign |
| `price/score/ratio` | float64 | DOUBLE | — |
| `label/mixed` | str | VARCHAR | — |
| `flag` ("true"/"false") | bool | BOOLEAN | — |
| `date_iso` ("2024-01-01") | str | **DATE** | semantic change |
| `date_us` ("01/02/2024") | str | VARCHAR | — |
| `timestamp_col` | str | **TIMESTAMP** | semantic change |
| `empty_num` | float64 | BIGINT | benign |
| `big_int` (19–20 digit) | uint64 (**exact**) | **DOUBLE (lossy)** | **regression** |

`all_varchar=true` breaks numeric SQL (`SUM(VARCHAR)` raises). `auto_type_candidates` cannot include `HUGEINT` (rejected by binder), so the `big_int` loss is unfixable via auto-detection.

## 2. `read_csv_auto` correctness hazards (why IH-2 is unsafe)

1. **Sampling mis-inference → hard error.** Default `sample_size=20480`: a numeric column whose first non-numeric value appears at row 30,001 is inferred BIGINT, then the full scan raises `ConversionException: Could not convert string 'oops' to INT64`. pandas reads the whole file and infers `object` with no error. `sample_size=-1` fixes inference but costs a full pre-scan (≈2× read).
2. **Big-integer precision loss.** `>int64` integers infer as `DOUBLE`, silently rounding. Current path preserves them exactly (pandas 3.0 `uint64` → `register` → `UBIGINT`).
3. **DATE/TIMESTAMP auto-detection.** A date-string column becomes a real DATE/TIMESTAMP, changing SQL semantics (string functions break) and the LLM-visible type.

## 3. Cost measurements

CSV binding, 200k rows / 13.6 MB (`probe_cost_binding.py`):

- current `pd.read_csv` (230 ms) + `register` (94 ms) ≈ **394 ms**
- `read_csv_auto` + `COUNT` ≈ **124 ms** (≈3× faster)

But the CSV binding path is **dead in production**: `register_dataset` always materializes imports to parquet (`dataset_service.py:199,206`), and every `DatasetRow.source_format` assignment in the tree is `PARQUET` (three sites). Only the `app.py` packaged-smoke query feeds a raw CSV into `_register_binding`.

Parquet `data.query`, 200k rows / 4.7 MB (`probe_parquet_path.py`, `probe_parquet_breakdown.py`):

| step | time |
| --- | --- |
| `duckdb.connect(":memory:")` | **15.4 ms (≈62%)** |
| result `fetchdf` + `to_json` (LIMIT 50) | ≈6.1 ms (≈25%) |
| header read (LIMIT 0) + view + COUNT | ≈2.0 ms (≈8%) |

Result materialization (`probe_roundtrip.py`): `fetchdf`+pandas `to_json` vs cursor `fetchall`+dict build saves **≈1.6 ms (LIMIT 50)** / **≈3.6 ms (LIMIT 1000)**.

## 4. Conclusion and revised recommendation

- **IH-2 (CSV direct scan): descope.** It optimizes a dead path and trades correctness (hard errors, big-int loss, date surprises) for speed that production never pays.
- **IH-1 (pandas round-trip): marginal.** ≈1.6–3.6 ms per bounded query, safe, but carries a visible type-string change (pandas dtype → DuckDB type name) for the LLM. Its real value is cleanliness, not speed.
- **Highest-leverage lever is connection reuse**: the per-call `duckdb.connect(":memory:")` costs ≈15.4 ms, ~62% of a parquet `data.query` call.

## 5. Connection-reuse evidence (`probe_connect.py`)

- `connect(':memory:')` ≈ **14.9 ms**, independent of `autoload_known_extensions`/`autoinstall_known_extensions` config (no cheap config fix).
- A reused connection's amortized query ≈ **0.17 ms** → reuse eliminates ≈15 ms per call.
- Temp objects collide across calls on a reused connection: plain `CREATE TEMP VIEW` raises "already exists"; `CREATE OR REPLACE TEMP VIEW` succeeds. Leftover temp objects are enumerable via `duckdb_tables()`/`duckdb_views()` (1.5.4 columns are `table_name/table_oid/database_name/...`).
- Concurrency: `query()` runs inline in the single-threaded Agent tool loop; `transform()` runs in a **spawned process** in production (`LocalPreprocessingWorkerRunner`) or inline in tests (`InlinePreprocessingWorkerRunner`). Reuse therefore helps the inline `query()` path; a thread-local connection avoids DuckDB's not-thread-safe hazard.

## 6. Dead-code reachability

- `DatasetRow.source_format` is assigned `PARQUET` at all 3 sites (`dataset_service.py:206`, `ml_task_service.py:763,823`); `register_dataset` always writes parquet (`dataset_service.py:199,206`), and `register_dataset_attachment` reuses the same materialization. No CSV/XLSX Dataset is ever created.
- `DataQueryTransformService._register_binding`'s CSV/`else` fallback (→ `_load_frame_with_schema` → `load_pandas_frame_with_schema`) is reached only by the `app.py` smoke query, which binds a raw CSV.
- `DataQueryTransformService._load_frame` has **no callers**; `_load_frame_with_schema` is called only by that dead `_load_frame` and the CSV fallback. Both are removable.
- `load_pandas_frame_with_schema` itself stays live (used by `data_cleaning.py:734`, `data_tokenization.py:75`, `ml/dataset_loader.py:17`) — only its use inside `DataQueryTransformService` is dead.
