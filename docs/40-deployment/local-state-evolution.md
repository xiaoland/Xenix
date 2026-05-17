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

## Safety Checks

- Keep migrations idempotent where practical.
- Record the schema version in SQLite once the database exists.
- Test fresh bootstrap for every schema baseline change.
- Test at least one upgrade path for every released baseline migration.
- Document any manual recovery step in `docs/40-deployment/`.

## Current Development Baseline

Current AI-first development schema baseline: SQLite `user_version=1`.

Older development databases from previous native UI or WorkItem-centered schemas are obsolete. Delete `state/xenix.db` under the selected runtime home and restart the app to bootstrap the current schema.
