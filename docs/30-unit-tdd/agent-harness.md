# Agent Harness Unit TDD

## Purpose

Preserve the local invariants for `src/xenix/services/agent/`. Agent Harness is the service that turns Chatbot-first user interaction into persisted conversation records, LLM provider calls, tool execution, and artifact-producing service work.

## Unit Boundary

Agent Harness owns:

- Thread creation, rename, delete, listing, and snapshot loading
- Thread system prompt projection into provider messages
- Turn start, end, cancellation, and step-budget pause/resume
- Message persistence for user, assistant, system, tool-call, and tool-call-result records
- Chatbot timeline projection from persisted records into user-visible Chatbot Events
- Provider boundary calls through a canonical provider contract
- Static tool registry exposure and tool execution
- Agent run recording and cancellation state

Storage owns persistence mechanics. Data, artifact, project, and ML services own domain operations. Qt UI owns rendering and user input collection.

## Records

- `Thread`: persisted conversation workspace with title and system prompt.
- `Turn`: ordered group of messages started by one user Message.
- `Message`: chronological content-block record with Harness kind, UI author, lifecycle status, and content blocks.
- `ToolCall`: execution record linking a tool-call Message to its result Message.
- `AgentRun`: one provider/tool orchestration attempt for a turn.
- `TurnCompletionGuard`: diagnostic audit record for a guard model decision made before ending a turn.
- `ChatbotEvent`: Harness-owned projection record consumed by Chatbot UI. One Chatbot Event may represent one Message or a paired tool-call Message and tool-result Message.

## Provider Loop

One user submission follows this service flow:

```text
submit_user_turn
  -> create thread when needed
  -> start turn and persist user Message
  -> start AgentRun
  -> build provider messages from ThreadSnapshot
  -> call provider complete/stream
  -> create/update/finalize assistant Message as stream content arrives or final content is known
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

The system prompt is stored on `AgentThreadRow.system_prompt`.

`ThreadSnapshot.provider_messages()` prepends it as the first provider message with role `system`. It is metadata for provider calls and hidden from the Chatbot timeline.

## Step Budget And Cancellation

The initial step budget is enforced by Agent Harness. When the granted step budget is exhausted, Agent Harness pauses the run with `AgentRunStatus.AWAITING_CONFIRMATION` and emits a confirmation event. The user may grant more steps up to the configured total limit or stop the run.

Cancellation is user-driven from the Chatbot stop control. A cancel request stops provider/tool progression, attempts to cancel active ML tasks when available, records a system cancellation Message, cancels the Turn, and marks the AgentRun cancelled.

## Tool Registry

The first-slice tool registry is static for the current application capability set:

- `data.peek`
- `data.integrate`
- `data.clean`
- `data.query`
- `data.transform`
- `data.feature.select`
- `model.metadata`
- `model.train`
- `model.hyper_train`
- `model.apply`

Each registered tool carries `ToolPresentation` metadata for Chatbot projection: semantic icon key, pending summary, success summary, failure action, and cancellation summary. `data.feature.select` creates an immutable dataset column role-binding snapshot and returns `binding_id`. `model.metadata` exposes canonical model keys, model capabilities, model family/task metadata, role schemas, and optional parameter schemas. `model.train` and `model.hyper_train` accept `binding_id`, keep schemas lightweight, and validate model keys through the model catalog at execution time. `model.apply` accepts a trained model plus at least one input source: `input_files` or inline `input_rows` shaped as `{header_index_map, data}`. Trained model metadata stores role bindings and apply role schema; any supervised feature-column list is a runtime projection, not a persisted metadata field.

## Provider Boundary

The provider contract is:

```text
complete(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderResponse
stream(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderStreamEvent*
```

`ProviderResponse` carries assistant content blocks, normalized tool calls, and raw provider payload. Provider adapters own OpenAI-compatible request assembly, streaming accumulation, provider tool-name mapping, and response parsing.

CopilotKit AIMock connects through the same OpenAI-compatible HTTP boundary during development testing.

## Test Obligations

Contract tests should cover:

- thread creation with default system prompt
- provider message projection with system prompt first
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
