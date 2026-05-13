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
- Feature/target selection in the first AI-first slice is represented by tool results and artifact records.
- Keep dataset inspection metadata ephemeral and runtime-derived.
- Validate column selections through service code, not UI-only checks.
- Do not let UI code parse `.csv` or `.xlsx` files for business decisions.

## Boundaries

- `DatasetService` owns source dataset registration, source-file inspection, and dataset export helpers.
- Artifact service owns artifact registration and artifact link resolution.
- ML service APIs should accept explicit dataset id, feature columns, target columns, model selections, and artifact output owner.
- `WorkItemService` exits the target AI-first service topology.
