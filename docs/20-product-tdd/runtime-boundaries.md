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
Supported operation families include schema normalization, duplicate handling, missing-value and high-missing-column handling, type conversion, text standardization, validation, outlier clipping, categorical encoding, and numeric scaling.
If no cleaning operations are provided, `data.clean` performs no cleaning, creates no derived dataset, and reports that nothing happened.
`data.clean.metadata` is an LLM-facing Agent tool that returns cleaning operation groups, operation names, and operation parameter schemas without executing cleaning.
The tool handler coordinates dataset lookup, service execution, dataset registration, and artifact registration; cleaning algorithms stay in the service layer.
`AnalysisProfileService` owns deterministic common descriptive analysis for the `data.peek` analysis path.
Composer data attachments are registered as datasets when the user sends a message. The Composer accepts only currently supported tabular dataset formats (`.csv`, `.xlsx`, and `.xls`) for this path. Provider-facing message blocks carry dataset metadata and `dataset_id`; local file paths remain service-owned facts and must not be serialized into LLM-facing content, tool schemas, or tool results.
`data.peek` is an LLM-facing Agent tool that inspects an already registered dataset by `dataset_id` and by default runs bounded common descriptive analysis. Its `analysis` boolean argument defaults to `true`; when set to `false`, `data.peek` returns only dataset inspection output. It does not register the input dataset and does not create an input dataset artifact.
The profile contract covers basic shape, duplicate rows, field missingness and cardinality, field type groups, numeric statistics, bounded value frequencies, datetime ranges, bounded correlations, and explicit target-column group summaries.
`AnalysisGraphService` owns deterministic dataset-scoped chart rendering for `analysis.graph`.
`analysis.graph` is an LLM-facing Agent tool shaped as `{dataset_id, spec}` where `spec` is a Vega JSON object under the Xenix Vega profile. The profile keeps graphing as pure drawing: Xenix injects the registered dataset resolved from `dataset_id` as a private Vega data source before rendering, and any user-authored Vega `data` or `datasets` declarations are ignored and replaced. External URL resources remain rejected. The Agent should use fields from the registered dataset and call `data.transform` first when grouping, aggregation, joins, reshaping, or durable derived rows are needed. Vega mark-level transforms remain allowed as drawing/layout behavior, including word-cloud layout. The graph service validates obvious field references, applies bounded render policy, patches simple mark and scale data references to the private injected source, renders a static SVG chart through `vl-convert-python`, registers an `ArtifactKind.IMAGE` artifact, and returns `artifact_id` plus structured graph metadata. The current render policy caps spec JSON at 64 KB, chart dimensions at 200-1600 px width and 160-1200 px height, rendered SVG output at 2 MB, and direct row injection at 10,000 rows. If the dataset exceeds the row cap, row-level charts render the first 10,000 rows with `truncated: true`; the Agent should pre-aggregate or reshape with `data.query` / `data.transform` before graphing when row order, grouping, or sampling affects the conclusion. Tool failures must provide enough detail for the Agent to adjust the Vega spec or pre-aggregate data with `data.query` / `data.transform`. The Thread system prompt tells the model to reference image artifacts with markdown image syntax such as `![alt](artifact://<artifact_id>)`.
`AnalysisLambdaService` remains available as service code for one-off Agent-authored Python analysis experiments, but `analysis.lambda` is currently not registered in the Agent-facing tool registry and must not be sent to providers.
The retained service shape is `{code, datasets, params?, manifest?}` where `datasets` maps aliases to registered dataset ids. The code must define `analyze(ctx, inputs, params) -> dict`; execution uses a local subprocess with bounded time, dataset count, input rows, output JSON size, artifact count, and artifact size. The lambda output must be a JSON-serializable dictionary and is returned through `result.output`. Lambda artifact creation remains limited to `ctx.artifact.create(...)`, currently supporting pandas DataFrame, SVG/string, bytes, and matplotlib Figure content. This service-level code protects against accidental bad Agent code such as syntax/runtime errors, timeouts, oversized output, non-serializable values, and unsupported imports; it does not claim hostile-code sandboxing.
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

LLM Service sits between Agent Harness and provider adapters. It owns persisted provider settings, configured model lists, `fq_model_key` parsing, and provider instance construction. `fq_model_key` uses `provider_key/model_key`; neither segment may contain `/`.

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
- Thread model selection is per-thread next-turn state. Agent Harness locks the selected provider at turn start, so in-flight turns and step-budget resumes do not change model when the Composer picker changes.
- Provider adapters own request assembly, response parsing, streaming chunk accumulation, and provider-specific tool-name mapping.

Tool boundaries:

- The tool registry is static for the current application capability set.
- Agent Harness filters provider-facing tool specs per primary provider request from thread state: `data.peek` is exposed when a registered dataset is present in user message blocks or prior tool payloads; `data.integrate` is exposed only when at least two registered dataset ids are present; other `data.*` tools and all `analysis.*` tools require an existing `dataset_id` or input dataset id in thread state; `model.train` and `model.hyper_train` require an existing selection binding in thread tool payloads; and `model.apply` requires an existing trained model in thread tool payloads. Provider tool calls must target tools attached to that request before Agent Harness persists or executes them.
- Runtime thread, turn, dataset, model, and artifact context is passed through validated tool arguments and `ToolExecutionContext`. Dataset source paths may be resolved internally by services from `dataset_id`, but they are not part of the provider contract.
- Target tool names are `data.peek`, `data.integrate`, `analysis.graph`, `data.clean`, `data.clean.metadata`, `data.query`, `data.transform`, `data.feature.select`, `model.metadata`, `model.train`, `model.hyper_train`, `model.apply`, and `model.task.query`.
- `data.feature.select` creates an immutable dataset column role-binding snapshot. `model.train` and `model.hyper_train` accept `binding_id`. `model.apply` accepts a trained model plus file-backed, tabular, or role-shaped inline inputs, then uses trained model metadata to validate the apply role schema. `model.train`, `model.hyper_train`, and `model.apply` wait for a bounded grace period and return either the completed result or explicit ML task ids for background follow-up. Training and hyperparameter training aggregate through the produced `trained_model_id`; follow-up evaluation task ids and metrics attach to trained-model metadata rather than being inferred from dataset task diffs. `model.task.query` accepts explicit task ids and returns ML task metadata, status, artifacts, errors, and bounded logs.
- Agent tool schemas do not expose ML worker selection. Local services choose a worker from the configured worker pool and record selected-worker diagnostics in service-owned task metadata/logs.
- Forward-looking tool contracts use `apply`, not `inference`; legacy `inference` names are migration inputs only.

Storage provides persistence interfaces for Agent Harness records. Agent Harness semantics stay in the Agent Harness service.

## ML Adapter Contract

ML adapters are responsible for:

- Running native model execution entrypoints under `src/xenix/services/ml/`
- Returning typed metadata about produced artifacts
- Emitting progress or log events through service-owned callbacks or loggers
- Dispatching execution through the configured ML worker pool when remote workers are enabled
- Treating SSH workers as execution/cache adapters, not API backends or artifact authorities

ML adapters must assume:

- They run in a single local user session
- They do not own application navigation, dialogs, or persistence policy
- They may evolve internally without changing UI entry points as long as service contracts stay stable
- Remote task staging paths are temporary execution state. Generated outputs must be downloaded and finalized into local service-managed artifact locations before a task can succeed.

## Agent Autonomy Contract

The first-slice acceptance path validates end-to-end capability. Prompts describe Xenix identity, tool semantics, and service boundaries. Planning and tool ordering remain model-owned within tool validation, step-budget, and cancellation boundaries.

Acceptance coverage should prove that a user can complete basic analysis from file intake through reusable model application with conversation, file drag-and-drop, service-backed tools, and artifact previews. Prefer integrated, E2E, smoke, or golden coverage for this layer; avoid one-off regression tests unless the failure exposes a stable boundary contract.

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
- ML worker pool settings, selection rules, SSH setup validation, or remote staging path rewrites

For deterministic cross-boundary outputs, prefer golden tests over many small assertion-heavy regression tests.
