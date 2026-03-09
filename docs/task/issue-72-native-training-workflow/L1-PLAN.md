# L1 Plan

## Stage Goal

Define the high-level technical strategy for issue `#72` based on the approved L0 analysis, the delivered storage foundation from issue `#70`, the existing native contracts, and a native-first training workflow design.

## Inputs Considered

- Issue `#72`: native training workflow, tuning, model persistence, task visibility
- Issue `#70` result: storage layer, task persistence, dataset temp-copy policy, minimal ML registry package
- Existing native contracts under `docs/contracts/` and `docs/runbooks/`
- Existing Python ML sources under `ml/`
- Selective implementation references under `../Xenix/packages/ml-backend`
  - concrete model-service code that may be ported or wrapped
  - task-directory logging and artifact-writing examples
  - filesystem handling ideas where they fit native runtime conventions

## Scope Boundary

Issue `#72` should deliver the first usable native training flow, not the complete end-state product.

Issue `#72` will own:

- model-selection and parameter-editing workflow for training
- hyperparameter tuning workflow for a curated supported model set
- manual training workflow for a curated supported model set
- background execution of ML work
- ML task queue/running/completion/failure visibility, including log-driven execution visibility
- ML task logs, summaries, and failure visibility
- trained-model persistence and reusable metadata
- work-item best-model tracking
- a minimal UI business flow:
  - select dataset
  - choose target and feature columns
  - run fit or tuning
  - show inference entry point as a placeholder, not a real inference workflow

Issue `#72` will explicitly not own:

- real inference execution
- prediction-result export and viewing
- full dataset import and profiling UX beyond what training needs
- exhaustive support for every legacy model in `ml/`
- packaging hardening for Windows distribution

## High-Level Product Flow

The approved minimal native business flow for this issue is:

1. user selects a registered dataset
2. user selects target column and feature columns
3. user chooses one of two training paths:
   - manual training: one model, editable params
   - hyperparameter tuning: multiple models, editable param grids
4. app submits a background ML task into the native task queue
5. worker execution performs fit and evaluation as separate ML steps, with tuning orchestrating repeated candidate fit/evaluate cycles
6. UI shows task state, logs, summaries, and failures
7. on success, app persists trained model metadata, evaluation summary, and marks the best model for the work item
8. UI exposes an inference area as a placeholder entry point for issue `#73`

Important interpretation:

- “label & fit” should be modeled as target-column selection plus explicit feature-column selection
- evaluation should be a separate atomic ML operation that runs automatically after fit, not a hidden side effect folded into fit semantics
- the inference placeholder should remain thin and non-functional, so issue `#72` does not absorb issue `#73`

## Native Reuse Rules

`../Xenix/packages/ml-backend` is not the architecture for issue `#72`. It is, at most, a source of selective implementation ideas.

What remains worth reusing in concept:

- per-task isolation on the filesystem
- code-owned model registry split by model family
- process boundary around CPU-heavy ML execution
- structured task logs written to per-task files

What issue `#72` should not inherit from it:

- HTTP request and polling model
- stateless server assumptions
- web deployment packaging assumptions
- controller-style routing by operation type
- backend-owned worker request/result API shape

Native interpretation:

- keep all orchestration native-service owned
- treat `fit` and `tune` as first-class workflow concepts rather than backend transport operations
- persist lifecycle state in SQLite from the main process instead of relying on external polling as the source of truth
- keep task directories and structured logs because they fit native runtime needs, not because the backend used them

## Architecture Strategy

Adopt this native layered design for issue `#72`:

- `UI`
  - Qt Widgets views and view-state only
  - invokes services with typed inputs
  - renders dataset selection, column selection, parameter forms, task list, logs, result summary, and inference placeholder
- `training workflow services`
  - validate requests
  - create and transition ML tasks
  - expose queue and execution-log state for UI consumption
  - coordinate dataset temp copies
  - prepare task working directories
  - spawn worker execution
  - persist trained-model metadata, evaluation summaries, and best-model designation
- `ML adapters / registry`
  - code-owned model definitions
  - parameter schemas and param-grid schemas
  - fit/evaluate/tune capability definitions
  - mapping from native model keys to implementation adapters
- `worker runtime`
  - isolated process entry point for fit/evaluate/tune execution
  - reads task execution context from app-managed task files
  - writes structured logs and operation outputs to task directory
- `persistence`
  - SQLModel tables and repositories
  - migration to extend schema for trained-model persistence and best-model tracking
- `filesystem runtime`
  - task working directories and trained-model artifacts

Allowed dependency direction:

`UI -> workflow services -> repositories + filesystem + worker launcher + ML registry`

Worker relationship:

`workflow services -> worker process -> result files/log files -> workflow services persist final state`

## Execution Strategy

### Process boundary

Use a separate Python worker process for long-running training and tuning work.

Reasoning:

- it keeps the Qt UI thread responsive
- it avoids shared SQLModel session concerns across long-running ML code
- it gives a clean seam for future issue `#73` inference execution
- it keeps heavy ML dependencies and failure modes outside the UI process

### State ownership

The main native process remains authoritative for:

- ML task creation
- transition to `pending` as the queued state visible in the UI
- transition to `running`
- transition to `succeeded` or `failed`
- task-state and log snapshots suitable for task-list and task-detail displays
- trained-model metadata persistence
- evaluation summary persistence
- best-model designation on the work item

The worker process owns only:

- dataset loading
- fitting, evaluation, and tuning execution
- structured logging
- result-file emission
- model artifact file creation

This keeps business state centralized and reviewable.

## Model Support Strategy

Do not expose the entire legacy model set in the first native iteration.

Recommended curated v1 support:

- regression:
  - `regression.linear`
  - `regression.ridge`
  - `regression.random_forest`
- classification:
  - `classification.logistic_regression`
  - `classification.random_forest`

Why this subset:

- covers both regression and classification flows
- keeps parameter-schema work manageable
- avoids requiring `xgboost` and `lightgbm` in the first native training milestone
- aligns with maintainability and later packaging constraints

Extension posture:

- registry structure should make later model additions mechanical rather than architectural

## Registry Strategy

Expand `src/xenix/services/ml/` into a real native registry.

High-level responsibilities:

- list supported models
- expose display metadata and model family
- expose manual-training parameter schema
- expose tuning param-grid schema when supported
- expose whether the model supports fit, evaluation, tuning, and later inference
- provide adapter binding for worker execution

Design rule:

- static model-definition metadata remains code-owned
- only trained-model instances and their resulting metrics/artifact paths are persisted

This keeps model support explicit and reviewable without turning registry design into a copy of the web backend.

## Worker Contract Strategy

Do not model the worker boundary as a rigid backend-style request/result API.

Instead, use a small stable task envelope plus operation-specific task files owned by the native workflow service.

User-facing workflow concepts for native issue `#72`:

- `fit`
- `tune`

Atomic execution concepts inside the worker boundary:

- `fit`
- `evaluate`

`tune` is not just another alias for `fit`. It is a search workflow that repeatedly uses fit/evaluate capabilities under a tuning policy.

Design direction:

- keep common task metadata stable across all operations
- keep operation-specific inputs in separate sections or files so future operations can extend naturally
- keep worker outputs append-only and file-based inside the task directory
- keep the main process responsible for interpreting worker outputs and deciding what becomes persisted product state

Common worker inputs should cover at least:

- task id
- work-item id
- operation kind: `fit` or `tune`
- dataset temp-copy path
- feature columns
- target column
- task working directory

Operation-specific inputs should cover at least:

- `fit`
  - one model key
  - validated parameter values
- `evaluate`
  - trained artifact location or in-memory handoff contract within the task directory
  - evaluation dataset reference or split policy
  - metric set or evaluation policy
- `tune`
  - one or more model keys
  - validated search-space definitions
  - tuning policy metadata such as scoring, search limits, and candidate selection rules

Worker outputs should cover at least:

- execution summary
- per-model fit summaries
- per-model evaluation summaries
- best-model selection summary when tuning runs multiple candidates
- persisted artifact locations relative to the task directory
- failure details when execution does not complete successfully

Filesystem outputs per task should include:

- `result.json`
- `logs.jsonl`
- one or more model artifact files under the task directory

Maintainability rule:

- avoid a single monolithic schema that must change every time a new ML operation is added
- the result file is not the system of record by itself
- the main process reads worker outputs, validates artifact existence, then updates SQLite state

Implication for issue `#72`:

- a successful manual training workflow should mean `fit` completed, `evaluate` completed, artifacts were validated, and metadata was persisted
- best-model designation should be derived from explicit evaluation output, not inferred from fit completion alone

## Persistence Strategy

Issue `#72` should extend the storage layer with a schema migration.

High-level persistence additions:

- reusable trained-model metadata table
- work-item pointer or field for current best model
- richer ML task result metadata sufficient to show summaries and link tasks to trained models

Persistence goals:

- trained models must be selectable across sessions
- each trained model must be traceable to the producing work item and ML task
- each trained model must have an explicit persisted evaluation summary suitable for later review
- the current best model for a work item must be explicit and queryable

Storage ownership remains:

- SQLite for metadata, summaries, and references
- filesystem for model binaries, task logs, and task result files

## Filesystem Strategy

Reuse the reference backend’s per-task directory idea, but root it in the native runtime layout already established by issue `#70`.

High-level target layout additions:

```text
artifacts/
  ml-tasks/
    <ml-task-id>/
      result.json
      logs.jsonl
      models/
        <trained model files>
  models/
    <work-item-id>/
      <persisted reusable model files>
```

Interpretation:

- task directory is the worker’s isolated scratch-and-output area
- reusable model storage under `artifacts/models/` is the canonical long-lived location
- task-local outputs may be retained for troubleshooting, but canonical reusable model references should point to stable app-managed artifact paths
- evaluation outputs should remain traceable within the task directory even when summary fields are persisted to SQLite

This avoids conflating execution-scoped outputs with reusable product state.

## UI Strategy

Keep the UI thin and service-driven, but implement one usable training screen in issue `#72`.

High-level UI composition:

- dataset selector
- target-column selector
- feature-column multi-selector
- training mode switch:
  - manual train
  - hyperparameter tuning
- model selection panel
  - single select for manual training
  - multi-select for tuning
- generated parameter editor widgets from typed schemas
- task list and detail panel
  - status
  - recent execution logs
  - timestamps
  - result summary
  - logs
  - failure reason
- inference placeholder panel
  - visible but disabled or informational only
  - states that inference lands in issue `#73`

UI rules:

- no direct filesystem layout logic in widgets
- no direct ML invocation in widgets
- no hidden task transition logic in widgets

## Existing ML Reuse Strategy

Use existing Python ML code as implementation material behind native adapters, not as the source of native architecture.

Recommended reuse posture:

- port or wrap concrete model implementations behind native adapters
- normalize dataset loading, parameter handling, and artifact output inside native-owned execution code
- keep task-directory log and result file behavior where it supports debugging and task visibility
- prefer native module boundaries that follow the desktop app's service layering

Avoid this shortcut:

- calling the existing loose `ml/` scripts as shell scripts with hard-coded working-directory assumptions

That would make native behavior brittle and difficult to test.

## Dependency Strategy

Issue `#72` will likely need a controlled dependency expansion beyond the current native package.

Recommended direction for this issue:

- add only the dependencies needed for the curated model set and dataset reading
- prefer:
  - `pandas`
  - `numpy`
  - `openpyxl`
  - `scikit-learn`
  - `joblib`
- defer `xgboost` and `lightgbm` unless L2 proves they are required for the curated model set

This keeps the first native training milestone smaller and reduces later packaging friction.

## Documentation Strategy

Issue `#72` should update documentation alongside the implementation, not after the fact.

Required documentation updates:

- update `docs/contracts/task-lifecycle.md` if queued/log/result guarantees become more explicit for ML work
- update `docs/contracts/storage-ownership.md` if trained-model and evaluation-summary ownership needs clarification
- update `docs/runbooks/runtime-state.md` with the training task directory and persisted model layout used by issue `#72`
- update `docs/runbooks/development.md` if new ML dependencies or local execution steps are introduced
- write `docs/task/issue-72-native-training-workflow/RESULT.md` to capture the delivered scope, deferred items, and verification commands

Documentation rule:

- architecture and storage decisions that affect later issue `#73` inference work should be written down during issue `#72`, not rediscovered later

## Testing Strategy

The high-level test strategy for issue `#72` should cover:

- migration from schema version `1` to the new training-capable version
- registry validation for supported models and typed parameter schemas
- workflow-service validation for manual training and tuning submission
- workflow-service validation that manual training runs fit then evaluation before success is recorded
- worker result ingestion and artifact validation
- trained-model persistence and best-model updates
- evaluation-summary persistence and best-model derivation behavior
- UI-level smoke tests for the minimal training flow if practical

Tests should prioritize service and worker contracts over deep widget behavior.

## Key Strategic Decisions Locked by L1

- use native contracts and service boundaries as the architectural source of truth
- use `../Xenix/packages/ml-backend` only as selective implementation material where it fits native needs
- keep the UI thin and implement only the minimal business flow needed for training
- include an inference placeholder in the UI, but not real inference execution
- use a separate worker process for CPU-heavy ML work
- keep task lifecycle and persistence ownership in the main native service layer
- introduce a schema migration for reusable trained models and work-item best-model tracking
- support a curated model subset first
- keep `fit` and `tune` as the primary user-facing workflows
- treat evaluation as a separate atomic ML operation that runs automatically after fit and provides the basis for best-model decisions
- use a stable task envelope with extensible operation-specific worker files instead of a monolithic backend-style request/result schema
- keep per-task filesystem outputs because they serve native execution and troubleshooting needs
- update contracts, runbooks, and the task result document as part of delivery

## Approval Gate to Enter L2

L2 should assume:

- the first native training screen is a thin service-driven workflow, not a generic workflow framework
- inference remains a placeholder in this issue
- worker execution uses an isolated process with task-directory outputs
- trained models are first-class persisted entities
- evaluation is a distinct atomic ML operation even when it is automatically chained after fit
- best-model designation is persisted on the work item
- the first supported model set is curated rather than exhaustive

If this strategy is approved, the next step is to define the concrete schema changes, task-file layout, registry entries, service interfaces, and UI module boundaries in L2.
