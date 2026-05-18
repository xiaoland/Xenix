# Issue 83 Data Cleaning Result

## Objective Recap

- Objective: Implement Slice 0 and Slice 1 for foundational data cleaning.

## Summary

- Added explicit derived dataset lineage through `derived_from_dataset_id`.
- Added forward storage migration from schema v1 to v2 for existing local databases.
- Removed product-facing `project_id` exposure from Agent data tools while retaining Project as a storage compatibility detail.
- Added `DataCleaningService` as the deterministic Python/Pandas execution boundary for `data.clean`.
- Expanded `data.clean` to support compact atomic operations: duplicate policy, missing policy, type corrections, text standardization, and validation rules.
- Preserved backward-compatible default behavior for `drop_duplicates` and default missing-value filling.
- Updated durable docs to use Chatbot terminology and record data-cleaning, artifact, storage, and service-boundary truths.

## Files Changed

- `src/xenix/services/data_cleaning.py`
- `src/xenix/services/agent/tools.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/repositories/datasets.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/app.py`
- `src/xenix/ui/AGENTS.md`
- `src/xenix/ui/widgets/AGENTS.md`
- `tests/test_data_cleaning.py`
- `tests/test_services.py`
- `tests/test_repositories.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_storage_bootstrap.py`
- `docs/10-prd/product-scope.md`
- `docs/10-prd/glossary.md`
- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/20-product-tdd/storage-ownership.md`
- `docs/20-product-tdd/artifact-links.md`
- `docs/20-product-tdd/ml-task-lifecycle.md`
- `docs/30-unit-tdd/agent-harness.md`
- `docs/30-unit-tdd/chatbot-ui.md`
- `docs/40-deployment/development.md`
- `docs/40-deployment/local-state-evolution.md`
- `docs/40-deployment/runtime-state.md`

## Verification

- Command: `pdm run check`
- Result: passed.
- Command: `pdm run pytest tests/test_data_cleaning.py tests/test_services.py tests/test_repositories.py tests/test_agent_harness_first_slice.py -q`
- Result: `18 passed`.
- Command: `pdm run pytest tests/test_ml_execution.py -q`
- Result: `5 passed`.
- Command: `pdm run pytest tests/test_main.py tests/test_i18n.py tests/test_ml_execution.py -q`
- Result: `29 passed`.
- Command: `pdm run pytest -q`
- Result: `75 passed`.
- Command: `pdm run check`
- Result: passed after the v1-to-v2 migration fix.
- Command: `pdm run pytest tests/test_storage_bootstrap.py -q`
- Result: `4 passed`.
- Command: `pdm run pytest -q`
- Result: `76 passed`.

## Promoted Truths

- Durable docs updated:
  - `docs/10-prd/product-scope.md`
  - `docs/10-prd/glossary.md`
  - `docs/20-product-tdd/runtime-boundaries.md`
  - `docs/20-product-tdd/storage-ownership.md`
  - `docs/20-product-tdd/artifact-links.md`
  - `docs/20-product-tdd/ml-task-lifecycle.md`
  - `docs/30-unit-tdd/agent-harness.md`
  - `docs/30-unit-tdd/chatbot-ui.md`
  - `docs/40-deployment/development.md`
- Reason: Slice 0 and Slice 1 changed product vocabulary, dataset lineage, service ownership, and storage schema. The storage change now includes automatic v1-to-v2 migration for existing local state.

## Deferred Items

- DuckDB-backed `data.query` and `data.transform` moved to `slice-2-3-result.md`.
- Dynamic cleaning tool family loading remains Slice 4.
- Full Project table removal remains a dedicated migration because ML task code still uses `project_id`.
