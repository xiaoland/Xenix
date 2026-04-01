# L2 Plan 01: Domain And Storage

## Domain Objects

Persisted objects:

- `Project`
- `Dataset`
- `WorkItem`
- `MLTask`
- `MLTaskArtifact`
- `TrainedModel`

Ephemeral objects:

- `DatasetInspection`
- `DatasetColumnMetadata`
- `InferWithFilesInput`
- `InferenceInputFile`
- `InferenceModelPayload`
- `InferenceTaskRequest`
- `InferenceSummary`
- `InferenceTaskResult`
- `ManualInferenceCsvInput`

## Schema Version 4

`CURRENT_SCHEMA_VERSION` should become `4`.

Issue `#73` changes core ownership rules enough that `v4` should describe the new invariant directly rather than carrying the older nullable work-item flow forward.

## `dataset` Table Changes

Extend `DatasetRow` with:

- `copied_from: str | None`
  - foreign key to `dataset.id`
  - indexed
- `copied_at: datetime | None`
- `ml_task_id: str | None`
  - foreign key to `ml_task.id`
  - indexed
  - unique for v1 inference output ownership

Existing fields remain:

- `project_id`
- `name`
- `source_path`
- `source_format`
- `created_at`
- `updated_at`

## Dataset Provenance Rules

The persisted meaning of a `dataset` row is derived from the new provenance fields.

### Source dataset

Rules:

- `copied_from is NULL`
- `ml_task_id is NULL`
- `source_path` points to the user-managed file

### Work-item-managed copied dataset

Rules:

- `copied_from is not NULL`
- `ml_task_id is NULL`
- `source_path` points to an app-managed copied file
- `copied_from` may reference either a source dataset or a generated dataset

### Generated inference-output dataset

Rules:

- `copied_from is NULL`
- `ml_task_id is not NULL`
- `source_path` points to the canonical app-managed inference output file

This avoids a new persisted enum while still making provenance queryable.

## `work_item` Table Changes

`WorkItemRow.dataset_id` should become non-nullable in `v4`.

Field intent:

- it points to the copied dataset row owned by the work item
- it is the stable dataset contract for both training and inference

Other work-item rules:

- `feature_columns` remains non-null JSON
- `target_columns` remains non-null JSON and may be empty
- `best_trained_model_id` remains nullable

## Row Models

Concrete SQLModel changes in `src/xenix/services/storage/models.py`:

- extend `DatasetRow` with:
  - `copied_from`
  - `copied_at`
  - `ml_task_id`
- change `WorkItemRow.dataset_id` from `str | None` to `str`
- keep `MLTaskType.INFERENCE`
- keep `MLTaskArtifactKind.INFERENCE_RESULT`
- keep `MLTaskArtifactKind.EXPORT_FILE` for explicit export copies if the app chooses to track them later

## Repository Additions

Extend `DatasetRepository` with:

- `get_by_ml_task(session, ml_task_id) -> DatasetRow | None`
- `list_source_by_project(session, project_id) -> list[DatasetRow]`
- `list_generated_by_project(session, project_id) -> list[DatasetRow]`
- `list_copies_by_source(session, source_dataset_id) -> list[DatasetRow]`

Query rules:

- `list_source_by_project(...)` filters `copied_from IS NULL AND ml_task_id IS NULL`
- `list_generated_by_project(...)` filters `ml_task_id IS NOT NULL`
- `list_copies_by_source(...)` filters `copied_from == source_dataset_id`

`WorkItemRepository.set_dataset_selection(...)` should be removed.

`WorkItemRepository.create(...)` remains, but the created row now requires a copied dataset id.

## Runtime Layout

Add explicit dataset-artifact paths to `src/xenix/services/storage/layout.py`.

Keep:

- `database_path()`
- `artifact_models_root()`
- `artifact_inference_root()`
- `ml_task_root()`
- `task_input_dir()`
- `task_request_path()`
- `task_result_path()`
- `task_logs_path()`
- `task_models_dir()`

Add:

- `artifact_datasets_root(paths) -> Path`
  - `paths.artifacts / "datasets"`
- `work_item_dataset_dir(paths, work_item_id) -> Path`
  - `artifacts/datasets/work-items/<work-item-id>/`
- `canonical_inference_dir(paths, work_item_id) -> Path`
  - `artifacts/inference/<work-item-id>/`
- `task_output_dir(paths, ml_task_id) -> Path`
  - `artifacts/ml-tasks/<ml-task-id>/output/`

## File Ownership Rules

### Copied dataset row file

Path rule:

- `work_item_dataset_dir(paths, work_item_id) / <original-file-name>`

Ownership rule:

- created once during work-item creation
- referenced by the copied dataset row's `source_path`
- remains canonical for that work item

### Inference output file

Path rule:

- `canonical_inference_dir(paths, work_item_id) / "<ml-task-id>-predictions.csv"`

Ownership rule:

- created during successful inference finalization
- referenced by the generated dataset row's `source_path`
- remains the canonical openable result file

### Temporary manual-input CSV

Path rule:

- `paths.temp / "manual-inference" / "<uuid>.csv"`

Ownership rule:

- created before inference submission
- referenced in the task request
- not persisted as a dataset row
- cleanup may be best-effort after task completion

## Migration Strategy

Backward compatibility is not required for the MVP branch.

Preferred `v4` strategy:

- if `user_version == 0`, create the schema directly from metadata and set `PRAGMA user_version = 4`
- if `user_version` is `1`, `2`, or `3`, raise a clear reset-required error instructing the developer to remove the local database and restart

Why this is preferable:

- it avoids embedding destructive automatic table drops in runtime migration code
- it keeps the schema aligned with the new invariant instead of carrying compatibility-only nullability
- it matches the explicit review direction that local reset is acceptable during MVP development

## Reset Error Contract

The migration error for pre-`v4` local databases should clearly state:

- the detected version
- that schema `v4` requires a local reset on the MVP branch
- the file path to delete, derived from `database_path(paths)`

That keeps failure explicit and local rather than silently discarding data.
