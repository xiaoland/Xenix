# Data Tools Parquet Slice Plan

## Objective

Rebuild the Agent-facing data preprocessing slice around atomic data tools and app-owned typed datasets.

This slice includes the previous `data.peek` removal and `data.transform` optimization work. It should make imported tabular data durable under AppData as Parquet, split workbook sheets into separate dataset records, let data tools bind DuckDB to app-owned dataset files instead of repeatedly reading raw user files, make `data.transform` the durable multi-step transformation tool, and move all internal dataset consumers including ML Service onto the Parquet-backed dataset contract.

Status on 2026-07-08: implementation is in progress and most production changes are landed locally. `data.peek` has been removed from the Agent-facing registry, import and derived datasets materialize to app-owned Parquet, workbook attachment registration can produce multiple datasets, DuckDB data tools read registered Parquet datasets, `data.transform` supports bounded temp-relation scripts with explicit `output`, ML loaders consume Parquet, and dataset activation now uses `dataset://` through LinkRouter plus lazy workbook export artifacts. Full-suite verification is passing; final diff review remains before commit.

## Why This Slice Exists

CSV is acceptable as an interchange format but weak as internal dataset storage:

- it has no durable type schema;
- readers must infer types repeatedly;
- late mixed values such as `3.8` after integer-looking rows can fail CSV parsing;
- it cannot represent workbook sheet boundaries;
- keeping user file paths as dataset truth makes datasets fragile when files move or disappear.

Parquet gives Xenix a typed, app-owned, DuckDB/Polars-readable table representation. Removing `data.peek` and strengthening `data.query` / `data.transform` keeps the Agent tool surface more atomic: query for evidence, transform for durable derived data, graph/model from registered datasets.

## Current Code Evidence

Dataset and export:

- `DatasetService.register_dataset()` currently validates a user-managed source path and stores that path directly on `DatasetRow.source_path`.
- `DatasetService.register_dataset_attachment()` registers one dataset for one input file and then returns lightweight attachment metadata.
- `DatasetService.export_dataset_copy()` is eager: it reads `dataset.source_path` and immediately writes `.csv` or `.xlsx` to a caller-provided absolute destination.
- `ArtifactService.register_artifact()` requires an existing absolute path. Artifact resolution opens existing files; there is no lazy materialization hook.

ML:

- `MLService.fit_with_evaluate()` and `tune_with_evaluate()` pass `context.dataset.source_path` into task request `dataset_source_path`.
- `MLService.apply()` passes the trained dataset path plus `input_files[].absolute_path`; registered dataset input sources are resolved to file paths before task creation.
- `src/xenix/services/ml/dataset_loader.py` is the shared ML loader and currently supports only `.csv`, `.xlsx`, and `.xls` for dataset inputs.
- SSH worker path staging already rewrites `dataset_source_path` and `absolute_path`, so Parquet paths should fit the existing staging shape.

Eager CSV producers:

- `data.integrate` writes `artifacts/datasets/integrated/*.csv`.
- `data.clean` writes `artifacts/datasets/cleaned/*.csv` when operations are present.
- `data.tokenize` writes `artifacts/datasets/tokenized/*.csv`.
- `data.transform` writes `artifacts/datasets/transformed/*.csv`.
- `model.apply` writes CSV outputs and may register apply-result datasets from those outputs.
- `analysis.lambda` DataFrame artifacts are CSV, but `analysis.lambda` is not currently exposed to providers.

## Scope

In scope:

- delete `data.peek` from the Agent-facing registry and replace its guidance with query-first inspection;
- keep `data.query` as the read-only, bounded probing tool and ensure its provider-facing schema stays Moonshot-compatible without `anyOf` / `oneOf`;
- preserve compact `data.query` result shape: `columns`, `rows`, `returned_row_count`, `truncated`, with schema-plus-rows representation;
- optimize `data.transform` into the durable transformation tool with bounded multi-statement in-memory SQL and explicit output semantics;
- add an app-owned dataset materialization path under AppData;
- import `.csv`, `.xlsx`, and `.xls` into app-owned Parquet files;
- split workbook imports into one dataset per sheet;
- keep original user file path as provenance, not the execution source of truth;
- update `data.query`, `data.transform`, `analysis.graph`, cleaning/tokenization/model paths as needed to read dataset `source_path` as app-owned Parquet;
- update ML Service and model dataset loaders to consume Parquet-backed registered datasets directly, not through a long-lived CSV conversion compatibility layer;
- make `data.transform` write derived Parquet datasets;
- make user-facing dataset export lazy and workbook-oriented: internal tools should not eagerly create export files unless the user opens/saves/requests them;
- save exported tabular data to workbook files by default, with CSV only as an explicit interchange option where still needed;
- update product TDD, Agent Harness TDD, skills, dev fixtures, AIMock fixtures, and tests to the new tool/storage contract.

Out of scope for this slice:

- hostile SQL sandboxing beyond existing local tool trust boundaries;
- DuckDB Excel extension usage;
- automatic semantic header detection;
- generalized multi-table workbook relationship inference;
- preserving CSV as an internal ML/training interchange layer;
- migrating historical datasets already registered in existing local user DBs, unless a deliberately bounded one-time migration or legacy compatibility policy is chosen.

## Target Model

Definitions:

- **Import file**: user-managed file selected or dropped by the user. It may be CSV/XLS/XLSX.
- **Dataset**: one app-owned tabular table stored under AppData, preferably Parquet.
- **Workbook**: an import file that may produce multiple datasets, one per sheet.
- **Provenance**: metadata that records original file path, file name, workbook sheet name/index, and import time.

Dataset row should point to the app-owned materialized file for execution. The original file path should not be the normal execution source.

## Storage Shape

Candidate AppData layout:

```text
AppData/
  datasets/
    imported/
      <dataset_id>.parquet
    derived/
      <dataset_id>.parquet
```

Open question: whether generated path needs the dataset id before row creation. If row id is generated by application code before insert, use `<dataset_id>.parquet`; otherwise use a temporary import id and update after row creation.

## Storage Metadata

The clean long-term direction is to separate import-file/workbook metadata from dataset metadata.

Current `dataset` schema is file-centric: `source_path` can point to user-managed `.csv`, `.xlsx`, or `.xls`; `source_format` describes the raw file; and `copied_from` points back to another dataset. After app-owned Parquet import, that meaning is wrong. A dataset should mean "one app-owned tabular table", not "the uploaded file".

Proposed storage owners:

- `data_import` or `dataset_import`: one user import action / original file.
  - original file path;
  - original file name;
  - original source format (`csv`, `xlsx`, `xls`);
  - file size / hash if cheap enough;
  - import status;
  - created/imported time;
  - optional project/thread provenance.
- `workbook` or `dataset_workbook`: metadata for workbook-like imports when relevant.
  - import id;
  - workbook sheet count;
  - parser/engine metadata;
  - optional workbook-level warnings.
- `dataset`: one app-owned tabular table.
  - app-owned materialized path;
  - materialized format, normally `parquet`;
  - row count;
  - column count;
  - display name;
  - import id / workbook id / sheet index / sheet name when imported from a workbook;
  - derived-from dataset id for tool-created datasets;
  - created/updated time.

Likely enum/storage changes:

- add `DatasetSourceFormat.PARQUET`, or rename the field toward `storage_format` / `materialized_format`;
- rename or semantically re-document `DatasetRow.source_path` as app-owned materialized path;
- replace file-provenance overloads in `DatasetRow` with explicit import/workbook references;
- reconsider `copied_from`: if it means "copied from another dataset", keep it dataset-to-dataset only; do not use it for raw user file provenance.

This expands blast radius, but avoids a half-migrated model where a dataset sometimes means a raw workbook and sometimes means a materialized table.

## Import Semantics

CSV:

1. Read with Polars.
2. Resolve canonical column names through the shared tabular schema resolver.
3. Write app-owned Parquet.
4. Register one dataset.

XLS/XLSX:

1. Read workbook sheet list through Polars/calamine-capable path or direct calamine-compatible reader.
2. For each non-empty sheet:
   - load sheet into a table;
   - resolve canonical column names;
   - write app-owned Parquet;
   - register one dataset with sheet provenance.
3. Return all dataset attachments to the composer/user-message path.

Open question: current `polars.read_excel(..., engine="calamine")` usage reads active/default sheet. Need verify exact API for sheet enumeration and per-sheet load before implementation.

## DuckDB Binding

Data tools should bind registered datasets by app-owned source format:

- Parquet: service creates temp table or view from `read_parquet(?)` using service-owned path parameter.
- CSV legacy compatibility: service can still read registered CSV paths with `read_csv(..., all_varchar=true)` or through a compatibility loader.
- XLS/XLSX legacy compatibility: only for old rows; new imports should not leave XLS/XLSX as dataset execution source.

LLM-authored SQL must reference only aliases, never raw paths.

## Internal Dataset Consumers

The Parquet contract should apply to every service whose input is a registered dataset:

- data query/transform;
- analysis graph/profile-like services if retained;
- data cleaning;
- data tokenization;
- feature selection and role binding;
- ML training, hyperparameter tuning, evaluation, and apply workflows;
- model-family-specific loaders under `src/xenix/services/ml/`.

Long-term rule: registered dataset consumption should use the app-owned materialized dataset path and support Parquet natively. Avoid adding a permanent "convert Parquet to CSV for ML" bridge, because that would keep the old file-centric dataset assumption alive and reintroduce type inference issues.

Temporary migration helpers are acceptable only when tightly scoped, named as transitional, and removed or retired by a tracked follow-up.

## Lazy Export Contract

Internal dataset storage is Parquet; user-facing export is a view/materialization over a dataset.

Export should be lazy:

- registering a dataset should not eagerly create a CSV/XLSX export copy;
- tool results should return dataset ids and artifact ids for app-owned dataset records, not pre-rendered workbook files unless the operation explicitly creates a user-facing report/export;
- opening or saving a dataset export should materialize an export file on demand;
- the default export format should be workbook (`.xlsx`) so one or more related datasets/sheets can be saved together;
- CSV remains an explicit interchange option, not the default internal or lazy export format.

Workbook export semantics:

- one dataset export -> one workbook with one sheet;
- workbook import group export -> one workbook with one sheet per imported dataset;
- derived dataset family export may later support one workbook with source/derived sheets, but this is optional.

Current evidence:

- `DatasetService.export_dataset_copy()` eagerly loads `dataset.source_path` and writes `.csv` or `.xlsx` to the requested destination.
- `ArtifactService` resolves already-existing files and has no lazy materialization hook.

Likely owner changes:

- add a service-level `DatasetExportService` or extend `DatasetService` with lazy workbook materialization methods;
- represent lazy export intent as dataset id(s) plus format, not as an existing artifact path;
- if artifacts are used for lazy exports, add an artifact kind/metadata contract that can resolve by materializing before open, or keep export outside artifact resolution and trigger it from explicit UI save/export actions.

Initial preference:

- Do not make `ArtifactService.resolve_uri()` secretly materialize exports in the first slice.
- Use explicit UI/service export actions keyed by dataset id or dataset group id.
- Preserve artifact links as "open existing file" until a materializable artifact contract is designed.

## Tool Surface Contract

`data.peek` is removed from the Agent-facing registry.

`data.query` remains:

- read-only;
- bounded;
- non-materializing;
- compatible with conservative provider JSON Schema subsets;
- the primary query-first inspection and profiling tool.

`data.transform` becomes:

- materializing;
- allowed to run bounded multi-statement in-memory scripts;
- responsible for producing app-owned Parquet derived datasets.

## `data.transform` Script Contract

`data.query` remains read-only and bounded.

`data.transform` may support multi-statement in-memory scripts.

Preferred transform contract:

- registered inputs are bound as aliases;
- SQL may create or mutate in-memory temp tables/views;
- SQL must leave a final relation named `output`;
- service materializes `SELECT * FROM output` to app-owned Parquet;
- durable dataset/artifact registration happens only after output Parquet validates.

Allowed statement families candidate:

- `SELECT`;
- `WITH`;
- `CREATE TEMP TABLE`;
- `CREATE TEMP VIEW`;
- `INSERT`;
- `UPDATE`;
- `DELETE`.

Rejected statement families:

- `ATTACH`, `DETACH`;
- `COPY`, `EXPORT`, `IMPORT`;
- `INSTALL`, `LOAD`;
- direct file scan functions in user SQL;
- persistent `CREATE TABLE` without `TEMP`;
- extension or pragma mutation unless explicitly whitelisted later.

## `data.peek` Removal

Delete from Agent-facing registry:

- `_build_data_peek_tool`;
- `_data_peek`;
- peek-only helper methods;
- provider exposure references;
- skill instructions that require `data.peek`.

Keep or defer:

- `AnalysisProfileService` can remain service code until a replacement profiling product surface is decided.
- Historical `data.peek` tool-call rows can render through generic Chatbot tool projection.

Replacement guidance:

- use dataset attachment metadata for initial dataset id and basic file shape;
- use `data.query` recipes for schema preview, sample rows, missingness, type checks, and descriptive statistics;
- use `data.transform` only when a durable derived dataset is needed.

## Migration Strategy

Preferred implementation order:

1. Update docs/task packet to define the full data-tool/storage contract.
2. Add storage schema migrations for import/workbook/dataset semantics.
3. Add Parquet source/materialized format and tabular loader support.
4. Delete `data.peek` from tool registry and migrate skills/tests toward query-first inspection.
5. Add app-owned import materialization for CSV.
6. Add workbook sheet splitting for XLS/XLSX.
7. Update dataset attachment registration to return one or more registered dataset attachments.
8. Update data tools to read Parquet datasets.
9. Make `data.transform` support bounded multi-statement scripts and write Parquet.
10. Update analysis/cleaning/tokenization paths that consume registered dataset source files.
11. Update ML Service contracts and model dataset loaders to read Parquet-backed registered datasets directly.
12. Replace eager dataset export assumptions with lazy workbook materialization.

Compatibility:

- Existing test fixtures and old local rows may still point at CSV/XLS/XLSX. Decide whether to migrate local rows to the new schema or keep a narrow legacy compatibility shim; avoid silently treating old raw workbooks as new app-owned datasets.
- ML output artifacts may remain CSV when they are user-facing exports or model reports. The required change is ML input dataset consumption, not every exported artifact format.
- Inline `model.apply` rows and external apply files are not necessarily registered datasets. They may need a transient materialization path, but registered dataset ids should resolve to app-owned Parquet.

## Verification

Minimum tests:

- provider tool specs no longer include `data.peek`;
- skills no longer instruct the model to call `data.peek`;
- `data.query` remains available after dataset attachment and returns compact rows;
- CSV attachment registers an app-owned Parquet dataset and records original file provenance.
- XLSX attachment with two sheets registers two datasets with distinct sheet provenance.
- Moving/deleting the original import file after registration does not break `data.query`.
- `data.query` reads app-owned Parquet through DuckDB and returns compact rows.
- `data.transform` multi-statement script creates `output` and registers a Parquet derived dataset.
- `data.transform` failure before validation leaves no final Parquet and no derived dataset row.
- ML training can consume an imported Parquet dataset without converting it through CSV.
- ML apply can consume a registered Parquet input dataset.
- Dataset export is lazy: no workbook file exists until an export/open/save action asks for one.
- Default dataset export materializes an `.xlsx` workbook from Parquet-backed dataset(s).
- `tests/test_ml_execution.py` covers Parquet registered dataset training and apply.
- `tests/test_ml_workers.py` covers local/SSH task path staging for Parquet inputs.
- `tests/test_services.py` covers Parquet registration, inspection, and lazy workbook export.
- UI tests cover workbook save action delegation to service code without UI parsing data files.

Smoke:

- Import `tasks/ml-service-optimizations/assets/4月堂食销售数据.xlsx`.
- Confirm each relevant sheet becomes a dataset.
- Run `data.query` against the imported Parquet dataset.
- Run a multi-statement `data.transform` that creates `output`.

## Risks

- Broad test churn because many tests assume a single attachment maps to one dataset.
- UI attachment flow may need to display multiple datasets produced by one workbook.
- Storage migration may need a compatibility path for existing local DB rows.
- Polars Excel sheet enumeration API needs verification before coding.
- Parquet write support may require optional dependency behavior checks in packaged builds.
- ML, cleaning, tokenization, and analysis services currently have pandas CSV/Excel assumptions; they need native registered-dataset Parquet loading. A permanent CSV compatibility boundary would undercut the purpose of this slice.
- Existing artifact links assume resolved artifacts point at existing files. Lazy export needs either an explicit export action path or a materializing artifact resolver; mixing lazy export into ordinary artifact resolution without a contract would be brittle.
