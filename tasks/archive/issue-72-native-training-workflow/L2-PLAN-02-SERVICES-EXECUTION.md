# L2 Plan 02: Services And Execution

## Public Service Boundary

Issue `#72` should introduce `src/xenix/services/ml_service.py` as the main UI-facing boundary.

`MLService` should own:

- model catalog lookup
- workflow-level request validation
- explicit workflow submission
- cross-task orchestration
- follow-up evaluation task creation for workflow-driven training

`MLTaskService` should own atomic task runtime:

- task queue management
- worker process dispatch
- worker output validation
- task artifact registration
- canonical model persistence
- trained-model creation
- evaluation-result finalization and best-model updates

Add `MLWorkerRunner` as a pure infrastructure helper for:

- spawning the worker process
- targeting the already-resolved operation entrypoint
- passing the task working directory / request file
- waiting for exit code

`MLWorkerRunner` should not know:

- `MLTask` lifecycle
- SQLite
- trained-model persistence
- workflow chaining
- operation routing tables inside the worker process

`DatasetService` remains the owner of dataset inspection.

`MLTaskService` remains the atomic-task boundary, not the main workflow entry point.

## `MLService` API

The public API should be:

- `list_models() -> list[ModelCatalogEntry]`
- `get_model(model_key: str) -> ModelCatalogEntry`
- `fit_with_evaluate(input_data: FitWithEvaluateInput) -> MLTaskRow`
- `tune_with_evaluate(input_data: TuneWithEvaluateInput) -> MLTaskRow`
- `bulk_tune_with_evaluate(input_data: BulkTuneWithEvaluateInput) -> list[MLTaskRow]`
- `list_work_item_tasks(work_item_id: str) -> list[MLTaskRow]`
- `get_task_details(ml_task_id: str) -> MLTaskDetails`
- `list_trained_models(work_item_id: str) -> list[TrainedModelRow]`

Atomic task submission helpers may exist behind this boundary, but they should not be the primary UI-facing workflow API.

## Input Models

`FitWithEvaluateInput` fields:

- `work_item_id: str`
- `model_key: str`
- `params: dict[str, Any]`

`TuneWithEvaluateInput` fields:

- `work_item_id: str`
- `model_key: str`
- `param_grid: dict[str, list[Any]]`

`BulkTuneWithEvaluateInput` fields:

- `work_item_id: str`
- `tasks: list[HyperparameterTuningSelection]`

`HyperparameterTuningSelection` fields:

- `model_key: str`
- `param_grid: dict[str, list[Any]]`

Validation rules:

- workflow inputs resolve `project_id`, `dataset_id`, `feature_columns`, and `target_columns` from the persisted `WorkItem`
- supervised models require `target_columns`
- targetless models require `target_columns == []`
- every selected feature/target column must exist in the inspected dataset
- params and param grids must validate through the registry's Pydantic models
- bulk tuning submission may reject mixed `problem_kind` selections in one UI action if that keeps review and best-model comparison clearer

## Queue Design

V1 execution should use a single service-owned queue with one active worker process at a time.

Components:

- `MLTaskService`
  - holds an in-memory queue of `ml_task_id`
  - runs one dispatcher thread
  - starts tasks
  - invokes `MLWorkerRunner`
  - validates worker output contracts
  - finalizes atomic task results
- `MLWorkerRunner`
  - launches the worker process
  - returns process exit status only

Why sequential in v1:

- the issue requires queue states, not parallel execution
- it keeps task lifecycle reasoning simple
- it avoids concurrent best-model updates racing against the same work item
- it keeps the first implementation easier to review and test

## Workflow Submission Algorithm

`fit_with_evaluate(...)`:

1. load the persisted work item
2. resolve project, dataset, feature columns, and target columns from work-item state
3. inspect dataset source file through `DatasetService`
4. validate the persisted column selection against the inspected dataset
5. load model definition
6. validate params through the model's Pydantic `Params` model
7. derive evaluation policy from `problem_kind`
8. create one `FIT` task with:
   - `task_type = FIT`
   - `status = PENDING`
   - `request_payload` containing resolved dataset state, model params, evaluation policy, and an explicit continuation plan for `EVALUATE`
9. write `request.json`
10. enqueue the task id
11. return the created fit task row immediately

`tune_with_evaluate(...)`:

1. load the persisted work item
2. resolve project, dataset, feature columns, and target columns from work-item state
3. inspect dataset source file through `DatasetService`
4. validate the persisted column selection against the inspected dataset
5. validate the selected model and `param_grid`
6. derive evaluation policy from the model's `problem_kind`
7. create one `HYPERPARAMETER_TUNING` task with:
   - `task_type = HYPERPARAMETER_TUNING`
   - `status = PENDING`
   - `request_payload` containing resolved dataset state, tuning grid, evaluation policy, and an explicit continuation plan for `EVALUATE`
8. write `request.json`
9. enqueue the task id
10. return the created tuning task row immediately

`bulk_tune_with_evaluate(...)`:

1. resolve shared work-item dataset state once
2. validate each selected model/grid pair independently
3. submit one tuning task per selection
4. return the created task rows in submission order

## Worker Launch Contract

`MLTaskService` launches one worker process through `MLWorkerRunner`, using `multiprocessing`, not `python -m`.

Why:

- PyInstaller packaging cannot assume a user-managed Python runtime
- `multiprocessing` can spawn the packaged executable and keeps one implementation path for dev and packaged runs
- the operation entrypoint stays importable and testable without shelling out to `python -m`
- task type is already known before spawn, so a second dispatch layer inside the worker process is unnecessary

Worker launch steps:

1. `MLTaskService` resolves the operation entrypoint from `MLTaskType`
2. `MLTaskService` transitions the task to `RUNNING`
3. `MLWorkerRunner` spawns that operation entrypoint in a worker process
4. the operation code loads `request.json`
5. the operation code writes `logs.jsonl`
6. the operation code writes `result.json`
7. the process exits with code `0` or non-zero

The worker does not write SQLite.

## Execution Finalization Algorithm

After worker exit, `MLTaskService` finalizes the atomic task.

`FIT` task finalization:

1. read and validate `FitTaskResult`
2. validate fit-task-owned artifacts
3. canonicalize the produced model artifact
4. create one `TrainedModelRow`
5. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
6. notify `MLService` that a workflow-owned continuation may be needed

`HYPERPARAMETER_TUNING` task finalization:

1. read and validate `HyperparameterTuningTaskResult`
2. validate tuning-task-owned artifacts
3. canonicalize the produced model artifact
4. create one `TrainedModelRow`
5. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
6. notify `MLService` that a workflow-owned continuation may be needed

`EVALUATE` task finalization:

1. read and validate `EvaluateTaskResult`
2. validate evaluation-task-owned artifacts
3. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
4. notify `MLService` so the workflow layer can decide whether to update `work_item.best_trained_model_id`

Failure conditions:

- missing result file
- invalid result schema
- declared artifact missing
- canonical model copy failure
- trained-model persistence failure

Any of those should fail the task and preserve logs/result files for debugging.

## Result Persistence Rule

Every successful `FIT` or `HYPERPARAMETER_TUNING` task persists exactly one `TrainedModelRow`.

That rule applies to both:

- manual training
- hyperparameter tuning

`EVALUATE` tasks do not create new model artifacts.

Evaluation inputs should reference predecessor-task artifacts rather than re-derive a fresh split from the live external dataset.

Bulk tuning in the UI is just repeated single-model tuning submission, so the persistence model stays simple.

## Best-Model Update Algorithm

When an `EVALUATE` task succeeds:

1. `MLService` loads the evaluated trained model reference from `request_payload`
2. `MLService` loads the new task's evaluation snapshot from `result_payload`
3. `MLService` loads the current work-item best model if one exists
4. if no current best exists, set the evaluated trained model
5. if a current best exists, load its linked evaluation-task result payload
6. if the policies are comparable, compare the evaluation snapshots
7. if the new trained model is better, update `best_trained_model_id`
8. if the policies are not comparable, leave the current best unchanged and record that decision in workflow-owned state

## Service Detail Model

`MLTaskDetails` should expose:

- persisted `MLTaskRow`
- request snapshot
- result summary
- persisted trained-model id
- recent parsed log entries
- task artifact paths
