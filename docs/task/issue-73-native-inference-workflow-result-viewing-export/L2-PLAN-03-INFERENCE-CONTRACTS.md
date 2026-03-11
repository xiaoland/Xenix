# L2 Plan 03: Inference Contracts And Model Services

## Contract Boundary

Inference should use explicit Pydantic contracts under `src/xenix/services/ml/contracts.py`.

The worker boundary stays file-based and request/result-driven, exactly like the current fit/tune/evaluate flow.

## Request Models

Add:

```python
class InferenceInputFile(BaseModel):
    absolute_path: str
    file_name: str
    source_kind: Literal["manual_csv", "user_file"]
```

```python
class InferenceModelPayload(BaseModel):
    trained_model_id: str
    model_key: str
    trained_model_artifact_path: str
```

```python
class InferenceTaskRequest(BaseModel):
    task_id: str
    project_id: str
    work_item_id: str
    dataset_id: str
    dataset_source_path: str
    feature_columns: list[str]
    inference_model: InferenceModelPayload
    input_files: list[InferenceInputFile]
```

Rules:

- `dataset_id` points to the copied dataset row owned by the work item
- `dataset_source_path` points to that copied dataset row's app-managed file path
- `feature_columns` is copied directly from the work item
- `input_files` is non-empty

## Result Models

Add:

```python
class InferenceSummary(BaseModel):
    row_count: int
    input_file_count: int
    prediction_column_name: str = "prediction"
```

```python
class InferenceTaskResult(BaseModel):
    task_id: str
    trained_model_id: str
    model_key: str
    output_file_path: str
    summary: InferenceSummary
    error_summary: str | None = None
```

Result rules:

- `output_file_path` points to the worker-produced task-local CSV
- `summary.row_count` is the combined output row count
- `summary.input_file_count` reflects how many normalized input files were processed

## Model-Service Interface

Extend `ModelServiceBase` with:

```python
@classmethod
@abstractmethod
def infer(cls, request: InferenceTaskRequest, task_dir: Path) -> InferenceTaskResult:
    raise NotImplementedError
```

All current supervised model services should implement inference through the shared base class.

## Shared Inference Algorithm

Add `infer(...)` to `NumericAndCategoricalModelService`.

Algorithm:

1. load the estimator from `request.inference_model.trained_model_artifact_path`
2. initialize an empty list of output frames
3. for each `input_file` in `request.input_files`:
   - load dataframe through `load_dataset(...)`
   - require every `feature_column` to exist
   - select `X = dataframe.loc[:, request.feature_columns]`
   - call `estimator.predict(X)`
   - create `result_frame = dataframe.copy()`
   - append `result_frame["prediction"] = predictions`
   - if `len(request.input_files) > 1`, append `result_frame["source_file"] = input_file.file_name`
   - append `result_frame` to the output list
4. concatenate output frames
5. write one CSV to `task_output_dir(task_id) / "predictions.csv"`
6. return `InferenceTaskResult`

## Output Format Decision

The canonical v1 inference output format should be CSV.

Reasons:

- simple and deterministic
- already supported by the current dependency set
- easy to open locally
- easy to export by file copy
- avoids xlsx writer branching in the first delivery

This does not prevent later xlsx export support, but it keeps the initial worker contract narrow.

## Validation Rules

Inference input validation happens in two layers.

### Main-process validation

- every input file path is absolute and exists
- every input file extension is supported
- every input file contains the required feature columns
- the trained model belongs to the selected work item

### Worker validation

- the model artifact exists
- file parsing succeeds
- feature-column projection succeeds
- the output CSV is written successfully

## Worker Entrypoint

Add `run_inference_task(task_dir: str) -> None` under `src/xenix/services/ml/operations/`.

Algorithm:

1. load `request.json` as `InferenceTaskRequest`
2. resolve the model service from `request.inference_model.model_key`
3. write log entries into `logs.jsonl`
4. call `model_service.infer(request, Path(task_dir))`
5. write `result.json`
6. exit `0` on success, non-zero on failure

## Error Surface

Inference failures should produce actionable summaries such as:

- missing required feature column
- unsupported input file format
- trained model artifact missing
- unable to load model artifact
- unable to write output CSV

Raw stack traces may still land in logs, but `error_summary` should remain operator-readable.
