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
- `MLTaskService` owns atomic task queueing, dispatch, lifecycle transitions, and task-artifact registration
- `MLWorkerRunner` is a pure process helper with no ML task or workflow semantics

That split avoids duplicating issue `#75` logic while keeping execution concerns out of the UI-facing service.

## `MLService` Construction

`MLService` should compose:

- session factory
- `AppPaths`
- `DatasetService`
- `WorkItemService`
- `MLTaskService`
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
- `src/xenix/services/ml/operations/`

`MLTaskService` responsibilities:

- keep an in-memory FIFO queue of `ml_task_id`
- start one dispatcher thread lazily on first submit
- launch at most one worker process at a time
- invoke `MLWorkerRunner`
- validate worker outputs by task type
- complete or fail atomic tasks
- register task-scoped artifacts
- persist atomic-task products such as `TrainedModelRow` when required

`MLWorkerRunner` responsibilities:

- spawn the worker process
- target the already-resolved operation entrypoint
- point it at the task directory
- wait for exit code
- return process outcome only

Pseudo-code:

```python
class MLTaskService:
    def submit(self, ml_task_id: str) -> None:
        self._queue.put(ml_task_id)
        self._ensure_dispatcher()

    def _dispatch_loop(self) -> None:
        while True:
            task = self._load_next_task()
            returncode = self._worker_runner.run(task)
            self._finalize_task(task, returncode)
```

Implementation rule:

- use `multiprocessing.get_context("spawn")`
- keep each operation entrypoint as a top-level importable function so it works in both dev runs and PyInstaller builds
- initialize `freeze_support()` in the packaged bootstrap path if needed
- avoid an extra route/dispatch layer inside the worker process once `MLTaskType` is already known in the parent process

## Step 4: Keep Evaluation Atomic And Workflow-Chained

Acceptance requires evaluation as an independent atomic ML operation after `fit`.

Implementation rule:

- each persisted `MLTask` represents one model and one operation
- only tasks created by explicit workflow methods carry continuation intent for `EVALUATE`
- evaluation does not run inside the fit or tuning worker

Worker algorithm for manual training:

1. operation entrypoint loads `request.json`
2. copy dataset source into `input/`
3. load normalized dataframe from the copied file
4. build estimator
5. split once into training and holdout partitions
6. run `fit` on the training partition only
7. persist task-local model artifact
8. persist the holdout partition as a task-owned artifact
9. write `result.json`

Worker algorithm for tuning:

1. operation entrypoint loads `request.json`
2. copy dataset source into `input/`
3. split once into training and holdout partitions
4. run tuning search on the training partition only
5. fit the winning estimator on the training partition
6. persist the best artifact for that model
7. persist the holdout partition as a task-owned artifact
8. write `result.json`

Explicit workflow continuation algorithm after successful fit or tuning finalization:

1. `MLTaskService` persists the canonical model artifact
2. `MLTaskService` creates one `TrainedModelRow`
3. `MLService` observes the successful atomic task and materializes one `EVALUATE` task referencing that trained model and the predecessor task's holdout artifact
4. `MLService` writes its `request.json`
5. `MLTaskService` enqueues it

Worker algorithm for evaluation:

1. operation entrypoint loads `request.json`
2. load the persisted model artifact referenced by `trained_model_id`
3. load the holdout artifact referenced from the predecessor task
4. evaluate on the held-out partition only
5. write `result.json`

## Step 5: Atomic Task Finalization

Files:

- `src/xenix/services/ml/execution.py`
- `src/xenix/services/storage/repositories/trained_models.py`
- `src/xenix/services/storage/layout.py`

`FIT` task finalization algorithm in `MLTaskService`:

1. read and validate `FitTaskResult`
2. verify fit-task-owned artifacts
3. canonicalize the produced model artifact
4. create one `TrainedModelRow`
5. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
6. notify `MLService` so the workflow layer can decide whether to request `EVALUATE`

`HYPERPARAMETER_TUNING` task finalization algorithm in `MLTaskService`:

1. read and validate `HyperparameterTuningTaskResult`
2. verify tuning-task-owned artifacts
3. canonicalize the produced model artifact
4. create one `TrainedModelRow`
5. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
6. notify `MLService` so the workflow layer can decide whether to request `EVALUATE`

`EVALUATE` task finalization algorithm in `MLTaskService`:

1. read and validate `EvaluateTaskResult`
2. verify evaluation-task-owned artifacts
3. call `complete_ml_task(...)` once with finalized artifact inputs and result payload
4. notify `MLService` so the workflow layer can decide whether to update `work_item.best_trained_model_id`

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
