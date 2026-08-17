# Plan-1 — Remove the pandas round-trip (IH-1)

## Working set

- `src/xenix/services/data_transform.py` (`DataQueryTransformService`)
- `tests/test_data_transform_service.py` (new)

## Pass 1 — cursor-based materialization

1. Add `_columns_from_description(description) -> list[dict[str, str]]` that maps each `(name, type_code, ...)` to `{"name": name, "type": str(type_code)}`.
2. Add `_records_from_cursor(rows, columns) -> list[dict[str, Any]]` that zips column names with each `fetchall()` tuple and applies the normalization contract from IH-1 (NULL→None, float nan/inf→None, DECIMAL→float, TIMESTAMP/DATE/TIME→ISO string, BOOLEAN→bool, BLOB→str fallback).
3. Rewrite `query()` to keep a `cursor` from the `SELECT ... LIMIT` execution, then derive `columns` and `rows` from it. Remove `.fetchdf()`.
4. Rewrite `_output_columns()` to use `cursor.description` from `SELECT * FROM output LIMIT 1` instead of `.fetchdf()`.
5. Delete `_records()` and `_columns()` if they become unused; otherwise keep only what is still referenced.

Stop condition: `query()` and `transform()` no longer import or call pandas for result materialization (pandas may still be used elsewhere in the module for schema headers, which is out of scope).

## Pass 2 — focused tests

Add `tests/test_data_transform_service.py` using the existing fixture pattern (`XENIX_APP_HOME` + `ensure_app_dirs` + `StorageBootstrapService`), pinning:

- numeric `SUM(value)` over a CSV binding == 3 (mirrors `app.py` smoke);
- null/boolean/date serialization: `NaN`/null → `None`, datetime → ISO string, bool → `true/false`;
- column name + `type` order, and numeric alignment (INTEGER/DOUBLE/DECIMAL) via the XTT renderer;
- `transform()` output parquet row count + columns.

## Pass 3 — verification

- `pdm run pytest --direct tests/test_data_transform_service.py`
- `pdm run test`
- `pdm run check`
- `pdm run smoke`
