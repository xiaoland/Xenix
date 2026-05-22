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
- Accepting explicit role-binding, model, and artifact owner inputs for ML work while expanding ML task payloads into dataset and role snapshots before execution

Service APIs should be designed around explicit request/result objects or narrow methods. They should return structured outcomes so the UI receives explicit success, failure, and output metadata.

`DataCleaningService` owns deterministic data-cleaning execution for `data.clean`.
`data.clean` is an LLM-facing Agent tool that applies explicit atomic predefined cleaning operations to one registered dataset and creates a new derived dataset when operations are provided.
If no cleaning operations are provided, `data.clean` performs no cleaning, creates no derived dataset, and reports that nothing happened.
`data.clean.metadata` is an LLM-facing Agent tool that returns cleaning operation groups, operation names, and operation parameter schemas without executing cleaning.
The tool handler coordinates dataset lookup, service execution, dataset registration, and artifact registration; cleaning algorithms stay in the service layer.
DuckDB-backed SQL execution belongs to internal data query/transform services.
`data.query` is an LLM-facing Agent tool for read-only SELECT/CTE queries over registered dataset bindings. It returns bounded result rows and metadata and creates no dataset artifact by default.
`data.transform` is an LLM-facing Agent tool for SELECT/CTE transformations over registered dataset bindings. It materializes the result as a new derived dataset artifact.
`data.duckdb` is not exposed as an LLM-facing tool.
DuckDB SQL validation must reject mutation, DDL, extension-management, direct filesystem scan, and multi-statement shapes before execution.

Dataset registration in the AI-first path can use a compatibility Project internally while Agent tools avoid product-facing Project inputs.
Dataset lineage is represented through dataset metadata instead of Project ownership.

## Agent Harness Contract

Agent Harness is a service under `src/xenix/services/agent/`.

Agent Harness owns:

- Thread, Turn, Message, tool-call, and tool-result semantics
- LLM provider dialect boundaries
- Provider request recording and token usage projection
- Static LLM-facing tool registry and contextual tool exposure
- Tool execution sequencing
- Run recording and cancellation
- Step budget tracking and user confirmation when a turn needs additional provider/tool steps

The first turn owns the hidden system Message used as the first provider-facing message. Empty threads do not send a provider request. When the first user message starts the first turn, Agent Harness persists the system Message before the user Message; the system Message remains hidden from the Chatbot timeline but remains part of provider-facing conversation history.

Provider requests are recorded separately from Messages. A provider request row records the provider/model boundary, request kind, lifecycle status, persisted input Message ids, persisted output Message ids, and normalized token usage when the provider reports it. Token usage is aggregated from provider request rows rather than inferred from Messages.

Turn progression:

- Each user submission starts a turn around one user Message.
- The first turn also persists the hidden system Message before the first user Message.
- A provider response with assistant content persists an assistant Message.
- A provider response with tool calls persists tool-call Messages, executes matching tools, persists tool-result Messages, and continues the provider loop.
- A provider response with zero tool calls ends the turn.
- Empty assistant content with zero tool calls also ends the turn.
- When a turn ends and provider usage is available, Chatbot may show a turn-level token usage overview inline after the turn.

Provider boundaries:

- The first provider dialect is OpenAI-compatible `/v1/chat/completions`.
- DeepSeek uses the same provider boundary where its API remains OpenAI-compatible.
- CopilotKit AIMock attaches at the LLM provider HTTP boundary during development tests.
- Provider adapters own request assembly, response parsing, streaming chunk accumulation, and provider-specific tool-name mapping.

Tool boundaries:

- The tool registry is static for the current application capability set.
- Agent Harness filters provider-facing tool specs per primary provider request from thread state: `data.*` requires at least one file attached anywhere in the thread, `model.train` and `model.hyper_train` require an existing selection binding in thread tool payloads, and `model.apply` requires an existing trained model in thread tool payloads. Provider tool calls must target tools attached to that request before Agent Harness persists or executes them.
- Runtime thread, turn, file, dataset, model, and artifact context is passed through validated tool arguments and `ToolExecutionContext`.
- Target tool names are `data.peek`, `data.integrate`, `data.clean`, `data.clean.metadata`, `data.query`, `data.transform`, `data.feature.select`, `model.metadata`, `model.train`, `model.hyper_train`, `model.apply`, and `model.task.query`.
- `data.feature.select` creates an immutable dataset column role-binding snapshot. `model.train` and `model.hyper_train` accept `binding_id`. `model.apply` accepts a trained model plus file-backed, tabular, or role-shaped inline inputs, then uses trained model metadata to validate the apply role schema. `model.train`, `model.hyper_train`, and `model.apply` wait for a bounded grace period and return either the completed result or explicit ML task ids for background follow-up. Training and hyperparameter training aggregate through the produced `trained_model_id`; follow-up evaluation task ids and metrics attach to trained-model metadata rather than being inferred from dataset task diffs. `model.task.query` accepts explicit task ids and returns ML task metadata, status, artifacts, errors, and bounded logs.
- Forward-looking tool contracts use `apply`, not `inference`; legacy `inference` names are migration inputs only.

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

The first-slice acceptance path validates end-to-end capability. Prompts describe Xenix identity, tool semantics, and service boundaries. Planning and tool ordering remain model-owned within tool validation, step-budget, and cancellation boundaries.

Acceptance coverage should prove that a user can complete basic analysis from file intake through reusable model application with conversation, file drag-and-drop, service-backed tools, and artifact previews.

## Boundary Tests Required

Add contract tests when any of the following change:

- UI-to-service request shape
- Agent Harness record semantics
- LLM provider serialization
- ML task state transitions
- Data-cleaning tool schemas or service request/result shapes
- Data query/transform tool schemas, SQL validator rules, or service request/result shapes
- Service-to-ML adapter invocation shape
- Storage location rules for logs, models, datasets, or results
