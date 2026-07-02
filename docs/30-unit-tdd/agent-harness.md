# Agent Harness Unit TDD

## Purpose

Preserve the local invariants for `src/xenix/services/agent/`. Agent Harness is the service that turns Chatbot-first user interaction into persisted conversation records, LLM provider calls, tool execution, and artifact-producing service work.

## Unit Boundary

Agent Harness owns:

- Thread creation, rename, delete, listing, and snapshot loading
- Thread-level next-turn LLM model selection as a stored `fq_model_key`
- Hidden system Message creation and projection into provider messages
- Turn start, end, cancellation, and step-budget pause/resume
- Message persistence for user, assistant, system, tool-call, and tool-call-result records
- Provider request persistence and token usage aggregation
- Chatbot timeline projection from persisted records into user-visible Chatbot Events
- Provider boundary calls through a canonical provider contract
- Contextual provider-facing tool exposure and tool execution
- Agent run recording and cancellation state
- AI observability projection from Harness-owned turn, provider request, tool-call,
  guard, step-budget, cancellation, and token usage facts

Storage owns persistence mechanics. Data, artifact, project, and ML services own domain operations. Qt UI owns rendering and user input collection.

## Records

- `Thread`: persisted conversation workspace with title and system prompt.
- `Turn`: ordered group of messages started by one user Message.
- `Message`: chronological content-block record with Harness kind, UI author, lifecycle status, and content blocks.
- `ProviderRequest`: one LLM provider call with persisted input Message ids, output Message ids, request kind, status, and token usage when reported by the provider.
- `ToolCall`: execution record linking a tool-call Message to its result Message.
- `AgentRun`: one provider/tool orchestration attempt for a turn.
- `TurnCompletionGuard`: diagnostic audit record for a guard model decision made before ending a turn.
- `ChatbotEvent`: Harness-owned projection record consumed by Chatbot UI. One Chatbot Event may represent one Message, a paired tool-call Message and tool-result Message, or a turn-level usage overview.

## Provider Loop

One user submission follows this service flow:

```text
submit_user_turn
  -> create thread when needed
  -> start turn and persist hidden system Message when this is the first turn
  -> persist user Message
  -> start AgentRun
  -> build provider messages from ThreadSnapshot
  -> persist ProviderRequest as the provider boundary is entered
  -> call provider complete/stream
  -> create/update/finalize assistant Message as stream content arrives or final content is known
  -> finalize ProviderRequest with output Message ids and token usage
  -> before ending a zero-tool turn, optionally run the turn completion guard
  -> end turn when provider returns zero tool calls and guard allows completion
  -> for each tool call:
       persist tool-call Message and ToolCall row
       execute registered tool with ToolExecutionContext
       persist tool-result Message and ToolCall result status
       continue provider loop
```

A provider response with empty assistant content and zero tool calls ends the turn. A turn-end tool is outside the current contract.

## Turn Completion Guard

The turn completion guard is a minimal Harness-owned safeguard at the zero-tool turn-end boundary. It is enabled only when a guard model is configured. When no guard model is configured, the Harness keeps the normal zero-tool turn-end behavior.

The guard input is only the latest assistant text from the provider response that is about to end the turn. It does not inspect the full conversation, tool history, artifacts, or task state. The guard provider returns JSON with:

```json
{"verdict":"continue","reason":"short reason"}
```

or:

```json
{"verdict":"complete","reason":"short reason"}
```

`complete` lets the Harness end the turn normally. `continue` means the assistant appears to have stated an in-turn next action without completing it. For `continue`, the Harness persists a system Message in the active turn and retries the primary provider. The system Message is ordinary conversation history and is included in future provider message projection.

The guard persists each decision to `agent_turn_completion_guard` with `turn_id`, `attempt_index`, `input`, `output`, and `created_at`. The audit row is diagnostic state; it is not a Chatbot Event and is not user-visible assistant content.

The Harness allows at most two `continue` retries per turn. If the primary provider still returns zero tool calls after the retry limit is exhausted, the Harness ends the turn normally. Invalid guard output or guard provider failure fails closed as `complete`.

## Chatbot Timeline Projection

Agent Harness owns the projection from persisted Thread records into Chatbot Events. Chatbot UI renders projected events and must not inspect storage rows to infer tool pairing, tool status wording, icon category, or result details.

Projection rules:

- User and assistant Messages project to text Chatbot Events.
- System Messages stay hidden from the normal Chatbot EventList unless a later control-event contract explicitly exposes them.
- A tool-call Message and its corresponding tool-call-result Message project to one tool Chatbot Event.
- A tool-call Message with no result yet still projects to a pending tool Chatbot Event.
- Ended turns with provider-reported token usage project to one usage Chatbot Event after the turn's visible content.
- Usage Chatbot Events are UI observability chrome and must not be persisted as provider-facing Messages.
- `AgentToolCallRow.request_message_id` and `AgentToolCallRow.result_message_id` are the authoritative pairing source for snapshots.
- During a running turn, a tool-call result is emitted after the corresponding tool-call request and completes the same logical tool event.
- Tool-event summary text, failure language, cancellation language, result detail blocks, and icon keys are Harness projection data.
- Tool presentation metadata is owned by the Agent Tool Registry. Chatbot projection consumes registry presentation data rather than maintaining a parallel tool-name display table.

Tool result text may also be projected into provider-facing tool content. UI-only chrome such as chevron state remains Qt UI-owned.

## Streaming Contract

Agent Harness exposes Chatbot timeline changes as ChatbotEvent-shaped stream events. Provider deltas remain internal Harness input.

`submit_user_turn_stream()` and `continue_step_budget_stream()` emit:

- `snapshot`: a full `ThreadSnapshot` plus projected Chatbot Events for turn start/resume and final convergence. `is_final=False` means the turn is still running; `is_final=True` means the UI may leave running state.
- `message_created`: a persisted `Message` has been created and may carry the corresponding Chatbot Event.
- `message_updated`: a persisted `Message` has changed content or lifecycle state and may carry the corresponding Chatbot Event.
- `message_finalized`: a persisted in-progress `Message` reached a terminal lifecycle state and may carry the corresponding Chatbot Event.
- `step_confirmation_required`: control state for user approval after the step budget is exhausted; the corresponding system Message is still persisted and emitted as a message event.

The Harness emits `THINKING` Chatbot Events around each provider request. The start event is emitted when the provider request boundary is entered; the completed event is emitted when the first provider stream event arrives, before rendering the first assistant delta or tool response. If the request fails or is cancelled before any provider event arrives, the failed or cancelled event clears the same transient thinking item. The Harness converts provider text chunks into updates on one assistant Message and one assistant Chatbot Event. Tool-call and tool-result records are one-shot persisted Messages, but project to one logical tool Chatbot Event. `AgentToolCallRow` remains execution metadata.

## System Prompt

`AgentThreadRow.system_prompt` stores the default text used to seed the first hidden system Message.

New threads format the default system prompt with the current application interface locale, such as `en_US` or `zh_CN`, so provider-facing assistant language follows the UI language instead of inferring language from user text.

The default system prompt frames the Agent as a non-technical business analysis guide. Before choosing an analysis path, it must identify the business scenario, analysis object, data grain, field roles, and user intent; hide algorithm menus behind business-language choices; prefer simple interpretable and data-supported paths; compare complex models against a simple baseline; explain field exclusions, merges, or non-use by listing original candidate fields, actually used fields, and the target field before proceeding; state evidence boundaries such as correlation not being causation and predictions not being automatic decisions; and make final outputs land in business meaning, action recommendations, risk notes, and process trace.

The first user turn persists that hidden system Message before the user Message, with role `system` when projected to provider messages. Empty threads do not send provider requests. Chatbot timeline projection hides system Messages unless a later control-event contract explicitly exposes them.

## Provider Request Usage

`agent_provider_request` is the authority for token usage. Each row records one primary or guard provider request, the persisted input Message ids, any persisted output Message ids created because of the provider response, provider/model metadata, lifecycle status, and normalized usage payload.

The normalized usage payload uses:

- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `total_tokens`
- `provider_usage`

Cached input tokens are a subset of input tokens and are not added to totals again. OpenAI-compatible streaming requests include `stream_options.include_usage=true`; if a compatible provider does not return usage, the row remains useful as a request record and Chatbot omits the token overview for that usage-missing slice.

## AI Observability Projection

Agent Harness owns AI observability collection semantics because it owns the turn-level causal graph. It projects safe telemetry from existing Harness facts into OpenTelemetry-compatible spans and metrics. LLM Service remains a provider router and provider-construction boundary; it does not own turn semantics, trace hierarchy, token attribution, tool exposure attribution, or AI behavior diagnosis.

The first AI observability projection records causality and request shape without exporting raw content by default:

- `agent.turn` spans carry the Agent workflow identity and hashed thread, turn, and run correlation.
- `agent.provider_request` spans carry GenAI/OpenInference-compatible operation metadata, request kind, loop step, provider, model hash, message role counts, tool exposure counts, response shape, token usage when reported, usage-present state, and invalid-tool-call classification.
- `agent.tool_call` spans carry tool operation metadata, tool category, hashed tool-call id, parent provider request correlation, and loop step.
- Provider request metrics expose low-cardinality status, duration, usage-present, and token usage measurements. Correlation ids stay on spans rather than metrics.

Remote telemetry must not include raw prompts, assistant completions, tool arguments, tool result payloads, dataset values, local paths, provider credentials, raw provider payloads, or raw provider usage payloads by default. Eval scores, judge-model decisions, human ratings, prompt quality judgments, and optimization recommendations belong to later analysis layers, not the collection layer.

## Step Budget And Cancellation

The initial step budget is enforced by Agent Harness. When the granted step budget is exhausted, Agent Harness pauses the run with `AgentRunStatus.AWAITING_CONFIRMATION` and emits a confirmation event. The user may grant more steps up to the configured total limit or stop the run.

Cancellation is user-driven from the Chatbot stop control. A cancel request stops provider/tool progression, attempts to cancel active ML tasks when available, records a system cancellation Message, cancels the Turn, and marks the AgentRun cancelled.

## Tool Registry

The first-slice tool registry is static for the current application capability set:

- `data.peek`
- `data.integrate`
- `analysis.graph`
- `data.clean`
- `data.clean.metadata`
- `data.query`
- `data.transform`
- `data.feature.select`
- `model.metadata`
- `model.train`
- `model.hyper_train`
- `model.apply`
- `model.task.query`

Agent Skill activation is a Harness-owned internal prompt-loading tool, not a domain tool owned by the Agent Tool Registry. When a build-generated static skill catalog is configured, the Harness injects one provider-facing system message listing the built-in skill names, descriptions, active state, and resource counts. The Harness also exposes `agent.skill.activate` as a constrained provider-facing tool whose schema enumerates only inactive built-in skill names. The tool returns the selected `SKILL.md` body plus its catalog-listed `references/` and `assets/` manifest as provider-facing tool-result content for later reasoning.

After a skill is activated, the Harness may expose `agent.skill.read_reference` and `agent.skill.read_asset` for activated skills that have catalog-listed resources of that kind. These tools return only bounded UTF-8 text content embedded in the generated catalog. They do not read skill source files at runtime, do not provide arbitrary filesystem access, and are unavailable before activation.

Xenix Agent Skill source directories under `src/xenix/services/agent/skills/<skill>/` are dev/build inputs, not runtime assets. They are not user-installed plugins, runtime-discovered files, script execution surfaces, credential/env injection surfaces, marketplace packages, or arbitrary filesystem access. `src/xenix/services/agent/skills/catalog.json` is generated by the build/dev preparation step, inlines activated skill bodies plus reference/asset content, and is ignored by git. Runtime consumes only the generated catalog; PyYAML is only needed for dev/build validation and generation.

Agent Skill tool-call and tool-result messages are persisted as normal Harness records to preserve provider tool-call protocol and auditability. Chatbot timeline projection hides `agent.skill.*` tools by default because they are prompt-loading mechanics rather than user-facing work, but projects them when `XENIX_ENV` is `development` or `dev` to support local debugging. Provider request `input_message_ids` include only persisted message ids; the dynamically injected skill catalog message has no persisted source id.

Provider-facing tool exposure is contextual per primary provider request. The Harness reads the static registry specs, derives availability from the current thread snapshot, and attaches only the visible specs to the provider request. `data.peek` is exposed when a file has been attached or a dataset already exists in thread tool payloads. `data.integrate` is exposed only when a file has been attached. Other `data.*` tools and registered `analysis.*` tools are exposed only after a prior tool payload in the thread contains `dataset_id` or `input_dataset_ids`. `model.train` and `model.hyper_train` are exposed only after a prior tool payload in the thread contains a `binding_id`. `model.apply` is exposed only after a prior tool payload in the thread contains a `trained_model_id` or a trained-model list entry with a `trained_model_id`. If a provider returns a tool call that was not attached to that request, the Harness rejects the response before persisting or executing the tool call. Tools hidden from a provider request remain registered and retain their execution-time validation.

Each registered tool carries `ToolPresentation` metadata for Chatbot projection: semantic icon key, pending summary, success summary, failure action, and cancellation summary. `data.peek` accepts file registration controls plus `analysis`, `target_columns`, `top_n`, and `correlation_column_limit`; `analysis` defaults to `true`, and the enabled path returns structured common descriptive statistics plus Markdown inside the `data.peek` result payload. `analysis.graph` accepts `{dataset_id, spec? , wordcloud_spec?}` with exactly one graph mode per call. `spec` is a Vega JSON object under the Xenix Vega profile: the Agent writes drawing structure only, Xenix injects the registered dataset as a private Vega data source, user-authored `data`/`datasets` declarations are ignored and replaced, external `url` resources are rejected, and data preparation belongs to `data.query` / `data.transform`. Vega word-cloud transforms are rejected; word clouds must use `wordcloud_spec`. `wordcloud_spec` is a compact Xenix-owned contract that expects an upstream chart-ready table, usually `word` + `count`, with Chinese segmentation already done upstream. The tool creates a bounded service-managed SVG image artifact and returns `artifact_id` plus structured graph metadata. `analysis.lambda` service code is retained but intentionally not registered, so it is absent from provider-facing specs. Tools that create user-openable artifacts return `artifact_id` values or artifact lists; the Thread system prompt instructs the model to construct `artifact://...` markdown links, including markdown image syntax for inline image artifacts. Tool-result Messages persist no `content_blocks`; provider-facing tool result content is derived from the completed tool-call payload. When a tool fails, the default failure payload still includes a top-level `error` string. If the thrown exception exposes structured retry metadata such as `error_code`, `error_details`, `repair_hints`, or `retryable`, the Harness forwards those fields into the tool-result payload so the provider can repair and retry instead of repeating the same invalid call. `data.clean` uses an operation-centric executor schema shaped as `{dataset_id, name?, operations?}`; each operation is `{operation, params?}`. If `operations` is absent or empty, `data.clean` performs no cleaning, registers no derived artifact, and reports that nothing happened. `data.clean.metadata` returns operation groups, operation names, and operation parameter schemas; it never performs cleaning. The `data.clean` operation catalog covers schema normalization, duplicate handling, missing-value and high-missing-column handling, type conversion, text standardization, validation, outlier clipping, categorical encoding, and numeric scaling while keeping the provider-facing schema compact. `data.feature.select` creates an immutable dataset column role-binding snapshot and returns `binding_id`; its provider-facing role binding schema exposes only `role` and `columns`, while service logic derives or validates role kind. Ordinary supervised models bind `feature` plus a complete `target`; semi-supervised classifiers bind `feature` plus `partial_target`, where blank/null cells in `partial_target` are unlabeled rows that may support training but are not evaluation evidence. `model.metadata` is a two-stage contract with a minimal provider-facing schema: `model_family` for lightweight directory browsing, `model_key` for single-model detail, and `include_param_grid_schema` for optional tuning-grid detail on a chosen model. It requires either `model_key` or `model_family`. Filtered directory queries return lightweight model summaries without role schemas or parameter schemas. Single-model detail queries return canonical model metadata, role schemas, and `param_schema` by default; `include_param_grid_schema=true` additionally returns `param_grid_schema`. Provider-facing schemas do not enumerate model keys; model keys and aliases are validated through the model catalog at execution time. `model.train` and `model.hyper_train` accept `binding_id`, keep schemas lightweight, and validate model keys through the model catalog at execution time. `model.apply` accepts a trained model plus at least one input source: `input_sources` containing registered dataset ids or `artifact://...` URIs, or inline `input_rows` shaped as `{header_index_map, data}`. Raw filesystem paths are not accepted by the Agent-facing tool. `model.train`, `model.hyper_train`, and `model.apply` are grace-period async tools: if the ML work completes inside the tool grace period, the tool returns the completed result; otherwise it returns explicit `task_ids`, Tool Call Detail action metadata, and a provider-facing instruction to query task status. `model.train` and `model.hyper_train` resolve completed work through the produced `trained_model_id`; follow-up evaluation task ids and metrics are read from trained-model metadata, not from dataset-wide task scans. Tool Call Item does not expose per-task cancellation; active run cancellation is owned by the Chatbot stop control. `model.task.query` accepts explicit `task_ids` and returns ML task metadata, status, artifacts, error summaries, and bounded logs; its Tool Call Item does not expose a Tool Call Detail action because the query result is already the detail surface. Trained model metadata stores role bindings and apply role schema; any supervised feature-column list is a runtime projection, not a persisted metadata field.

### Provider-Facing Tool Schema Design

Agent Harness owns the provider-facing tool schema budget.

- Expose only fields that materially change routing, authority resolution, or execution.
- Prefer the smallest user-meaningful surface over internal taxonomies or alternate query knobs.
- Split discovery from detail when one tool shape would otherwise mix browsing, selection, and deep configuration.
- Add short descriptions to non-obvious fields so the provider can tell when and why to use them.
- Keep nested payload schemas shallow when service validators or typed inputs already own the real contract.
- Avoid schema-level closure or explicit unknown-key rejection unless strictness is safety-critical and the runtime truly depends on it.

## Provider Boundary

LLM Service owns provider configuration, configured model lists, `fq_model_key` generation/parsing, and provider construction. `fq_model_key` has the format `provider_key/model_key`; provider keys and model keys must not contain `/`.

Agent Harness reads the selected Thread `fq_model_key` at turn start and asks LLM Service for a provider instance. That provider instance is locked for the whole turn, including any provider-loop retries and step-budget resume. Changing the Thread model while a turn is running affects only the next turn.

The provider contract is:

```text
complete(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderResponse
stream(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderStreamEvent*
```

`ProviderResponse` carries assistant content blocks, normalized tool calls, normalized token usage when available, and raw provider payload. Provider adapters own OpenAI-compatible request assembly, streaming accumulation, provider tool-name mapping, usage parsing, and response parsing.

CopilotKit AIMock connects through the same OpenAI-compatible HTTP boundary during development testing.

## Test Obligations

Contract tests should cover:

- thread creation with default system prompt seed text
- first-turn hidden system Message creation
- provider message projection with the persisted system Message first
- provider request persistence and usage aggregation
- user turn persistence and turn ending on zero tool calls
- empty-text zero-tool provider response ending a turn
- assistant streaming as message create/update/finalize events on a single persisted assistant Message
- ChatbotEvent projection for user, assistant, request-only tool, completed tool, failed tool, and cancelled tool states
- tool-call and tool-result message events before final turn snapshot, each carrying the appropriate Chatbot Event when visible
- tool-call and tool-result persistence
- step-budget pause, resume, stop, and maximum total limit
- cancellation during provider and tool execution
- model metadata schema and model key normalization
- artifact link production for dataset, training, and apply outputs
