# L3 Plan 01: Storage And Contracts

## Step 1: Advance Storage To `v3`

Files:

- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/storage/repositories/work_items.py`
- `src/xenix/services/storage/repositories/trained_models.py`
- `src/xenix/services/storage/repositories/__init__.py`

Changes:

- add `ProblemKind`
- add `TrainedModelRow`
- extend `WorkItemRow` with `best_trained_model_id`
- add `TrainedModelRepository`
- extend `WorkItemRepository` with `set_best_trained_model(...)`

Non-goals:

- do not change the existing `DatasetRow` ownership model
- do not move dataset inspection metadata into SQLite
- do not split evaluation into a second persisted task table in v1
- do not duplicate task-owned training metadata onto `trained_model`

## `models.py` Target Shape

`WorkItemRow` gains:

- `best_trained_model_id: str | None`

New `TrainedModelRow` fields:

- `id`
- `work_item_id`
- `ml_task_id`
- `model_key`
- `artifact_path`
- `created_at`
- `updated_at`

Implementation rule:

- keep `artifact_path` as an absolute canonical artifact path, because the current storage layer already persists absolute paths for task artifacts
- keep `model_key` on `trained_model` so trained-model listings do not need to decode task JSON just to show model identity
- keep training metadata in `MLTask.request_payload` and `MLTask.result_payload` instead of duplicating it in `trained_model`

## Migration Algorithm: `v2 -> v3`

Files:

- `src/xenix/services/storage/migrations.py`

Implementation steps:

1. change `CURRENT_SCHEMA_VERSION` from `2` to `3`
2. add `apply_v3(engine)` for fresh databases
3. add `apply_v2_to_v3(engine)` for existing databases
4. update `run_migrations(engine)` to dispatch `0 -> 3`, `1 -> 2 -> 3`, and `2 -> 3`

`apply_v2_to_v3(engine)` pseudo-code:

```python
with engine.begin() as connection:
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    connection.exec_driver_sql("CREATE TABLE trained_model (...)")
    connection.exec_driver_sql("CREATE TABLE work_item_v3 (...)")
    connection.exec_driver_sql(
        """
        INSERT INTO work_item_v3 (...)
        SELECT ..., NULL AS best_trained_model_id
        FROM work_item
        """
    )
    connection.exec_driver_sql("DROP TABLE work_item")
    connection.exec_driver_sql("ALTER TABLE work_item_v3 RENAME TO work_item")
    connection.exec_driver_sql("CREATE INDEX ...")
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
set_user_version(engine, 3)
```

Migration guarantees:

- all existing issue `#75` data stays intact
- every existing work item starts with `best_trained_model_id = NULL`
- migration is deterministic for both fresh and upgraded app homes

## Step 2: Normalize Task Layout Helpers

Files:

- `src/xenix/services/storage/layout.py`
- `src/xenix/services/dataset_service.py`

Changes:

- add:
  - `task_input_dir(paths, ml_task_id)`
  - `task_models_dir(paths, ml_task_id)`
  - `task_request_path(paths, ml_task_id)`
  - `task_result_path(paths, ml_task_id)`
  - `task_logs_path(paths, ml_task_id)`
  - `canonical_model_dir(paths, work_item_id)`
- remove:
  - `dataset_temp_root()`
  - `dataset_temp_dir()`
  - `DatasetService.materialize_read_copy(...)`

Implementation note:

- if `dataset_temp_root()` is still referenced by older tests, remove those references in the same commit as the layout cleanup
- `DatasetService` should remain responsible for dataset registration and inspection only after this issue

## Step 3: Add Worker File Contracts

Files:

- `src/xenix/services/ml/contracts.py`

Contract categories:

- task request
- evaluation policy snapshot
- candidate result
- task result
- task log entry

Execution rule:

- SQLite remains the system of record for task lifecycle
- `request.json`, `result.json`, and `logs.jsonl` are worker-owned execution files under `artifacts/ml-tasks/<ml-task-id>/`

## Step 4: Add Persistence-Side Regression Tests First

Tests:

- `tests/test_migrations.py`
- `tests/test_repositories.py`

Required coverage:

- `v2 -> v3` migration preserves existing work-item dataset state
- `TrainedModelRepository` create/get/list behavior
- `WorkItemRepository.set_best_trained_model(...)`
- canonical artifact path persistence is stored exactly as written
- training metadata remains task-owned, not duplicated onto `trained_model`
