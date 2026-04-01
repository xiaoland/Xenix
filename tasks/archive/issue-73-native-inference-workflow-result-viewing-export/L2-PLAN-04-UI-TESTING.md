# L2 Plan 04: UI And Testing

## UI Module Layout

The UI additions should use these files:

- `src/xenix/ui/main_window.py`
  - extend the shell to host `Datasets`, `Training`, and `Inference`
- `src/xenix/ui/inference_workspace.py`
  - new inference workflow screen
- `src/xenix/ui/dataset_workspace.py`
  - replace the old mutable attach flow with create-from-dataset setup
- `src/xenix/ui/widgets/inference_row_editor.py`
  - dedicated row-entry widget
- `src/xenix/ui/widgets/task_log_view.py`
  - reused for inference task logs

## Dataset Workspace Changes

Concrete UI direction:

- keep dataset file import and inspection in `DatasetWorkspace`
- keep project selection there
- change work-item creation to require:
  - work-item name
  - selected source dataset
  - selected feature columns
  - optional target columns
- remove the old "create work item first, attach later" primary path

## Inference Workspace Composition

`InferenceWorkspace` should contain:

- project selector
- work-item selector
- copied-dataset summary label
- trained-model selector
- input-mode tabs or segmented control
  - manual
  - batch file
- `InferenceRowEditorWidget`
- batch file chooser/list
- submit button
- task table
- task detail summary
- task log view
- open-result button
- export-result button

## `InferenceRowEditorWidget`

Public API:

- `set_columns(columns: list[str]) -> None`
- `rows() -> list[dict[str, str | None]]`
- `clear() -> None`

Widget behavior:

- one table column per feature
- one blank starter row
- add-row button
- remove-selected-row button
- values stored as strings or empty values

The widget does not:

- infer dtypes
- write CSV files
- validate model compatibility

## Manual Submission Flow

1. UI reads rows from `InferenceRowEditorWidget`
2. UI calls `DatasetService.materialize_manual_inference_csv(...)`
3. UI receives one temp CSV path
4. UI calls `MLService.infer(...)` with `input_files=[temp_csv_path]`
5. UI refreshes the task/runtime view

## Batch Submission Flow

1. UI collects one or more user-selected tabular files
2. UI calls `MLService.infer(...)` with those absolute paths
3. UI refreshes the task/runtime view

## Result Action Enablement

The open/export buttons should stay disabled until the selected task:

- is `SUCCEEDED`
- has `result_dataset_id`
- has an openable `INFERENCE_RESULT` artifact

This keeps the UI state derived from service-owned results rather than guesses.

## Testing Layout

Add or update tests:

- `tests/test_migrations.py`
  - reset-required behavior for schema versions `< 4`
  - fresh `v4` schema creation
- `tests/test_repositories.py`
  - dataset provenance queries
  - `get_by_ml_task(...)`
- `tests/test_services.py`
  - immutable work-item creation
  - copied dataset row creation
  - temporary manual CSV materialization
  - export copy behavior
- `tests/test_ml_execution.py`
  - inference task queueing
  - worker inference result ingestion
  - canonical output copy
  - generated dataset registration
- `tests/test_inference_workspace.py`
  - model default selection
  - row-editor extraction
  - result action enablement

## Fixtures

Add small fixtures under `tests/fixtures/`:

- `regression_predict.csv`
- `classification_predict.csv`
- `predict_multi_file_a.csv`
- `predict_multi_file_b.xlsx`

They should be tiny and deterministic.

## Documentation Updates

Implementation should update:

- `docs/20-product-tdd/storage-ownership.md`
- `docs/20-product-tdd/task-lifecycle.md`
- `docs/40-deployment/runtime-state.md`
- `docs/40-deployment/development.md`
- `tasks/archive/issue-73-native-inference-workflow-result-viewing-export/RESULT.md`

## L3 Preparation

When L3 starts, the work should be staged in this order:

1. schema `v4`, repository changes, and reset-required migration behavior
2. work-item creation rewrite and dataset provenance helpers
3. inference contracts and worker operation
4. `MLService` / `MLTaskService` inference flow
5. inference workspace and row-entry widget
6. tests and documentation

