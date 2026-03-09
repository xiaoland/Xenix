# L2 Plan

## Stage Goal

Define the concrete low-level design for issue `#70`: package layout, table models, request/result models, repository and service interfaces, runtime path rules, and the core storage algorithms.

## Design Principles Locked for L2

- Keep the foundational persisted domain intentionally small.
- Use `SQLModel` for table models and typed persistence mapping.
- Keep static model-definition metadata out of SQLite.
- Keep dataset-derived metadata out of SQLite.
- Keep temporary dataset copies out of SQLite.
- Use `ML task` consistently as the persistent task abstraction.

## Proposed Package Layout

```text
src/xenix/
  config.py
  services/
    __init__.py
    project_service.py
    work_item_service.py
    dataset_service.py
    ml_task_service.py
    ml/
      __init__.py
      registry.py
      types.py
    storage/
      __init__.py
      layout.py
      database.py
      migrations.py
      models.py
      repositories/
        __init__.py
        projects.py
        work_items.py
        datasets.py
        ml_tasks.py
```

Rationale:

- `services/ml/` is the native business-logic location for ML-facing code.
- `ml/` at repo root remains legacy script territory and is not treated as the native service package.
- `storage/models.py` stays single-file in version `1` because the schema is still small.
- repositories are split by aggregate to avoid one large persistence file.

## Runtime Path Design

### `AppPaths` changes

Extend `AppPaths` with these new top-level directories:

- `state`
- `temp`
- `artifacts`

Keep detailed subpaths out of `config.py`. Those belong in `services/storage/layout.py`.

### Storage layout helpers

`services/storage/layout.py` should define functions, not constants embedded across the codebase:

- `database_path(paths: AppPaths) -> Path`
- `dataset_temp_root(paths: AppPaths) -> Path`
- `dataset_temp_dir(paths: AppPaths, owner_id: str) -> Path`
- `artifact_models_root(paths: AppPaths) -> Path`
- `artifact_training_root(paths: AppPaths) -> Path`
- `artifact_inference_root(paths: AppPaths) -> Path`
- `ml_task_root(paths: AppPaths, ml_task_id: str) -> Path`
- `task_artifact_dir(paths: AppPaths, ml_task_id: str, family: str) -> Path`

Concrete runtime layout:

```text
XENIX_APP_HOME/
  config/
  logs/
  cache/
  state/
    xenix.db
  temp/
    datasets/
      <owner-id>/
  artifacts/
    models/
    training/
    inference/
    ml-tasks/
      <ml-task-id>/
```

## Enumerations

Use Python `StrEnum` for persisted categorical fields.

### `MLTaskType`

- `inspect_dataset`
- `fit`
- `hyperparameter_tuning`
- `inference`

### `MLTaskStatus`

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`

### `DatasetSourceFormat`

- `csv`
- `xlsx`
- `xls`
- `unknown`

### `MLTaskArtifactKind`

- `model`
- `training_report`
- `inference_result`
- `export_file`
- `other`

## Persistence Model Design

All timestamps are stored in UTC.

All aggregate identifiers use `str` ids generated from `uuid.uuid4().hex`.

Reasoning:

- task ids become easy to use in temp/artifact directory names
- ids remain stable across UI and future subprocess boundaries
- this avoids exposing SQLite rowid semantics as application identity

### `ProjectRow`

Purpose:

- top-level local workspace container

Fields:

- `id: str`
  - primary key
- `name: str`
  - indexed
- `description: str | None`
- `created_at: datetime`
- `updated_at: datetime`

Constraints:

- no uniqueness on `name` in version `1`

### `WorkItemRow`

Purpose:

- scoped work unit within a project

Fields:

- `id: str`
  - primary key
- `project_id: str`
  - foreign key to `project.id`
  - indexed
- `name: str`
  - indexed
- `description: str | None`
- `created_at: datetime`
- `updated_at: datetime`

Constraints:

- work item must belong to a project
- no uniqueness on `name` in version `1`

### `DatasetRow`

Purpose:

- durable reference to an external user-managed dataset file

Fields:

- `id: str`
  - primary key
- `project_id: str`
  - foreign key to `project.id`
  - indexed
- `name: str`
  - user-facing nickname
  - indexed
- `source_path: str`
  - absolute external path
- `source_format: DatasetSourceFormat`
- `created_at: datetime`
- `updated_at: datetime`

Explicitly omitted from version `1`:

- file size
- last modified time
- detected columns
- row count
- inferred dtypes
- profile/statistics

Those are runtime-derived, not canonical persisted metadata.

### `MLTaskRow`

Purpose:

- canonical persistent record for background ML-related work

Fields:

- `id: str`
  - primary key
- `project_id: str`
  - foreign key to `project.id`
  - indexed
- `work_item_id: str`
  - foreign key to `work_item.id`
  - indexed
- `dataset_id: str | None`
  - foreign key to `dataset.id`
  - indexed
- `task_type: MLTaskType`
  - indexed
- `status: MLTaskStatus`
  - indexed
- `request_payload: dict[str, Any]`
  - JSON column
  - default `{}`
- `result_payload: dict[str, Any] | None`
  - JSON column
- `error_summary: str | None`
- `created_at: datetime`
- `started_at: datetime | None`
- `finished_at: datetime | None`
- `updated_at: datetime`

Design note:

- `request_payload` and `result_payload` are intentionally generic in `#70`
- `#72` and `#73` can later validate richer ML-operation-specific shapes in `services/ml/types.py` without reshaping the foundational table

### `MLTaskArtifactRow`

Purpose:

- persistent file-reference records for ML task outputs without introducing a full model catalog yet

Fields:

- `id: str`
  - primary key
- `ml_task_id: str`
  - foreign key to `ml_task.id`
  - indexed
- `artifact_kind: MLTaskArtifactKind`
  - indexed
- `absolute_path: str`
- `ready_to_open: bool`
- `created_at: datetime`

Reason this table exists in `#70`:

- the task lifecycle contract already requires structured result-file metadata
- this avoids hiding file references inside opaque JSON blobs
- it supports `#72` and `#73` without forcing a trained-model table too early
- it fits the future model where each ML task has its own working directory with large outputs

## ORM Relationship Policy

Use foreign keys but avoid SQLModel relationship loading in version `1`.

Reason:

- repository methods remain explicit
- query behavior stays predictable
- there is no need for lazy/eager-loading complexity in this issue

So `models.py` should define:

- foreign keys
- indexes
- JSON columns

But repositories should perform explicit queries instead of depending on ORM relationship traversal.

## Service DTO Design

Use non-table `SQLModel` or Pydantic-compatible models in `services/` and `services/ml/types.py`.

### Core DTOs

- `CreateProjectInput`
- `CreateWorkItemInput`
- `RegisterDatasetInput`
- `RenameDatasetInput`
- `CreateMLTaskInput`
- `StartMLTaskInput`
- `CompleteMLTaskInput`
- `FailMLTaskInput`
- `CancelMLTaskInput`
- `MLTaskArtifactInput`
- `MaterializeDatasetCopyInput`
- `MaterializedDatasetCopy`

### DTO responsibilities

- validate service boundaries
- keep UI from constructing persistence rows directly
- keep operation-specific payload validation out of raw dictionaries at the service boundary

### `MaterializedDatasetCopy`

This should be a small service-owned handle, not a persisted model.

Fields:

- `dataset_id: str`
- `owner_id: str`
- `source_path: Path`
- `copied_path: Path`

Methods:

- `cleanup() -> None`
- context-manager support for automatic cleanup

## Repository Interface Design

Repositories should accept a `Session` created by the service layer.

### `ProjectRepository`

- `create(session, row: ProjectRow) -> ProjectRow`
- `get(session, project_id: str) -> ProjectRow | None`
- `list_all(session) -> list[ProjectRow]`

### `WorkItemRepository`

- `create(session, row: WorkItemRow) -> WorkItemRow`
- `get(session, work_item_id: str) -> WorkItemRow | None`
- `list_by_project(session, project_id: str) -> list[WorkItemRow]`

### `DatasetRepository`

- `create(session, row: DatasetRow) -> DatasetRow`
- `get(session, dataset_id: str) -> DatasetRow | None`
- `list_by_project(session, project_id: str) -> list[DatasetRow]`
- `rename(session, dataset_id: str, new_name: str, now: datetime) -> DatasetRow | None`

### `MLTaskRepository`

- `create(session, row: MLTaskRow) -> MLTaskRow`
- `get(session, ml_task_id: str) -> MLTaskRow | None`
- `list_by_work_item(session, work_item_id: str) -> list[MLTaskRow]`
- `update_status(session, ml_task_id: str, from_status: MLTaskStatus, to_status: MLTaskStatus, now: datetime) -> MLTaskRow | None`
- `complete(session, ml_task_id: str, result_payload: dict[str, Any], finished_at: datetime, artifacts: list[MLTaskArtifactRow]) -> MLTaskRow | None`
- `fail(session, ml_task_id: str, error_summary: str, finished_at: datetime) -> MLTaskRow | None`
- `cancel(session, ml_task_id: str, finished_at: datetime) -> MLTaskRow | None`

Implementation note:

- repository methods stay thin
- status transition legality should be checked by the service before repository mutation

## Service Interface Design

### `StorageBootstrapService`

Responsibilities:

- ensure runtime directories exist
- create engine/session factory
- run schema bootstrap/migrations

Methods:

- `initialize(paths: AppPaths) -> StorageContext`

`StorageContext` fields:

- `paths: AppPaths`
- `engine: Engine`
- `session_factory: sessionmaker[Session]`
- `schema_version: int`

### `ProjectService`

- `create_project(input: CreateProjectInput) -> ProjectRow`
- `list_projects() -> list[ProjectRow]`
- `get_project(project_id: str) -> ProjectRow`

### `WorkItemService`

- `create_work_item(input: CreateWorkItemInput) -> WorkItemRow`
- `list_work_items(project_id: str) -> list[WorkItemRow]`
- `get_work_item(work_item_id: str) -> WorkItemRow`

### `DatasetService`

- `register_dataset(input: RegisterDatasetInput) -> DatasetRow`
- `rename_dataset(input: RenameDatasetInput) -> DatasetRow`
- `list_datasets(project_id: str) -> list[DatasetRow]`
- `get_dataset(dataset_id: str) -> DatasetRow`
- `materialize_read_copy(input: MaterializeDatasetCopyInput) -> MaterializedDatasetCopy`

### `MLTaskService`

- `create_ml_task(input: CreateMLTaskInput) -> MLTaskRow`
- `start_ml_task(input: StartMLTaskInput) -> MLTaskRow`
- `complete_ml_task(input: CompleteMLTaskInput) -> MLTaskRow`
- `fail_ml_task(input: FailMLTaskInput) -> MLTaskRow`
- `cancel_ml_task(input: CancelMLTaskInput) -> MLTaskRow`
- `list_ml_tasks(work_item_id: str) -> list[MLTaskRow]`
- `get_ml_task(ml_task_id: str) -> MLTaskRow`

## ML Registry Interface Design

The native registry lives under `src/xenix/services/ml/`.

### `registry.py`

Responsibilities:

- list available model keys
- return parameter schema classes for a model key
- return operation support metadata for a model key

Suggested interfaces:

- `list_model_keys() -> list[str]`
- `get_model_definition(model_key: str) -> ModelDefinition`
- `list_model_definitions() -> list[ModelDefinition]`

### `ModelDefinition`

Fields:

- `model_key: str`
- `family: str`
- `display_name: str`
- `supports_fit: bool`
- `supports_hyperparameter_tuning: bool`
- `supports_inference: bool`
- `param_model: type[BaseModelLike]`
- `param_grid_model: type[BaseModelLike] | None`

Persistence rule:

- none of this is stored in SQLite in `#70`

## ML Task Process Boundary

Even though the ML workflow itself is deferred, `#70` should design for this execution model:

- each ML task runs in a standalone process
- each ML task process has a standalone working directory at `artifacts/ml-tasks/<ml-task-id>/`
- large result files and artifacts may be written inside that working directory
- per-task process logs may be written inside that working directory
- the main process remains responsible for canonical ML task state persistence in SQLite

Logging reconciliation:

- per-task detailed logs may live in `artifacts/ml-tasks/<ml-task-id>/`
- the canonical application log contract remains under `paths.logs`
- the main process should mirror user-relevant start/failure/completion summaries into the canonical application log

## Migration and Bootstrap Algorithm

### Engine creation

`database.py` should expose:

- `create_engine_for_path(db_path: Path) -> Engine`
- `create_session_factory(engine: Engine) -> sessionmaker[Session]`

### Migration registry

`migrations.py` should expose:

- `CURRENT_SCHEMA_VERSION = 1`
- `run_migrations(engine: Engine) -> int`

Internal helpers:

- `get_user_version(engine: Engine) -> int`
- `set_user_version(engine: Engine, version: int) -> None`
- `apply_v1(engine: Engine) -> None`

Algorithm:

1. Read current `user_version`.
2. If version is `0`, run `apply_v1()`.
3. `apply_v1()` calls `SQLModel.metadata.create_all(engine)`.
4. Set `user_version` to `1`.
5. Return final version.

Note:

- the only unavoidable direct SQL text in version `1` should be the `PRAGMA user_version` read/write
- business queries remain SQLModel-based

## Dataset Temporary Copy Algorithm

Implement in `DatasetService.materialize_read_copy()`.

Inputs:

- `dataset_id`
- `owner_id`
  - usually the ML task id
  - if absent, generate an ephemeral request id

Algorithm:

1. Load dataset row.
2. Validate that `source_path` exists and is a file.
3. Resolve owner temp directory as `temp/datasets/<owner_id>/`.
4. Create the owner temp directory.
5. Copy the external file using `shutil.copy2()` to preserve filesystem metadata where possible.
6. Return a `MaterializedDatasetCopy` handle pointing to the copied file.
7. On `cleanup()`:
   - remove the copied file if it exists
   - remove the owner directory if it becomes empty
   - ignore best-effort cleanup race conditions safely

Failure behavior:

- if the external source file is missing, raise a service-layer domain error
- no partial persisted state is written for the temp copy

## ML Task State Transition Algorithm

Service layer owns transition legality.

Allowed transitions:

- `pending -> running`
- `running -> succeeded`
- `running -> failed`
- `pending -> cancelled`
- `running -> cancelled`

Algorithm:

### Create ML task

1. Validate referenced project/work item exist.
2. Validate dataset exists if `dataset_id` is provided.
3. Persist a new `MLTaskRow` with:
   - `status=pending`
   - `request_payload`
   - `created_at`
   - `updated_at`

### Start ML task

1. Load task.
2. Require current status `pending`.
3. Set `status=running`.
4. Set `started_at` if empty.
5. Update `updated_at`.

### Complete ML task

1. Load task.
2. Require current status `running`.
3. Validate every declared artifact path exists.
4. Persist:
   - `status=succeeded`
   - `result_payload`
   - artifact rows
   - `finished_at`
   - `updated_at`
5. Commit in one transaction.

### Fail ML task

1. Load task.
2. Require current status `running`.
3. Persist:
   - `status=failed`
   - `error_summary`
   - `finished_at`
   - `updated_at`

### Cancel ML task

1. Load task.
2. Require current status `pending` or `running`.
3. Persist:
   - `status=cancelled`
   - `finished_at`
   - `updated_at`

## Validation Rules

### Project and work item

- names must be non-empty after trimming

### Dataset registration

- source path must be absolute
- source path must exist at registration time
- allowed source formats in version `1` are `.csv`, `.xlsx`, `.xls`
- dataset name defaults to file stem if omitted

### ML task creation

- `task_type` must be a valid enum value
- `request_payload` must be a dictionary
- `dataset_id` is optional in the schema but may be required by later task-specific service validation

## Error Model

Define small domain exceptions under `src/xenix/exceptions.py` or a new service-local exception module.

Suggested errors:

- `NotFoundError`
- `ValidationError`
- `InvalidStateTransitionError`
- `DatasetSourceMissingError`
- `StorageBootstrapError`

These should carry short, UI-safe messages.

## Test Design Boundaries for the Later Implementation Stage

The implementation derived from this L2 should test:

- runtime path bootstrap includes new directories
- schema bootstrap creates all tables and sets `user_version=1`
- repository CRUD for project/work item/dataset/ML task
- ML task transition legality
- dataset temp-copy creation and cleanup
- artifact-record persistence on ML task completion

## Deferred Design Explicitly Left for `#72` and `#73`

- detailed training payload schemas
- best-model selection rules
- trained-model artifact semantics beyond generic artifact rows
- inference-result summary schema
- subprocess protocol between native services and the ML runner

These are intentionally deferred so `#70` does not over-model follow-up workflows.

## Approval Gate to Enter L3

L3 should assume this concrete design:

- one SQLModel schema file with five table models in version `1`
- top-level services plus a dedicated `services/ml/` package
- dataset temp copies managed via a context-like service handle
- ML task state transitions validated in services and persisted transactionally
- generic JSON payload columns plus explicit artifact rows

If approved, the next step is to turn this design into an implementation roadmap with file-by-file steps, pseudo-code, and a concrete test plan.
