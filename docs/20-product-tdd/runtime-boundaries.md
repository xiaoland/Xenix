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

- Presenting the Chatbot-first shell through MainWindow, History sidebar, ThreadDetailView, Composer, and Settings
- Collecting user intent from Chatbot, composer, and file drop intake
- Rendering visible user and assistant Messages
- Rendering tool progress, cancellation state, and artifact previews
- Rendering ML task status, validation errors, and result locations
- Invoking services with plain Python inputs
- Opening files or directories after a service reports a successful output

The UI stays outside:

- Dataset parsing for training logic
- Hidden id or result path creation outside service mediation
- Model selection by arbitrary disk file reads outside service mediation
- Hidden business state beyond view state

## Service Contract

Services are responsible for:

- Owning product and workflow semantics
- Providing Agent Harness, artifact, data, and ML boundaries
- Validating user requests before long-running ML work starts
- Translating Chatbot and tool actions into local service operations
- Persisting ML task metadata and status transitions
- Resolving runtime paths
- Coordinating ML adapters and export paths
- Registering and resolving artifacts used by Chatbot markdown links
- Accepting explicit dataset, feature, target, model, and artifact owner inputs for ML work

Service APIs should be designed around explicit request/result objects or narrow methods. They should return structured outcomes so the UI receives explicit success, failure, and output metadata.

`DataCleaningService` owns deterministic data-cleaning execution for `data.clean`.
`data.clean` is an LLM-facing Agent tool that applies atomic predefined cleaning operations to one registered dataset and creates a new derived dataset.
The tool handler coordinates dataset lookup, service execution, dataset registration, and artifact registration; cleaning algorithms stay in the service layer.
DuckDB DSL execution belongs to a separate future tool boundary.

Dataset registration in the AI-first path can use a compatibility Project internally while Agent tools avoid product-facing Project inputs.
Dataset lineage is represented through dataset metadata instead of Project ownership.

## Agent Harness Contract

Agent Harness is a service under `src/xenix/services/agent/`.

Agent Harness owns:

- Thread, Turn, Message, tool-call, and tool-result semantics
- LLM provider dialect boundaries
- Static LLM-facing tool registry
- Tool execution sequencing
- Run recording and cancellation
- Step budget tracking and user confirmation when a turn needs additional provider/tool steps

Thread records own a system prompt. When Agent Harness constructs provider messages, it prepends that system prompt as the first provider-facing system message. The system prompt stays thread metadata and stays hidden from the Chatbot timeline.

Turn progression:

- A turn starts by persisting one user Message.
- A provider response with assistant content persists an assistant Message.
- A provider response with tool calls persists tool-call Messages, executes matching tools, persists tool-result Messages, and continues the provider loop.
- A provider response with zero tool calls ends the turn.
- Empty assistant content with zero tool calls also ends the turn.

Provider boundaries:

- The first provider dialect is OpenAI-compatible `/v1/chat/completions`.
- DeepSeek uses the same provider boundary where its API remains OpenAI-compatible.
- CopilotKit AIMock attaches at the LLM provider HTTP boundary during development tests.
- Provider adapters own request assembly, response parsing, streaming chunk accumulation, and provider-specific tool-name mapping.

Tool boundaries:

- The tool registry is static for the current application capability set.
- Runtime thread, turn, file, dataset, model, and artifact context is passed through validated tool arguments and `ToolExecutionContext`.
- First-slice tool names are `data.peek`, `data.integrate`, `data.clean`, `data.feature.select`, `model.metadata`, `model.train`, `model.hyper_train`, and `model.inference`.

Storage provides persistence interfaces for Agent Harness records. Agent Harness semantics stay in the Agent Harness service.

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

The first-slice acceptance scenario validates end-to-end capability. Prompts describe Xenix identity, tool semantics, and service boundaries. Planning and tool ordering remain model-owned within tool validation, step-budget, and cancellation boundaries.

Acceptance scenarios should prove that a user can complete basic analysis from file intake through prediction with conversation, file drag-and-drop, service-backed tools, and artifact previews.

## Boundary Tests Required

Add contract tests when any of the following change:

- UI-to-service request shape
- Agent Harness record semantics
- LLM provider serialization
- ML task state transitions
- Data-cleaning tool schemas or service request/result shapes
- Service-to-ML adapter invocation shape
- Storage location rules for logs, models, datasets, or results
