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

SQLite must not store:

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
- Trained-model registration rows are durable metadata pointers to canonical model artifacts, not a duplication of task-owned training payloads.
- Task working files such as `request.json`, `result.json`, `logs.jsonl`, and holdout artifacts are execution-scoped ML task files, not canonical storage.

## Deletion Rules

- Deleting a SQLite row must not silently delete user-managed dataset files.
- Deleting an app-managed dataset artifact must not affect the original external source file.
- Deleting an app-managed artifact should update SQLite metadata in the same service operation.
- Cache cleanup may remove reproducible files, but not canonical datasets, models, or exports.
- Deleting ML task working files must not affect canonical trained-model artifacts or external dataset source files.
