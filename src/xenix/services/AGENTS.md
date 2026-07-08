# Service Layer Guidance

## Scope

This guidance applies to AI-first service boundaries under `src/xenix/services/`.

## Rules

- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recording, provider interaction, and tool execution.
- Storage provides persistence interfaces for service-owned records.
- Keep registered datasets pointed at app-owned materialized dataset files; user-managed source files are import provenance, not execution authority.
- Data services may create app-owned datasets under runtime state. User-openable dataset exports are materialized as artifacts under runtime artifacts when the dataset-producing operation completes.
- Persist source import provenance, app-owned dataset metadata, and user-openable artifact metadata through their service-owned records.
- The target generalized ML lifecycle represents dataset inputs as immutable column role-binding records. The older feature/target column-selection records are migration inputs only.
- Keep dataset inspection metadata ephemeral and runtime-derived.
- Validate column role bindings through service code, not UI-only checks.
- Do not let UI code parse `.csv` or `.xlsx` files for business decisions.
- Before changing storage models, repositories, or migrations, read `docs/40-deployment/local-state-evolution.md`.
- Fix app-owned bad SQLite data through forward-only data migrations; do not use tolerant ORM reads to hide known invalid persisted values.
- For SQLAlchemy-backed Python `Enum` columns, verify the exact persisted representation before writing migrations. `SQLAlchemyEnum(SomeEnum)` stores enum member names by default, while `values_callable=lambda enum_class: [member.value for member in enum_class]` stores enum values. Raw SQL inserts/updates and data migrations must write the representation configured on the model, then prove ORM readability in tests.
- Any SQLite schema or data migration change must update the schema version, cover fresh bootstrap and upgrade/data-migration tests, and update durable storage/runtime docs.

## Boundaries

- `DatasetService` owns dataset registration, source-file inspection, and explicit dataset export helpers.
- `DatasetExportService` owns materializing registered datasets into user-openable workbook artifacts.
- `ArtifactService` owns artifact registration, artifact link resolution, and artifact file activation/open.
- `LinkRouter` owns UI-triggered link activation and dispatches service-owned artifact URI schemes to the owning service.
- ML service training APIs should accept immutable role-binding ids, model selections, and artifact output owner inputs. ML task payloads should expand to explicit dataset id and role-binding snapshots before execution.
- `WorkItemService` exits the target AI-first service topology.
