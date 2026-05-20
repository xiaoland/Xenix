# Service Layer Guidance

## Scope

This guidance applies to AI-first service boundaries under `src/xenix/services/`.

## Rules

- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recording, provider interaction, and tool execution.
- Storage provides persistence interfaces for service-owned records.
- Keep source dataset registrations pointed at user-managed source files.
- Data services may register app-managed dataset artifacts under runtime artifacts.
- Persist both source-dataset metadata and app-managed dataset-artifact metadata through service-owned records.
- The target generalized ML lifecycle represents dataset inputs as immutable column role-binding records. The older feature/target column-selection records are migration inputs only.
- Keep dataset inspection metadata ephemeral and runtime-derived.
- Validate column role bindings through service code, not UI-only checks.
- Do not let UI code parse `.csv` or `.xlsx` files for business decisions.
- Before changing storage models, repositories, or migrations, read `docs/40-deployment/local-state-evolution.md`.
- Fix app-owned bad SQLite data through forward-only data migrations; do not use tolerant ORM reads to hide known invalid persisted values.
- Any SQLite schema or data migration change must update the schema version, cover fresh bootstrap and upgrade/data-migration tests, and update durable storage/runtime docs.

## Boundaries

- `DatasetService` owns source dataset registration, source-file inspection, and dataset export helpers.
- Artifact service owns artifact registration and artifact link resolution.
- ML service training APIs should accept immutable role-binding ids, model selections, and artifact output owner inputs. ML task payloads should expand to explicit dataset id and role-binding snapshots before execution.
- `WorkItemService` exits the target AI-first service topology.
