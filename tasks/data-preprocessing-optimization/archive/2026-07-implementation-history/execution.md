# Execution Notes

## Implemented Slice

### Runtime Artifact Link Diagnosis

- User clicked `artifact://eb1367a427164cf1b9bb29d18cc54df7` in latest thread `dddee0c550f94caf9efd7a4868b8879d`.
- Runtime DB was `C:\Users\yyh\AppData\Local\Xenix\state\xenix.db` with `PRAGMA user_version=14`.
- `artifact` lookup for `eb1367a427164cf1b9bb29d18cc54df7` returned no row.
- `dataset` lookup for `eb1367a427164cf1b9bb29d18cc54df7` returned derived dataset `4月堂食销售数据_最终清洗版`, source format `PARQUET`, source path `C:\Users\yyh\AppData\Local\Xenix\state\datasets\derived\eb1367a427164cf1b9bb29d18cc54df7.parquet`.
- The relevant `data.transform` tool call `728c086cf78241d8a799a288ea61b527` returned both `dataset_id=eb1367a427164cf1b9bb29d18cc54df7` and `artifact_id=1adb63b6cd1249639fe01000f9cb57e7`, plus `artifact_uri=artifact://1adb63b6cd1249639fe01000f9cb57e7`.
- The final assistant message nevertheless rendered `[4月堂食销售数据_最终清洗版](artifact://eb1367a427164cf1b9bb29d18cc54df7)`.
- Root cause: provider-facing result exposes dataset id and artifact id side by side, while the system/tool contract does not prevent the model from turning a dataset id into an `artifact://` link. Chatbot then resolves the link strictly through `ArtifactService`, so it reports the dataset id as a missing artifact.
- Secondary design bug: the correct artifact row points at the internal Parquet dataset file. This is not the desired lazy export contract; opening a dataset should materialize a workbook on demand instead of exposing/opening app-owned Parquet storage.

### LinkRouter / Lazy Dataset Export Implementation

- Added `LinkRouter` as the UI-facing link activation boundary.
- `MainWindow` now passes activated links to `LinkRouter` instead of resolving artifact URIs and opening local files itself.
- `ArtifactService.activate_uri()` now owns artifact readiness checks, missing-file checks, and OS file opening.
- Added `DatasetExportService` for `dataset://<dataset_id>` activation. It resolves the dataset, materializes or reuses an `.xlsx` workbook export artifact under `artifacts/datasets/exports/<dataset_id>/`, and delegates final opening to `ArtifactService`.
- Dataset-producing Agent tools now return `dataset_id` plus `dataset_uri` and no longer eager-register the internal app-owned Parquet file as an `ArtifactKind.DATASET` artifact.
- The default Agent system prompt now distinguishes `dataset_id`, `dataset_uri`, and `artifact_id`, and explicitly forbids using a dataset id inside an `artifact://` URI.
- Durable docs now describe `dataset://` for dataset activation, `artifact://` for artifact activation, LinkRouter as the activation owner, and lazy workbook export artifacts as the user-openable dataset representation.
- Verification:
  - `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_main.py -q`: 157 passed.
  - `pdm run pytest`: 302 passed, 3 warnings.

### Dataset Link UI Freeze Diagnosis

- Current `dataset://` click path is synchronous on the Qt UI thread:
  `ThreadDetailView.service_link_activated -> MainWindow._open_service_link -> LinkRouter.activate -> DatasetExportService.activate_uri -> DatasetService.export_dataset_copy -> ArtifactService.activate_uri`.
- `DatasetService.export_dataset_copy()` reads the app-owned dataset and writes the workbook export immediately. For large Parquet datasets this can be long-running.
- Because `MainWindow._open_service_link()` calls the full chain directly, the progress/dialog/event loop cannot repaint while export is running, which explains the observed "UI no response" symptom.
- Boundary decision:
  - `LinkRouter` remains the service-owned URI activation authority.
  - `DatasetExportService` remains the dataset lazy export owner and still delegates final file opening to `ArtifactService`.
  - `ArtifactService` remains the only place that opens artifact files through the OS.
  - `MainWindow` should only choose the UI execution mode: service-owned link activation runs in a background worker and is accompanied by a non-modal indeterminate progress dialog.
- Verification target:
  - Add a UI boundary test where `LinkRouter.activate()` blocks behind an event. Calling `_open_service_link("dataset://...")` must return promptly and show the progress dialog before the worker is released.
  - Successful worker completion closes the dialog.
  - Failed worker completion closes the dialog and renders the error through `ThreadDetailView.show_error()`.

### Dataset Link UI Freeze Implementation

- `MainWindow._open_service_link()` now creates a per-click activation id, shows an indeterminate `QProgressDialog`, and starts a daemon `xenix-service-link-activation` thread.
- The worker thread calls `LinkRouter.activate(uri, thread_id=...)`, so link authority remains behind `LinkRouter`.
- Worker success emits `_service_link_activation_succeeded`; worker failure emits `_service_link_activation_failed`.
- Main-thread completion handlers remove the activation id, close the progress dialog when no service-link activations remain, and render failures through `ThreadDetailView.show_error()`.
- `DatasetExportService` and `ArtifactService` remain unchanged; lazy export still materializes/reuses workbook artifacts and file opening still happens inside `ArtifactService.activate_uri()`.
- Verification:
  - `pdm run pytest tests/test_main.py::test_main_window_opens_service_link_off_ui_thread tests/test_main.py::test_main_window_service_link_activation_failure_closes_progress -q`: 2 passed.
  - `pdm run pytest tests/test_services.py::test_link_router_lazily_exports_dataset_to_workbook_artifact -q`: 1 passed.
  - `pdm run pytest tests/test_main.py -q`: 53 passed.
  - `pdm run pytest tests/test_services.py -q`: 15 passed.
  - `pdm run python -m compileall -q src/xenix`: passed.
  - `pdm run pytest`: 304 passed, 3 warnings.

### Polars Dataset Export Implementation

- Diagnosed `DatasetService.export_dataset_copy()` as a remaining Pandas path: it loaded app-owned Parquet into a Pandas DataFrame and used `DataFrame.to_csv()` / `DataFrame.to_excel()`.
- Added runtime dependency `xlsxwriter>=3.2.0` so Polars can write `.xlsx` exports directly.
- `DatasetService.export_dataset_copy()` now:
  - resolves and loads the source through `load_tabular_frame()` / Polars;
  - writes CSV with `DataFrame.write_csv()`;
  - writes XLSX with `DataFrame.write_excel()`;
  - writes to a sibling temporary export path first, then replaces the requested destination;
  - preserves `csv_encoding`, including direct UTF-8/UTF-8-BOM paths and streaming transcode for other encodings.
- Regression guard: export tests monkeypatch Pandas `DataFrame.to_csv()` and `DataFrame.to_excel()` to fail if dataset export re-enters Pandas.
- Verification:
  - `pdm run pytest tests/test_services.py::test_dataset_service_materializes_manual_apply_csv_and_exports_utf8_by_default tests/test_services.py::test_dataset_service_exports_csv_with_selected_encoding_and_xlsx tests/test_services.py::test_link_router_lazily_exports_dataset_to_workbook_artifact -q`: 3 passed.
  - `pdm run pytest tests/test_services.py -q`: 15 passed.
  - `pdm run python -m compileall -q src/xenix`: passed.
  - `pdm run pytest`: 304 passed, 3 warnings.

### Service Link Progress Follow-Up Diagnosis

- User observed that the progress modal should not prevent continued use of the main window.
- Current `MainWindow._show_service_link_progress()` creates a `QProgressDialog` and calls `setWindowModality(Qt.WindowModal)`. That blocks interaction with the parent main window until activation finishes.
- Corrected UI contract should be: link activation remains in the background worker, the progress surface is visible but non-modal/modeless, and the main window remains interactive.
- i18n gap:
  - `"Opening link..."` and `"Open Link"` are wrapped in `self.tr(...)` but have not been propagated through `pdm run i18n-extract`, `src/xenix/translations/xenix_zh_CN.ts`, and `pdm run i18n-compile`.
  - `MainWindow.retranslate_ui()` currently refreshes shell labels and child widgets, but not a visible service-link progress dialog.
- Verification target:
  - UI test should assert the service-link progress dialog is non-modal / not window-modal.
  - i18n test should assert the new strings translate to Chinese and update a visible progress dialog after language switch.

### Service Link Progress Follow-Up Implementation

- `MainWindow._show_service_link_progress()` now uses `Qt.NonModal`, so the progress surface does not block main-window interaction while the activation worker runs.
- Added `_retranslate_service_link_progress()` and call it from both dialog creation and `MainWindow.retranslate_ui()`.
- Ran `pdm run i18n-extract`, filled new Chinese translations in `xenix_zh_CN.ts`, filled same-text English translations in `xenix_en_US.ts`, and ran `pdm run i18n-compile`.
- Regression coverage:
  - `tests/test_main.py::test_main_window_opens_service_link_off_ui_thread` asserts the progress dialog is non-modal.
  - `tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell` asserts `Open Link` / `Opening link...` translate to Chinese and update a visible progress dialog after language switch.
- Verification:
  - `pdm run pytest tests/test_main.py::test_main_window_opens_service_link_off_ui_thread tests/test_main.py::test_main_window_service_link_activation_failure_closes_progress -q`: 2 passed.
  - `pdm run pytest tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`: 1 passed.
  - `pdm run pytest tests/test_main.py -q`: 53 passed.
  - `pdm run pytest tests/test_i18n.py -q`: 5 passed.
  - `pdm run python -m compileall -q src/xenix`: passed.
  - `pdm run pytest`: 304 passed, 3 warnings.

### Parquet Dataset / Data Tool Slice

- Removed Agent-facing `data.peek` from the tool registry, tool presentations, Harness contextual exposure, dev fixtures, skill guidance, durable TDD, and tests.
- Kept `AnalysisProfileService` as service code, but no longer exposes it through `data.peek`.
- `data.query` is now the atomic read-only probing tool. Its schema stays Moonshot-compatible by documenting input-source requirements and `bindings` priority instead of relying on `anyOf`.
- `data.query` success payload stays compact: `columns`, `rows`, `returned_row_count`, and `truncated`; it does not echo inputs or success validation summaries.
- Added `DatasetSourceFormat.PARQUET`, `dataset_import`, `dataset_workbook`, and dataset provenance columns: `import_id`, `workbook_id`, `sheet_name`, and `sheet_index`.
- Dataset import now materializes user CSV/XLS/XLSX inputs into app-owned Parquet files under dataset storage. CSV imports produce one dataset; workbook imports produce one dataset per non-empty sheet.
- Composer attachment registration now returns all datasets produced by a workbook import while preserving first-dataset compatibility for existing call sites.
- Registered dataset consumption moved to app-owned Parquet for query/transform, analysis loaders, cleaning/tokenization, and ML dataset loading.
- `data.transform` now supports bounded multi-statement DuckDB scripts that leave an `output` relation. It allows temp relation mutation while rejecting direct filesystem authority, extension management, permanent DDL, attachment, import, and export statements.
- `data.transform` materializes derived datasets as Parquet only after the output can be read back successfully; failed transforms do not leave durable derived dataset rows or final artifacts.
- ML apply result dataset registration now materializes the result table as an app-owned Parquet dataset instead of treating a CSV output artifact as the registered dataset source of truth.
- Lazy export direction is preserved: internal tools register dataset ids and app-owned Parquet datasets, while explicit export/open/save paths materialize CSV/XLSX only when requested.

### Phase 1 Follow-Up

- Converged ordinary tool results around canonical `result_payload`.
- Removed ordinary `ToolExecutionResult.content_blocks` and `ToolExecutionResult.provider_payload` from the production result contract.
- Harness no longer writes `provider_payload.tool_result` for completed tool calls.
- `ConversationStore` replays completed tool calls from `AgentToolCallRow.result_payload` directly.
- `data.peek` now returns compact `inspection` with `row_count`, `column_count`, coordinate-system text, compact `columns`, and compact `row_windows`.
- `data.peek` no longer returns `structure`, `format`, `sheet`, `layout_evidence`, loader/source/name-source fields, profile markdown, or a separate provider projection.
- Repeated LLM-facing rows now use `_schema` plus `data` arrays for `data.peek` columns and row windows.
- `data.transform` writes transform output to a temp file, validates that output, then moves it to the final transformed dataset path. Failed output validation no longer leaves a final transformed CSV or derived dataset row.
- Agent Harness Unit TDD now records canonical result replay and the compact table pattern.
- Product TDD now records observability/debug/audit material in tool output as an anti-pattern.

### Query/Peek Contract Follow-Up

- `data.query` provider-facing schema now states that callers must provide at least one input source: `bindings` or `dataset_id`.
- `data.query` accepts both `bindings` and `dataset_id`; `bindings` has priority and `dataset_id` is ignored in that case.
- `data.query` success payload now returns only `columns`, `rows`, `returned_row_count`, and `truncated`.
- `data.query` no longer echoes `input_dataset_ids`, `bindings`, `limit`, or `validation_summary` in successful tool results.
- `data.query.columns` and `data.query.rows` use compact `_schema` plus `data` projections.
- `data.peek` now defaults to `analysis=false`, making the default call inspection-only.
- `data.peek.inspection.columns` now includes field `kind` and `nullable` alongside executable name, position, and samples.
- `data.peek.analysis` no longer returns `basic_info` or `field_type_summary`; enabled analysis contains compact descriptive statistics only.

### Follow-Up Design State

- User confirmed `anyOf` is not provider-compatible for Moonshot API. Tool schemas should stay in a conservative JSON Schema subset; priority and conditional requirements belong in descriptions plus execution-time validation.
- Current decision is to delete `data.peek`. The dataset id path remains intact because Composer attachments create dataset content blocks, and Harness collects dataset ids from those blocks before considering prior tool payloads.
- Deleting `data.peek` requires replacing skill guidance that says "start with data.peek" with query-first inspection recipes using `data.query`.
- `AnalysisProfileService` may remain as service code for now, but it should not be exposed through `data.peek`.
- `data.query` should remain read-only and single-purpose.
- `data.transform` should support multi-statement in-memory DuckDB transformation scripts. The preferred contract is an explicit `output` table/view created by the script, with service-owned registration selecting from `output`.
- `data.transform` can allow temporary in-memory writes such as `CREATE TEMP TABLE`, `CREATE TEMP VIEW`, `INSERT`, `UPDATE`, and `DELETE` against DuckDB session objects. It must continue to reject filesystem authority such as `ATTACH`, `COPY`, `EXPORT`, extension install/load, and user-authored direct file scans.
- CSV output validation failure was reproduced as a Polars CSV schema inference issue: Polars default read can infer an integer column from early rows and fail when a later value is `3.8`.
- User challenged whether CSV validation should be fixed tactically or solved by replacing CSV as app-owned dataset storage. Updated direction: treat CSV as an import/export interchange format, not as durable internal dataset storage.
- Parquet should cover both imported datasets and derived datasets, not only `data.transform` outputs. Import should materialize user-managed CSV/XLS/XLSX files into AppData-owned Parquet datasets.
- Workbook import should split sheets into separate dataset records. A workbook is an input file; a dataset is a tabular app-owned result such as one sheet materialized as Parquet.
- This import materialization also improves DuckDB input: tools can bind service-owned Parquet paths directly instead of repeatedly reading user-managed CSV/XLS/XLSX files and re-inferring schema.
- DuckDB input registration decision is now: app-owned Parquet datasets should be read directly by DuckDB from service-owned paths; XLS/XLSX should only appear during ingestion, where Polars/calamine reads each sheet before Parquet materialization. Do not rely on DuckDB Excel extensions for XLS/XLSX in this slice.
- Parquet migration has broader blast radius than a transform-only fix because current storage models only enumerate `csv`, `xlsx`, `xls`, and current services/tests assume `source_path` often points to the user file.
- User confirmed this should not be half-migrated. Current long-term direction is to add explicit import/workbook metadata storage and change `dataset` semantics to one app-owned tabular table, usually Parquet.
- `dataset` should not remain a raw CSV/XLS/XLSX file-centric table. Original file and workbook facts belong to import/workbook records; dataset rows should point to app-owned materialized data.
- User clarified blast radius includes ML Service and model loaders. Long-term correct direction is that all internal work around registered datasets, including ML training/evaluation/apply, consumes Parquet-backed app-owned datasets directly.
- Avoid a permanent conversion compatibility layer such as "registered Parquet dataset -> temporary CSV for ML"; that would preserve the old dataset-as-file assumption and reintroduce inference/type-loss issues.
- User clarified export should be lazy and workbook-oriented. Internal dataset registration should not eagerly create CSV/XLSX exports; export/open/save actions should materialize workbook files on demand from app-owned Parquet datasets.
- Current `DatasetService.export_dataset_copy()` is eager and writes `.csv` or `.xlsx` immediately to a requested destination. Current `ArtifactService` resolves existing files and has no lazy materialization hook, so lazy export needs an explicit service/action contract.
- User SQL must still reference only registered aliases. Service-owned file reads are implementation detail and must not grant the LLM raw filesystem path authority.

### Earlier Phase 1

- Added a thin tabular schema resolver in `src/xenix/services/tabular.py`.
- `tool_name` is now the executable column authority for placeholder, duplicate, empty, and unstable names.
- `data.query` and `data.transform` use the same canonical schema projection.
- CSV query/transform keeps pandas type inference for existing numeric SQL behavior.
- XLS/XLSX query/transform uses Polars/calamine plus a temporary CSV table registered with DuckDB as `all_varchar=true`, avoiding pandas full-read slowness and mixed-type cast failures.

## Verification

- `pdm run python -m compileall -q src/xenix`
  - Result: passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py -q`
  - Result: 24 passed.
- `pdm run pytest tests/test_agent_harness_first_slice.py -q`
  - Result: 19 passed.
- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_data_cleaning.py tests/test_data_tokenization.py -q`
  - Result: 60 passed.
- `pdm run pytest tests/test_ml_execution.py -q`
  - Result: 16 passed.
- `pdm run pytest tests/test_analysis_profile.py tests/test_agent_ai_observability.py tests/test_agent_harness_streaming.py tests/test_main.py tests/test_i18n.py -q`
  - Result: 92 passed.
- `pdm run pytest tests/test_storage_bootstrap.py tests/test_repositories.py -q`
  - Result: 21 passed.
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_lambda.py tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py -q`
  - Result: 67 passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py -q`
  - Result: 26 passed after adding workbook sheet materialization and transform missing-output atomicity coverage.
- `pdm run pytest`
  - Result: 301 passed, 3 warnings.
- `rg -n "data\\.peek" src/xenix docs tests -g "*.py" -g "*.md"`
  - Result: only negative test assertions remain.

- `pdm run pytest`
  - Result: 299 passed, 3 warnings.
- Real XLSX `data.peek` / query smoke after follow-up:
  - Source: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`
  - `data.peek` with `analysis=false` returned payload keys `analysis`, `dataset_id`, and `inspection`.
  - `inspection` keys were `column_count`, `columns`, `coordinate_system`, `row_count`, and `row_windows`.
  - Payload was about 4,517 JSON characters.
  - `columns` used `_schema: {"tool_name": 0, "position": 1, "samples": 2}`.
  - First two executable column rows were `品项销售明细` at position 0 and `column_2` at position 1.
  - `row_windows` used `_schema: {"row": 0, "non_empty": 1, "width": 2, "cells": 3}`.
  - `SELECT "column_2" FROM input LIMIT 3` returned `NULL`, `机构编码`, and `C7`.
- Real XLSX smoke after query/peek contract follow-up:
  - Default `data.peek` returned `analysis: {"enabled": false}`.
  - `inspection.columns._schema` was `{"tool_name": 0, "position": 1, "kind": 2, "nullable": 3, "samples": 4}`.
  - `data.query` returned only `columns`, `rows`, `returned_row_count`, and `truncated`.
  - Query rows used compact `_schema: {"column_2": 0}` and `data: [[null], ["机构编码"], ["C7"]]`.
- `pdm run pytest tests/test_tabular_schema.py tests/test_analysis_profile.py tests/test_data_transform.py tests/test_agent_harness_foundation.py`
  - Result: 32 passed after adding transform atomicity coverage.
- Real XLSX query smoke:
  - Source: `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`
  - SQL: `SELECT "column_23" FROM input LIMIT 5`
  - Result: succeeded in about 25.84s.
  - Rows included `NULL`, `销售数量`, `1`, `2`, `1`.
- Real XLSX `data.peek` smoke:
  - `analysis=false`
  - Result: succeeded in about 24.37s.
  - Structure DSL exposed row 3 as a 50-column dense row and `column_2` / `column_3` canonical names for Polars placeholders.
  - Provider compact payload did not include markdown.
