# Runtime Boundaries

## Purpose

Define the allowed call graph and integration rules for the native application so feature work does not create accidental coupling.

## Layer Model

The native app uses a one-process layered model:

- UI layer: `src/xenix/ui/`
- Service layer: `src/xenix/services/` when introduced
- ML adapters: native execution pipeline under `src/xenix/services/ml/`
- Persistence adapters: SQLite metadata access and filesystem access

Allowed dependency direction:

`UI -> services -> adapters -> SQLite/filesystem/ML`

Forbidden dependency direction:

- UI -> `ml/`
- UI -> SQLite
- UI -> raw filesystem writes outside user-selected paths and app runtime paths
- ML -> Qt objects
- ML -> SQLite access that bypasses services

## UI Contract

The UI is responsible for:

- Collecting user intent from Qt Widgets
- Rendering guided scenario surfaces that may hide project or work-item selectors
- Rendering ML task status, validation errors, and result locations
- Invoking services with plain Python inputs
- Opening files or directories after a service reports a successful output

The UI must not:

- Parse datasets directly for training logic
- Invent hidden project ids, work-item ids, or result paths outside service mediation
- Select models by reading arbitrary files on disk without service mediation
- Maintain hidden business state beyond view state

## Service Contract

Services are responsible for:

- Validating user requests before long-running ML work starts
- Translating UI actions into ML task executions
- Owning application-managed scenario containers when the UI hides project management details
- Persisting ML task metadata and status transitions
- Resolving runtime paths
- Coordinating ML adapters and export paths

Service APIs should be designed around explicit request/result objects or narrow methods. They should return structured outcomes rather than leaving the UI to infer success from side effects.

## ML Adapter Contract

ML adapters are responsible for:

- Running native model execution entrypoints under `src/xenix/services/ml/`
- Returning typed metadata about produced artifacts
- Emitting progress or log events through service-owned callbacks or loggers

ML adapters must assume:

- They run in a single local user session
- They do not own application navigation, dialogs, or persistence policy
- They may evolve internally without changing UI entry points as long as service contracts stay stable

## Boundary Tests Required

Add contract tests when any of the following change:

- UI-to-service request shape
- ML task state transitions
- Service-to-ML adapter invocation shape
- Storage location rules for logs, models, datasets, or results
