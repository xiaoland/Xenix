# Dataset Domain Guidance

## Scope

This guidance applies to dataset registration, dataset inspection, and work-item dataset materialization plus dataset-selection state under `src/xenix/services/`.

## Rules

- Keep source dataset registrations pointed at user-managed source files.
- Work-item creation may materialize an app-managed dataset copy under runtime artifacts.
- Persist both source-dataset metadata and app-managed dataset-copy metadata on `Dataset`.
- Persist selected dataset, feature columns, and target columns on `WorkItem`.
- Keep dataset inspection metadata ephemeral and runtime-derived.
- Validate column selections through service code, not UI-only checks.
- Do not let UI code parse `.csv` or `.xlsx` files for business decisions.

## Boundaries

- `DatasetService` owns source dataset registration, source-file inspection, and dataset export helpers.
- `WorkItemService` owns work-item dataset materialization and persisted work-item dataset-selection state.
- Issue `#72` should consume the dataset-analysis capability built here rather than reimplementing it.
