# ML Task Lifecycle

## Purpose

Define the minimum contract for persisted ML task execution such as dataset inspection, training, evaluation, and model apply.

This document governs `MLTask` lifecycle semantics. It does not govern task packets under `tasks/<task-slug>/`.

## ML Task Identity

Each persisted ML task must have:

- A stable ML task id
- An ML task type such as `inspect_dataset`, `fit`, `hyperparameter_tuning`, or `apply`
- A created timestamp
- A current status
- A finished timestamp once the ML task reaches a terminal state

SQLite is the default store for ML task metadata.

Current AI-first service contracts are dataset-scoped and analyzer-scoped. A model is a reusable analyzer: a service-owned artifact trained from declared input roles and later applied to compatible input roles.

Column-role binding is first persisted as an immutable binding snapshot. Training and hyperparameter training tools pass `binding_id`; ML task requests expand that reference into explicit dataset id, role bindings, model selection, parameters, and run name inputs before execution. Supervised feature/target labels are derived from role bindings when needed for display or adapter compatibility, but they are not a second persistent contract.

Apply tasks use the trained model metadata as the apply-role contract. New service and Agent contracts use `apply`, not `inference`. Legacy persisted task rows or tests that use `inference` are migration inputs only.

## Role Binding Contract

Dataset column role bindings must be persisted as service-owned records before training starts.

Each binding record must include:

- A stable binding id
- Dataset id
- Role binding payload
- Optional model key
- Optional model family
- Optional model task kind
- Schema version
- Created timestamp

The canonical storage table is `dataset_column_binding`. The old `dataset_column_selection` table is a migration source and must not be used as the forward contract.

Role binding rules:

- Every bound column must exist in the registered dataset inspection.
- Required roles must be present before a model can train.
- Single-column roles bind exactly one column.
- Many-column roles bind one or more columns unless the role schema marks them optional.
- Model catalog metadata owns the train-role schema and apply-role schema used for validation.

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

## Result Artifact Contract

ML tasks that produce artifacts must return result metadata that includes:

- Result kind
- Artifact kind
- Absolute filesystem path when the artifact is file-backed
- Preview kind when the artifact can be previewed in Chatbot
- Whether the file or directory is ready to open

ML tasks surfaced after the originating Chatbot turn closes, such as apply results shown in history, must preserve enough terminal metadata for later review and export.

Result ownership rules:

- Source dataset registrations may point to user-managed files.
- ML task requests carry expanded dataset, role binding, model selection, parameters, and artifact output owner inputs from service contracts.
- App-managed dataset artifacts used by ML tasks are registered through service-owned artifact metadata.
- Generated models, exports, and reports live in service-managed directories on the local filesystem.
- ML task working directories live under `artifacts/ml-tasks/<ml-task-id>/`.
- An ML task reaches `succeeded` only after every declared output path exists.
- Chatbot result presentation flows through markdown summaries and `artifact://...` links registered by services.

## Failure Contract

On failure, services must preserve enough information for local troubleshooting:

- Final ML task status is `failed`
- The last error summary is persisted in ML task metadata
- The main application log contains the matching error context
