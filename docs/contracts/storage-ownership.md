# Storage Ownership

## Purpose

Define which local state belongs in SQLite and which belongs on the filesystem.

## SQLite Responsibilities

SQLite is reserved for small, queryable application metadata:

- Task records and status history
- Dataset registration metadata
- Model catalog metadata
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

- Imported or selected dataset files
- Trained model artifacts
- Inference outputs and exported reports
- Application logs
- Cache files and temporary working files

App-managed runtime directories live under `XENIX_APP_HOME` or the platform default returned by `xenix.config`.

## Ownership Rules

- SQLite stores references, summaries, and state.
- The filesystem stores bytes, artifacts, and user-openable outputs.
- Services coordinate both stores and keep references consistent.
- UI code consumes resolved paths from services instead of constructing storage layouts itself.

## Deletion Rules

- Deleting a SQLite row must not silently delete user-managed dataset files.
- Deleting an app-managed artifact should update SQLite metadata in the same service operation.
- Cache cleanup may remove reproducible files, but not canonical datasets, models, or exports.
