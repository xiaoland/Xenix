# Data Preprocessing Optimization

## Dashboard

Objective: make Xenix's Agent-facing data preprocessing reliable on messy business spreadsheets by replacing bundled inspection shortcuts with atomic query/transform tools, app-owned Parquet datasets, explicit export artifacts, and clear link activation boundaries.

Latest implementation commit: `542561f Refine dataset tools and lazy exports`.

Current uncommitted slice: `08-eager-derived-export-artifacts` removes lazy dataset links and creates export artifacts during dataset-producing tool completion.

Current mode: ongoing program workspace. The main implementation slice is committed; future work should be tracked as focused sub-tasks under `workstreams/`.

Important target change after commit `9d0de57`: lazy dataset export is no longer the desired product behavior. The current local implementation removes lazy dataset activation and replaces derived dataset completion with eager export artifact creation; this slice is not committed yet.

## Current State

- `data.peek` is removed from the Agent-facing tool surface.
- `data.query` is the bounded, read-only probing tool and returns compact `_schema` plus `data` table shapes.
- `data.transform` creates durable derived datasets from bounded DuckDB scripts that leave an `output` relation.
- Imported and derived registered datasets are app-owned Parquet tables under AppData state.
- Workbook imports can split non-empty sheets into separate dataset rows.
- Internal dataset consumers, including ML loaders, can consume Parquet-backed registered datasets.
- Current local code: generated dataset-producing tools create the corresponding workbook export artifact before returning, then return `dataset_id` plus `artifact_id`.
- Tools do not return `artifact_uri`; the System Prompt owns the `artifact://<artifact_id>` link format and explains that artifacts are user-openable/previewable business outputs.
- Service-owned link activation runs off the Qt UI thread with a non-modal, i18n-aware progress surface.

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
| `08-eager-derived-export-artifacts` | implemented, focused verification passed | Globally remove `dataset://` and create synchronous export artifacts for derived datasets. |

## Latest Verification

- `pdm run python -m pytest -q`: 304 passed, 3 sklearn warnings in 271.21s.
- `git commit`: `542561f Refine dataset tools and lazy exports`.
- Current uncommitted slice verification: `compileall` passed and 100 affected tests passed; see `ledger/verification.md`.

See `ledger/verification.md` for details and historical runs.

## Next Step

Run broader regression if needed, then prepare a focused commit only after explicit commit instruction.
