# No-Run Repository and Migration Impact

## Status

This is a read-only impact map for the favored provisional-exchange protocol in `11`. It records existing consumers that must change before Turn/Run persistence can be removed. It is not an implementation approval and does not modify product code, durable owner documentation, or the database.

The selected model deliberately does **not** require domain idempotency by Tool Call ID. A process-loss interruption drops the incomplete exchange; a later explicit sample is new provider work and may create new domain effects. This is a product trade, not a missing recovery implementation.

## Why This File Exists

The target ontology is small: Thread plus final typed Client/LLM Messages, with one provisional pending sampling Message and live Harness policy in memory. The current implementation spreads Turn, Run, provider-request, Tool Call, and guard identities across storage, provider projection, tools, artifacts, UI, observability, fixtures, and public DTOs. Removing tables before moving those consumers would create hidden split authority or data loss.

This file separates migration complexity from the target ontology. Complexity in the transition is not evidence that obsolete durable execution objects deserve to survive.

## Persistent Authority Mapping

| Current record / fact | Current consumers | Target authority | Migration consequence |
| --- | --- | --- | --- |
| `AgentThreadRow` | system prompt, selected model preference, title | Thread configuration remains; live model lock does not | Keep Thread identity/config/title. Deduplicate copied base SYSTEM rows and reject model changes while a provisional exchange exists. |
| `AgentMessageRow` and `AgentMessageRow.turn_id` | canonical content, kind/status/provider payload, Harness writes, replay, UI, title, tests | Typed `UserMessage` / `ClientControlMessage` / `AssistantMessage` / `ToolCallMessage` / `ToolResultMessage` | Reshape or replace explicitly. Add provisional sampling lifecycle and atomic LLM-emission/Call/Result commit constraints; remove Turn FK only after every reader moves. |
| `AgentTurnRow` | Harness open/end gates, history/event grouping, title and tests | Typed Message frontier | Replace status/group queries with the deterministic frontier; do not retain a hidden grouping row. |
| `AgentRunRow` | model lock, step budget, cancellation, retry/usage payload, UI active ID | In-process Harness context | No backfilled execution aggregate. Historical diagnostic fields are migrated only to approved final Message facts or discarded from conversation state. |
| `AgentProviderRequestRow` | retry/usage UI, provider correlation, telemetry, guard requests | Live semantic events plus Observability; optional final-Message usage/continuity | Remove as conversation state. Do not reconstruct Messages or recovery from old attempts. |
| `AgentTurnCompletionGuardRow` | persisted guard attempts and continuation | In-memory guard counter; explicit Client Control Message only when model context changes | Remove row/FK. Migrate meaningful old control content only if already a finalized conversation fact. |
| `AgentToolCallRow` | call identity, status, result/error payload, replay grouping, Chatbot details/actions | independent immutable `ToolCallMessage` plus directly linked `ToolResultMessage` | Remove mutable result/lifecycle authority. A final emission with Calls is valid only with all Results committed atomically. |
| persisted SYSTEM Messages | base prompt, guard/step/cancel reminders | Thread instructions or explicit Client Control Message | Classify by semantics; prevent duplicated instructions and hidden Run-control reconstruction. |
| Artifact `thread_id/turn_id/message_id/tool_call_id` provenance | Artifact service, repositories, exports, worker DTOs | Artifact domain state only; no Conversation-derived field or UI-filter label remains | Remove all four fields, FKs, Conversation-derived repository queries, worker DTO fields, and ArtifactService conversation validation. No `ToolResultMessage.artifact_refs` replacement is introduced. |

## Provider and Context Compiler

Current provider DTOs separate assistant content and Tool Calls, and replay reconstructs provider messages by joining adjacent Message and Tool Call rows. The target provider-neutral Message sequence requires these changes before storage removal:

- normalize normal and streaming responses into one ordered sequence of independent Message drafts, including text, refusal, reasoning, Tool Calls, provider-wire correlation, and supported extension items;
- stage a tool-calling response under a provisional sampling Message, then expose only the jointly committed LLM Message sequence/Tool Result unit to provider history;
- validate unknown/unexposed/malformed Tool Calls against the immutable advertised scope before any tool dispatch;
- preserve required opaque continuation items losslessly under an explicit adapter allowlist; do not assume old raw payloads or reasoning summaries can rebuild them;
- compile each provider's history from final Messages while retaining direct call/result pairing, Message sequence, and provider-wire IDs; a Chat Completions adapter may synthesize an assistant envelope while a Responses-style adapter may emit separate items;
- compile Responses continuation through a locally committed cursor when valid, otherwise through a provider-valid replay path or explicit capability failure; and
- exclude provisional Messages from provider input, title generation, dataset/tool-scope discovery, and all secondary prompts.

The existing provider response types and scripted fixtures must learn the independent-Message and atomic-exchange contract. Otherwise the new database shape would promise a complete tool protocol while the adapter still exposes half of one.

## LLM Conversation Port and Harness

The public boundary must replace current Turn/Run-oriented DTOs rather than wrap them:

- `append_user_message(thread_id, client_submission_id, ...)` commits one idempotent Client atom;
- `sample_existing_frontier(thread_id, ...)` samples the existing Client frontier without another User Message or attachment import;
- `cancel_sampling(message_id)` discards a pending sampling Message before it becomes a complete exchange;
- Harness requests live Tool Call progress through the LLM-owned registry/service interface. It never sends tool name, arguments, handler, or result payload back for persistence;
- no post-restart command reopens an old Tool Call by ID, fabricates a Tool Result, reconciles a generic effect, or restores live tool progress;
- a typed snapshot exposes `IDLE`, `NEEDS_LLM`, or `PENDING`, not open Turn/Run or durable Tool-execution status; and
- model lock, step counters, guard attempts, cancellation tokens, live Tool candidates, and Chatbot activity references remain in one in-process Harness context and disappear at exit.

Application composition and `services.agent` exports must remove `StartTurn`, `StartAgentRun`, provider-request, guard persistence inputs, and `invoke_tool(call_id)` recovery semantics on a bounded schedule. Compatibility aliases may exist only within an approved slice and cannot remain as alternate authorities.

The application root—not a replaceable service object—owns the private ConversationWriter capability until provider/tool callbacks terminate. Startup acquires the conversation-writer single-instance guard before constructing this capability or exposing commands. The packaged entry currently does this, but the development entry bypasses it; move ownership to the common GUI root. Shutdown stops new commands, signals live work, waits for safe callbacks where possible, then disposes storage. It does not manufacture a Tool Result or start recovery work.

## Tool Dispatch and Side Effects

`ToolExecutionContext` and concrete handlers currently receive Turn/tool-row identities. They must move to Thread plus an in-memory staged Tool Call handle for live dispatch only; Artifact/domain services must not accept that handle as provenance. Cancellation remains live-only.

The target intentionally does not add a domain call-ID idempotency contract, a durable invocation lease, or a general single-flight subsystem. In ordinary live control flow, one normalized provider response is consumed once and its calls are dispatched by the LLM-owned registry. No handler is automatically retried. The final exchange transaction enforces one Result per Tool Call Message, but cannot and does not compensate a duplicate domain effect if faulty live control flow invokes a handler twice.

Current source therefore needs no idempotency retrofit merely to support no-Run recovery. Its behavior remains an explicit risk profile:

- many default local success paths create app-owned Dataset, Binding, Artifact, MLTask, or Model output;
- `data.integrate` uses a timestamp-based generated path and can collide/overwrite an existing app-owned output; this is an independent naming defect to fix only in a separately authorized slice;
- cleanup failure paths can remove app-owned intermediate data; and
- optional SSH ML workers make remote filesystem/process changes, so a new later provider call can do more than add local unused rows.

No incomplete exchange result may be reconstructed from these domain records, provider diagnostics, or observability. If the process stops after a domain effect but before final exchange commit, startup discards the pending Message and an explicit later sample is allowed to create a new provider Tool Call. The new model request will not automatically know the orphaned IDs because they were never committed as a canonical Tool Result.

## Chatbot UI and Events

Current UI state and event IDs are Run/Turn-centric. The migration must provide a complete replacement rather than only rename fields:

- provider-sampling start/end -> Harness-owned Chatbot activity correlated internally by pending Message ID; “Thinking” is UI wording, not an LLM Service event;
- staged text/tool-call Messages -> live, non-historical Chatbot projection while the sampling Message remains provisional;
- successful joint commit -> replace/projection with final typed Assistant, Tool Call, and Tool Result activities;
- known tool failure/cancellation -> project the final Tool Result error/cancellation activity;
- pending discard, cancellation, stale cleanup, or process exit -> remove the provisional activity with no failed transcript row;
- history, auto-title, usage/connection projection, composer gating, and optimistic submission restore -> final/frontier APIs with pending exclusion.

The current `cancel_run` behavior spans provider and tool phases. It must split into live sampling/tool cancellation paths while preserving one user-facing Stop action through Harness routing. No final sampling Message remains a cancellation ID for later tool work.

## Observability

Removing provider-request/Run/Turn rows also changes telemetry schemas:

- replace Turn/Run/provider-request hashes with Thread, provisional sampling Message, and final Tool Call Message correlation as appropriate;
- retain provider attempts, retry timing, raw diagnostic wire, failures, and orphan responses only in observability sinks under retention/redaction limits;
- decide whether successful token usage is a final Message fact or observability-only before migrating old `usage_payload` rows; and
- do not let Chatbot history reconstruct connection/retry state from diagnostic persistence.

An observability outage or retention cleanup must leave provider replay, final Tool Result truth, and frontier eligibility unchanged.

## SQLite Migration Shape

The migration needs both a fresh current bootstrap and an explicit v14-to-next upgrade path.

1. Introduce typed Message/Tool Call/Result storage and constraints while old records remain readable.
2. Backfill only complete finalized protocol units:
   - map valid old Assistant/Tool Call/Result groups into ordered independent Assistant, Tool Call, and Tool Result Messages;
   - preserve stable provider call correlation and Artifact/domain records themselves while removing their conversation provenance;
   - classify SYSTEM rows as Thread instructions, Client controls, or obsolete execution notices;
   - retain only allowlisted provider continuity required by supported adapters; and
   - recover a locked model reference only from a unique provable provider-request/model or Run model fact; otherwise mark it unknown rather than inventing one.
3. An old Tool Call with no unambiguous terminal Result cannot become a final target Message. Omit/discard its enclosing incomplete assistant exchange from canonical history, preserve the preceding finalized Client frontier, never reissue the old call, and report the disposition in migration diagnostics rather than inferring it from logs.
4. Treat old `IN_PROGRESS`, `FAILED`, or `CANCELLED` partial Assistant rows, `OPEN`/nonterminal Turns, `RUNNING`/`AWAITING_CONFIRMATION` Runs, and RUNNING provider requests as non-final execution residue. Do not replay, auto-retry, restore pause/model lock, or promote them into final history.
5. Fail the database migration transaction when old complete groups are non-adjacent/corrupt and cannot be mapped without inventing order or result pairing; use the deployment migration recovery procedure. Do not invent a Thread-quarantine execution authority in this slice.
6. Rewrite Artifact and all other foreign-key consumers, then rebuild SQLite tables/indexes in dependency order.
7. Prove old/new read equivalence for valid complete history before removing obsolete Turn, Run, provider-request, guard, and mutable Tool Call authorities.
8. Delete stale new-protocol pending Messages only from the explicit main-application/LLM-writer startup barrier after migration and before snapshot/command exposure. Generic `StorageBootstrapService.initialize` is also used by preprocessing workers and must not perform conversation recovery.

Required constraints include one pending sampling Message per Thread, unique `(thread_id, sequence_index)` with transactional allocation, unique `(thread_id, client_submission_id)`, unique `ToolResultMessage.tool_call_message_id`, valid Result-to-Call same-Thread ownership, all-or-nothing final LLM-emission-with-calls/result commit, immutable final content, and fail-closed duplicate/conflict behavior.

## Verification Matrix

- Fresh schema and v14 upgrade produce the same target schema, constraints, and typed snapshot.
- Ordinary multi-message history, attachments, text-plus-tools order, multiple Tool Results, and provider-wire IDs survive migration. Artifact records survive as domain records, but their Turn/Message/Tool Call links do not.
- Legacy partial/running/unmatched-call rows never enter model context or Chatbot history and never trigger work.
- Pending insert/finalize/discard and startup cleanup are transactional; a late provider callback cannot resurrect a discarded Message.
- Only the main LLM-writer startup path performs stale-pending cleanup; preprocessing/domain worker initialization cannot alter conversation state.
- Concurrent duplicate `sample`, User submission, cancel, Thread deletion, model/scope change, and final exchange commit fail closed at the Message boundary.
- Normal and streaming provider paths finalize the same typed Message for text, refusal, reasoning, tool-only, mixed, empty, malformed, and invalid-scope responses.
- A known tool exception/cancellation produces one canonical Tool Result and permits the next model sample to choose a fresh Tool Call.
- Parallel Tool Results may finish in any order but the complete LLM Message sequence plus all Results commit atomically and replay in source Tool Call order.
- Process exit after any domain effect but before final exchange commit leaves no final Tool Call/Result in history. Restart executes nothing; an explicit re-sample starts from the prior Client frontier and may create a new semantic effect.
- Step-budget confirmation preserves its locked model only in the live process and cannot be resumed after restart.
- Chatbot activity starts/terminates correctly for provider sampling, live tools, final commit, known failure, cancellation, and stale cleanup; no provisional Message renders as history.
- `ThreadSnapshot.provider_messages`, `_dataset_ids_for_thread`, `_thread_title_snapshot_prompt`, `_should_auto_title_thread`, and `project_chatbot_events` all use final typed/frontier filters rather than Turn or raw-status shortcuts.
- Active Thread deletion is rejected until live callbacks terminate or explicitly sequenced as invalidate/cancel -> transactional delete -> late callback no-op; no callback can recreate deleted conversation state.
- Observability sink loss, rotation, or schema migration does not change canonical replay or next action.

## Documentation and Task Contracts

After implementation approval—not during this investigation—the slice must update the durable owners for Agent Harness and local-state evolution, plus task packets that declare Run/provider-request lifecycle, recovery by Tool Call ID, or `AgentToolCallRow.result_payload` as canonical. Documentation follows proven source/schema behavior; it must not pre-authorize the migration.
