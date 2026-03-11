# L2 Plan 01: Domain And Storage

## Domain Objects

The implementation should introduce the following domain-level objects.

Persisted objects:

- `Project`
- `WorkItem`
- `Dataset`
- `MLTask`
- `MLTaskArtifact`
- `TrainedModel`

Ephemeral objects:

- `DatasetInspection`
- `DatasetColumnMetadata`
- `ManualTrainRequest`
- `HyperparameterTuningRequest`
- `EvaluateModelRequest`
- `EvaluationSnapshot`
- `TaskContinuationPlan`
- `TaskRequestBase`
- `FitTaskRequest`
- `HyperparameterTuningTaskRequest`
- `EvaluateTaskRequest`
- `TaskResultBase`
- `FitTaskResult`
- `HyperparameterTuningTaskResult`
- `EvaluateTaskResult`

## Schema Version 3

`CURRENT_SCHEMA_VERSION` should become `3`.

### `work_item` changes

Add:

- `best_trained_model_id: str | None`

Storage rule:

- this field records the current best model for the work item
- it is nullable
- it should use a foreign key to `trained_model.id`

Service rule:

- only `MLService` updates this field
- the service validates that the referenced trained model belongs to the same work item before persisting

### New `trained_model` table

Add table `trained_model` with these columns:

- `id: str` primary key
- `work_item_id: str` foreign key to `work_item.id`, indexed
- `ml_task_id: str` foreign key to `ml_task.id`, indexed, unique
- `model_key: str`, indexed
- `artifact_path: str`
- `created_at: datetime`
- `updated_at: datetime`

Field intent:

- `trained_model` is the durable pointer to one canonical fitted-model artifact
- `model_key` stays on the row so trained-model listings and best-model references have a stable model identity without decoding task JSON each time
- model family, params, feature columns, target columns, evaluation policy, and metrics are read from the linked `MLTask` payloads rather than duplicated here
- `artifact_path` points to the canonical persisted model artifact under `artifacts/models/`

Rationale:

- `problem_kind` belongs to model metadata and evaluation policy, not to a duplicated row column
- training mode can be derived from `MLTask.task_type`
- feature columns, target columns, params, and metrics already have a better ownership boundary in task request/result payloads

## Row Models

Concrete SQLModel additions in `src/xenix/services/storage/models.py`:

- new enum `ProblemKind(StrEnum)`:
  - `REGRESSION = "regression"`
  - `CLASSIFICATION = "classification"`
  - `UNSUPERVISED = "unsupervised"`
- `WorkItemRow.best_trained_model_id`
- new `TrainedModelRow`

`MLTaskType` should remain:

- `FIT`
- `HYPERPARAMETER_TUNING`
- `EVALUATE`

Evaluation is a distinct atomic ML operation and should be represented by a persisted `MLTaskType` in v1.

## Repository Additions

Add `src/xenix/services/storage/repositories/trained_models.py` with methods:

- `create(session, row) -> TrainedModelRow`
- `get(session, trained_model_id) -> TrainedModelRow | None`
- `list_by_work_item(session, work_item_id) -> list[TrainedModelRow]`
- `get_by_ml_task(session, ml_task_id) -> TrainedModelRow | None`

Extend `WorkItemRepository` with:

- `set_best_trained_model(session, work_item_id, trained_model_id, now) -> WorkItemRow | None`

## Filesystem Layout

Canonical runtime layout for issue `#72`:

- `artifacts/ml-tasks/<ml-task-id>/`
  - `request.json`
  - `result.json`
  - `logs.jsonl`
  - `input/`
    - task-local dataset copy
  - `models/`
    - task-produced model artifacts
- `artifacts/models/<work-item-id>/`
  - canonical persisted model files

Notes:

- task-local dataset copies live only under the task directory
- task-local model files are execution artifacts
- canonical model files are the product-owned artifacts referenced by `trained_model.artifact_path`

## Layout API Changes

Change `src/xenix/services/storage/layout.py` as follows:

- remove:
  - `dataset_temp_root()`
  - `dataset_temp_dir()`
- keep:
  - `database_path()`
  - `artifact_models_root()`
  - `artifact_training_root()` for now, even if unused
  - `artifact_inference_root()`
  - `ml_task_parent_root()`
  - `ml_task_root()`
  - `task_artifact_dir()`
- add:
  - `task_input_dir(paths, ml_task_id) -> Path`
  - `task_models_dir(paths, ml_task_id) -> Path`
  - `task_request_path(paths, ml_task_id) -> Path`
  - `task_result_path(paths, ml_task_id) -> Path`
  - `task_logs_path(paths, ml_task_id) -> Path`
  - `canonical_model_dir(paths, work_item_id) -> Path`

## Dataset Copy Design

Remove the shared app-managed dataset-copy area from the ML workflow.

Implications:

- `DatasetService.materialize_read_copy()` should be removed
- task execution gets a dedicated helper:
  - `copy_dataset_to_task_input(paths, ml_task_id, dataset_row) -> Path`

This helper should:

- create `artifacts/ml-tasks/<id>/input/`
- copy the dataset source file into that directory
- preserve the original suffix
- return the copied absolute path

## Migration Algorithm

Migration `v2 -> v3` should be implemented manually in `src/xenix/services/storage/migrations.py`.

Algorithm:

1. open a transaction
2. disable foreign key enforcement temporarily
3. create `trained_model`
4. create `work_item_v3` with the new `best_trained_model_id` column while preserving:
   - `dataset_id`
   - `feature_columns`
   - `target_columns`
5. copy all old `work_item` rows into `work_item_v3` with `best_trained_model_id = NULL`
6. drop old `work_item`
7. rename `work_item_v3` to `work_item`
8. recreate indexes
9. re-enable foreign key enforcement
10. set `PRAGMA user_version=3`

Migration guarantees:

- no dataset, task, or artifact rows are lost
- existing work items start with `best_trained_model_id = NULL`
- no dataset inspection metadata is introduced into SQLite
- trained-model metadata duplication is intentionally avoided
