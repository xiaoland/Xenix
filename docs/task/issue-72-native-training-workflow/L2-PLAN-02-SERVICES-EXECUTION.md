# L2 Plan 02: Services And Execution

## Public Service Boundary

Issue `#72` should introduce `src/xenix/services/ml_service.py` as the main UI-facing boundary.

`MLService` should own:

- dataset inspection
- model catalog lookup
- request validation
- task submission
- task queue management
- worker result ingestion
- trained-model persistence
- best-model updates

`MLTaskService` remains the lifecycle and artifact persistence helper, not the main feature entry point.

## `MLService` API

The public API should be:

- `inspect_dataset(input_data: InspectDatasetInput) -> DatasetInspection`
- `list_models() -> list[ModelCatalogEntry]`
- `get_model(model_key: str) -> ModelCatalogEntry`
- `submit_manual_training(input_data: SubmitManualTrainingInput) -> MLTaskRow`
- `submit_hyperparameter_tuning(input_data: SubmitHyperparameterTuningInput) -> MLTaskRow`
- `list_work_item_tasks(work_item_id: str) -> list[MLTaskSummary]`
- `get_task_details(ml_task_id: str) -> MLTaskDetails`
- `list_trained_models(work_item_id: str) -> list[TrainedModelRow]`

## Input Models

`SubmitManualTrainingInput` fields:

- `project_id: str`
- `work_item_id: str`
- `dataset_id: str`
- `feature_columns: list[str]`
- `target_columns: list[str]`
- `model_key: str`
- `params: dict[str, Any]`

`SubmitHyperparameterTuningInput` fields:

- `project_id: str`
- `work_item_id: str`
- `dataset_id: str`
- `feature_columns: list[str]`
- `target_columns: list[str]`
- `models: list[TuningModelSelection]`

`TuningModelSelection` fields:

- `model_key: str`
- `param_grid: dict[str, list[Any]]`

Validation rules:

- all selected models must belong to the same `problem_kind`
- supervised models require `target_columns`
- targetless models require `target_columns == []`
- every selected feature/target column must exist in the inspected dataset
- params and param grids must validate through the registry's Pydantic models

## Queue Design

V1 execution should use a single service-owned queue with one active worker at a time.

Components:

- `MLExecutionManager`
  - holds an in-memory queue of `ml_task_id`
  - runs one dispatcher thread
  - launches one worker subprocess at a time

Why sequential in v1:

- the issue requires queue states, not parallel execution
- it keeps task lifecycle reasoning simple
- it avoids concurrent best-model updates racing against the same work item
- it keeps the first implementation easier to review and test

## Task Submission Algorithm

Manual training submission:

1. inspect dataset source file
2. validate feature/target columns
3. load model definition
4. validate params through the model's Pydantic `Params` model
5. derive evaluation policy from `problem_kind`
6. create `MLTaskRow` with:
   - `task_type = FIT`
   - `status = PENDING`
   - `request_payload = SubmitManualTrainingInput.model_dump()`
7. write `request.json`
8. enqueue the task id
9. return the created task row immediately

Tuning submission:

1. inspect dataset source file
2. validate feature/target columns
3. validate every selected model and `param_grid`
4. derive one shared evaluation policy from the common `problem_kind`
5. create `MLTaskRow` with:
   - `task_type = HYPERPARAMETER_TUNING`
   - `status = PENDING`
   - `request_payload = SubmitHyperparameterTuningInput.model_dump()`
6. write `request.json`
7. enqueue the task id
8. return the created task row immediately

## Worker Launch Contract

The dispatcher launches:

```text
python -m xenix.services.ml.worker_main --task-dir <absolute-task-dir>
```

Worker launch steps:

1. load `request.json`
2. transition task to `RUNNING`
3. copy the dataset into `input/`
4. invoke the appropriate ML model service(s)
5. write `logs.jsonl`
6. write `result.json`
7. exit with code `0` or non-zero

The worker does not write SQLite.

## Result Ingestion Algorithm

After worker exit, the dispatcher:

1. reads `result.json`
2. validates it with `MLWorkerTaskResult`
3. validates that every declared task artifact exists
4. copies winning task artifacts into `artifacts/models/<work-item-id>/`
5. creates one `TrainedModelRow` per persisted trained model
6. computes whether `work_item.best_trained_model_id` should be updated
7. writes a concise `result_payload` snapshot into `MLTaskRow`
8. calls `complete_ml_task()` or `fail_ml_task()`

Failure conditions:

- missing result file
- invalid result schema
- declared artifact missing
- canonical model copy failure
- trained-model persistence failure

Any of those should fail the task and preserve logs/result files for debugging.

## Result Persistence Rule

Manual training persists:

- exactly one `TrainedModelRow`

Hyperparameter tuning persists:

- one `TrainedModelRow` for the best fitted result of each selected model
- one task winner across those persisted models

This avoids storing every grid-search candidate while still preserving the useful tuned outcomes.

## Best-Model Update Algorithm

When a task succeeds:

1. determine the task winner under the task's evaluation policy
2. load the current work-item best model if one exists
3. if no current best exists, set the new winner
4. if the current best shares the same `evaluation_policy_key`, compare primary metric values
5. if the new winner is better, update `best_trained_model_id`
6. if the policies are not comparable, leave the current best unchanged and record that decision in `result_payload`

## Service Detail Models

`MLTaskSummary` should expose:

- task id
- task type
- status
- created/start/finish timestamps
- winner model key if available
- primary metric summary if available
- error summary if failed

`MLTaskDetails` should extend that with:

- request snapshot
- result summary
- persisted trained-model ids
- recent parsed log entries
- task artifact paths
