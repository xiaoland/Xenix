# L3 Plan 02: ML Service And Worker Execution

## Step 1: Establish The Training Boundary

Files:

- `src/xenix/services/ml_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/work_item_service.py`
- `src/xenix/services/ml/execution.py`

Boundary rule:

- `MLService` is the UI-facing training workflow boundary
- `DatasetService` keeps raw dataset inspection ownership
- `WorkItemService` keeps ownership of work-item dataset-selection state
- `MLTaskService` keeps lifecycle transitions and task-artifact registration
- `MLTaskExecutor` owns atomic task execution finalization: worker output validation, artifact registration, canonical model persistence, and execution-side continuation handling

That split avoids duplicating issue `#75` logic while keeping execution concerns out of the UI-facing service.

## `MLService` Construction

`MLService` should compose:

- session factory
- `AppPaths`
- `DatasetService`
- `WorkItemService`
- `MLTaskService`
- `MLExecutionManager`
- model registry

Public methods:

- `list_models()`
- `get_model(model_key)`
- `fit_with_evaluate(input_data)`
- `tune_with_evaluate(input_data)`
- `bulk_tune_with_evaluate(input_data)`
- `list_work_item_tasks(work_item_id)`
- `get_task_details(ml_task_id)`
- `list_trained_models(work_item_id)`

## Step 2: Validate Workflow Requests Against Existing Work-Item State

`fit_with_evaluate(...)` validation algorithm:

1. load the work item
2. resolve project, dataset, feature columns, and target columns from work-item state
3. require `dataset_id` to exist
4. require stored `feature_columns`
5. require stored `target_columns` when the selected model requires a target
6. load the dataset row
7. re-inspect the dataset source file through `DatasetService.inspect_source_file(...)`
8. validate that the persisted column selection still exists in the source file
9. validate model params through the registry's Pydantic model
10. derive evaluation policy from `problem_kind`
11. create one `FIT` task with an explicit continuation plan for `EVALUATE`
12. write `request.json`
13. enqueue the task

`tune_with_evaluate(...)` validation algorithm:

1. perform the same work-item and dataset-state resolution as above
2. validate one param grid through the registry's grid schema
3. derive evaluation policy from `problem_kind`
4. create one `HYPERPARAMETER_TUNING` task with an explicit continuation plan for `EVALUATE`
5. write `request.json`
6. enqueue the task

Bulk tuning UI algorithm:

1. collect selected model/grid pairs
2. validate each pair independently
3. create one tuning task per pair
4. enqueue them in UI submission order

Implementation note:

- issue `#72` should consume the persisted feature/target selection from `WorkItem`
- the first delivery does not need user-editable columns inside the training workspace

## Step 3: Introduce The Execution Manager

Files:

- `src/xenix/services/ml/execution.py`
- `src/xenix/services/ml/worker_main.py`

`MLExecutionManager` responsibilities:

- keep an in-memory FIFO queue of `ml_task_id`
- start one dispatcher thread lazily on first submit
- launch at most one worker process at a time
- delegate one task at a time to `MLTaskExecutor`

`MLTaskExecutor` responsibilities:

- mark tasks `RUNNING` before worker execution
- validate worker outputs after exit
- register task-owned artifacts
- canonicalize produced model artifacts when required
- persist `TrainedModelRow` when required
- ask `MLService` to materialize explicit continuation tasks when required
- fail tasks cleanly on missing files, invalid schema, or worker failure

Pseudo-code:

```python
class MLExecutionManager:
    def submit(self, ml_task_id: str) -> None:
        self._queue.put(ml_task_id)
        self._ensure_dispatcher()

    def _dispatch_loop(self) -> None:
        while True:
            ml_task_id = self._queue.get()
            self._executor.execute(ml_task_id)
```

Implementation rule:

- use `multiprocessing.get_context("spawn")`
- keep the worker target as a top-level importable function so it works in both dev runs and PyInstaller builds
- initialize `freeze_support()` in the packaged bootstrap path if needed

## Step 4: Keep Evaluation Atomic And Workflow-Chained

Acceptance requires evaluation as an independent atomic ML operation after `fit`.

Implementation rule:

- each persisted `MLTask` represents one model and one operation
- only tasks created by explicit workflow methods carry continuation intent for `EVALUATE`
- evaluation does not run inside the fit or tuning worker

Worker algorithm for manual training:

1. load `request.json`
2. copy dataset source into `input/`
3. load normalized dataframe from the copied file
4. build estimator
5. split once into training and holdout partitions
6. run `fit` on the training partition only
7. persist task-local model artifact
8. persist the holdout partition as a task-owned artifact
9. write `result.json`

Worker algorithm for tuning:

1. load `request.json`
2. copy dataset source into `input/`
3. split once into training and holdout partitions
4. run tuning search on the training partition only
5. fit the winning estimator on the training partition
6. persist the best artifact for that model
7. persist the holdout partition as a task-owned artifact
8. write `result.json`

Explicit workflow continuation algorithm after successful fit or tuning finalization:

1. persist the canonical model artifact
2. create one `TrainedModelRow`
3. materialize one `EVALUATE` task referencing that trained model and the predecessor task's holdout artifact
4. write its `request.json`
5. enqueue it

Worker algorithm for evaluation:

1. load `request.json`
2. load the persisted model artifact referenced by `trained_model_id`
3. load the holdout artifact referenced from the predecessor task
4. evaluate on the held-out partition only
5. write `result.json`

## Step 5: Execution Finalization

Files:

- `src/xenix/services/ml/execution.py`
- `src/xenix/services/storage/repositories/trained_models.py`
- `src/xenix/services/storage/layout.py`

Execution finalization algorithm:

1. read and validate `result.json`
2. verify declared task-owned artifacts exist under the task directory
3. prepare finalized task-artifact inputs
4. if the task is `FIT` or `HYPERPARAMETER_TUNING`, canonicalize the model artifact and create one `TrainedModelRow`
5. if the task is `FIT` or `HYPERPARAMETER_TUNING` and its continuation plan requests evaluation, ask `MLService` to create the follow-up `EVALUATE` task
6. if the task is `EVALUATE`, compare the evaluated trained model against `work_item.best_trained_model_id`
7. if the task is `EVALUATE`, update `best_trained_model_id` only when the policies are comparable and the new candidate is better
8. write a concise result snapshot to `MLTaskRow.result_payload`
9. call `complete_ml_task(...)` once with the finalized artifact list and result payload

Failure path:

- if any ingestion step fails, call `fail_ml_task(...)`
- preserve `request.json`, `result.json`, and `logs.jsonl` for debugging

## Step 6: Add Service-Level Integration Tests Before UI

Tests:

- `tests/test_ml_service.py`
- `tests/test_ml_execution.py`

Coverage:

- request validation against stored work-item state
- workflow inputs derive dataset state from `WorkItem`
- queue order and single-worker execution
- worker-process result ingestion
- canonical model copy
- explicit workflow evaluation-task chaining
- best-model update rules
- bulk tuning fan-out
- incompatible policy no-op on best-model replacement
- task failure on invalid result contract
