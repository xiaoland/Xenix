# L2 Plan 02: Services And Execution

## Public Service Boundary

Issue `#73` keeps the existing split:

- `WorkItemService`
  - owns immutable work-item creation
  - owns copied-dataset creation as part of that flow
- `DatasetService`
  - owns source-dataset registration and inspection
  - owns temporary manual-input CSV materialization
  - owns dataset listing helpers
- `MLService`
  - owns workflow-facing inference submission and task inspection
- `MLTaskService`
  - owns atomic inference task dispatch and finalization
- `MLWorkerRunner`
  - remains a pure process helper

## `WorkItemService` API

Replace the old mutable attach flow with:

```python
class CreateWorkItemInput(SQLModel):
    project_id: str
    name: str
    source_dataset_id: str
    feature_columns: list[str]
    target_columns: list[str] = Field(default_factory=list)
```

Public methods:

- `create_work_item(input_data: CreateWorkItemInput) -> WorkItemRow`
- `list_work_items(project_id: str) -> list[WorkItemRow]`
- `get_work_item(work_item_id: str) -> WorkItemRow`

Remove:

- `AttachDatasetSelectionInput`
- `attach_dataset_selection(...)`

## Work-Item Creation Algorithm

`create_work_item(...)` should run this algorithm:

1. validate `name`
2. normalize `feature_columns` and `target_columns`
3. reject empty `feature_columns`
4. reject feature/target overlap
5. open one DB session
6. load the project
7. load the source dataset row by `source_dataset_id`
8. validate the dataset belongs to the same project
9. inspect the dataset file and validate the selected columns
10. create an in-memory `WorkItemRow` with a generated id
11. copy the dataset file to `work_item_dataset_dir(paths, work_item.id)`
12. create one copied `DatasetRow`:
    - `project_id = work_item.project_id`
    - `name = source_dataset.name`
    - `source_path = copied_path`
    - `source_format = source_dataset.source_format`
    - `copied_from = source_dataset.id`
    - `copied_at = now`
    - `ml_task_id = NULL`
13. persist the copied dataset row
14. assign `work_item.dataset_id = copied_dataset.id`
15. persist the work item row with selected columns
16. commit

Failure rule:

- if file copy fails, nothing is committed
- if DB commit fails after the file copy, the service should best-effort delete the copied file before re-raising

## `DatasetService` Additions

Keep existing:

- `register_dataset(...)`
- `inspect_source_file(...)`
- `get_dataset(...)`
- `list_datasets(...)`

Add:

```python
class MaterializeManualInferenceCsvInput(SQLModel):
    feature_columns: list[str]
    rows: list[dict[str, str | None]]
```

```python
def materialize_manual_inference_csv(
    self,
    input_data: MaterializeManualInferenceCsvInput,
) -> Path:
    ...
```

Rules:

- write a temporary CSV under `paths.temp / "manual-inference" /`
- columns must exactly match `feature_columns`
- row count must be at least `1`
- every row must contain every selected feature column
- output uses UTF-8 CSV with header row

Also add filtered list methods:

- `list_source_datasets(project_id: str) -> list[DatasetRow]`
- `list_generated_datasets(project_id: str) -> list[DatasetRow]`

## `MLService` API

Add:

```python
class InferWithFilesInput(SQLModel):
    work_item_id: str
    trained_model_id: str | None = None
    input_files: list[str]
```

Public methods:

- `infer(input_data: InferWithFilesInput) -> MLTaskRow`
- `list_work_item_tasks(work_item_id: str) -> list[MLTaskRow]`
- `get_task_details(ml_task_id: str) -> MLTaskDetails`
- `list_trained_models(work_item_id: str) -> list[TrainedModelRow]`

`get_task_details(...)` should expose enough result metadata to support:

- task summary
- open canonical result
- export copied result

## Inference Submission Algorithm

`infer(...)` should run:

1. load the work item
2. load the copied dataset row referenced by `work_item.dataset_id`
3. require non-empty `feature_columns`
4. resolve the trained model:
   - explicit `trained_model_id` first
   - otherwise `work_item.best_trained_model_id`
   - otherwise fail with a clear validation error
5. validate that the trained model belongs to the same work item
6. validate every input file path:
   - absolute
   - exists
   - supported extension
7. inspect each input file and require `feature_columns` to be present
8. create one `INFERENCE` task row
9. persist `request_payload` with:
   - project id
   - work item id
   - copied dataset id
   - copied dataset path
   - trained model id
   - model key
   - model artifact path
   - input file metadata list
   - feature columns
10. write `request.json`
11. enqueue the task
12. return the created task row immediately

## Request Persistence Rule

The persisted inference request should contain file metadata objects, not just raw strings.

Persisted fields per file:

- `absolute_path`
- `file_name`
- `source_kind`
  - `manual_csv`
  - `user_file`

That makes task details and debugging clearer without complicating worker logic.

## `MLTaskService` Changes

Extend `_resolve_entrypoint(...)`:

- `MLTaskType.INFERENCE -> run_inference_task`

Extend `_finalize_success(...)`:

- handle `MLTaskType.INFERENCE`

Add `_finalize_inference_task(session, row)`:

1. read and validate `InferenceTaskResult`
2. require the produced output file to exist
3. copy the produced output file to `canonical_inference_dir(paths, row.work_item_id)`
4. create one generated `DatasetRow`:
   - `project_id = row.project_id`
   - `name = "<work-item-name> predictions <timestamp>"`
   - `source_path = canonical_output_path`
   - `source_format = DatasetSourceFormat.CSV`
   - `copied_from = NULL`
   - `copied_at = NULL`
   - `ml_task_id = row.id`
5. append one `MLTaskArtifactInput` with `artifact_kind = INFERENCE_RESULT`
6. return finalized payload plus artifact inputs

## Inference Finalized Payload

The final persisted `result_payload` should include:

- `trained_model_id`
- `model_key`
- `row_count`
- `input_file_count`
- `prediction_column_name`
- `canonical_output_path`
- `result_dataset_id`

This is the minimum task summary surface the UI needs.

## Export Algorithm

Do not make export part of worker execution.

Preferred export boundary:

- the UI resolves `result_dataset_id` from task details
- `DatasetService.export_dataset_copy(dataset_id, destination_path)` performs the copy

`export_dataset_copy(...)` algorithm:

1. load the dataset row
2. require its source file to exist
3. require `destination_path` to be absolute
4. copy the canonical file to the destination
5. return the copied destination path

This keeps export a user-initiated file-copy action, not an ML task concern.
