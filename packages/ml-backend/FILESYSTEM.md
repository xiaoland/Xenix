# Filesystem Reference

Quick reference for ML Backend filesystem structure and I/O patterns.

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
**Read by**: server.py GET /tasks/{id}/result endpoint

**Success**:
```json
{
  "status": "completed",
  "result": {
    "task_id": 123,
    "best_params": {"alpha": 1.0},
    "metrics": {"r2": 0.92, "mse": 12.45},
    "model_path": "/tmp/ml-backend/tasks/123/models/model_123_20260117_143022.pkl"
  }
}
```

**Failure**:
```json
{
  "status": "failed",
  "error": "FileNotFoundError: data.csv",
  "traceback": "Traceback..."
}
```

**Pending**: File does not exist (task still running)

### logs.jsonl
**Location**: `{task_path}/logs.jsonl`
**Format**: JSON Lines (one object per line)
**Written by**: TaskLogger (batched, size 10)

```jsonl
{"type":"log","timestamp":1737125422123456789,"severity_text":"INFO","body":"Message","attributes":{"task_id":123}}
```

**Read**:
```python
with open(f"{task_path}/logs.jsonl") as f:
    for line in f:
        log = json.loads(line)
```

### model_{task_id}_{timestamp}.pkl
**Location**: `{task_path}/models/model_{task_id}_{timestamp}.pkl`
**Format**: joblib pickle
**Written by**: Controllers (batch_train, single_train)
**Count**: One per task

```python
import joblib
model = joblib.load(model_path)
```

## Path Calculation

### Task Base Path
```python
# server.py
def get_task_base_path(task_id: int) -> str:
    base_dir = os.getenv("ML_BASE_PATH", "/tmp/ml-backend")
    return str(Path(base_dir) / "tasks" / str(task_id))
```

### Model Storage Path
```python
# Config.py (updates when base_path changes)
Config.set_base_path("/tmp/ml-backend/tasks/123")
# → Config.MODEL_STORAGE_PATH = "/tmp/ml-backend/tasks/123/models"
```

## I/O Patterns

### Server → Subprocess
```python
# server.py - spawn with task-specific path
base_path = get_task_base_path(123)  # → /tmp/ml-backend/tasks/123
process = await asyncio.create_subprocess_exec(
    sys.executable,
    "main.py",
    "--base-path", base_path,  # Pass task path
    stdin=subprocess.PIPE
)
```

### Subprocess Sets Config
```python
# main.py - receive and set base path
args = parser.parse_args()  # --base-path /tmp/ml-backend/tasks/123
Config.set_base_path(args.base_path)
# → Config.BASE_PATH = "/tmp/ml-backend/tasks/123"
# → Config.MODEL_STORAGE_PATH = "/tmp/ml-backend/tasks/123/models"
```

### Write Result
```python
# main.py - write on completion
result_file = Path(Config.BASE_PATH) / "result.json"
result_file.parent.mkdir(parents=True, exist_ok=True)
with open(result_file, 'w') as f:
    json.dump({"status": "completed", "result": result.model_dump()}, f, indent=2)
```

### Batch Logging
```python
# TaskLogger - buffer and flush
logger = TaskLogger(task_id, base_path=Config.BASE_PATH)
logger.log("Message", "INFO")  # Buffered
# ... 10 logs later → auto-flush to logs.jsonl
logger.flush()  # Explicit flush on completion
```

### Save Model
```python
# Controllers - save to model storage path
model_filename = f"model_{task_id}_{timestamp}.pkl"
model_path = os.path.join(Config.MODEL_STORAGE_PATH, model_filename)
# → /tmp/ml-backend/tasks/123/models/model_123_20260117_143022.pkl
joblib.dump(trained_model, model_path)
```

## Path Resolution

**Absolute paths** → used as-is:
```python
"/data/training.csv" → "/data/training.csv"
```

**Relative paths** → resolved from ML_BASE_PATH:
```python
"data/training.csv" → "{ML_BASE_PATH}/data/training.csv"
```

## Input Data Formats

**Supported**: `.xlsx`, `.xls`, `.csv`

```python
# ml_backend/utils/file_io.py
def read_data(file_path: str) -> pd.DataFrame:
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
```

## Directory Creation

**Auto-created** (on-demand):
```python
# Config.ensure_directories()
os.makedirs(Config.MODEL_STORAGE_PATH, exist_ok=True)  # {base}/models
os.makedirs(Config.DATA_STORAGE_PATH, exist_ok=True)   # {base}/data

# TaskLogger.__init__()
log_file_path.parent.mkdir(parents=True, exist_ok=True)  # {base}/ for logs

# main.py result writer
result_file.parent.mkdir(parents=True, exist_ok=True)  # {base}/ for result.json
```

## Configuration

**Environment Variables**:
```bash
export ML_BASE_PATH=/custom/path  # Default: /tmp/ml-backend
export PORT=8000                  # Server port
export HOST=0.0.0.0              # Server host
```

**CLI Arguments** (main.py):
```bash
python main.py --base-path /tmp/ml-backend/tasks/123
```

## Example: Complete Task Flow

### Task 123 - Ridge Regression

**1. Server receives request** (task_id: 123)

**2. Spawn subprocess**:
```bash
python main.py --base-path /tmp/ml-backend/tasks/123
```

**3. Subprocess executes**:
```python
Config.set_base_path("/tmp/ml-backend/tasks/123")
logger = TaskLogger(123, "/tmp/ml-backend/tasks/123")
result = batch_train(...)
```

**4. Files created**:
```
/tmp/ml-backend/tasks/123/
├── result.json                         # Success result
├── logs.jsonl                          # 15 log entries
└── models/
    └── model_123_20260117_143022.pkl   # One trained model
```

**5. Client polls**:
```bash
GET /tasks/123/result
→ Returns content of result.json
```

## Storage Estimates

**Per Task**:
- result.json: ~1-5 KB
- logs.jsonl: ~10-100 KB
- models/*.pkl: ~1-100 MB (one file)
- **Total**: ~1-100 MB

**Cleanup**:
- Delete entire task directory: `rm -rf /tmp/ml-backend/tasks/123`
- No auto-cleanup (implement externally)

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [PROCESSES.md](PROCESSES.md) - Process model
