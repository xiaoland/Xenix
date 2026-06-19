# Dataset Create UI Freeze Profile

## Objective & Hypothesis

- Objective: reproduce and profile the UI freeze reported when a 3M-row Excel dataset is attached/sent and a dataset is created.
- Initial hypothesis: synchronous dataset inspection or persistence on the UI-triggered path blocks the Qt event loop.

## Guardrails Touched

- Reality / Diagnose route.
- Service boundary: `DatasetService` owns source dataset registration, source-file inspection, and export helpers.
- UI boundary: UI must stay service-driven and should not parse datasets for business decisions.

## Verification

- Locate the dataset creation call path from chat send/file attachment to service layer.
- Run targeted timing/profiling against `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx`.
- Compare wall time across file metadata, dataset registration, dataset inspection, and any synchronous UI-path calls.

## Current Understanding

- Reported symptom: when sending a message, dataset creation for a 3M Excel file makes the UI unresponsive for about 3-5 seconds.
- No product code changes are allowed in this diagnostic slice.
- The send path clears the composer, then synchronously calls `MainWindow._register_composer_datasets()` before adding the visible user message or starting the agent harness background thread.
- `_register_composer_datasets()` calls `DatasetService.register_dataset()` and then `DatasetService.inspect_source_file()` for each attachment.
- `register_dataset()` is metadata/SQLite work only. `inspect_source_file()` currently calls `inspect_dataset_file()`, which calls `pandas.read_excel()` for `.xlsx` files and loads the entire worksheet.
- Exploration after user approval of the direction:
  - Runtime TDD allows Composer attachments to be registered as datasets on send and provider-facing blocks to carry dataset metadata plus `dataset_id`. It does not require full dataframe loading at send time.
  - Existing MainWindow async pattern uses `threading.Thread` plus Qt `Signal(object)` to marshal results back to the UI thread.
  - There is no repo-wide QThread worker abstraction, so introducing one only for this fix would add avoidable shape unless we need cancellation/progress beyond one background preflight.
  - `DatasetAttachmentInput` requires `dataset_id`, `name`, `file_name`, `source_format`, `row_count`, `column_count`, and `preview_columns`; it does not require column kinds, nullability, or preview row values.
  - Current `ThreadDetailView._handle_button_clicked()` clears text and attachments before emitting `message_submitted`, so async preflight failures currently need an explicit UX decision if we want to preserve user input.
- Implemented after approval:
  - `DatasetService.register_dataset_attachment()` registers the dataset and returns attachment metadata without full semantic inspection.
  - `.csv` attachment metadata uses streaming `csv.reader`.
  - `.xlsx` attachment metadata uses `openpyxl` read-only workbook metadata and the header row.
  - `.xls` attachment metadata intentionally falls back to full inspection because no lightweight `.xls` parser is in the declared dependency set.
  - `MainWindow` runs dataset attachment preflight in a background `threading.Thread` and marshals completion through Qt signals.
  - Existing Agent Harness streaming stays unchanged and starts only after preflight succeeds.
  - Preflight failure restores composer text and attachment chips.

## Evidence Log

- Test file: `F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx`.
- File size: 2,863,935 bytes.
- Parsed shape in current code path: 100,721 rows x 5 columns.
- Segmented timing, cold-ish run with `tracemalloc`:
  - `storage.initialize`: 0.294s.
  - `detect_source_format`: ~0.000s.
  - `DatasetService.register_dataset`: 0.069s.
  - `DatasetService.inspect_source_file`: 21.358s with tracing overhead.
- `cProfile inspect_dataset_file()`:
  - elapsed: 11.129s under profiler.
  - 11.079s cumulative in `dataset_inspection.load_dataframe()`.
  - 11.079s cumulative in `pandas.read_excel()`.
  - 10.615s cumulative in pandas openpyxl reader `get_sheet_data()`.
- `cProfile load_dataframe()`:
  - elapsed: 12.523s under profiler.
  - 12.522s cumulative in `pandas.read_excel()`.
  - 12.041s cumulative in pandas openpyxl reader `get_sheet_data()`.
- Hot-cache repeated `pandas.read_excel()` without profiler/tracemalloc:
  - 3.443s, 3.314s, 3.446s.
- Lightweight xlsx metadata/preview prototype using `openpyxl.load_workbook(read_only=True, data_only=True)`, `ws.max_row`, `ws.max_column`, and first six rows:
  - 0.119s, 0.105s, 0.102s without profiler.
  - 0.311s under cProfile.
- Post-fix verification against the same file:
  - `inspect_attachment_metadata` repeated timings: 0.305s cold-ish, then 0.125s, 0.098s, 0.100s, 0.105s.
  - `register_dataset_attachment` repeated timings: 0.118s, 0.105s, 0.112s.
  - Returned metadata: 100,721 rows x 5 columns; preview columns `电影编号`, `名称`, `类别`, `用户编号`, `评分`.
- Automated verification:
  - `pdm run pytest tests/test_main.py tests/test_services.py -q`
  - Result: 51 passed.
  - Added service coverage that `.xlsx` attachment registration does not call `pandas.read_excel()`.
  - Added UI coverage that dataset preflight runs off the UI thread before harness submission.

## Next Step

- Done for this slice. A future improvement could expose visible "preparing dataset" status text during preflight, but the blocking behavior and full-read attachment path are fixed.
