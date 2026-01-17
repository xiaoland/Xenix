# ML Backend Architecture

HTTP-based ML backend for Xenix with process isolation and fire-and-forget execution.

## Overview

FastAPI HTTP server that spawns isolated Python processes for CPU-intensive ML tasks. Each task runs independently with its own logger and filesystem isolation.

```
HTTP Request (POST /execute)
  ↓
FastAPI Server (server.py)
  ↓ 202 Accepted (immediate response)
  ↓
Spawn subprocess → python main.py --base-path /tasks/{task_id}
  ↓
Isolated ML Process (main.py)
  ├─ Task-specific logger
  ├─ Task-specific filesystem
  └─ CPU-intensive ML operations
  ↓
Write results to filesystem
  ├─ result.json (task result)
  └─ logs.jsonl (batched logs)
  ↓
Process exits
```

Client polls `GET /tasks/{task_id}/result` to check completion.

## Key Design Principles

### 1. Process Isolation
Each ML task runs in a **separate Python process**:
- Prevents CPU-intensive work from blocking the HTTP server
- No shared state between tasks (no race conditions)
- Python GIL doesn't affect concurrency
- If one task crashes, server continues running

### 2. Fire-and-Forget HTTP
Server returns immediately, task runs in background:
- `POST /execute` → 202 Accepted (instant response)
- Task executes asynchronously in subprocess
- Client polls `GET /tasks/{task_id}/result` for completion
- Connection can be closed after response without error

### 3. Filesystem-Based Communication
No in-memory state, all communication via filesystem:
- Request data sent via stdin to subprocess
- Results written to `{base_path}/result.json`
- Logs written to `{base_path}/logs.jsonl`
- Enables stateless server (can restart without losing tasks)

### 4. Task-Specific Isolation
Each task gets its own directory:
- Base path: `/tmp/ml-backend/tasks/{task_id}/`
- Logs: `{base_path}/logs.jsonl`
- Results: `{base_path}/result.json`
- Models: `{base_path}/models/`
- Complete isolation between tasks

## Architecture Components

### HTTP Server (server.py)

Lightweight FastAPI server - does NOT execute ML code directly.

**Responsibilities**:
- Accept HTTP requests
- Calculate task-specific base paths
- Spawn subprocess with `python main.py --base-path {task_base_path}`
- Send operation data via stdin
- Return 202 Accepted immediately
- Provide result retrieval endpoint

**Key Code**:
```python
# Calculate task-specific base path
base_path = get_task_base_path(task_id)  # → /tmp/ml-backend/tasks/{task_id}

# Spawn subprocess
process = await asyncio.create_subprocess_exec(
    sys.executable,
    "main.py",
    "--base-path", base_path,
    stdin=subprocess.PIPE
)

# Send data and return immediately
await process.communicate(input=json.dumps(request).encode())
```

### ML Script (main.py)

Standalone ML execution script - runs in separate process.

**Responsibilities**:
- Parse `--base-path` argument
- Read operation data from stdin
- Create TaskLogger instance
- Execute ML operations (batch-train, single-train, predict)
- Write results to `result.json`
- Flush logs to `logs.jsonl`
- Exit with status code

**Key Code**:
```python
# Parse CLI args
args = parser.parse_args()
Config.set_base_path(args.base_path)  # Task-specific path

# Create task-specific logger
logger = TaskLogger(task_id, base_path=Config.BASE_PATH)

# Execute operation
result = batch_train(input_data, logger)

# Write result
result_file = Path(Config.BASE_PATH) / "result.json"
with open(result_file, 'w') as f:
    json.dump({"status": "completed", "result": result.model_dump()}, f)

# Flush logs and exit
logger.flush()
sys.exit(0)
```

### Controllers

Request routing and file I/O coordination.

**Controllers**:
- `batch_train.py` - GridSearchCV hyperparameter tuning
- `single_train.py` - Training with specific parameters
- `predict.py` - Batch predictions

**Signature**: All controllers accept `(input_data, logger: TaskLogger)`

**Responsibilities**:
- Validate input
- Log progress
- Delegate to model services
- Save trained models
- Return structured results

### Services (Model Registry)

Model-specific training and prediction logic.

**Service Architecture**:
```
services/
├── regression/
│   ├── base.py              # RegressionModelBase (abstract)
│   ├── linear.py            # Linear Regression
│   ├── ridge.py             # Ridge Regression
│   ├── lasso.py             # Lasso Regression
│   ├── polynomial.py        # Polynomial Regression
│   ├── knn.py               # K-Nearest Neighbors
│   ├── decision_tree.py     # Decision Tree
│   ├── random_forest.py     # Random Forest
│   ├── adaboost.py          # AdaBoost
│   ├── gbdt.py              # Gradient Boosting
│   ├── xgboost.py           # XGBoost
│   ├── lightgbm.py          # LightGBM
│   └── bayesian_ridge.py    # Bayesian Ridge
└── classification/
    ├── base.py              # ClassificationModelBase (abstract)
    ├── logistic_regression.py
    └── random_forest.py
```

**Base Class Contract**:
```python
class RegressionModelBase(ABC):
    @abstractmethod
    def batch_train(self, df, input_data) -> dict

    @abstractmethod
    def single_train(self, df, input_data) -> dict

    @abstractmethod
    def predict(self, train_df, predict_df, input_data) -> DataFrame
```

### TaskLogger (Class-Based Logging)

Per-task logger instance with batch writes.

**Features**:
- Instance-based (no global state)
- Buffers logs in memory
- Writes to filesystem in batches (default: 10 logs)
- JSONL format (one JSON object per line)
- Also outputs to stdout for backward compatibility

**Usage**:
```python
# Create logger for task
logger = TaskLogger(task_id=123, base_path="/tmp/ml-backend/tasks/123")

# Log messages (buffered)
logger.log("Training started", "INFO")
logger.log("Model metrics", "INFO", {"r2": 0.95})

# Force flush remaining logs
logger.flush()
```

**Log Format**:
```json
{
  "type": "log",
  "timestamp": 1234567890123456789,
  "severity_text": "INFO",
  "severity_number": 9,
  "body": "Training started",
  "resource": {"service.name": "ml-backend", "service.version": "2.0.0"},
  "attributes": {"task_id": 123}
}
```

## Request Flow

### Complete Request Lifecycle

1. **Client sends request**:
```bash
POST http://localhost:8000/execute
{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "data.csv",
    "model": "regression.ridge",
    ...
  }
}
```

2. **Server processes** (server.py):
   - Middleware calculates base path: `/tmp/ml-backend/tasks/123`
   - Returns 202 Accepted immediately
   - Spawns subprocess in background: `python main.py --base-path /tmp/ml-backend/tasks/123`

3. **Subprocess executes** (main.py):
   - Sets `Config.BASE_PATH = /tmp/ml-backend/tasks/123`
   - Creates `TaskLogger(123, base_path="/tmp/ml-backend/tasks/123")`
   - Reads operation data from stdin
   - Executes: `batch_train(input_data, logger)`
   - Writes: `/tmp/ml-backend/tasks/123/result.json`
   - Writes: `/tmp/ml-backend/tasks/123/logs.jsonl`
   - Exits

4. **Client polls for result**:
```bash
GET http://localhost:8000/tasks/123/result
```

Returns:
```json
{
  "status": "completed",
  "result": {
    "task_id": 123,
    "best_params": {...},
    "metrics": {...},
    "model_path": "/tmp/ml-backend/tasks/123/models/model_123_20260117_123456.pkl"
  }
}
```

## HTTP API Endpoints

### POST /execute
Execute ML operation (fire-and-forget).

**Request**:
```json
{
  "operation": "batch-train",  // batch-train | single-train | predict
  "data": {
    "task_id": 123,
    ...operation-specific fields
  }
}
```

**Response** (202 Accepted):
```json
{
  "status": "accepted",
  "task_id": 123,
  "message": "Task 123 accepted for processing"
}
```

### GET /tasks/{task_id}/result
Check task completion status.

**Response** (pending):
```json
{
  "status": "pending",
  "message": "Result not available yet"
}
```

**Response** (completed):
```json
{
  "status": "completed",
  "result": {...}
}
```

**Response** (failed):
```json
{
  "status": "failed",
  "error": "Error message",
  "traceback": "Full traceback..."
}
```

### GET /health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy"
}
```

## Error Handling

### Server Errors
- Failed to spawn subprocess → writes error to `result.json`
- Logs subprocess stdout/stderr for debugging
- Server continues running even if subprocess crashes

### Subprocess Errors
- Validation errors (Pydantic) → captured with traceback
- File I/O errors → captured with traceback
- ML training errors → captured with traceback
- All errors written to `result.json` with `status: "failed"`
- Logs also written to `logs.jsonl` before exit

### Error Result Format
```json
{
  "status": "failed",
  "error": "Missing required field: input_file",
  "traceback": "Traceback (most recent call last):\n..."
}
```

## Configuration

**Environment Variables**:
- `ML_BASE_PATH` - Global base directory (default: `/tmp/ml-backend`)
- `PORT` - HTTP server port (default: 8000)
- `HOST` - HTTP server host (default: 0.0.0.0)

**Task-Specific Paths**:
Calculated per-task: `{ML_BASE_PATH}/tasks/{task_id}`

**CLI Arguments** (main.py):
- `--base-path` - Override base path (required when spawned by server)

## Performance

### Concurrency
- **Multiple concurrent tasks**: Each in separate process, no GIL contention
- **Non-blocking HTTP**: Server handles thousands of requests/sec
- **CPU utilization**: GridSearchCV uses all cores (`n_jobs=-1`)

### Scalability
- **Horizontal**: Run multiple server instances behind load balancer
- **Vertical**: CPU-bound tasks scale with core count
- **Memory**: Each subprocess has independent memory space

### Optimization Tips
- Use CSV instead of Excel for faster I/O
- Reduce parameter grid size for faster tuning
- Use single-train for production (skip hyperparameter search)

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.

## Related Documentation

- [FILESYSTEM.md](FILESYSTEM.md) - File system structure and I/O
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development guide
- [README.md](README.md) - Getting started guide
