# L1 Plan 01: Architecture

## Scope Boundary

Issue `#72` should deliver the first usable native ML training capability, not the full end-state ML product.

In scope:

- dataset selection from registered datasets
- dataset column inspection needed for training setup
- manual training with single-model parameter editing
- hyperparameter tuning with multi-model selection and editable param grids
- evaluation as a distinct atomic ML operation chained after `fit`
- ML task status, logs, summaries, and failure visibility
- trained-model persistence and best-model tracking

Out of scope:

- inference execution
- prediction export flows
- generic workflow engine infrastructure
- exhaustive support for every legacy model under `./ml`

## Native Product Flow

The intended native business flow is:

1. user selects a registered dataset
2. app reads dataset columns from the dataset source file
3. user selects an ML mode:
   - manual training
   - hyperparameter tuning
4. user selects one or more supported models
5. app renders parameter editors from model schemas
6. user selects target/feature columns if the chosen model requires a target column
7. app submits an ML task
8. task execution performs:
   - task-local dataset copy
   - fit
   - evaluation
   - artifact persistence inside the task directory
9. main process persists summaries, trained-model metadata, and best-model updates
10. UI renders task state, logs, summary, and failures

Important interpretation:

- target selection is conditional, not universal
- supervised models require target selection
- unsupervised models do not require a target column
- evaluation remains a distinct atomic ML operation even when automatically chained after fit

## Layer Strategy

Use the existing native boundary model:

- `UI`
  - Qt Widgets view state
  - no direct ML invocation
  - no direct SQLite or filesystem policy logic
- `ml service`
  - validates requests
  - inspects datasets
  - creates and transitions ML tasks
  - prepares task working directories
  - launches ML task execution
  - persists trained-model metadata and best-model updates
- `ML model services / adapters`
  - code-owned model definitions
  - normalized dataset loading
  - fit, tune, and evaluate behavior behind a native contract
- `persistence`
  - SQLite repositories and migrations
- `filesystem runtime`
  - task directories
  - model artifacts
  - per-task logs and result files

Allowed dependency direction:

`UI -> ml service -> repositories + filesystem + ML model services`

## Execution Strategy

Use task-scoped background execution so long-running ML work does not block the UI thread.

Preferred L1 direction:

- launch ML execution in a separate Python worker process per task
- justify this primarily by UI responsiveness, task atomicity, and clean task-local working directories
- do not justify it primarily by heavy dependency isolation

This choice fits the current branch because:

- ML task execution needs a natural ownership boundary for logs, working files, and final result files
- task-local execution makes it easier to lock execution state around one task id
- task-local execution avoids filename collisions and extra mapping state for copied datasets

## State Ownership

The main process remains authoritative for:

- task creation
- task status transitions
- final success/failure decision
- trained-model metadata persistence
- best-model updates on the work item
- exposing task list and task detail data to the UI

Task execution owns only:

- dataset copy into the task working directory
- fit, tune, and evaluate execution
- writing structured per-task logs
- writing result files and model artifacts into the task directory

This preserves the branch's service boundary and keeps SQLite mutations centralized.

## Dataset Copy Boundary

Two different dataset interactions should be kept separate:

- dataset inspection
  - reads the registered source dataset file directly
  - does not create a temp copy
- task execution
  - copies the dataset into the task working directory
  - uses that task-local copy for the ML operation

For issue `#72`, ML execution should not rely on a shared app-managed dataset-copy directory. Task-local copies are simpler to reason about and avoid name-collision and mapping problems.
