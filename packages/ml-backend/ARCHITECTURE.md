# ML Backend Architecture

HTTP-based ML backend with process isolation and fire-and-forget execution.

## Overview

FastAPI server spawns isolated Python processes for CPU-intensive ML tasks. Each task runs independently with task-specific logger and filesystem.

```
HTTP Request → Server → Spawn Process → Isolated Execution
              ↓ 202
         Return Immediately
```

Client polls for result via GET endpoint.

## Design Principles

### 1. Process Isolation
- Separate Python process per ML task
- No CPU blocking on HTTP server
- No shared state between tasks
- Task crash doesn't affect server

### 2. Fire-and-Forget HTTP
- POST /execute → 202 Accepted (immediate)
- Task executes in background subprocess
- Client polls GET /tasks/{id}/result
- Connection close after response allowed

### 3. Filesystem Communication
- Request data via stdin
- Results via result.json
- Logs via logs.jsonl
- Stateless server (restartable)

### 4. Task Isolation
- Per-task directory: `/tasks/{task_id}/`
- Isolated logs, results, models
- No file path conflicts

## Components

### HTTP Server (server.py)

**Responsibilities**:
- Accept HTTP requests
- Calculate task base paths
- Spawn subprocess: `main.py --base-path {task_path}`
- Send operation data via stdin
- Return 202 immediately
- Serve result endpoint

**Interface**:
```
spawn_subprocess(task_id, operation, data):
    base_path = calculate_task_path(task_id)
    process = create_subprocess("main.py", "--base-path", base_path)
    process.stdin.write(json(operation, data))
    return 202_ACCEPTED
```

### ML Script (main.py)

**Responsibilities**:
- Parse --base-path CLI arg
- Read operation from stdin
- Create TaskLogger instance
- Execute ML operation
- Write result.json
- Flush logs.jsonl
- Exit with status code

**Interface**:
```
main():
    base_path = parse_cli_args()
    request = read_stdin()
    logger = TaskLogger(task_id, base_path)
    result = execute_operation(request, logger)
    write_result(result)
    logger.flush()
    exit(0)
```

### Controllers

Request routing and file I/O coordination.

**Available Operations**:
- **batch-train** - GridSearchCV hyperparameter tuning (returns metrics + best_params, NO model saving)
- **single-train** - Fixed parameter training (returns metrics only, NO model saving)
- **predict-file** - File-based prediction (trains model, saves fitted model + prediction file)
- **predict-inline** - Inline data prediction (trains model, saves fitted model, returns predictions as JSON)

**Signature**: `(input_data, logger: TaskLogger) → Output`

**Key Design Decisions**:
1. **Model Saving Location**: Models saved ONLY during prediction operations, NOT during training
   - Training operations focus on finding optimal parameters/evaluating metrics
   - Prediction operations train on full dataset and persist the fitted model
2. **Target Columns as Array**: Changed from single string to array for future multi-target support
3. **Split Predict Operations**: Separate `predict-file` and `predict-inline` for clarity and type safety
4. **Task-Specific Directories**: All files isolated in `{BASE_PATH}/tasks/{task_id}/`
5. **Auto-Generated Filenames**: No `outputPath` parameter - backend generates timestamped filenames

**Training Workflow** (batch-train, single-train):
1. Validate input
2. Read training data
3. Train model and evaluate metrics
4. Return metrics (and best_params for batch-train)
5. NO model saving

**Prediction Workflow** (predict-file, predict-inline):
1. Validate input
2. Read training data
3. Read/parse prediction data
4. Train model on full training dataset
5. Make predictions
6. Save fitted model (model_{timestamp}.pkl)
7. Save/return predictions
8. Return result with model path and prediction data/path

### Services (Model Registry)

Model-specific training/prediction logic.

**Base Interface**:
```python
abstract class ModelBase:
    # Training methods (NO model return, only metrics)
    abstract batch_train(dataframe, input) → {best_params, metrics}
    abstract single_train(dataframe, input) → {metrics}

    # Prediction methods (train + return fitted model)
    abstract train_and_get_model(dataframe, input) → fitted_model
    abstract predict_with_model(model, predict_df, input) → predictions_df
```

**Key Changes**:
- Training methods (`batch_train`, `single_train`) return metrics only, NO model object
- New `train_and_get_model()` trains on full dataset and returns fitted model instance
- New `predict_with_model()` makes predictions with a fitted model

**Available Models**:
- Linear: linear, ridge, lasso, bayesian_ridge
- Polynomial: polynomial
- Instance-based: knn
- Tree-based: decision_tree, random_forest
- Boosting: adaboost, gbdt, xgboost, lightgbm

### TaskLogger

Per-task logger instance with batch writes.

**Features**:
- Instance-based (no globals)
- Memory buffer (size: 10)
- Batch writes to logs.jsonl
- JSONL format
- Stdout passthrough

**Interface**:
```
class TaskLogger:
    init(task_id, base_path, batch_size=10)
    log(message, level, attributes)
    flush()
    get_logs() → [log_entries]
```

## Request Flow

### Lifecycle

1. **Client request**: POST /execute with task_id
2. **Server response**: 202 Accepted immediately
3. **Background spawn**: `python main.py --base-path /tasks/{id}`
4. **Subprocess executes**: Sets config, creates logger, runs operation
5. **Writes results**: result.json, logs.jsonl, model.pkl
6. **Process exits**: Status code 0 (success) or 1 (failure)
7. **Client polls**: GET /tasks/{id}/result until complete

### Data Flow

```
Client
  ↓ POST /execute
Server (server.py)
  ↓ spawn with stdin
Subprocess (main.py)
  ↓ write files
Filesystem
  ├─ result.json
  ├─ logs.jsonl
  └─ models/model.pkl
  ↑ read files
Server (GET /tasks/{id}/result)
  ↑ return JSON
Client
```

## Output File Structure

All operations write to task-specific directory: `{ML_BASE_PATH}/tasks/{task_id}/`

### Common Files (All Operations)

- **status.txt** - Current task status (pending/running/completed/failed)
- **result.json** - Operation results in JSON format
- **logs.jsonl** - Structured logs in JSONL format

### Operation-Specific Files

**Training Operations** (batch-train, single-train):
- Only common files (no model saving)

**Prediction Operations** (predict-file, predict-inline):
- **model_{timestamp}.pkl** - Fitted model (joblib format)
- **predictions_{timestamp}.xlsx** - Prediction results (predict-file only)

### Result.json Formats

**batch-train**:
```json
{
  "metrics": {"r2": 0.95, "mse": 0.05, "mae": 0.1},
  "best_params": {"alpha": 1.0, "max_iter": 100}
}
```

**single-train**:
```json
{
  "metrics": {"r2": 0.93, "mse": 0.07, "mae": 0.12}
}
```

**predict-file**:
```json
{
  "fitted_model_path": "model_20260119_120000.pkl",
  "predicted_data_path": "predictions_20260119_120000.xlsx"
}
```

**predict-inline**:
```json
{
  "fitted_model_path": "model_20260119_120000.pkl",
  "predicted_data": [
    {"col1": 1.5, "col2": 2.0, "prediction": 3.2},
    {"col1": 1.8, "col2": 2.2, "prediction": 3.5}
  ]
}
```

**Error**:
```json
{
  "error": "Error message",
  "traceback": "Full traceback..."
}
```

## HTTP API

### POST /execute
Fire-and-forget execution.

**Request**: `{operation, data: {task_id, ...}}`
**Response**: `{status: "accepted", task_id}`
**Status**: 202 Accepted

**Supported Operations**:
- `batch-train` - GridSearchCV hyperparameter tuning
- `single-train` - Fixed parameter training
- `predict-file` - File-based prediction
- `predict-inline` - Inline data prediction

### GET /tasks/{task_id}/result
Check completion and retrieve results.

**Returns**: Contents of result.json (format depends on operation type)

### GET /tasks/{task_id}/status
Check task status.

**Returns**: Contents of status.txt (pending/running/completed/failed)

### GET /health
Health check.

**Response**: `{status: "healthy"}`

## Error Handling

### Server Errors
- Spawn failure → write error to result.json
- Log subprocess stdout/stderr
- Server continues running

### Subprocess Errors
- Validation errors → captured with traceback
- File I/O errors → captured with traceback
- Training errors → captured with traceback
- All errors → result.json with status: "failed"
- Logs written before exit

**Error Format**: `{status: "failed", error: "message", traceback: "..."}`

## Configuration

**Environment**:
- ML_BASE_PATH - Global base (default: /tmp/ml-backend)
- PORT - Server port (default: 8000)
- HOST - Server host (default: 0.0.0.0)

**Task Paths**: `{ML_BASE_PATH}/tasks/{task_id}`

**CLI Args**: `main.py --base-path {path}`

## Performance

### Concurrency
- Multiple tasks: Separate processes, no GIL contention
- HTTP server: Thousands requests/sec (async I/O)
- CPU: GridSearchCV uses all cores

### Scalability
- Horizontal: Multiple servers behind load balancer
- Vertical: CPU scales with core count
- Memory: Independent per subprocess

### Optimization
- Use CSV over Excel (faster I/O)
- Smaller parameter grids (faster tuning)
- Single-train for production (skip tuning)

## Related

- [FILESYSTEM.md](FILESYSTEM.md) - Filesystem structure
- [PROCESSES.md](PROCESSES.md) - Process model
