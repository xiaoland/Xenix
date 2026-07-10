# Data Preprocessing Optimization

## Dashboard

Objective: make Xenix's Agent-facing data preprocessing reliable on messy business spreadsheets by replacing bundled inspection shortcuts with atomic query/transform tools, app-owned Parquet datasets, explicit export artifacts, and clear link activation boundaries.

Latest implementation commit: `7b6a603 Replace lazy dataset links with eager export artifacts`.

Current implementation slice: `11-xenix-table-text-tool-results` is locally verified and uncommitted. `09-deferred-attachment-import-after-send` and `10-preprocessing-runtime-isolation` also remain locally verified and uncommitted.

Current mode: implementation locally verified; waiting for next instruction. The previous committed slice is `08-eager-derived-export-artifacts`; deferred attachment import, preprocessing runtime isolation, and Xenix Table Text replay are local uncommitted work.

Important target change after commit `7b6a603`: lazy dataset export has been removed. The next target is deferring source workbook/CSV import until after the user clicks Send, so large file import no longer blocks message submission.

Latest implementation change: Agent-facing tabular tool results now use Xenix Table Text, a YAML-style metadata block plus Markdown table or records block. Xenix Table Text is only an AgentHarness provider-facing projection, not a service/tool output format. This supersedes compact JSON `_schema` plus `data` for LLM-facing tabular responses such as `data.query` and generated dataset previews.

## Current State

- `data.peek` is removed from the Agent-facing tool surface.
- `data.query` is the bounded, read-only probing tool. Current local code keeps compact structured `result_payload` but AgentHarness provider replay renders it as Xenix Table Text with exact `total_row_count`.
- Generated dataset-producing `data.*` tools return an `inspection` preview table. AgentHarness provider replay renders that preview as Xenix Table Text while preserving scalar ids, row counts, and operation summaries in the metadata prefix.
- `data.transform` creates durable derived datasets from bounded DuckDB scripts that leave an `output` relation.
- Imported and derived registered datasets are app-owned Parquet tables under AppData state.
- Workbook imports can split non-empty sheets into separate dataset rows.
- Internal dataset consumers, including ML loaders, can consume Parquet-backed registered datasets.
- Current local code: generated dataset-producing tools create the corresponding workbook export artifact before returning, then return `dataset_id` plus `artifact_id`.
- Tools do not return `artifact_uri`; the System Prompt owns the `artifact://<artifact_id>` link format and explains that artifacts are user-openable/previewable business outputs.
- Service-owned link activation runs off the Qt UI thread with a non-modal, i18n-aware progress surface.
- Current local code registers Composer attachments as source artifacts, renders an optimistic user message immediately on Send, and lets AgentHarness import source artifacts into datasets before the first durable user turn, AgentRun, or provider request.
- Target UserMessage presentation is workbook/file-level only; imported sheet datasets are provider/tool context, not visible UserMessage chips.
- Target Composer attachment behavior registers the source workbook/file with `ArtifactService` immediately; clicks open through `ArtifactService`.
- Target failure behavior restores the original user text and source attachments to Composer and shows a message-list error item.
- Current local code dispatches `data.transform` and `data.clean` full-data execution through a local preprocessing worker subprocess.
- Current local code dispatches generated dataset registration and eager workbook export artifact creation through the preprocessing worker boundary.
- `data.transform` writes the final DuckDB `output` relation directly to Parquet instead of fetching the full output into Pandas.
- `data.clean` writes derived cleaning output as Parquet; existing Pandas operation semantics are preserved inside the worker process.

## Control Files

- `protocol.md`: packet-local working rules for future sub-tasks.
- `ledger/decisions.md`: durable decisions consumed by all sub-tasks.
- `ledger/open-questions.md`: unresolved questions, owners, and blocking level.
- `ledger/verification.md`: latest authoritative verification and historical verification index.
- `ledger/change-map.md`: durable owners and blast radius map.
- `ledger/canonical-columns.md`: column identity and executable-name decision memo.
- `ledger/loader-wrapper-boundary.md`: loader/schema resolver boundary memo.
- `ledger/tool-results-boundary.md`: canonical tool result boundary memo.
- `workstreams/*/packet.md`: one focused sub-task per folder.
- `evidence/`: runtime evidence and source notes.
- `archive/`: historical plans/logs that no longer define current state.

## Workstreams

| Workstream | Status | Purpose |
| --- | --- | --- |
| `01-query-first-data-tools` | verified | Remove `data.peek`; make `data.query` the atomic probing surface. |
| `02-parquet-dataset-storage` | verified | Materialize imports and derived datasets as app-owned Parquet. |
| `03-transform-sql-contract` | verified | Support bounded multi-statement transform scripts with atomic registration. |
| `04-ml-parquet-consumption` | verified with follow-up risk | Move registered-dataset ML paths to Parquet without a permanent CSV bridge. |
| `05-lazy-export-link-router` | superseded | Historical committed slice: LinkRouter plus lazy `dataset://` export. |
| `06-ui-service-link-progress` | verified | Keep dataset/artifact activation off the UI thread with non-modal progress. |
| `07-docs-skills-fixtures` | verified, ongoing | Keep durable docs, skills, fixtures, and i18n aligned with the new contract. |
| `08-eager-derived-export-artifacts` | committed | Globally remove `dataset://` and create synchronous export artifacts for derived datasets. |
| `09-deferred-attachment-import-after-send` | locally verified; uncommitted | Move source file import from UI preflight to AgentHarness turn startup after Send. |
| `10-preprocessing-runtime-isolation` | locally verified; uncommitted | Keep large `data.transform` / `data.clean` execution, derived dataset registration, and eager export out of the desktop process. |
| `11-xenix-table-text-tool-results` | locally verified; uncommitted | Replace Agent-facing tabular JSON replay with AgentHarness-owned Xenix Table Text for `data.query` and generated dataset previews. |

## Latest Verification

- Workstream `11-xenix-table-text-tool-results`: formatter, data query/transform, generated preview replay, clean/tokenize, Harness foundation/first-slice/streaming/observability tests passed; targeted compileall passed.
- Workstream `10-preprocessing-runtime-isolation`: compileall passed; focused preprocessing worker, transform, cleaning, tokenization, analysis, export, and Harness tests passed; combined affected test run passed 116 tests; `git diff --check` passed.
- Workstream `09-deferred-attachment-import-after-send`: compileall passed; 5 focused UI/Harness tests, 53 UI tests, and 52 Harness/streaming/observability tests passed; `git diff --check` passed.
- Commit `7b6a603 Replace lazy dataset links with eager export artifacts`: `compileall` passed and 100 affected tests passed; see `ledger/verification.md`.
- Earlier full-suite baseline after `542561f`: `pdm run python -m pytest -q`, 304 passed, 3 sklearn warnings in 271.21s.

See `ledger/verification.md` for details and historical runs.

## Next Step

Run final diff checks if preparing a commit; otherwise continue with the next data-preprocessing subtask.
