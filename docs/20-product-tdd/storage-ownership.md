# Storage Ownership

## Purpose

Define which local state belongs in SQLite and which belongs on the filesystem.

## SQLite Responsibilities

SQLite is reserved for small, queryable application metadata:

- Agent Harness Thread, Turn, Message, tool-call, tool-result, and run records
- Artifact registration metadata and artifact links
- ML task records and status history
- Dataset registration metadata for user-managed source datasets, app-managed derived datasets, and compatibility copies
- User selections and lightweight preferences
- References to files owned by the application
- ML worker pool configuration remains lightweight JSON configuration under `config/`; SQLite does not own worker credentials or remote cache state.

The current implemented AI-first SQLite baseline is schema version `12`. It contains Agent Harness conversation tables, provider request usage records, artifact metadata, dataset metadata, immutable dataset column role bindings, ML task metadata, trained-model metadata, and turn completion guard records. The legacy work item table, `work_item_id` columns, old dataset column-selection table, old inference task values, and old inspect-dataset task rows are outside this baseline.

Agent Thread rows retain the default system prompt text used to seed the first hidden system Message and the selected next-turn LLM `fq_model_key`. Agent Turn rows store the turn sequence and status. Agent Message rows store chronological content blocks, provider payloads, lifecycle status, update timestamps, and finalization timestamps. The first turn stores the hidden system Message before the first user Message. Message kind and UI author are persisted as SQLAlchemy enum member names such as `SYSTEM` and `USER`; message lifecycle statuses are persisted as lowercase enum values such as `in_progress` and `completed`. Provider request rows store input Message ids, output Message ids, provider/model metadata, request status, and token usage payloads. Tool-call rows store execution status, arguments, result payload, and links back to request/result Messages.

ML task type, status, and artifact-kind enum columns persist lowercase enum values such as `fit`, `apply`, `pending`, `succeeded`, and `apply_result`, not Python enum member names such as `FIT` or `APPLY`.

SQLite stays limited to metadata and excludes:

- Full datasets
- Trained model binaries
- Model apply exports
- Large logs
- Binary assets that already exist as files

## Filesystem Responsibilities

The filesystem is the source of truth for large or user-openable artifacts:

- User-selected external import files
- App-owned materialized dataset files under service-managed state directories
- Lazy dataset export artifacts under service-managed artifact directories
- Trained model artifacts
- Model apply outputs and exported reports
- Application logs
- Cache files and temporary working files
- Remote worker caches created through SSH setup are reproducible execution state and not canonical storage.

App-managed runtime directories live under `XENIX_APP_HOME` or the platform default returned by `xenix.config`.

Current app-managed runtime layout includes:

- `state/`
- `temp/`
- `artifacts/`

## Ownership Rules

- SQLite stores references, summaries, and state.
- The filesystem stores bytes, artifacts, and user-openable outputs.
- Services coordinate both stores through persistence interfaces and keep references consistent.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, and run semantics.
- Storage provides persistence interfaces for Agent Harness records.
- UI code activates links through LinkRouter instead of constructing storage layouts, resolving paths, or opening local files itself.
- Dataset registration stores app-owned materialized dataset paths plus stable naming metadata. Composer data attachments enter storage through dataset registration and source import provenance, not through artifact registration.
- Derived dataset registration stores the generated app-owned dataset path and an explicit `derived_from_dataset_id` when one source dataset owns the lineage.
- Query results returned by `data.query` are tool-result payloads by default and do not create dataset rows or artifact rows.
- `data.transform` stores transformed output files under app-owned dataset state directories and registers them as derived datasets.
- Multi-input transforms return input dataset ids in tool results until storage has a first-class multi-parent lineage field.
- `copied_from` is retained for compatibility copy semantics; data cleaning and transformation use derived lineage.
- Dataset inspection metadata such as row counts, inferred column kinds, and previews is runtime-derived and should not be persisted by default.
- Dataset column role binding is stored as immutable metadata. Model outputs and apply outputs are represented by service-owned metadata and artifact records.
- Artifacts are produced durable user-openable outputs such as workbook exports, reports, images, models, apply outputs, and other generated files. Registered datasets are referenced by dataset ids for tool and service inputs, while user-openable dataset outputs are artifact rows.
- Dataset export artifacts are materialized from app-owned datasets by the operation that owns the exported output. The export path uses Polars to read app-owned Parquet and write interchange files; XLSX writing depends on `xlsxwriter`.
- Artifact links activate through `LinkRouter` and `ArtifactService`. Filesystem access stays behind services.
- LLM-facing Agent content, tool schemas, and tool result payloads use dataset ids for registered datasets. Dataset `source_path` values remain internal persistence facts resolved by services.
- Trained-model registration rows are durable metadata pointers to canonical model artifacts.
- Task working files such as `request.json`, `result.json`, `logs.jsonl`, and holdout artifacts are execution-scoped ML task files.
- Remote staging paths may mirror task working files during execution. Services must download and normalize remote outputs to local service-owned paths before registering artifacts or trained-model rows.

## Deletion Rules

- Deleting a SQLite row leaves user-managed dataset files in place.
- Deleting an app-owned dataset file leaves the original import file in place.
- Deleting a derived dataset row leaves its source dataset row and source file in place.
- Deleting an app-managed artifact should update SQLite metadata in the same service operation.
- Cache cleanup may remove reproducible files. Canonical datasets, models, and exports stay under their owning services.
- Deleting ML task working files leaves canonical trained-model artifacts and external dataset source files in place.
