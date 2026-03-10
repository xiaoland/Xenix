# L1 Plan 02: ML And Data Contract

## Dataset Inspection Strategy

Issue `#72` needs a minimal dataset inspection capability because the UI cannot configure training without column metadata.

High-level rule:

- inspection reads the registered dataset source file directly
- inspection returns lightweight metadata only
- inspection does not create execution copies

Minimum inspection output for L2:

- column names
- coarse column kinds suitable for UI validation
- row-count or preview metadata only if it materially helps training setup

This keeps inspection lightweight and avoids conflating it with task execution.

## Registry And Boundary Strategy

Expand `src/xenix/services/ml/` into a real native registry, but keep it explicit and code-owned.

Each model definition should provide at least:

- model key
- display metadata
- problem kind or learning mode
- whether target selection is required
- whether manual fit is supported
- whether tuning is supported
- Pydantic model for manual parameters
- Pydantic model for tuning param-grid input when supported
- binding to the native ML model service implementation

Boundary rule:

- Pydantic request and result models define the service-to-execution contract
- UI form generation uses the JSON Schema exported from those Pydantic models

This gives the app a typed boundary and avoids hand-maintained widget logic for every parameter.

## Parameter Editor Strategy

Parameter forms should be generated dynamically from:

- `Model Hyperparameter Schema`
- `Model ParamGrid Schema`

The source of truth is the Pydantic schema model, not ad hoc Qt form code.

L1 expectation:

- the UI uses JSON Schema to decide which editors to render
- the service validates the submitted values again through the same Pydantic models
- unsupported schema shapes may be intentionally limited in v1 if that keeps the form system maintainable

## Native ML Reuse Strategy

The legacy `./ml` directory is reference material, not the public native execution contract.

That means the native app should:

- implement its own ML model services under `src/xenix/services/ml/` or an adjacent native package
- normalize dataset loading so model code does not care whether the source file was `csv`, `xlsx`, or `xls`
- reorganize or port useful logic from `./ml` into maintainable functions or classes
- avoid shelling out to the legacy scripts as-is

This is the maintainable interpretation of "reuse existing Python ML capability".

## Best-Model Policy

Best-model tracking needs a stronger definition than "highest score".

At L1, best-model selection should be treated as an explicit evaluation-policy concern:

- each ML task runs under a declared evaluation policy
- the evaluation policy defines:
  - the primary metric
  - the sort direction
  - the set of comparable candidates
- automatic best-model updates occur only when the produced candidates are comparable under that policy

This avoids incorrect comparisons across unrelated metric families.

Examples of what should not happen:

- comparing classification AUC to regression R2
- assuming every model family has the same primary metric
- overwriting the work-item best model when the evaluation policy does not establish comparability

L2 should define the exact policy shape. L1 only locks the principle that best-model selection is policy-owned, not heuristic.

## Model Support Strategy

Issue `#72` should support a controlled initial model set rather than the full `./ml` catalog.

However, L1 deliberately does not hard-lock the exact list yet.

What L1 does lock:

- the first supported set should be small enough to keep schema work, adapter work, and tests reviewable
- the registry must be designed so later model additions are mechanical
- the contract must already support models that do not require target selection, even if the initial delivered set is supervised-first

## Persistence Strategy

Issue `#72` should introduce storage changes for reusable trained-model metadata and best-model tracking.

High-level additions:

- trained-model metadata table
- work-item best-model reference
- ML-task-to-trained-model linkage
- persisted evaluation summary suitable for later inspection

Storage ownership remains unchanged:

- SQLite stores metadata, summaries, references, and policy outputs
- filesystem stores model files, task logs, and task result files

## Filesystem Strategy

Task execution should remain task-directory-based.

High-level layout:

- `artifacts/ml-tasks/<ml-task-id>/`
  - task-local dataset copy
  - per-task logs
  - result file
  - task-produced model artifacts
- `artifacts/models/`
  - canonical long-lived model artifacts referenced by trained-model metadata

The task directory is execution-scoped.
The canonical model location is product-scoped.

L2 should define whether canonical model persistence happens by moving or copying the final artifact. L1 does not need to lock that detail.

## Dependency Direction

Pydantic should be treated as an intentional boundary dependency rather than an accidental transitive dependency.

Issue `#72` will likely require a controlled ML dependency expansion, but heavy-dependency isolation is not the main design driver. The main drivers are:

- typed contracts
- maintainable model integration
- responsive UI
- task-local execution semantics
