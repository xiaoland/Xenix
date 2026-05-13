# Runtime Boundaries

## Purpose

Define the allowed call graph and integration rules for the native application so feature work does not create accidental coupling.

## Layer Model

The native app uses a one-process layered model:

- UI layer: `src/xenix/ui/`
- Service layer: `src/xenix/services/`
- Agent Harness service: `src/xenix/services/agent/`
- ML adapters: native execution pipeline under `src/xenix/services/ml/`
- Persistence interfaces and adapters: SQLite metadata access and filesystem access

Allowed dependency direction:

`UI -> services -> adapters -> SQLite/filesystem/ML`

Forbidden dependency direction:

- UI -> `ml/`
- UI -> SQLite
- UI -> raw filesystem writes outside user-selected paths and app runtime paths
- ML -> Qt objects
- ML -> SQLite access that bypasses service persistence interfaces

## UI Contract

The UI is responsible for:

- Collecting user intent from ChatBox, composer, and file drop intake
- Rendering visible user and assistant Messages
- Rendering tool progress, cancellation state, and artifact previews
- Rendering ML task status, validation errors, and result locations
- Invoking services with plain Python inputs
- Opening files or directories after a service reports a successful output

The UI must not:

- Parse datasets directly for training logic
- Invent hidden ids or result paths outside service mediation
- Select models by reading arbitrary files on disk without service mediation
- Maintain hidden business state beyond view state

## Service Contract

Services are responsible for:

- Owning product and workflow semantics
- Providing Agent Harness, artifact, data, and ML boundaries
- Validating user requests before long-running ML work starts
- Translating ChatBox and tool actions into local service operations
- Persisting ML task metadata and status transitions
- Resolving runtime paths
- Coordinating ML adapters and export paths

Service APIs should be designed around explicit request/result objects or narrow methods. They should return structured outcomes rather than leaving the UI to infer success from side effects.

## Agent Harness Contract

Agent Harness is a service under `src/xenix/services/agent/`.

Agent Harness owns:

- Thread, Turn, Message, tool-call, and tool-result semantics
- LLM provider dialect boundaries
- Static LLM-facing tool registry
- Tool execution sequencing
- Run recording and cancellation

Storage provides persistence interfaces for Agent Harness records. Storage does not own Agent Harness semantics.

## ML Adapter Contract

ML adapters are responsible for:

- Running native model execution entrypoints under `src/xenix/services/ml/`
- Returning typed metadata about produced artifacts
- Emitting progress or log events through service-owned callbacks or loggers

ML adapters must assume:

- They run in a single local user session
- They do not own application navigation, dialogs, or persistence policy
- They may evolve internally without changing UI entry points as long as service contracts stay stable

## Agent Autonomy Contract

The first-slice acceptance scenario validates end-to-end capability. System and developer prompts describe tool semantics, boundaries, and the `turn_end` convention. Planning and tool ordering remain model-owned within tool validation and cancellation boundaries.

## Boundary Tests Required

Add contract tests when any of the following change:

- UI-to-service request shape
- Agent Harness record semantics
- LLM provider serialization
- ML task state transitions
- Service-to-ML adapter invocation shape
- Storage location rules for logs, models, datasets, or results
