# L1 Plan

## Stage Goal

Define the high-level technical strategy for issue `#70` based on the approved L0 analysis and the follow-up issue split already present in `#72` and `#73`.

## Inputs Considered

- Issue `#70`: native local data model and storage layer
- Issue `#72`: native training workflow and model persistence
- Issue `#73`: native inference workflow and result viewing/export
- Current native contracts under `docs/contracts/`, `docs/adr/`, and `docs/migrations/`
- Current native repository state as of `2026-03-09`
- Reference pattern from `../Xenix/packages/ml-backend`
- Official SQLModel docs

## Scope Boundary

Issue `#70` should deliver the persistence substrate and service boundaries, not the full ML business workflow.

Therefore `#70` will own:

- runtime storage layout
- SQLite database bootstrap
- executable schema-version bootstrap and migration entrypoint
- native table models for the foundational entities
- repository layer for metadata CRUD
- service layer for atomic metadata operations
- task metadata/status persistence contract
- runtime-facing dataset copy policy

Issue `#70` will explicitly not own:

- full training execution
- model artifact scoring or best-model selection logic
- inference execution
- rich dataset profiling
- persisted trained-model catalog beyond what `#72` truly requires
- persisted inference-result catalog beyond what `#73` truly requires

This keeps `#70` foundational and lets `#72` and `#73` extend the storage layer instead of forcing it to predict their final shapes.

## High-Level Architecture

Adopt this layered design:

- `UI`
  - Qt Widgets only
  - invokes services with typed inputs
- `services`
  - owns business operations, storage policy, and task-state transitions
- `persistence`
  - SQLModel table models
  - session/engine factory
  - migration/bootstrap runner
  - repositories
- `filesystem runtime`
  - app-managed directories for database, temporary dataset copies, artifacts, and results
- `ML runtime registry`
  - code-owned model definitions and parameter schemas
  - derived from Python code, not persisted in SQLite
- `ML runner process`
  - separate process in later workflow issues
  - no direct database ownership

Allowed dependency direction:

`UI -> services -> repositories/persistence + runtime filesystem + ML registry`

Future runner isolation direction:

`services -> subprocess runner -> result payload -> services persist outcome`

## Dependency Strategy

Approved dependency direction:

- add `sqlmodel`
- keep SQLite as the database backend

Recommended dependency posture:

- use `SQLModel` for table models and typed row mapping
- use SQLAlchemy/SQLModel sessions via a service-owned session factory
- avoid a full migration dependency in `#70`

Reasoning:

- the schema surface is still small
- version `1` can be created from metadata without handwritten SQL strings
- the migration contract can be established now with a version runner, while richer schema evolution lands in later tasks

Trade-off explicitly accepted:

- `SQLModel` increases abstraction compared with plain `sqlite3`
- but it improves readability for this codebase because you want to avoid raw SQL strings and the domain is still compact

## Persistence Strategy

### Database technology

- SQLite remains the single local metadata store.
- `SQLModel` is the ORM/modeling layer over SQLite.

### Schema versioning

- Use a service-owned migration/bootstrap runner.
- Record schema version with SQLite `PRAGMA user_version`.
- Version `1` is created from SQLModel metadata.
- Migration execution happens during application/service bootstrap, not in UI code.

This satisfies the current migration contract without overcommitting to Alembic before the schema churn justifies it.

### Session lifecycle

- Do not share long-lived sessions across threads.
- Use short-lived sessions per repository/service operation.
- Future background runner processes return data to the main process, which then persists state through its own session.

This matches the approved process-isolation direction and avoids unsafe shared SQLite usage.

## Foundational Domain Strategy

The foundational persistent entities for `#70` remain:

- `project`
- `work_item`
- `dataset`
- `ml_task`

High-level meaning:

- `project`
  - top-level local container for user work
- `work_item`
  - a scoped unit of work under a project
- `dataset`
  - reference to an external user-managed source file plus stable storage metadata
- `ml_task`
  - persisted metadata for service-managed training or inference tasks

Not part of the foundational persisted domain in `#70`:

- static model definitions
- dataset structural/profile metadata
- trained model definitions as a code catalog

Those remain runtime-derived or belong to follow-up issues.

## Dataset Strategy

Approved dataset policy:

- the dataset source file remains external when the dataset is created
- the dataset record stores only stable file/storage metadata
- any structural/schema/profile inspection is computed at runtime in services
- when a read is needed, the service creates a temporary app-managed copy
- that temporary copy is execution-scoped and deleted after the read lifecycle completes

Implications for the storage layer:

- no canonical raw dataset copy is persisted by `#70`
- the runtime directory still needs a dedicated temp area for dataset read copies
- repository state stores only durable references, not ephemeral copies

## Model Registry Strategy

Adopt the `web` worktree pattern conceptually, not literally:

- model availability comes from Python code
- parameter schemas come from runtime-registered Pydantic/SQLModel-compatible model classes
- the persistence layer does not store static model-definition metadata

This mirrors the useful part of `../Xenix/packages/ml-backend`:

- explicit model registries
- code-owned parameter schemas
- no need for a database-backed model catalog just to describe available algorithms

Current path note:

- the target native business-logic location is `src/xenix/services/ml/`
- the current legacy scripts that may be wrapped later are still under `ml/`

## Runtime Filesystem Strategy

Extend the runtime home beyond the current `config/logs/cache` shape.

High-level target layout:

```text
XENIX_APP_HOME/
  config/
  logs/
  cache/
  state/
    xenix.db
  temp/
    datasets/
  artifacts/
    models/
    training/
    inference/
```

Interpretation:

- `state/xenix.db`
  - SQLite metadata store
- `temp/datasets/`
  - ephemeral app-managed copies of external datasets
- `artifacts/models/`
  - reserved for model artifacts used by `#72`
- `artifacts/training/`
  - reserved for task-scoped training outputs used by `#72`
- `artifacts/inference/`
  - reserved for inference outputs used by `#73`

This gives `#70` a documented storage contract without forcing `#72` and `#73` to redesign the runtime tree later.

## Service and Repository Strategy

Introduce a new service-oriented package structure under `src/xenix/services/`.

High-level responsibilities:

- storage bootstrap service
  - ensure directories
  - initialize engine
  - run migrations/bootstrap
- project service
  - create/list/get local projects
- work item service
  - create/list/get work items within a project
- dataset service
  - register external datasets
  - resolve temp copies for execution
- ML task service
  - create/update/list ML task records using the task lifecycle contract

Repository layer posture:

- repositories should expose narrow, aggregate-focused operations
- service methods should be the transactional boundary
- UI should never assemble SQLModel sessions or know table details

## Relationship to Follow-Up Issues

Issue `#72` will build on `#70` by adding:

- training orchestration
- model artifact persistence
- best-model designation
- richer task outputs and logs

Issue `#73` will build on `#70` by adding:

- inference orchestration
- prediction result persistence/export
- result-summary presentation

Because those issues already exist, `#70` should provide extension points, not final workflow semantics.

## Recommended Deliverables for `#70`

- runtime path expansion in config/bootstrap
- SQLModel table definitions for foundational entities
- engine/session bootstrap
- versioned schema bootstrap runner using `user_version`
- repository package
- service package with atomic metadata methods
- tests for bootstrap, versioning, and basic CRUD
- docs updates for runtime-state and storage ownership

## Key Strategic Decisions Locked by L1

- Use `SQLModel` with SQLite.
- Keep migrations service-owned and versioned by `PRAGMA user_version`.
- Keep dataset source files external by default.
- Use temporary app-managed dataset copies only during execution.
- Keep dataset schema/profile metadata runtime-derived.
- Keep static model-definition metadata code-owned, not persisted.
- Prepare the storage layout now for `#72` and `#73`, but do not fully implement their business concepts in `#70`.

## Sources

- Issue `#70`: `https://github.com/xiaoland/Xenix/issues/70`
- Issue `#72`: `https://github.com/xiaoland/Xenix/issues/72`
- Issue `#73`: `https://github.com/xiaoland/Xenix/issues/73`
- SQLModel docs: `https://sqlmodel.tiangolo.com/`
- Reference worktree: `F:\CODING\Project\Xenix\packages\ml-backend`

## Approval Gate to Enter L2

L2 should assume:

- the foundational persisted entities stay limited to `project`, `work_item`, `dataset`, and `ml_task`
- the runtime tree includes `state/`, `temp/`, and `artifacts/`
- schema version `1` is created from SQLModel metadata with a service-owned bootstrap runner
- static model definitions remain outside the database

If this strategy is approved, the next step is to define the concrete table set, fields, relationships, service interfaces, temp-copy lifecycle, and migration/bootstrap interfaces in L2.
