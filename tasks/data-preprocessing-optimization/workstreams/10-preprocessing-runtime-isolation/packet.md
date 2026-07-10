# Preprocessing Runtime Isolation

## Objective & Hypothesis

Diagnose why large `data.transform` / `data.clean` runs make the desktop UI feel stuck even when Task Manager reports only moderate CPU usage.

Hypothesis: the current implementation moved AgentHarness submission off the Qt main thread, but preprocessing tools still execute synchronously inside the same Python process as `MainWindow`. Large full-table materialization, Pandas operations, DuckDB `fetchdf()`, Polars export, SQLite writes, filesystem IO, and Python GC/memory pressure can starve or delay the UI event loop without saturating total CPU.

## Status

locally verified; uncommitted

## Durable Owners / Blast Radius

- Chatbot UI and stream rendering:
  - `src/xenix/ui/main_window.py`
  - `src/xenix/ui/chatbot.py`
- AgentHarness tool execution loop:
  - `src/xenix/services/agent/harness_service.py`
  - `src/xenix/services/agent/tools.py`
  - `src/xenix/services/agent/chatbot_events.py`
- Data execution:
  - `src/xenix/services/data_transform.py`
  - `src/xenix/services/data_cleaning.py`
  - `src/xenix/services/tabular.py`
- Dataset materialization and export:
  - `src/xenix/services/dataset_service.py`
  - `src/xenix/services/dataset_export_service.py`
- Durable runtime-boundary docs:
  - `docs/20-product-tdd/runtime-boundaries.md`
  - `docs/30-unit-tdd/agent-harness.md`
  - `docs/40-deployment/runtime-state.md`

## Current Evidence

- `MainWindow._start_harness_submission()` starts `submit_user_turn_stream()` on `threading.Thread(name="xenix-agent-harness")`; it does not create a subprocess.
- `AgentHarnessService.submit_user_turn_stream()` materializes source attachments, starts the turn/run, then enters `_run_provider_loop_stream()`.
- `_run_provider_loop_stream()` executes provider tool calls by invoking `_execute_tool_call()` synchronously in the Harness thread.
- `AgentToolRegistry._data_transform()` calls `DataQueryTransformService.transform()` directly.
- Before this slice, `DataQueryTransformService.transform()` registered DuckDB bindings, created `output`, then used `connection.execute("SELECT * FROM output").fetchdf()`, materializing the full result as a Pandas DataFrame before writing Parquet through a second DuckDB connection.
- `AgentToolRegistry._data_clean()` calls `DataCleaningService.clean_dataset()` directly.
- Before this slice, `DataCleaningService.clean_dataset()` loaded a full Pandas DataFrame, applied operations in-process, and wrote a CSV output before dataset registration converted it back to app-owned Parquet.
- Before this slice, `_register_generated_dataset_result()` inspected, registered, and synchronously called `DatasetExportService.materialize_dataset_export_artifact()` in the desktop process.
- Before this slice, `DatasetExportService.materialize_dataset_export_artifact()` called `DatasetService.export_dataset_copy()`, which reads the dataset through Polars and writes an XLSX export before the tool returns.
- Before this slice, `docs/20-product-tdd/runtime-boundaries.md` stated the native app used a one-process layered model. ML tasks had a worker boundary; preprocessing tools did not.
- UI stream events cross back to Qt through `MainWindow._harness_stream_event = Signal(object)`. Tool execution completion may carry a projected `ChatbotEvent` and final snapshot back to the main thread.
- Tool detail blocks currently render a JSON projection of arguments/result payloads, truncated to 12 KB per dump. This is bounded, but it is still created and rendered synchronously in the UI path.
- Production LLM streaming through `LLMService.stream()` appears to buffer text deltas and can replay updates after provider completion, causing rapid SQLite writes / signal emissions / Markdown rerenders. This is adjacent to preprocessing stalls but not the main transform/clean root cause.
- Source attachment artifact registration still occurs synchronously on attach. It is lightweight compared with dataset import, but slow disks or many files can still cause short UI pauses.

## Initial Conclusion

Large preprocessing is mixed into the MainWindow application process. It is not on the Qt main thread, but it is in the same Python process. This distinction matters: a Python background thread does not isolate memory pressure, allocator contention, process-wide GC, native library thread pools, SQLite/file IO contention, or GIL-heavy Pandas sections from the UI.

The likely product-correct fix is not another UI spinner or local thread. The missing boundary is a preprocessing execution/task boundary that can run large dataset operations outside the GUI process while preserving AgentHarness semantics, tool result contracts, derived dataset registration, eager artifact creation, cancellation policy, and progress projection.

Secondary UI risks remain after process isolation: avoid sending bulky snapshots/details through Qt signals, avoid eager detail rendering when collapsed, and avoid bursty streaming replay. These are follow-up UI smoothness issues, not substitutes for a proper preprocessing runtime boundary.

## Candidate Direction

- Define a preprocessing task model for full-data dataset-producing tools.
- Dispatch `data.transform`, `data.clean`, and likely `data.tokenize`/`data.integrate` through a local worker process by default.
- Keep Agent-facing tool semantics stable: the tool may wait for completion for now, but the heavy work should be out-of-process.
- Prefer DuckDB/Polars streaming or direct file-to-file execution over Pandas full materialization where possible.
- Avoid `fetchdf()` for full transform outputs; write final `output` directly to Parquet and derive row/schema metadata without loading all rows into Pandas.
- Stop writing cleaned outputs as CSV in the internal path; align cleaning output with app-owned Parquet.
- Re-evaluate eager XLSX artifact creation cost: if the product requires the tool to return only after artifact creation, that export should also happen inside the worker boundary.

## First Implementation Slice

- Add a narrow local preprocessing worker runner that uses a spawned subprocess and task-directory JSON handoff, not a Qt/Python background thread.
- Route `DataQueryTransformService.transform()` and `DataCleaningService.clean_dataset()` through that runner by default.
- Keep `data.query` in-process because it is bounded and returns at most the requested row limit.
- Keep Agent tool semantics synchronous for this slice: the tool waits until the worker completes and then returns the same tool result shape.
- Move the expensive transform core out of `fetchdf()` full Pandas materialization by writing DuckDB `output` directly to Parquet and deriving row/schema metadata through bounded DuckDB queries.
- Leave the existing Pandas clean operation semantics intact inside the worker process for this slice. Converting the operation catalog to Polars/DuckDB is a follow-up, because changing every operation at once would broaden correctness risk.
- Move generated dataset registration and eager XLSX export artifact creation into the preprocessing worker boundary as well, so full-table copy/export work does not return to the GUI process.

## Implemented Shape

- Added `src/xenix/services/preprocessing_worker.py` with a `spawn`-based `LocalPreprocessingWorkerRunner`, a top-level `run_preprocessing_worker_task()` entrypoint, JSON request/result handoff, and an inline runner for focused tests.
- `DataQueryTransformService.transform()` now delegates to the worker by default; `_transform_in_process()` is the worker-side implementation.
- `DataCleaningService.clean_dataset()` now delegates to the worker by default; `_clean_dataset_in_process()` is the worker-side implementation.
- `AgentToolRegistry._register_generated_dataset_result()` now delegates inspect/register/export payload creation to the preprocessing worker through `data.register_generated_dataset`.
- `data.transform` writes `COPY (SELECT * FROM output) TO ? (FORMAT PARQUET)` directly from DuckDB and uses only bounded metadata queries for row/schema reporting.
- `data.clean` writes Parquet output instead of CSV for cleaning-derived intermediate output.
- Existing small unit tests inject `InlinePreprocessingWorkerRunner`; `tests/test_preprocessing_worker.py` covers the production runner's `spawn` boundary and one real child-process transform.

## Open Questions

- Should a long-running preprocessing tool return a task receipt, or should AgentHarness block the tool call until the worker finishes while UI stays responsive?
- What progress signals are required for non-cancellable preprocessing after the tool call has started?
- Which operations can be converted from Pandas to Polars/DuckDB now, and which need a compatibility phase?
- Should `data.integrate`, `data.tokenize`, and source attachment import move their full-data compute into the preprocessing worker boundary?

## Verification Plan

- Add a targeted runtime-boundary test that proves large preprocessing runs through a process boundary, not directly in the Harness thread.
- Add a transform test that proves full output Parquet is produced without `fetchdf()` full Pandas materialization.
- Add a cleaning test that proves derived output is Parquet and no intermediate CSV becomes a durable dependency.
- Add UI/streaming test coverage for responsiveness/progress semantics once the task boundary is chosen.
- Manually verify with a large local dataset while observing process tree, CPU, memory, UI responsiveness, and artifact creation timing.

## Verification Run Log

- `pdm run pytest tests/test_preprocessing_worker.py -q` - passed, 2 tests; includes one fake-context spawn-boundary test and one real child-process transform.
- `pdm run pytest tests/test_data_transform.py -q` - passed, 14 tests.
- `pdm run pytest tests/test_data_cleaning.py -q` - passed, 13 tests.
- `pdm run pytest tests/test_preprocessing_worker.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py -q` - passed, 34 tests.
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_lambda.py tests/test_analysis_profile.py -q` - passed, 30 tests.
- `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_agent_ai_observability.py -q` - passed, 52 tests.
- `pdm run pytest tests/test_services.py::test_dataset_service_exports_csv_with_selected_encoding_and_xlsx tests/test_services.py::test_dataset_export_service_materializes_workbook_artifact -q` - passed, 2 tests.
- `pdm run python -m compileall -q src/xenix/services/preprocessing_worker.py src/xenix/services/data_transform.py src/xenix/services/data_cleaning.py src/xenix/services/agent/tools.py tests/test_preprocessing_worker.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_analysis_graph.py tests/test_analysis_lambda.py tests/test_analysis_profile.py tests/test_agent_harness_first_slice.py` - passed.
- `pdm run pytest tests/test_preprocessing_worker.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_analysis_graph.py tests/test_analysis_lambda.py tests/test_analysis_profile.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_agent_ai_observability.py -q` - passed, 116 tests in 108.95s.
- `git diff --check` - passed.

## Next Action

Wait for the user's commit instruction. Keep unrelated dirty files out of any commit.
