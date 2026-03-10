# L3 Plan 03: Tests And Docs

## 1. Service Tests

Files:

- `tests/test_services.py`
- new `tests/test_dataset_inspection.py`

Changes:

- replace the current temp-copy-focused dataset test with inspection-focused tests
- keep existing dataset registration coverage
- add tests for:
  - valid csv inspection
  - valid xlsx inspection
  - unsupported suffix
  - missing file
  - empty file
- add work-item dataset-selection persistence tests

Suggested test cases:

- `test_dataset_service_inspects_csv_summary_and_column_kinds`
- `test_dataset_service_rejects_empty_dataset_file`
- `test_work_item_service_persists_dataset_feature_and_target_selection`
- `test_work_item_service_rejects_overlapping_feature_and_target_columns`

## 2. Migration Tests

Files:

- `tests/test_storage_bootstrap.py`
- new `tests/test_migrations.py`

Add assertions for schema v2:

- migrated `work_item` rows have:
  - `dataset_id is None`
  - `feature_columns == []`
  - `target_columns == []`

Update storage bootstrap tests to reflect the direction of the branch:

- stop treating `temp/datasets/` as import-critical behavior
- keep runtime directory assertions aligned with current storage layout until `#72` removes the shared temp-copy path

## 3. UI Smoke Tests

Files:

- new `tests/test_dataset_workspace.py`

If Qt test setup is practical, add smoke coverage for:

- file-drop handling
- file-picker inspection flow
- summary rendering
- save action with mocked services

If full widget testing is too costly for the first pass, prefer:

- isolated tests for `ColumnSelectionWidget`
- isolated tests for `FileDropZone`

## 4. Fixtures

Files:

- new `tests/fixtures/import_customers.csv`
- new `tests/fixtures/import_sales.xlsx`
- new `tests/fixtures/empty.csv`

Fixture rules:

- keep files small
- keep columns intentionally mixed:
  - numeric
  - boolean-like or nullable
  - text
  - date-like if feasible

## 5. Documentation Updates

Files:

- `docs/contracts/storage-ownership.md`
- `docs/runbooks/runtime-state.md`
- `docs/runbooks/development.md`
- new `docs/task/issue-75-native-dataset-import-column-analysis/RESULT.md`

Required updates:

- clarify that dataset inspection metadata is ephemeral
- clarify that work item owns selected dataset/feature/target state
- remove wording that implies dataset temp copies are part of import
- document added dependencies and verification commands

## 6. Optional Local Guidance

File:

- new `src/xenix/ui/AGENTS.md` only if the workspace and widget composition becomes non-trivial

For issue `#75`, this is optional.
The stronger candidate for module-local guidance remains `src/xenix/services/ml/AGENTS.md` in issue `#72`.

## 7. Downstream Alignment With Issue `#72`

After `#75` implementation:

- revise issue `#72` plans and later code to consume:
  - `WorkItem.dataset_id`
  - `WorkItem.feature_columns`
  - `WorkItem.target_columns`
  - `DatasetService.inspect_source_file()`
  - the reusable column-selection widget if still appropriate

This keeps `#72` focused on ML execution rather than dataset setup duplication.

## 8. Verification Commands

Expected verification commands after implementation:

```bash
pdm install
pdm run test
pdm run check
```

Manual verification:

1. launch `pdm run dev`
2. create a project and work item
3. import a `.csv` file by file picker
4. import a `.csv` or `.xlsx` file by drag-and-drop
5. confirm summary and inferred column kinds render
6. save selected feature/target columns to the work item
