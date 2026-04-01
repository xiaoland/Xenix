# L0 Plan

## Task

- Issue: `#72 Native: 调优与训练工作流（调优 / 训练）`
- Source: `https://github.com/xiaoland/Xenix/issues/72`
- Parent issue: `#46 基于PySide开发本地版`
- Issue publish date: `2026-03-08`
- Review date: `2026-03-09`

## Objective of This Stage

Deconstruct the issue, compare it against the current native branch, review the existing `issue-72-native-training-workflow` drafts for drift, and define the constraints that should govern L1.

This stage does not lock the implementation architecture yet. It only establishes what is required, what already exists, what is missing, and which assumptions from the current draft are justified versus premature.

## Issue Text, Restated

Issue `#72` asks for the first native training workflow around the existing ML capability.

In-scope requirements from the issue text:

- native training service(s) that reuse existing Python ML capability through a stable native contract
- hyperparameter tuning flow:
  - multi-select models
  - editable hyperparameters for selected models
- manual training flow:
  - single model selection
  - editable training parameters
- evaluation as an independent atomic ML operation that runs automatically after `fit`
- ML task status management for queue/running/completed/failed
- visible ML task logs, result summary, and failure details
- local persistence of trained models and related metadata
- recording the current best model on the `WorkItem`

Explicitly out of scope:

- inference workflow
- packaging and release work

Acceptance criteria stated by the issue:

- tuning supports model multi-select
- tuning supports parameter editing for the selected models
- manual training supports single-model parameter editing and execution
- `fit` automatically triggers a distinct `evaluation` step
- background execution keeps the UI responsive and exposes state/log/failure visibility
- trained models are persisted locally after training
- the system identifies and records the current best model on the `WorkItem`

## Current Native Baseline

### Implemented today

- desktop bootstrap, runtime directory setup, logging, and Qt shell window exist
- SQLite bootstrap exists with schema versioning through `PRAGMA user_version`
- schema version is now `2` after issue `#75`
- runtime storage foundations already exist for:
  - `project`
  - `work_item`
  - `dataset`
  - `ml_task`
  - `ml_task_artifact`
- service and repository layers exist for:
  - projects
  - work items
  - datasets
  - ML tasks
- dataset registration stores the external source path and supports execution-scoped temp copies
- dataset inspection and dataset-analysis UI now exist through issue `#75`
- `work_item` now owns:
  - `dataset_id`
  - `feature_columns`
  - `target_columns`
- ML task lifecycle transitions are already enforced in `MLTaskService`
- runtime layout already reserves:
  - `temp/datasets/`
  - `artifacts/models/`
  - `artifacts/training/`
  - `artifacts/inference/`
  - `artifacts/ml-tasks/<ml-task-id>/`
- `src/xenix/services/ml/` already exists as the intended registry surface, but it is only a stub

### Missing today

- no native training workflow service exists
- no training execution runner exists
- no trained-model persistence table exists
- `work_item` has no best-model field or relationship
- no evaluation-summary persistence model exists beyond generic task payload JSON
- no populated registry definitions exist
- no stable adapter contract exists between native services and the loose `ml/` scripts
- no training or tuning UI exists

## Contracts Already Binding This Task

The following project contracts are already in force and materially constrain the solution:

- `docs/20-product-tdd/runtime-boundaries.md`
  - required layering is `UI -> services -> adapters -> SQLite/filesystem/ML`
  - UI must not call raw ML code, SQLite, or arbitrary filesystem layout logic directly
- `docs/20-product-tdd/task-lifecycle.md`
  - task states are already defined
  - `succeeded` requires declared outputs to exist
  - application logs under `logs/` remain canonical
  - per-task logs under `artifacts/ml-tasks/<ml-task-id>/` are supplementary
- `docs/20-product-tdd/storage-ownership.md`
  - SQLite stores metadata and references
  - filesystem stores large artifacts such as models, logs, reports, and working files
- `docs/40-deployment/runtime-state.md`
  - current runtime layout already reserves `artifacts/ml-tasks/` and `artifacts/models/`
- issue `#70` result
  - dataset source files remain external and user-managed
  - services may create temporary dataset copies for execution

These rules mean issue `#72` must be delivered as a service-owned workflow with explicit metadata persistence and filesystem artifacts. Direct UI-to-script integration would violate the branch's existing architecture.

## Existing ML Reality

The repository contains substantial ML code under `ml/`, but that code is not yet a stable native integration layer.

Observed characteristics:

- many modules are script-oriented rather than library-oriented
- several scripts assume local files or working-directory-sensitive execution
- parameter handling is inconsistent across files
- model coverage is uneven across regression and classification
- some scripts depend on heavier libraries such as `xgboost` and `lightgbm`
- the native package does not currently declare any ML runtime dependencies beyond `PySide6` and `sqlmodel`

Practical implication:

- the issue requirement to "reuse existing Python ML capability" should be interpreted as reusing implementation logic behind native adapters or wrappers
- it should not be interpreted as exposing the current `ml/` directory as the native service contract

## Review of the Existing Drafts

### L0 draft status

The existing `L0-PLAN.md` is mostly directionally correct. It correctly identifies:

- the need for a training orchestration layer
- the need for schema changes
- the absence of a real model registry
- the need to keep the UI thin and service-driven
- the risk of wiring the placeholder UI directly to `ml/` scripts

The main problem is not with the existing L0. The problem is that the current L1 draft hardens several decisions that L0 did not yet justify sufficiently.

### L1 drift found during review

The current `L1-PLAN.md` contains several decisions that are plausible, but not yet supported strongly enough by the issue text or current branch context:

1. It treats a separate worker process as already decided.
   The issue requires background execution, but that does not by itself prove that `QProcess` or `subprocess` is the only maintainable choice. A thread-based runner, process-based runner, or service-owned job launcher all remain possible at L0.

2. It adds an inference placeholder to the UI scope.
   The issue explicitly marks inference as out of scope. A placeholder may be harmless later, but it is not required by the issue and should not be locked into the strategy unless there is a concrete downstream reason.

3. It locks a curated model subset before enough implementation review.
   Constraining the first model set is probably the right maintenance trade-off, but the exact subset should follow from adapter feasibility, parameter-schema effort, and dependency impact, not from an early preference alone.

4. It leans too heavily on `../Xenix/packages/ml-backend`.
   That package can be a useful implementation reference, but it is an HTTP/backend project with different responsibilities, dependency weight, and file contracts. It should not be treated as a baseline input that defines the native architecture.

5. It introduces more filesystem and result-shape specifics than the current branch needs at this stage.
   The branch already reserves `artifacts/ml-tasks/` and `artifacts/models/`. L1 should be careful not to create redundant path conventions or overfit to the backend package before L2 proves a concrete file contract.

6. It risks over-modeling evaluation and persistence too early.
   The issue clearly requires evaluation as an atomic step and best-model persistence on the work item. That does justify new metadata. It does not yet justify a broad generic workflow framework or a large result schema unless L2 shows that it keeps the implementation simpler.

## Key Architectural Tensions Identified

### 1. Background execution is required, but the boundary is not yet chosen

The issue requires long-running training work to happen in the background with visible status and logs.

What is already clear:

- training cannot run on the Qt UI thread
- the service layer should remain authoritative for task metadata and status transitions
- worker-side code should not mutate SQLite directly

What is not yet justified at L0:

- whether the runner must be a separate process
- whether the runner should be a thread plus isolated adapter
- whether logs and results should be communicated by files only, or by a smaller in-memory bridge plus persisted files

This needs an explicit L1 decision with maintainability as the primary criterion.

### 2. Storage foundation exists, but reusable trained-model persistence does not

The current schema can store:

- generic ML tasks
- generic ML task artifacts

It cannot yet express:

- reusable trained model records
- model metadata tied to a work item
- an explicit best-model reference on `work_item`
- explicit persisted evaluation summaries suitable for later review

Issue `#72` therefore almost certainly requires a schema migration.

### 3. Model metadata needs typing, but not uncontrolled abstraction

The issue requires editable parameters for both manual training and tuning.

That means the native app needs some typed model-definition layer for:

- supported model list
- training parameter schema
- tuning parameter-grid schema
- capability flags

Without that, the UI would be forced into free-form JSON editing, which would damage readability and validation quality.

At the same time, L1 should avoid turning the registry into a generic platform before the first real workflows exist.

### 4. Dataset column selection is a hidden requirement

The issue does not explicitly say "dataset inspection", but the requested UX implies it:

- manual training requires target/feature selection
- tuning requires model-specific parameter editing against an actual dataset shape
- evaluation needs a repeatable understanding of which columns were used

Because issue `#75` now delivers dataset inspection and work-item dataset-selection state, issue `#72` should consume that capability rather than rebuilding it.

This is a real dependency for L1, not an optional convenience.

### 5. Dependency scope is under-specified

The native app currently declares only:

- `PySide6`
- `sqlmodel`

Training almost certainly requires adding part of the ML stack.

The maintainability question is not whether dependencies will grow. It is how aggressively issue `#72` should expand them. That decision should be tied to the chosen supported model set and adapter strategy.

## Minimum Capability Gaps That L1 Must Address

To satisfy the issue without violating existing contracts, the next planning stage must define a strategy for at least:

1. schema changes for trained-model metadata and work-item best-model tracking
2. a concrete training execution boundary that keeps the UI responsive and the service layer authoritative
3. consumption of the dataset introspection and work-item dataset-selection state already delivered by issue `#75`
4. a real model registry with typed training/tuning schemas for the supported model set
5. a native adapter contract that reuses current ML capability without exposing script-style modules directly
6. task-log and result-summary handling that matches the current task lifecycle contract
7. a minimal Qt training workflow UI

## L1 Guardrails

The next stage should proceed with these guardrails:

- treat `../Xenix/packages/ml-backend` as a reference source only, not as an architectural dependency
- do not lock process-vs-thread execution in L0
- do not add inference UI scope unless L1 can justify it as necessary and low-cost
- assume a schema migration is required
- assume best-model tracking on `WorkItem` is a first-class persistence concern
- assume evaluation is a distinct atomic ML step that follows `fit`
- prefer a small, explicit native design over a generic ML workflow framework

## Approval Gate to Enter L1

L1 should proceed only if the following L0 interpretation is accepted:

- issue `#72` requires real storage changes, not just UI and service glue
- issue `#72` should remain strictly training-focused; inference stays out of scope unless later justified explicitly
- existing L1 assumptions around worker process, model subset, and backend-package influence should be treated as open questions, not locked decisions
- model definitions and parameter schemas should stay code-owned in the native app
- task metadata transitions should remain service-owned
- dataset column inspection and work-item dataset-selection state are prerequisites that should now be treated as existing upstream capability from issue `#75`

