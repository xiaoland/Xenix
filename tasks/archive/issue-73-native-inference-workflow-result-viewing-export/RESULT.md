# Issue 73 Result

## Scope Delivered

Issue `#73` is implemented in the native shell without a separate L3 document. The final delivery follows the approved L0-L2 decisions:

- work items are created as dataset-bound and feature-bound units
- app-managed dataset copies are materialized as first-class `dataset` rows
- manual and batch inference share one file-based inference contract
- inference results are persisted as generated `dataset` rows linked by `dataset.ml_task_id`
- the desktop UI now exposes a dedicated `Inference` workspace for submission, result viewing, and export
- export is implemented as copying the canonical managed result artifact to a user-chosen destination

## Key Implementation Outcomes

### Domain and storage

- schema version advanced to `v4`
- local databases older than `v4` are now rejected with a reset-required bootstrap error
- `work_item.dataset_id` is now required
- `dataset` now tracks `copied_from`, `copied_at`, and nullable `ml_task_id`
- storage layout now includes canonical dataset and inference output directories

### Services and execution

- `WorkItemService.create_work_item(...)` now validates selected columns, copies the chosen source dataset into managed storage, creates the copied `dataset` row, and locks the work item onto that copy
- `DatasetService` now supports:
  - listing source and generated datasets
  - manual inference CSV materialization
  - canonical dataset export by copy
  - lookup of generated datasets by `ml_task_id`
- `MLService.infer(...)` now submits inference jobs using either the explicit trained model or the work item's best model
- the ML worker stack now supports inference execution and emits canonical `predictions.csv` outputs
- `MLTaskService` now finalizes inference tasks by copying canonical outputs, registering generated datasets, and publishing inference-result artifacts

### UI

- the dataset workspace now creates work items directly from dataset inspection instead of a later attach step
- a new `InferenceWorkspace` supports:
  - project, work item, and model selection
  - manual row-entry inference through a dedicated table widget
  - batch-file inference
  - inference task inspection and logs
  - opening canonical results
  - exporting canonical results
- the main window now exposes `Datasets`, `Training`, and `Inference` tabs

## Verification

Executed successfully:

- `pdm run test`
- `pdm run check`

Result:

- `28` tests passed
- source and tests compiled successfully during `pdm run check`

## Notes

- older local databases must be recreated because the implementation intentionally does not preserve pre-`v4` compatibility
- manual inference rows are normalized to temporary CSV files so inference runs through the same worker contract as batch files
