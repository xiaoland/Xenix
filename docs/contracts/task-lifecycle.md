# Task Lifecycle

## Purpose

Define the minimum contract for background work such as dataset inspection, training, and inference.

## Task Identity

Each service-managed task must have:

- A stable task id
- An ML task type such as `inspect_dataset`, `fit`, `hyperparameter_tuning`, or `inference`
- A created timestamp
- A current status

SQLite is the default store for task metadata once task persistence is implemented.

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

Each task must write user-relevant execution logs to the application log sink under `paths.logs`.

Minimum guarantees:

- The application log remains append-only for a single process run.
- Task log entries include the task id once task execution exists.
- Failure paths include a human-actionable message, not only a stack trace.

Detailed per-task logs may later use separate files, but the canonical location stays under the runtime `logs/` directory.

When ML task subprocess execution exists, each task may also write detailed process logs under `artifacts/ml-tasks/<ml-task-id>/`. Those per-task logs are supplementary. The canonical application log remains under `paths.logs`.

## Result File Contract

Tasks that produce artifacts must return result metadata that includes:

- Result kind
- Absolute filesystem path
- Whether the file or directory is ready to open

Result ownership rules:

- Datasets selected by the user stay in user-managed locations.
- Generated models, exports, and reports live in service-managed directories on the local filesystem.
- ML task working directories live under `artifacts/ml-tasks/<ml-task-id>/`.
- A task is not `succeeded` until every declared output path exists.

## Failure Contract

On failure, services must preserve enough information for local troubleshooting:

- Final task status is `failed`
- The last error summary is persisted in metadata once task storage exists
- The main application log contains the matching error context
