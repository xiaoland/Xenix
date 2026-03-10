# Dataset Domain Guidance

## Scope

This guidance applies to dataset registration, dataset inspection, and work-item dataset-selection state under `src/xenix/services/`.

## Rules

- Keep dataset files external. Do not copy imported datasets into canonical app-managed storage.
- Persist dataset registration metadata on `Dataset`.
- Persist selected dataset, feature columns, and target columns on `WorkItem`.
- Keep dataset inspection metadata ephemeral and runtime-derived.
- Validate column selections through service code, not UI-only checks.
- Do not let UI code parse `.csv` or `.xlsx` files for business decisions.

## Boundaries

- `DatasetService` owns dataset registration and source-file inspection.
- `WorkItemService` owns persisted work-item dataset-selection state.
- Issue `#72` should consume the dataset-analysis capability built here rather than reimplementing it.
