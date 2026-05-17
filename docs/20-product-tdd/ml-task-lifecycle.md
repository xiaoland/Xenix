# ML Task Lifecycle

## Purpose

Define the minimum contract for persisted ML task execution such as dataset inspection, training, evaluation, and inference.

This document governs `MLTask` lifecycle semantics. It does not govern task packets under `tasks/<task-slug>/`.

## ML Task Identity

Each persisted ML task must have:

- A stable ML task id
- An ML task type such as `inspect_dataset`, `fit`, `hyperparameter_tuning`, or `inference`
- A created timestamp
- A current status
- A finished timestamp once the ML task reaches a terminal state

SQLite is the default store for ML task metadata.

Current AI-first service contracts are dataset-scoped. Training, hyperparameter training, evaluation, and inference requests carry explicit dataset id, feature columns, target columns, model selection, and run name inputs. Agent Harness tools call these contracts from tool arguments and thread context.

## Status Contract

Allowed status values:

- `pending`: accepted by the service and waiting to start
- `running`: actively executing
- `succeeded`: finished and produced the declared outputs
- `failed`: finished without producing all required outputs
- `cancelled`: stopped by the user or shutdown flow before completion

State transition rules:

- `pending -> running`
- `running -> succeeded`
- `running -> failed`
- `pending -> cancelled`
- `running -> cancelled`

Any other transition requires an ADR or a contract update.

## Logging Contract

Each ML task must write user-relevant execution logs to the application log sink under `paths.logs`.

Minimum guarantees:

- The application log remains append-only for a single process run.
- ML task log entries include the ML task id.
- Failure paths include a human-actionable message, not only a stack trace.

Detailed per-ML-task logs may later use separate files, but the canonical location stays under the runtime `logs/` directory.

When ML task subprocess execution exists, each ML task may also write detailed process logs under `artifacts/ml-tasks/<ml-task-id>/`. Those per-ML-task logs are supplementary. The canonical application log remains under `paths.logs`.

## Result File Contract

ML tasks that produce artifacts must return result metadata that includes:

- Result kind
- Absolute filesystem path
- Whether the file or directory is ready to open

ML tasks surfaced after the original dialog closes, such as inference results shown in history, must preserve enough terminal metadata for later review and export.

Result ownership rules:

- Source dataset registrations may point to user-managed files.
- ML task requests carry explicit dataset, feature column, target column, model selection, and artifact output owner inputs from service contracts.
- App-managed dataset artifacts used by ML tasks are registered through service-owned artifact metadata.
- Generated models, exports, and reports live in service-managed directories on the local filesystem.
- ML task working directories live under `artifacts/ml-tasks/<ml-task-id>/`.
- An ML task reaches `succeeded` only after every declared output path exists.
- ChatBox result presentation flows through markdown summaries and `artifact://...` links registered by services.

## Failure Contract

On failure, services must preserve enough information for local troubleshooting:

- Final ML task status is `failed`
- The last error summary is persisted in ML task metadata
- The main application log contains the matching error context
