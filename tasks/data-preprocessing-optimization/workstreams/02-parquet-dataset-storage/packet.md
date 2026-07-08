# Parquet Dataset Storage

## Objective & Hypothesis

Make registered datasets app-owned typed tables, not raw user-file pointers. Parquet should remove repeated CSV inference and keep CSV/XLS/XLSX as import/export interchange.

## Status

verified

## Durable Owners / Blast Radius

- `DatasetService`
- storage models and migrations
- tabular loader/schema resolver
- dataset attachment UI path
- services that consume registered datasets

## State Diff

From: dataset rows commonly pointed at user-managed CSV/XLS/XLSX files.

To: dataset rows point at app-owned Parquet files; import/workbook provenance is stored separately.

## Invariants

- Original user file path is provenance, not normal execution authority.
- Workbook imports can produce multiple dataset rows.
- Dataset content remains app-owned after the original file moves or disappears.
- Legacy rows need an explicit migration/compatibility decision, not silent semantic drift.

## Decisions Consumed

- Dataset means one app-owned tabular table.
- Workbook means an imported source that may produce many datasets.
- Internal registered-dataset work should use Parquet.

## Open Questions

- OQ-001: runtime DB legacy row migration policy.
- OQ-005: packaging verification for Parquet/workbook dependencies.

## Verification Plan

- CSV import creates app-owned Parquet.
- XLS/XLSX import splits non-empty sheets into separate datasets.
- Original file provenance is recorded outside execution authority.
- Data tools can query imported Parquet.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

Create a future workstream for legacy runtime DB migration policy before changing compatibility behavior.
