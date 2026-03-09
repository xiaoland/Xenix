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

## Approval Gate to Enter L1

Before L1, one product-level interpretation should be confirmed because it affects the entire storage design:

- Preferred direction: datasets selected by the user remain external by default, while the schema leaves room for an optional app-managed imported copy later.
- Alternative direction: importing a dataset always creates an app-managed canonical copy inside the Xenix runtime tree.

The preferred direction is easier to keep maintainable because it matches the current storage contract and avoids surprising deletion/backup behavior.
