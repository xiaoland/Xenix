# L0 Plan

## Task

- Issue: `#70 Native: 单用户本地数据模型与存储层`
- Source: `https://github.com/xiaoland/Xenix/issues/70`
- Parent issue: `#46 基于PySide开发本地版`
- Date: `2026-03-09`

## Objective of This Stage

Deconstruct the request, inspect the current native branch, identify architectural constraints already committed in code and docs, and surface the main trade-offs that should govern the L1 strategy.

## Request Decomposition

Issue `#70` asks for the native branch to establish the local data model and persistence foundation for a single-user desktop application. The required outcomes are:

- Define native core entities for:
  - `project`
  - `work item`
  - `dataset`
  - `ML task` (`fit`, `hyperparameter_tuning`, `inference`)
- Design and implement a SQLite schema and migration strategy.
- Design local filesystem conventions for:
  - raw datasets
  - training artifacts
  - model files
  - inference results
  - logs
- Remove or replace web-era concepts such as `user` and `ML-Backend Deployment`.
- Provide repository/service-layer interfaces for atomic local metadata access that can be reused by UI and ML workflows.

Out of scope for this issue:

- End-to-end training and inference business flows
- Packaging and distribution

## Current Codebase Baseline

### Implemented today

- Bootstrap and runtime-path resolution exist in `src/xenix/app.py` and `src/xenix/config.py`.
- Runtime directories currently created are only:
  - `config/`
  - `logs/`
  - `cache/`
- Logging exists in `src/xenix/logging.py`.
- The UI shell in `src/xenix/ui/main_window.py` only displays resolved runtime paths and opens the log directory.
- Tests currently cover only config, logging, and resource resolution.

### Not implemented today

- No `src/xenix/services/` package exists yet.
- No SQLite database file, connection factory, migration runner, or schema exists.
- No repository layer or persistence adapter exists.
- No domain entities or request/result objects exist for datasets, projects, work items, or ML tasks.
- No documented directory layout exists yet for datasets, models, results, or database files.

## Existing Native Contracts Already in This Branch

The branch is not blank on persistence policy. Several documents already constrain the design:

- `docs/adr/0002-sqlite-for-local-state.md`
  - SQLite is already the accepted store for small, queryable local metadata and task state.
- `docs/contracts/storage-ownership.md`
  - SQLite owns metadata and references.
  - The filesystem owns large artifacts and user-openable outputs.
  - UI should consume resolved paths from services instead of constructing storage layouts.
- `docs/contracts/runtime-boundaries.md`
  - Intended layering is `UI -> services -> adapters -> SQLite/filesystem/ML`.
  - UI must not talk directly to SQLite or raw filesystem persistence.
- `docs/contracts/task-lifecycle.md`
  - Task persistence is expected in SQLite once implemented.
  - Status vocabulary is already constrained.
- `docs/migrations/local-state-evolution.md`
  - Migrations must be forward-only in application code.
  - Services own migration execution.
  - Schema version must be recorded once the database exists.

These documents mean issue `#70` should be implemented as the first real persistence and service layer, not as UI-local state or ad hoc filesystem code.

## External Research Notes

Primary sources reviewed:

- GitHub issue API for `#70` and parent `#46`
- Python `sqlite3` documentation: `https://docs.python.org/3/library/sqlite3.html`
- SQLite pragma reference: `https://www.sqlite.org/pragma.html`
- SQLite foreign key documentation: `https://www.sqlite.org/foreignkeys.html`

Relevant takeaways:

- Python standard-library `sqlite3` is sufficient for a lightweight local embedded database without adding an ORM or a separate migration dependency.
- SQLite exposes `PRAGMA user_version`, which is a practical fit for recording schema version in a small single-file native application.
- SQLite foreign key enforcement must be enabled per connection with `PRAGMA foreign_keys = ON` if referential integrity is part of the design.
- Python `sqlite3` connections are thread-affine by default (`check_same_thread=True`), so the service design should avoid sharing one connection object across background worker threads.

## Architectural Tensions Identified

### 1. Dataset ownership is not fully settled

Issue `#70` asks for directory conventions that save raw datasets locally, but the current storage contract says user-selected dataset files remain user-managed and must not be silently deleted.

This is the main design tension in the issue. The cleanest maintainable interpretation is:

- A dataset record can reference an external user-managed source file.
- The app may optionally create an app-managed imported copy or normalized snapshot later, but that should be explicit in the model and deletion rules.

This avoids baking contradictory ownership semantics into the first schema.

### 2. Scope can either stay foundational or drift into workflow implementation

If the schema tries to fully encode training workflows, model metrics, and inference UX now, issue `#70` will become larger than its stated scope and harder to evolve.

A maintainable boundary is:

- Define stable metadata primitives now.
- Keep execution-specific details narrow and extensible.
- Let later issues add richer task payloads and model-result semantics without rewriting the storage foundation.

### 3. Choosing simplicity over abstraction is preferable here

Given the current codebase size and the project rules, introducing an ORM or a third-party migration framework would increase indirection more than it would reduce risk at this stage.

The branch already prefers:

- explicit bootstrap code
- standard library first
- Qt Widgets without extra framework layers

The persistence layer should likely follow the same rule unless L1 analysis proves otherwise.

## Initial Gap Analysis

To satisfy the acceptance criteria, the branch needs at least:

1. A service-owned runtime storage layout beyond `config/logs/cache`.
2. A SQLite connection/bootstrap module and migration runner.
3. A first native schema covering the minimal accepted entities.
4. Repository interfaces for metadata reads/writes.
5. Service interfaces that own atomic persistence operations.
6. Tests that prove schema creation, migration/version tracking, and basic repository writes/reads.
7. Runbook and contract updates documenting the final directory/file conventions.

## Risks to Watch in Later Stages

- Over-modeling the domain before training/inference workflows exist.
- Hard-coding filesystem layout directly into UI code instead of services.
- Treating external datasets and app-managed artifacts as the same ownership class.
- Sharing SQLite connections unsafely across future background tasks.
- Creating a migration scheme that is harder to review than the schema itself.

## Recommended Direction for L1

Draft L1 around these assumptions unless explicitly rejected:

- Use standard-library `sqlite3`, not an ORM.
- Use service-owned migrations with `PRAGMA user_version`.
- Keep the schema intentionally small and centered on metadata, task tracking, and file references.
- Separate user-managed dataset source paths from app-managed artifact paths.
- Introduce `src/xenix/services/` and a persistence subpackage rather than attaching storage code to the UI.

## Review Round 1 Decisions and Adjustments

The following direction was provided after L0 review and is now treated as the working assumption for L1 unless revised again:

### Dataset lifecycle

- Creating a dataset keeps the original file external.
- When a service needs to read the dataset, it requests a temporary app-managed copy.
- That temporary copy is destroyed after the read finishes.

Implication:

- The canonical dataset record should describe the external source file and user-facing storage metadata only.
- Any transient read copy belongs to service execution, not to the canonical dataset model.

### Refined stance on issue slicing

- Agree: this task should stay foundational and avoid over-modeling.
- Practical interpretation for L1:
  - keep the schema small
  - avoid encoding rich dataset profiling
  - avoid introducing a full model catalog if artifact-instance persistence is not yet required by this issue
  - leave room for follow-up issues rather than baking speculative fields into the first schema

### Refined stance on dependencies

- `pydantic` is reasonable for request/result objects or future ML parameter schemas.
- `SQLModel` is less convincing at this stage.

Reason:

- The codebase currently has no service layer, no repository layer, and no persistence code.
- The first schema is expected to be small and migration rules are already explicitly documented.
- Introducing an ORM here would add another abstraction boundary before the repository and service boundaries even exist.

L1 should therefore evaluate:

- option A: stdlib `sqlite3` plus explicit row mapping
- option B: `pydantic` for service DTOs while keeping persistence on stdlib `sqlite3`

Using `SQLModel` is still possible, but it should clear a higher bar than “it is convenient.”

### Refined stance on dataset metadata

Agree:

- Persist only file/storage metadata for datasets in the foundational schema.
- Compute file-level or structural metadata such as modified time, column names, row counts, inferred types, or profiling summaries at runtime inside services.

This keeps the first schema narrower and avoids stale derived metadata.

### Refined stance on ML task execution isolation

Agree with the process boundary:

- the ML task runner should be a separate process
- the runner should not own database writes or business-state transitions
- the main process service should persist task lifecycle changes and interpret runner outputs

This is the cleanest way to avoid unsafe shared SQLite access across background execution.

### Refined stance on model metadata persistence

This needs one clarification because two different concepts are being mixed:

- static model-definition metadata
  - example: model kind, editable parameter schema, registry membership
  - this can reasonably come from runtime registration and code-owned metadata
- persisted artifact-instance metadata
  - example: a trained model artifact path, which task produced it, whether it is reusable later
  - this is different and may still need persistence once cross-session reuse exists

So the likely correct position is:

- do not persist static model-definition metadata in SQLite
- do persist artifact-instance references once the product needs cross-session model reuse

That distinction keeps the design clean and avoids forcing code-owned model definitions into the database.

## Updated Approval Gate to Enter L1

L1 can now proceed if the following interpretation is accepted:

- dataset records persist only stable file/storage metadata for external source files
- temporary app-managed dataset copies are execution-scoped and deleted after use
- derived dataset metadata stays runtime-computed, not canonical in SQLite
- static model-definition metadata stays code-owned, not persisted in SQLite
- if trained artifact reuse needs to exist across sessions, artifact-instance references remain eligible for persistence later even without a full `model catalog` now
