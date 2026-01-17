# Filesystem Reference

Filesystem structure and I/O patterns for ML Backend.

## Directory Layout

```
{ML_BASE_PATH}/                           # Default: /tmp/ml-backend
└── tasks/{task_id}/                      # Per-task isolation
    ├── result.json                       # Task result (required)
    ├── logs.jsonl                        # Batched logs (required)
    └── models/model_{task_id}_{ts}.pkl   # Trained model (one per task)
```

**Key Paths**:
- Base: `ML_BASE_PATH` env var (default: `/tmp/ml-backend`)
- Task: `{ML_BASE_PATH}/tasks/{task_id}`
- Result: `{task_path}/result.json`
- Logs: `{task_path}/logs.jsonl`
- Model: `{task_path}/models/model_{task_id}_{timestamp}.pkl`

Note: Each task produces exactly ONE model file despite the `models/` directory.

## File Formats

### result.json
**Location**: `{task_path}/result.json`
**Written by**: main.py on completion/error
**Read by**: server.py GET /tasks/{id}/result

**Success**:
```json
{
  "status": "completed",
  "result": {
    "task_id": 123,
    "best_params": {...},
    "metrics": {...},
    "model_path": "..."
  }
}
```

**Failure**:
```json
{
  "status": "failed",
  "error": "error message",
  "traceback": "..."
}
```

**Pending**: File does not exist (task still running)

### logs.jsonl
**Location**: `{task_path}/logs.jsonl`
**Format**: JSON Lines (one object per line)
**Written by**: TaskLogger (batched, size 10)

**Format**:
```jsonl
{"type":"log","timestamp":...,"severity_text":"INFO","body":"message","attributes":{...}}
```

**Reading**: Parse each line as separate JSON object

### model_{task_id}_{timestamp}.pkl
**Location**: `{task_path}/models/model_{task_id}_{timestamp}.pkl`
**Format**: joblib pickle
**Written by**: Controllers (batch_train, single_train)
**Count**: One per task

## Path Calculation

### Task Base Path
```
get_task_base_path(task_id):
    base_dir = ENV["ML_BASE_PATH"] || "/tmp/ml-backend"
    return "{base_dir}/tasks/{task_id}"
```

### Model Storage Path
```
Config.set_base_path(base_path):
    Config.BASE_PATH = base_path
    Config.MODEL_STORAGE_PATH = "{base_path}/models"
```

## I/O Patterns

### Server → Subprocess
```
server.py:
    base_path = get_task_base_path(task_id)
    spawn("main.py", "--base-path", base_path)
    stdin.write(json_data)
```

### Subprocess Sets Config
```
main.py:
    args = parse_args("--base-path")
    Config.set_base_path(args.base_path)
    # → MODEL_STORAGE_PATH = "{base_path}/models"
```

### Write Result
```
main.py:
    result_file = "{BASE_PATH}/result.json"
    mkdir_parents(result_file)
    write_json(result_file, {status, result})
```

### Batch Logging
```
TaskLogger:
    buffer = []

    log(message):
        buffer.append(log_entry)
        if len(buffer) >= 10:
            flush_to_file()

    flush():
        write_jsonl(log_file, buffer)
        buffer = []
```

### Save Model
```
controller:
    filename = "model_{task_id}_{timestamp}.pkl"
    path = "{MODEL_STORAGE_PATH}/{filename}"
    joblib_dump(model, path)
```

## Path Resolution

**Absolute**: `/data/train.csv` → used as-is

**Relative**: `data/train.csv` → `{ML_BASE_PATH}/data/train.csv`

## Input Data Formats

**Supported**: `.xlsx`, `.xls`, `.csv`

**Read**:
```
read_data(file_path):
    if ends_with(file_path, '.csv'):
        return read_csv(file_path)
    else if ends_with(file_path, ('.xlsx', '.xls')):
        return read_excel(file_path)
```

## Directory Creation

**Auto-created** (on-demand):
```
Config.ensure_directories():
    mkdir("{MODEL_STORAGE_PATH}")
    mkdir("{DATA_STORAGE_PATH}")

TaskLogger.__init__():
    mkdir_parents(log_file_path)

main.py result writer:
    mkdir_parents(result_file)
```

## Configuration

**Environment**:
```bash
ML_BASE_PATH=/custom/path  # Default: /tmp/ml-backend
PORT=8000                  # Server port
HOST=0.0.0.0              # Server host
```

**CLI**:
```bash
main.py --base-path /tmp/ml-backend/tasks/123
```

## Complete Task Example

### Task 123 - Ridge Regression

**1. Server receives**: task_id=123

**2. Spawn**:
```bash
python main.py --base-path /tmp/ml-backend/tasks/123
```

**3. Executes**:
```
Config.set_base_path("/tmp/ml-backend/tasks/123")
logger = TaskLogger(123, base_path)
result = batch_train(...)
```

**4. Files created**:
```
/tmp/ml-backend/tasks/123/
├── result.json                         # Success
├── logs.jsonl                          # 15 entries
└── models/
    └── model_123_20260117_143022.pkl   # One model
```

**5. Client polls**:
```
GET /tasks/123/result → content of result.json
```

## Storage Estimates

**Per Task**:
- result.json: ~1-5 KB
- logs.jsonl: ~10-100 KB
- models/*.pkl: ~1-100 MB (one file)
- **Total**: ~1-100 MB

**Cleanup**:
```bash
rm -rf /tmp/ml-backend/tasks/123  # Delete task
```

No auto-cleanup (external implementation needed).

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [PROCESSES.md](PROCESSES.md) - Process model
