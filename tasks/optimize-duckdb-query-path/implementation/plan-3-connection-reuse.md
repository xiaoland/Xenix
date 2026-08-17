# Plan-3 — Connection reuse (IH-3)

## Working set

- `src/xenix/services/data_transform.py` (`DataQueryTransformService`)
- `tests/test_data_transform_service.py` (new)

## Pass 1 — thread-local connection + teardown

1. Add `import threading` and a `threading.local()` holder in `__init__`.
2. Add `_connection()` that lazily creates `duckdb.connect(":memory:")` per thread, stores it on the holder, and clears leftover temp objects first.
3. Add `_clear_temp_objects(con)` that drops all objects in the temp schema (enumerate via `duckdb_tables()`/`duckdb_views()`, matching 1.5.4 columns).

Stop condition: `_connection()` returns a connection with an empty temp schema on every call.

## Pass 2 — swap call sites

4. In `query()`, replace `with duckdb.connect(database=":memory:") as connection:` with `connection = self._connection()` (keep the `tempfile.TemporaryDirectory()` and `start_span` wrappers).
5. In `_transform_in_process()`, do the same.

Stop condition: no `duckdb.connect(":memory:")` remains in the service's per-call path.

## Pass 3 — focused tests

Extend `tests/test_data_transform_service.py`:

- two `query()` calls on the same instance with the same alias return identical results and do not raise "already exists";
- a `query()` followed by an inline `transform()` (via `InlinePreprocessingWorkerRunner`) reuses without stale temp leakage.

## Pass 4 — verification

- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`, `pdm run check`, `pdm run smoke`
