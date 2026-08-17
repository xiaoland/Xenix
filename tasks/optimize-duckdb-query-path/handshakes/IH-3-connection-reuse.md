# IH-3 — Reuse the in-memory DuckDB connection

- status: `proposed`

## Address and Object

`src/xenix/services/data_transform.py`, class `DataQueryTransformService`:

- `__init__()` — add a `threading.local()` holder.
- new `_connection()` helper — lazily create the thread-local `:memory:` connection and clear leftover temp objects.
- `query()` and `_transform_in_process()` — replace `with duckdb.connect(database=":memory:") as connection:` with `connection = self._connection()`.

## State Diff

`From -> To`:

- From: each `query()` / `_transform_in_process()` opens a fresh `duckdb.connect(":memory:")` (≈14.9 ms) and closes it on exit.
- To: a lazily created **thread-local** in-memory connection is reused across calls on the same thread; before each operation the prior call's temp-schema objects are dropped so the operation starts clean.

## Blast Radius

- `query()` / `transform()` call sites: `agent/tools.py`, `app.py` smoke, `preprocessing_worker.py`.
- Temp-object lifetime: temp views/tables are now dropped at the start of the next call instead of at connection close. Internal only; no external surface observes temp objects.
- Thread-local reuse keeps DuckDB connections from being shared across threads (they are not thread-safe). Production `data.transform` still runs in a spawned worker process, so it is unaffected by reuse in the parent process.

## Invariants

- Identical query/transform results across calls (each operation sees a clean temp slate).
- No temp-name collisions across calls (drop-leftovers, and `CREATE OR REPLACE` where the service creates views/tables).
- `data.query` / `data.transform` validation, SQL authority boundary, and result contract are unchanged.

## Verification

- New tests: repeated `query()` calls on one instance with the same alias return identical results (no "already exists" collision); a `query()` then an inline `transform()` reuses without stale temp leakage.
- `pdm run pytest --direct tests/test_data_transform_service.py`, `pdm run test`, `pdm run check`, `pdm run smoke`.

## prerequisite Evidence IDs

- `probe_connect.py`: connect ≈14.9 ms (config-insensitive); reused query ≈0.17 ms; `CREATE TEMP VIEW` collides, `CREATE OR REPLACE` + drop-leftovers avoids it.

## return-to-discussion triggers

- If a caller ever runs `query()` from multiple threads concurrently and needs shared connection state (it does not today), or if any code depends on temp objects persisting after a call returns (none does).
