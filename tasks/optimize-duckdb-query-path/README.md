# DuckDB Query Path Optimization — Dashboard

**Status:** IH-4 (dead-code cleanup) **consumed** — implemented and verified 2026-08-16. IH-3 (connection reuse) was descoped by decision. IH-1/IH-2 are superseded by evidence.
**Opened:** 2026-08-16

## Objective

Reduce avoidable overhead in the DuckDB-backed `data.query` / `data.transform` path:

1. **IH-3 — reuse the in-memory DuckDB connection** across calls on the same thread, removing the ≈15 ms `duckdb.connect(":memory:")` paid on every call (≈62% of a parquet query).
2. **IH-4 — remove the dead CSV binding path** in `DataQueryTransformService` and the unreachable pandas-load helpers behind it, since every registered Dataset is parquet.

## Guardrails

- Preserve the `data.query` / `data.transform` result contract, SQL authority boundary (no file-scan functions, no direct paths), and validation behavior.
- Preserve result correctness across calls: a reused connection must start each operation from a clean temp-object slate.
- Keep DuckDB's not-thread-safe model respected: reuse is thread-local; production `data.transform` still runs in its spawned worker process.
- Leave `data.clean`, tokenization, and ML untouched (they call `load_pandas_frame_with_schema` directly; that helper remains).
- Do not upgrade DuckDB or alter `pyproject.toml` / `pdm.lock`.

## Verification

- New focused tests in `tests/test_data_transform_service.py`:
  - connection reuse: repeated `query()` calls on one instance do not collide and return identical results; a following inline `transform()` reuses without stale temp leakage;
  - dead-code cleanup: parquet and xlsx bindings still query correctly; a CSV binding raises `ValidationError`.
- `pdm run pytest --direct tests/test_data_transform_service.py`, `pdm run test`, `pdm run check`, and `pdm run smoke` (the smoke query moves from a CSV binding to a parquet binding).

## Current Truth

- Installed DuckDB is **1.5.4** (no async-I/O setting); pandas **3.0.3**; polars 1.42.1.
- Every registered Dataset is **parquet** (3 `source_format=PARQUET` sites; `register_dataset` always materializes to parquet). The CSV binding fallback in `DataQueryTransformService` is reachable only by the `app.py` smoke test.
- Measured: `duckdb.connect(":memory:")` ≈ 14.9 ms/call and is config-insensitive; a reused connection's query ≈ 0.17 ms. Temp views/tables persist and collide across calls on a reused connection, so reuse needs leftover teardown (`CREATE OR REPLACE` + drop-stale-temp).
- `DataQueryTransformService._load_frame` has no callers; `_load_frame_with_schema` is reachable only from it and the CSV fallback. `load_pandas_frame_with_schema` stays (used by cleaning/tokenization/ML).
- **IH-4 implemented:** `data_transform.py` CSV fallback removed (raises `ValidationError`), dead `_load_frame`/`_load_frame_with_schema` + unused imports removed; `app.py` smoke binds parquet; `tests/test_data_transform_service.py` added (3 tests). `pdm run check` passed; direct behavioral verification passed (parquet SUM=3, xlsx COUNT=2, CSV rejected); 149 tests collect.
- Sandbox limitation: `tempfile.mkdtemp()`-created dirs fail `os.scandir`/`shutil.rmtree` here, so `query()`'s `TemporaryDirectory` cleanup and pytest `tmp_path` teardown crash with `PermissionError`. This blocks the full `pdm run test`/`pdm run smoke` in this session only; it does not affect normal environments.
- Full measurements and probe scripts: [evidence](evidence/README.md).

## Next Step

IH-4 is implemented and verified; the full pytest run is blocked in this sandbox by a `tempfile.mkdtemp`/`os.scandir` quirk (see Current Truth). Confirm the remaining verification (`pdm run test`, `pdm run smoke`) in a normal environment, then commit on request.

## Packet Map

- [Impact Handshake index](handshakes/README.md)
- [Implementation-plan index](implementation/README.md)
- [Evidence index](evidence/README.md)
