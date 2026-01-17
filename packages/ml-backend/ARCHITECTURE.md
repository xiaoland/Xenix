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

**Available**:
- batch_train - GridSearchCV tuning
- single_train - Fixed parameters
- predict - Batch predictions

**Signature**: `(input_data, logger: TaskLogger) → Output`

**Workflow**:
1. Validate input
2. Log progress
3. Delegate to model service
4. Save trained model
5. Return structured result

### Services (Model Registry)

Model-specific training/prediction logic.

**Base Interface**:
```
abstract class ModelBase:
    abstract batch_train(dataframe, input) → {model, best_params, metrics}
    abstract single_train(dataframe, input) → {model, metrics}
    abstract predict(train_df, predict_df, input) → predictions_df
```

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

## HTTP API

### POST /execute
Fire-and-forget execution.

**Request**: `{operation, data: {task_id, ...}}`
**Response**: `{status: "accepted", task_id}`
**Status**: 202 Accepted

### GET /tasks/{task_id}/result
Check completion.

**Pending**: `{status: "pending"}`
**Success**: `{status: "completed", result: {...}}`
**Failure**: `{status: "failed", error, traceback}`

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
