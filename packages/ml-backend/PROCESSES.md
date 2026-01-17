# Process Model

Quick reference for ML Backend process isolation and execution model.

## Process Architecture

```
[HTTP Server Process]              [ML Task Process]
server.py (FastAPI)                main.py (Python)
Port 8000                          Spawned per-request
├─ HTTP handler                    ├─ Parse --base-path
├─ Calculate task path             ├─ Create TaskLogger
├─ Spawn subprocess ───stdin──────>├─ Read operation data
└─ Return 202                      ├─ Execute ML operation
                                   ├─ Write result.json
                                   ├─ Write logs.jsonl
                                   └─ Exit (0 or 1)
```

**Key Principle**: Server NEVER executes ML code. Each task runs in isolated subprocess.

## Process Spawning

### Server Side (server.py)

```python
# Calculate task-specific path
task_id = data.get("task_id")
base_path = get_task_base_path(task_id)  # /tmp/ml-backend/tasks/{task_id}

# Prepare request payload
request_payload = {
    "operation": "batch-train",
    "data": {...}
}

# Spawn subprocess
process = await asyncio.create_subprocess_exec(
    sys.executable,              # Python interpreter
    "main.py",                   # ML script
    "--base-path", base_path,    # Task-specific path
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Send data and wait
stdout, stderr = await process.communicate(
    input=json.dumps(request_payload).encode()
)

# Check exit code
if process.returncode != 0:
    # Task failed
    print(f"Task {task_id} failed with code {process.returncode}")
```

### Subprocess Side (main.py)

```python
# Parse CLI args
parser = argparse.ArgumentParser()
parser.add_argument('--base-path', required=True)
args = parser.parse_args()

# Set config
Config.set_base_path(args.base_path)

# Read stdin
input_text = sys.stdin.read()
request = json.loads(input_text)

# Extract data
task_id = request["data"]["task_id"]
operation = request["operation"]

# Create logger
logger = TaskLogger(task_id, base_path=Config.BASE_PATH)

# Execute operation
if operation == "batch-train":
    result = batch_train(BatchTrainInput(**request["data"]), logger)

# Write result
result_file = Path(Config.BASE_PATH) / "result.json"
with open(result_file, 'w') as f:
    json.dump({"status": "completed", "result": result.model_dump()}, f)

# Flush logs and exit
logger.flush()
sys.exit(0)
```

## Process Lifecycle

### 1. HTTP Request
```http
POST /execute
{"operation": "batch-train", "data": {"task_id": 123, ...}}
```

### 2. Server Response (Immediate)
```http
202 Accepted
{"status": "accepted", "task_id": 123}
```

### 3. Subprocess Execution (Async)
```
Time: 0ms     - Subprocess spawned
Time: 10ms    - Config set, logger created
Time: 100ms   - Data loaded
Time: 30s     - Model training (CPU-intensive)
Time: 30.5s   - Result written, logs flushed
Time: 30.6s   - Process exits
```

### 4. Client Polls (Until Complete)
```http
GET /tasks/123/result
→ {"status": "pending"}  (before 30.6s)
→ {"status": "completed", "result": {...}}  (after 30.6s)
```

## Process Isolation Benefits

### No Shared State
```python
# Server process
task_123_logger = None  # ✓ Server has no logger

# Subprocess A (task 123)
logger = TaskLogger(123, "/tmp/ml-backend/tasks/123")

# Subprocess B (task 124)
logger = TaskLogger(124, "/tmp/ml-backend/tasks/124")

# No interference - separate memory spaces
```

### No GIL Contention
```python
# Multiple concurrent tasks
Task 123: CPU-intensive training → Process 1 (100% CPU)
Task 124: CPU-intensive training → Process 2 (100% CPU)
Task 125: CPU-intensive training → Process 3 (100% CPU)

# Total: 300% CPU utilization (3 cores)
# No Python GIL blocking
```

### Crash Isolation
```python
# Task 123 crashes with segfault
→ Process exits with code -11
→ Server continues running
→ Other tasks unaffected
```

## Communication Patterns

### Server → Subprocess (stdin)
```python
# server.py
request_json = json.dumps({"operation": "batch-train", "data": {...}})
await process.communicate(input=request_json.encode())
```

```python
# main.py
input_text = sys.stdin.read()
request = json.loads(input_text)
```

### Subprocess → Server (filesystem)
```python
# main.py writes
result_file = Path(base_path) / "result.json"
with open(result_file, 'w') as f:
    json.dump(result_data, f)
```

```python
# server.py reads
with open(result_file, 'r') as f:
    return json.load(f)
```

### Subprocess → Subprocess (none)
```
No communication between tasks.
Each task is completely isolated.
```

## TaskLogger Instance Model

### Old (Global - Broken)
```python
# BAD: Global state
_task_id = None
_logs_buffer = []

def init_logger(task_id):
    global _task_id
    _task_id = task_id  # Race condition!
```

### New (Instance - Safe)
```python
# GOOD: Instance per task
class TaskLogger:
    def __init__(self, task_id, base_path):
        self.task_id = task_id
        self.logs_buffer = []
        self.log_file_path = Path(base_path) / "logs.jsonl"

# Each subprocess creates its own instance
logger = TaskLogger(123, "/tmp/ml-backend/tasks/123")
```

## Process Exit Codes

```python
# Success
sys.exit(0)  # → result.json has status: "completed"

# Failure
sys.exit(1)  # → result.json has status: "failed"

# Crash (server logs stderr)
# → result.json may not exist or incomplete
```

## Concurrency Model

### HTTP Server (Async I/O)
```python
# server.py - handles 1000s of concurrent connections
async def execute(request):
    # Non-blocking
    background_tasks.add_task(execute_task_async, ...)
    return 202  # Immediate
```

### ML Subprocess (CPU-bound)
```python
# main.py - blocks on CPU work
result = batch_train(...)  # Blocking, but in separate process
# No impact on server responsiveness
```

### Parallelism
```
CPU Cores: 8
Concurrent HTTP Requests: 10000 (async I/O)
Concurrent ML Tasks: 8 (CPU-bound, one per core)
```

## Error Handling

### Server Error (spawn failure)
```python
try:
    process = await asyncio.create_subprocess_exec(...)
except Exception as e:
    # Write error to result.json
    result_file = Path(base_path) / "result.json"
    with open(result_file, 'w') as f:
        json.dump({"status": "failed", "error": str(e)}, f)
```

### Subprocess Error (execution failure)
```python
try:
    result = batch_train(...)
    # Write success
except Exception as e:
    # Write error to result.json
    error_data = {
        "status": "failed",
        "error": str(e),
        "traceback": traceback.format_exc()
    }
    with open(result_file, 'w') as f:
        json.dump(error_data, f)
    sys.exit(1)
```

## Process Management

### No Auto-Cleanup
```python
# Completed tasks leave files on disk
/tmp/ml-backend/tasks/123/  # Remains after process exits
```

### Manual Cleanup
```bash
# Delete single task
rm -rf /tmp/ml-backend/tasks/123

# Delete all completed tasks
find /tmp/ml-backend/tasks -name "result.json" -exec dirname {} \; | xargs rm -rf

# Delete old tasks (>30 days)
find /tmp/ml-backend/tasks -type d -mtime +30 -exec rm -rf {} \;
```

### Process Monitoring
```bash
# List running ML processes
ps aux | grep "python.*main.py"

# Monitor specific task
tail -f /tmp/ml-backend/tasks/123/logs.jsonl
```

## Performance Characteristics

### Process Startup Overhead
```
Spawn time: ~50-100ms
Python import time: ~200-500ms
Total overhead: ~250-600ms per task
```

### Memory Isolation
```
Server: ~50 MB base
Task process: ~200-500 MB (depends on dataset size)
Total for 10 tasks: ~2-5 GB
```

### CPU Utilization
```
Server: <5% CPU (I/O bound)
Task process: 100-800% CPU (GridSearchCV uses all cores)
```

## Testing Process Spawning

### Test Spawn
```bash
# Prepare test input
cat > /tmp/test_input.json <<EOF
{
  "operation": "batch-train",
  "data": {
    "task_id": 999,
    "input_file": "test_data.csv",
    "model": "regression.linear",
    "feature_columns": ["x"],
    "target_column": "y"
  }
}
EOF

# Test subprocess execution
python main.py --base-path /tmp/ml-backend/tasks/999 < /tmp/test_input.json

# Check result
cat /tmp/ml-backend/tasks/999/result.json
cat /tmp/ml-backend/tasks/999/logs.jsonl
```

### Test Server
```bash
# Start server
python server.py

# Send request
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"operation": "batch-train", "data": {"task_id": 999, ...}}'

# Poll result
curl http://localhost:8000/tasks/999/result
```

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [FILESYSTEM.md](FILESYSTEM.md) - Filesystem structure
