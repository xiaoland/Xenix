# Local State Evolution

## Purpose

Define the minimum policy for changing local persistence once SQLite and additional runtime files are introduced.

## Rules

- Released SQLite baselines require explicit forward migration steps for incompatible schema changes.
- During unreleased development, a schema baseline reset is allowed when the repo records the new schema version, fresh bootstrap tests cover the current schema, and the runbook explains local database recovery.
- Application migrations run forward from the active supported baseline.
- Services own migration execution. UI code stays outside schema execution.
- Runtime file layout changes must document old and new paths before implementation.
- User-managed dataset files stay in their original locations during schema migration.
- SQLite schema changes must increment `CURRENT_SCHEMA_VERSION` and add a named forward migration step from the previous version.
- Data shape fixes are migrations. If persisted values are wrong, add a forward-only data migration that rewrites those values instead of adding tolerant reads to the model layer.
- ORM model definitions must match the post-migration canonical database representation. Migrations must leave rows readable by the current strict ORM mapping.
- Enum columns must have an explicit persisted representation. For new enum-backed fields, prefer the enum value stored in SQLite, not the Python enum member name, unless an existing column already has a documented representation.
- SQLAlchemy enum columns are representation-sensitive. `SQLAlchemyEnum(SomeEnum)` persists Python enum member names such as `SYSTEM`; adding `values_callable=lambda enum_class: [member.value for member in enum_class]` persists enum values such as `system`. Raw SQL migrations must inspect the model mapping and write the configured representation exactly.

## SQLite Migration Development Rules

- Each migration function should represent one version edge, such as `v3 -> v4`, and `run_migrations()` should compose those edges in order.
- Migrations must be forward-only. Do not rewrite history inside an old migration once that version may exist in a developer or user database; add a new migration edge.
- Schema migrations should add or reshape columns, indexes, and tables. Data migrations should normalize existing rows to the current canonical representation.
- Avoid model-layer compatibility shims for known bad persisted data. Use compatibility reads only for genuinely external input formats, not for app-owned SQLite state.
- When adding a column with a default semantic value, backfill existing rows in the same version edge or a subsequent data migration before exposing the schema as current.
- Migrations may be idempotent for resilience, but idempotence is not a substitute for versioned ownership. The recorded `PRAGMA user_version` must still advance only after the migration work is complete.

## Safety Checks

- Keep migrations idempotent where practical.
- Record the schema version in SQLite once the database exists.
- Test fresh bootstrap for every schema baseline change.
- Test at least one upgrade path for every released baseline migration.
- Test data migrations with raw legacy rows and then read the migrated rows through the current ORM model.
- Test enum-backed columns against the canonical persisted representation, including any data migration from earlier accidental representations.
- For SQLAlchemy enum changes, include an ORM-read assertion after migration so a row with the migrated value is loaded as the expected Python enum member.
- Document any manual recovery step in `docs/40-deployment/`.

## Current Development Baseline

Current AI-first development schema baseline: SQLite `user_version=12`.

Older development databases from previous native UI or WorkItem-centered schemas are obsolete. Delete `state/xenix.db` under the selected runtime home and restart the app to bootstrap the current schema.
