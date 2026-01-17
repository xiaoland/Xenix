# Process Model

Process isolation and execution model for ML Backend.

## Process Architecture

```
[Server Process]              [Task Process]
server.py                     main.py
FastAPI on port 8000          Spawned per-request
├─ HTTP handler               ├─ Parse CLI args
├─ Calculate task path        ├─ Create logger
├─ Spawn subprocess ─stdin──→ ├─ Read stdin
└─ Return 202                 ├─ Execute operation
                              ├─ Write result.json
                              ├─ Write logs.jsonl
                              └─ Exit (0 or 1)
```

**Principle**: Server NEVER executes ML code. Tasks run in isolated subprocesses.

## Process Spawning

### Server Side (server.py)

```
execute_task_async(operation, data, base_path):
    task_id = data.task_id

    # Prepare payload
    request = {operation, data}

    # Spawn subprocess
    process = spawn_subprocess(
        python_interpreter,
        "main.py",
        "--base-path", base_path,
        stdin=PIPE
    )

    # Send data and wait
    stdout, stderr = process.communicate(json_encode(request))

    # Check exit code
    if process.returncode != 0:
        log_error(task_id, returncode)
```

### Subprocess Side (main.py)

```
main():
    # Parse args
    args = parse_args("--base-path")
    Config.set_base_path(args.base_path)

    # Read stdin
    request = json_decode(stdin.read())

    # Setup
    task_id = request.data.task_id
    logger = TaskLogger(task_id, Config.BASE_PATH)

    # Execute
    result = execute_operation(request.operation, request.data, logger)

    # Write result
    write_file(BASE_PATH + "/result.json", {status: "completed", result})

    # Cleanup
    logger.flush()
    exit(0)
```

## Process Lifecycle

### Timeline

```
0ms      - HTTP request received
1ms      - 202 Accepted returned
10ms     - Subprocess spawned
50ms     - Config set, logger created
100ms    - Data loaded
30s      - Model training (CPU-intensive)
30.5s    - Result/logs written
30.6s    - Process exits
```

### Client Polling

```
GET /tasks/{id}/result
→ Before 30.6s: {status: "pending"}
→ After 30.6s:  {status: "completed", result}
```

## Process Isolation Benefits

### No Shared State
```
Server:        logger = None          ✓ No logger
Subprocess A:  logger = TaskLogger(123, path_123)
Subprocess B:  logger = TaskLogger(124, path_124)

→ Separate memory spaces
→ No interference
```

### No GIL Contention
```
Task 123: Process 1 → 100% CPU on Core 1
Task 124: Process 2 → 100% CPU on Core 2
Task 125: Process 3 → 100% CPU on Core 3

Total: 300% CPU (3 cores, no GIL blocking)
```

### Crash Isolation
```
Task 123: Segfault → Process exits with -11
Server:   Continues running
Task 124: Unaffected
```

## Communication Patterns

### Server → Subprocess (stdin)
```
server:
    payload = json({operation, data})
    process.stdin.write(payload)

subprocess:
    request = json_decode(stdin.read())
```

### Subprocess → Server (filesystem)
```
subprocess:
    write_file("result.json", result_data)

server:
    return read_file("result.json")
```

### Subprocess ↔ Subprocess
```
None. Tasks completely isolated.
```

## TaskLogger Model

### Old (Global - Broken)
```
# Global state
_task_id = None
_buffer = []

init_logger(task_id):
    _task_id = task_id  # Race condition!
```

### New (Instance - Safe)
```
class TaskLogger:
    task_id
    buffer
    log_file_path

    init(task_id, base_path):
        self.task_id = task_id
        self.buffer = []
        self.log_file_path = base_path + "/logs.jsonl"

# Each subprocess creates instance
logger = TaskLogger(123, path)
```

## Process Exit Codes

```
Success:   exit(0) → result.json has status: "completed"
Failure:   exit(1) → result.json has status: "failed"
Crash:     exit(-N) → result.json may not exist
```

## Concurrency Model

### HTTP Server (Async I/O)
```
async execute(request):
    background_tasks.add_task(spawn_subprocess, ...)
    return 202  # Immediate, non-blocking
```

### ML Subprocess (CPU-bound)
```
result = batch_train(...)  # Blocking in separate process
# No impact on server
```

### Parallelism
```
CPU Cores:         8
HTTP Connections:  10000 (async I/O)
ML Tasks:          8 (one per core, CPU-bound)
```

## Error Handling

### Server Error (spawn failure)
```
try:
    process = spawn_subprocess(...)
catch:
    write_file("result.json", {status: "failed", error})
```

### Subprocess Error (execution failure)
```
try:
    result = batch_train(...)
    write_file("result.json", {status: "completed", result})
catch:
    write_file("result.json", {status: "failed", error, traceback})
    exit(1)
```

## Process Management

### Cleanup
```bash
# Delete task
rm -rf /tmp/ml-backend/tasks/123

# Delete completed tasks
find /tmp/ml-backend/tasks -name "result.json" | xargs dirname | xargs rm -rf

# Delete old tasks (>30 days)
find /tmp/ml-backend/tasks -mtime +30 -type d -exec rm -rf {} \;
```

### Monitoring
```bash
# List running ML processes
ps aux | grep "python.*main.py"

# Monitor task
tail -f /tmp/ml-backend/tasks/123/logs.jsonl
```

## Performance Characteristics

### Overhead
```
Spawn:        ~50-100ms
Python import: ~200-500ms
Total:        ~250-600ms per task
```

### Memory
```
Server:       ~50 MB
Task process: ~200-500 MB (dataset-dependent)
10 tasks:     ~2-5 GB total
```

### CPU
```
Server:       <5% (I/O bound)
Task process: 100-800% (GridSearchCV, all cores)
```

## Testing

### Test Subprocess
```bash
# Prepare input
echo '{"operation": "batch-train", "data": {...}}' > input.json

# Execute
python main.py --base-path /tmp/ml-backend/tasks/999 < input.json

# Check result
cat /tmp/ml-backend/tasks/999/result.json
cat /tmp/ml-backend/tasks/999/logs.jsonl
```

### Test Server
```bash
# Start
python server.py

# Request
curl -X POST http://localhost:8000/execute \
  -d '{"operation": "batch-train", "data": {...}}'

# Poll
curl http://localhost:8000/tasks/999/result
```

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [FILESYSTEM.md](FILESYSTEM.md) - Filesystem structure
