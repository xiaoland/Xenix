# Plan-4 — Dead-code cleanup (IH-4)

## Working set

- `src/xenix/services/data_transform.py` (`DataQueryTransformService`)
- `src/xenix/app.py` (`_run_smoke_checks`)
- `tests/test_data_transform_service.py`

## Pass 1 — remove the CSV fallback and dead helpers

1. In `_register_binding()`, after the parquet and xlsx/xls branches, `raise ValidationError` for any other source format (do not fall back to pandas load).
2. Delete `_load_frame()` and `_load_frame_with_schema()`.
3. Remove `load_pandas_frame_with_schema` and `LoadedPandasFrame` from the `.tabular` import (verify they are otherwise unused in the module).

Stop condition: `_register_binding()` has exactly parquet and xlsx/xls branches plus a rejection; the dead helpers are gone.

## Pass 2 — smoke query to parquet

4. In `app.py` `_run_smoke_checks()`, replace the CSV smoke source with a parquet file (e.g. `pd.DataFrame({"value": [1, 2]}).to_parquet(...)`) and keep `SELECT SUM(value) AS total FROM input` returning 3.

Stop condition: the smoke still asserts `rows[0]["total"] == 3` against a parquet binding.

## Pass 3 — focused tests

Extend `tests/test_data_transform_service.py`:

- parquet binding queries correctly (numeric aggregation);
- xlsx binding still queries correctly (regression);
- a CSV binding raises `ValidationError`.

## Pass 4 — verification

- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`, `pdm run check`, `pdm run smoke`
