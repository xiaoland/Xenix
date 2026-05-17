# Storage Ownership

## Purpose

Define which local state belongs in SQLite and which belongs on the filesystem.

## SQLite Responsibilities

SQLite is reserved for small, queryable application metadata:

- Agent Harness Thread, Turn, Message, tool-call, tool-result, and run records
- Artifact registration metadata and artifact links
- ML task records and status history
- Dataset registration metadata for both user-managed source datasets and app-managed dataset copies
- User selections and lightweight preferences
- References to files owned by the application

The current AI-first SQLite baseline is schema version `1`. It contains Agent Harness conversation tables, artifact metadata, dataset metadata, ML task metadata, and trained-model metadata. The legacy work item table and `work_item_id` columns are outside this baseline.

Agent Thread rows store the thread-level system prompt. Agent Turn rows store the turn sequence and status. Agent Message rows store chronological content blocks and provider payloads. Tool-call rows store execution status, arguments, result payload, and links back to request/result Messages.

SQLite stays limited to metadata and excludes:

- Full datasets
- Trained model binaries
- Prediction exports
- Large logs
- Binary assets that already exist as files

## Filesystem Responsibilities

The filesystem is the source of truth for large or user-openable artifacts:

- User-selected external dataset files
- App-managed dataset artifacts under service-managed dataset artifact directories
- Trained model artifacts
- Inference outputs and exported reports
- Application logs
- Cache files and temporary working files

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
- UI code consumes resolved paths from services instead of constructing storage layouts itself.
- Source dataset registration stores the external source path and stable naming metadata.
- Dataset inspection metadata such as row counts, inferred column kinds, and previews is runtime-derived and should not be persisted by default.
- Feature/target selection, model outputs, and prediction outputs are represented by tool results and artifact metadata in the first AI-first slice.
- Artifact links resolve through `ArtifactService`; ChatBox receives an artifact id and view hint, while filesystem access stays behind services.
- Trained-model registration rows are durable metadata pointers to canonical model artifacts.
- Task working files such as `request.json`, `result.json`, `logs.jsonl`, and holdout artifacts are execution-scoped ML task files.

## Deletion Rules

- Deleting a SQLite row leaves user-managed dataset files in place.
- Deleting an app-managed dataset artifact leaves the original external source file in place.
- Deleting an app-managed artifact should update SQLite metadata in the same service operation.
- Cache cleanup may remove reproducible files. Canonical datasets, models, and exports stay under their owning services.
- Deleting ML task working files leaves canonical trained-model artifacts and external dataset source files in place.
