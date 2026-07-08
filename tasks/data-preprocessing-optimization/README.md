# Data Preprocessing Optimization

## Objective & Hypothesis

Objective: improve Xenix Agent's data preprocessing capability for real-world business spreadsheets, using `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`, Xenix thread `8e844868143140bba7a237a6dcea789c`, and follow-up thread `c1eddca9396c4f3ba18aaa54e8be8805` as diagnostic cases.

Hypothesis: the first valuable slice was not a larger cleaning catalog. It was a stronger executable data-tool contract. The current direction is to delete `data.peek` as a bundled, non-atomic inspection/profile shortcut and make `data.query` plus `data.transform` the primary atomic data understanding and preprocessing tools.

## Input Classification

- Type: `Reality`
- Mode: `Diagnose` moving toward `Solidify`
- Durable owner candidates:
  - Agent Harness provider-facing tool result projection
  - `data.peek` removal and replacement by query-first inspection
  - Thin tabular loader wrapper and column-name consistency
  - Data query/transform error repairability
  - Preprocessing skill/tool guidance

## Active Decisions

- This is an independent task, not part of `ml-service-optimizations`.
- Phase 1 includes `data.peek` structure DSL, Harness provider-facing result compaction, and column-name/loading consistency together.
- Current follow-up decision: delete `data.peek` instead of continuing to refine it.
- Dataset ids do not depend on `data.peek`; the authoritative Agent entrypoint is the dataset content block created by Composer attachment registration, plus any later tool payloads containing `dataset_id` or `input_dataset_ids`.
- `data.query` remains the read-only probing tool and should stay side-effect free.
- `data.transform` should become the durable transformation tool and may support multi-statement in-memory DuckDB scripts, but only service-owned output registration may create durable files/datasets.
- `data.transform` SQL may write to in-memory temporary relations, but must not gain arbitrary local filesystem authority.
- Internal app-owned dataset storage should move away from CSV for both imported datasets and derived datasets. CSV remains an import/export interchange format, not the preferred durable typed dataset storage.
- Preferred direction for app-owned tabular storage is Parquet because Polars and DuckDB can both read/write it directly and preserve column types.
- Dataset import should copy/materialize user-provided data into AppData-owned Parquet datasets instead of keeping user-managed source files as the dataset source of truth.
- Workbook imports should split sheets into separate dataset records, usually one sheet -> one app-owned Parquet dataset.
- DuckDB input decision: app-owned Parquet datasets can be read directly by DuckDB from service-owned paths; XLS/XLSX ingestion stays on the Polars/calamine boundary before Parquet materialization.
- Implementation state: `data.peek` is no longer registered as an Agent-facing tool; registered datasets now materialize into app-owned Parquet on import/derived creation; workbook attachment registration can return multiple dataset content blocks; DuckDB query/transform and ML dataset loading consume Parquet-backed registered datasets.
- Provider-facing spreadsheet structure has one authoritative representation: JSON DSL.
- Agent Harness gives the LLM a reliable real-world interaction base. It does not pre-package human-facing explanation for the LLM.
- Markdown tables or narrative explanations belong in assistant messages authored by the LLM from tool evidence when the user needs them.
- The tool should not decide semantic claims such as which row is "the real header"; it should expose executable structure evidence and coordinates.
- Canonical column names are not stored directly on `dataset` table in Phase 1.
- Canonical column names are deterministic runtime projections from a shared thin loader/schema resolver.
- Loader-specific facts such as `Unnamed: n` and `__UNNAMED__n` must stay inside the loader wrapper boundary.
- Column index is valid as a separate reference channel, but name and index must not be mixed in one ambiguous field.

## File Map

- `evidence.md`: observed real-world failure chain and current code facts.
- `phase-1-scope.md`: first implementation slice.
- `structure-dsl.md`: provider-facing spreadsheet structure DSL.
- `canonical-columns.md`: canonical column reference design.
- `loader-wrapper-boundary.md`: where loader-specific logic belongs.
- `harness-tool-results.md`: Harness responsibility boundary for tool results.
- `source-notes.md`: notes from Polars/pandas docs and local asset scripts.
- `verification.md`: tests and proof obligations.
- `execution.md`: implementation notes and verification results.
- `data-tools-storage-slice-plan.md`: next large data tools/storage slice plan covering `data.peek` removal, query-first inspection, app-owned Parquet import, workbook sheet splitting, DuckDB binding, storage schema cleanup, and `data.transform` multi-statement Parquet output.

## Current Verification

- `pdm run python -m compileall -q src/xenix`: passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py -q`: 24 passed.
- `pdm run pytest tests/test_agent_harness_first_slice.py -q`: 19 passed.
- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_data_cleaning.py tests/test_data_tokenization.py -q`: 60 passed.
- `pdm run pytest tests/test_ml_execution.py -q`: 16 passed.
- `pdm run pytest tests/test_analysis_profile.py tests/test_agent_ai_observability.py tests/test_agent_harness_streaming.py tests/test_main.py tests/test_i18n.py -q`: 92 passed.
- `pdm run pytest tests/test_storage_bootstrap.py tests/test_repositories.py -q`: 21 passed.
- `pdm run pytest tests/test_analysis_graph.py tests/test_analysis_lambda.py tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py -q`: 67 passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py -q`: 26 passed after adding workbook sheet materialization and transform missing-output atomicity coverage.
- `pdm run pytest`: 301 passed, 3 warnings after the final targeted tests were added.
- `rg -n "data\\.peek|data_peek" src/xenix docs tests -g "*.py" -g "*.md" -g "*.json"`: only negative test assertions remain.
- `pdm run pytest`: 302 passed, 3 warnings after LinkRouter / lazy dataset export implementation.
- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_main.py -q`: 157 passed.
- `pdm run pytest tests/test_main.py::test_main_window_opens_service_link_off_ui_thread tests/test_main.py::test_main_window_service_link_activation_failure_closes_progress -q`: 2 passed after service-link activation moved off the UI thread.
- `pdm run pytest tests/test_services.py::test_link_router_lazily_exports_dataset_to_workbook_artifact -q`: 1 passed after preserving lazy export service behavior.
- `pdm run pytest`: 304 passed, 3 warnings after async service-link activation.
- `pdm run pytest tests/test_services.py::test_dataset_service_materializes_manual_apply_csv_and_exports_utf8_by_default tests/test_services.py::test_dataset_service_exports_csv_with_selected_encoding_and_xlsx tests/test_services.py::test_link_router_lazily_exports_dataset_to_workbook_artifact -q`: 3 passed after migrating dataset export to Polars.
- `pdm run pytest tests/test_services.py -q`: 15 passed after migrating dataset export to Polars.
- `pdm run python -m compileall -q src/xenix`: passed after migrating dataset export to Polars.
- `pdm run pytest`: 304 passed, 3 warnings after migrating dataset export to Polars.
- `pdm run pytest tests/test_main.py -q`: 53 passed after making service-link progress non-modal.
- `pdm run pytest tests/test_i18n.py -q`: 5 passed after completing service-link progress i18n.
- `pdm run python -m compileall -q src/xenix`: passed after service-link progress/i18n fix.
- `pdm run pytest`: 304 passed, 3 warnings after service-link progress/i18n fix.

## Active Diagnosis

- 2026-07-08 runtime DB diagnosis for clicked link `artifact://eb1367a427164cf1b9bb29d18cc54df7`:
  - Runtime DB: `C:\Users\yyh\AppData\Local\Xenix\state\xenix.db`, `user_version=14`.
  - `eb1367a427164cf1b9bb29d18cc54df7` exists in `dataset`, not in `artifact`.
  - The actual artifact row for that derived dataset is `1adb63b6cd1249639fe01000f9cb57e7`, with metadata `dataset_id=eb1367a427164cf1b9bb29d18cc54df7`.
  - The final assistant message linked `[4月堂食销售数据_最终清洗版](artifact://eb1367a427164cf1b9bb29d18cc54df7)`, so the user-facing failure is caused by a dataset id being rendered as an artifact URI.
  - The correct artifact currently points directly at the internal app-owned Parquet file under `state/datasets/derived/`, so even the correct artifact link does not satisfy the desired lazy workbook export behavior.
- Refined design direction:
  - UI should not resolve artifact/dataset links directly or call OS file opening with returned paths.
  - A LinkRouter service should own link activation for `artifact://`, `dataset://`, and ordinary external links.
  - `ArtifactService` should own artifact activation/open semantics, including file existence/readiness checks and OS-open behavior for artifact files.
  - Dataset activation/open should go through dataset export materialization first, producing or reusing a workbook export artifact, then delegate opening to `ArtifactService`.
  - Dataset export artifacts remain the unified user-openable representation for datasets; dataset activation must not bypass artifacts or open internal Parquet directly.
  - `artifact://` must remain artifact-id authority only; it must not fall back to dataset lookup.
- Implementation state:
  - `LinkRouter` now owns link activation for `artifact://`, `dataset://`, and ordinary external links.
  - `ArtifactService.activate_uri()` owns artifact readiness/file checks and OS-open behavior.
  - `DatasetExportService` owns `dataset://` activation, lazily materializes/reuses workbook export artifacts, then delegates opening to `ArtifactService`.
  - Dataset-producing tools now return `dataset_uri` and no longer eager-register internal Parquet files as artifact links.
  - The Agent system prompt now explicitly forbids putting `dataset_id` inside `artifact://`.
- New runtime diagnosis:
  - User clicked a `dataset://` link and the UI became unresponsive.
  - Current activation chain is `ThreadDetailView.service_link_activated -> MainWindow._open_service_link -> LinkRouter.activate -> DatasetExportService.activate_uri -> DatasetService.export_dataset_copy -> ArtifactService.activate_uri`.
  - That chain runs synchronously on the Qt UI thread. Large workbook export can block event processing until the export and OS-open call finish.
  - Correct next design: keep `LinkRouter` as the activation owner, but make `MainWindow` run link activation in a background worker for service-owned links, show an indeterminate non-modal progress dialog while activation is pending, close it on completion/failure, and let the service-side activation continue to own OS file opening.
- Implementation state:
  - `MainWindow._open_service_link()` now starts a daemon background activation worker and returns immediately.
  - `MainWindow` shows an indeterminate non-modal progress dialog while service-link activation is pending.
  - Worker success/failure is bridged back to the Qt thread through signals; failure closes progress and renders the error in `ThreadDetailView`.
  - `LinkRouter`, `DatasetExportService`, and `ArtifactService` ownership boundaries are unchanged.
- Export implementation update:
  - `DatasetService.export_dataset_copy()` now reads export source data through Polars and writes CSV/XLSX through Polars.
  - `xlsxwriter` is now a runtime dependency for Polars XLSX export.
  - `csv_encoding` compatibility remains: UTF-8 and UTF-8-BOM stay on direct Polars write paths; other encodings are produced by Polars UTF-8 output followed by streaming transcode.
  - Tests now fail if dataset export regresses to Pandas `DataFrame.to_csv()` or `DataFrame.to_excel()`.
- New UI follow-up diagnosis:
  - The service-link progress surface currently uses `Qt.WindowModal`, which blocks interaction with the main window while background dataset export is running.
  - The intended behavior is non-blocking main-window interaction while export/open continues in the background. The progress surface should be modeless or otherwise non-modal.
  - i18n is incomplete: new service-link progress strings are wrapped in `self.tr(...)`, but the translation catalogs were not extracted/updated/compiled and `MainWindow.retranslate_ui()` does not refresh the progress dialog if it is visible during a language switch.
- Implementation state:
  - Service-link progress now uses `Qt.NonModal`, so the main window remains interactive during background export/open.
  - `MainWindow.retranslate_ui()` refreshes visible service-link progress text.
  - `xenix_en_US.ts`, `xenix_zh_CN.ts`, and compiled `.qm` catalogs include `Opening link...` and `Open Link`; Chinese translations are `正在打开链接...` and `打开链接`.

## Next Step

Run broader UI/i18n verification, then review the final diff for unrelated dirty files before any user-requested commit.
