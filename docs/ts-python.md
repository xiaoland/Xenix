# TS ↔ Python JSON IO

- Entry point: TypeScript spawns Python via `spawn` and writes a JSON object to stdin. See [server/utils/pythonExecutor.ts](server/utils/pythonExecutor.ts).

- TS → Python: TS sends a single JSON document with `pythonProcess.stdin.write(JSON.stringify(stdinData))` then `pythonProcess.stdin.end()` (one complete payload).

- Python stdin parsing: Python calls `read_json_input()` in [server/business/ml/structured_io.py](server/business/ml/structured_io.py) which does `sys.stdin.read()` then `json.loads(...)` to parse the full payload.

- Python → TS (stdout): Python scripts use `emit_json_output`, `emit_log`, `emit_result`, etc. (in [server/business/ml/structured_io.py](server/business/ml/structured_io.py)) to print one JSON object per call (newline-terminated).

-- TS stdout handling: `executePythonTask` in [server/utils/pythonExecutor.ts](server/utils/pythonExecutor.ts) reads `stdout`/`stderr` streams, splits on newlines, parses each line with `JSON.parse()` and routes parsed objects to `handleStructuredOutput` (types: `log`, `status`, `result`).

- Sync helper: `executePythonScript` collects entire stdout buffer and `JSON.parse(stdoutBuffer)` on exit (used when a single JSON object is expected).

- Framing & encoding: stdin uses one full JSON doc; stdout is newline-delimited JSON objects. Encoding is plain UTF-8 text; serialization is JSON (JS `JSON.stringify` ↔ Python `json.dumps`/`json.loads`).

-- Caveat (bug risk): Prediction output is now emitted under the `result` message type. Keys are normalized to `output_file` and `num_predictions` (snake_case) while the TS side stores `outputFile` internally; `handleStructuredOutput` normalizes these fields. Keep message shapes consistent or update the parser accordingly.

- Recommendation: Keep message shapes consistent (prefer one naming convention) or normalize keys in `handleStructuredOutput`.

Files referenced:

- [server/utils/pythonExecutor.ts](server/utils/pythonExecutor.ts)
- [server/business/ml/structured_io.py](server/business/ml/structured_io.py)
- [server/business/ml/predict_on_json.py](server/business/ml/predict_on_json.py)
