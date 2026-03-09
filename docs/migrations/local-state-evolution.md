# Local State Evolution

## Purpose

Define the minimum policy for changing local persistence once SQLite and additional runtime files are introduced.

## Rules

- Every incompatible SQLite change must ship with an explicit migration step.
- Migrations must be forward-only in application code.
- Services own migration execution. UI code must not run schema changes directly.
- Runtime file layout changes must document old and new paths before implementation.
- User-managed dataset files must never be moved or deleted automatically by a schema migration.

## Safety Checks

- Keep migrations idempotent where practical.
- Record the schema version in SQLite once the database exists.
- Test at least one upgrade path when changing persistent state.
- Document any manual recovery step in `docs/runbooks/`.
