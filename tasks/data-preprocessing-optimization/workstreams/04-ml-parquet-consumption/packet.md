# ML Parquet Consumption

## Objective & Hypothesis

ML should consume registered app-owned Parquet datasets directly. A permanent Parquet-to-CSV bridge would preserve the old file-centric dataset model and reintroduce type inference risk.

## Status

verified with follow-up risk

## Durable Owners / Blast Radius

- `MLService`
- `MLTaskService`
- `src/xenix/services/ml/dataset_loader.py`
- ML execution tests and worker staging paths

## State Diff

From: ML registered dataset paths primarily assumed CSV/XLS/XLSX-like file inputs.

To: ML registered dataset loading supports Parquet-backed app-owned datasets.

## Invariants

- Registered dataset identity resolves to app-owned dataset content.
- User-facing ML artifacts may still be CSV/reports when they are exports, not registered dataset storage.
- Do not add a long-lived Parquet -> CSV compatibility layer for registered datasets.

## Decisions Consumed

- Internal registered-dataset operations should use Parquet.
- CSV remains allowed for user-facing exports and reports.

## Open Questions

- OQ-006: remote/SSH worker path staging verification for Parquet inputs.

## Verification Plan

- ML training/evaluation can load Parquet registered datasets.
- ML apply can use registered Parquet input datasets.
- Worker staging does not rewrite Parquet into a CSV-only path.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

Add targeted worker-path verification if the next ML-related sub-task touches remote execution.
