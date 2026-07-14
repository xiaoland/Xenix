# Client / LLM Message Protocol — Independent Tool Call Messages, No Persistent Run

## Status

This is the current favored state model after Sir rejected both persistent `Run` and the earlier `LLMMessage.parts` envelope. It supersedes the lifecycle portions of `05`, `06`, and `07`; their tool-ownership and observability conclusions remain valid unless contradicted here. No product-code or durable-document mutation is authorized yet.

The accepted trade is intentionally lossy across process exit:

- Agent Tools are **not** required to be idempotent by Tool Call ID or equal arguments.
- There is no persistent call claim, recovery ledger, generic `effect_disposition`, or automatic tool replay.
- A live process does not retry a dispatched Tool Call. A later explicit re-sample is a new provider request and may yield a new provider Tool Call ID and repeat the semantic work.
- A tool-calling response is provisional until every one of its Tool Results is terminal. Process exit discards that provisional exchange from canonical history.

Most current default-local success paths append app-owned rows/files, but this is not a universal harmlessness proof: `data.integrate` has a timestamp-name collision risk, and configured SSH ML workers have remote side effects. Those are recorded as findings, not solved by this slice.

## Decision Thesis

Persist one linear Thread of typed Client/LLM Messages. Do not persist `Turn`, `Run`, provider-request lifecycle, step-budget continuation, a Tool Call execution ledger, a response-group record, or generic effect-disposition state as an additional conversation authority.

Provider response containers are transport facts, not canonical Message shapes. The normalizer has this direction:

```text
provider response / output items
        │
        ▼
ordered canonical Message drafts
        │
        ▼
adapter-specific provider-history projection
```

It does **not** have the reverse shape `provider response -> one persisted LLMMessage with parts`. An OpenAI-compatible response may put text and `tool_calls` in one assistant container; an OpenAI Responses result may instead expose separate output items; another adapter may expose ordered content blocks. All normalize to the same independent Message algebra below.

The simplification is valid because Xenix does not require automatic continuation of active Harness work after process exit. Harness may keep in-memory policy for model lock, step budget, cancellation, live tool progress, and Chatbot correlation. That policy is deliberately abandoned when the process stops; it is not reconstructed from observability.

`PendingLLMSamplingMessage` is a provisional Message, not a renamed Run. It has no persisted owner, retry count, tool-progress state, cancellation token, step counter, or recovery action. It exists only so a live sample can either become a complete final Message sequence or be discarded. The live phase within that provisional interval belongs to Harness memory.

## Two Sides, One Writer

`Client` and `LLM` describe message provenance, not storage ownership.

- **Client-side Messages:** `UserMessage`, `ToolResultMessage`, and an explicit `ClientControlMessage` only when a product rule must affect later model context.
- **LLM-side Messages:** `AssistantMessage` and `ToolCallMessage`. They are independent entries in the Thread's total order.
- **Provisional entry:** `PendingLLMSamplingMessage` is neither final assistant content nor a Chatbot activity. It is removed and replaced with final Messages, or discarded.
- **Single writer:** `LLMConversationService` validates, appends, finalizes, exposes typed snapshots, and compiles provider projections from canonical Messages. Harness requests live progress, owns policy and Chatbot/UI projection, and never writes a Message row or supplies a canonical tool outcome.

`Thinking`, loading, and Chatbot event identity are **not** LLM Conversation Service concepts. Harness starts/stops its own Chatbot activity around provider sampling and tool work. The UI may call an activity “Thinking”; a Message lifecycle never does.

Stable system/developer instructions are Thread configuration compiled explicitly into provider input. They are not a third participant. A guard intervention that changes later model input is a Client fact; a step counter or pause that affects only the live loop remains ephemeral Harness policy.

## Canonical Shape

```text
Thread
├─ instructions / stable conversation configuration
└─ Message[] (one immutable logical total order)
   ├─ UserMessage(client_submission_id, content, bounded attachment/domain refs)
   ├─ ClientControlMessage(kind, bounded content)
   ├─ AssistantMessage(text/refusal/reasoning, bounded adapter-continuity facts)
   ├─ ToolCallMessage(
   │    provider_call_id?, tool_id, contract_version,
   │    immutable arguments, immutable advertised-scope fingerprint)
   ├─ ToolResultMessage(
   │    tool_call_message_id, terminal status,
   │    bounded value/error)
   └─ PendingLLMSamplingMessage(PENDING only; provisional and excluded)
```

`ToolCallMessage` is a first-class LLM-authored Message. It is not an `AssistantMessage` child, a field inside an LLM envelope, or a mutable `AgentToolCallRow` beside Message state. Its own immutable Message ID is the canonical call identity; `provider_call_id` is adapter pairing data only. Neither is a domain idempotency key, replay lease, or durable execution identity.

`ToolResultMessage` is a first-class Client-authored Message. It carries the sole bounded terminal outcome and has a direct, same-Thread foreign key to `ToolCallMessage.id`. The database admits at most one final Result for a final Call. Artifact and domain entities remain authoritative and are not linked to Messages as conversation provenance.

There is deliberately no `parent_assistant_id`, `response_group_id`, or hidden Assistant envelope. A relationship that merely says “this call is a part of that assistant response” recreates the rejected shape under another name. The only required identity relation is call-to-result; model-output chronology is represented by the immutable Thread sequence and validated protocol grammar.

## Protocol Grammar and Provider Projection

For one serialized Thread, a final sampled LLM emission is a non-empty contiguous sequence of `AssistantMessage` and `ToolCallMessage` entries. It begins after a finalized Client frontier and ends before the next Client Message. A fresh LLM sample is not allowed until that frontier changes.

If the emission contains Tool Calls, its next Client contribution consists of exactly one terminal `ToolResultMessage` for every Call, each linked by `tool_call_message_id`. Results are written in originating Tool Call order even when live handlers completed in another order. Only after this complete Client contribution is the next model sample eligible.

```text
UserMessage / ClientControlMessage
        │
        ▼
AssistantMessage? ── ToolCallMessage*      (one LLM emission)
                          │
                          └── ToolResultMessage* (direct FK to each call)
                                       │
                                       ▼
                              next LLM sample, if requested
```

An LLM emission with no Tool Calls can contain one or more `AssistantMessage`s and then permits the next Client message. A tool-only response needs no empty Assistant shell. A future adapter that genuinely exposes text-before/call/text-after must expose that order as `ProviderOutputItem`s; only then can it become the corresponding ordered sequence of independent Messages. The current Chat Completions dialect does not claim such interleaving inside its one assistant container.

This is not the current adjacency heuristic. Current code identifies a call's relationship to an assistant response by scanning for consecutive `TOOL_CALL` rows, and it stores result truth elsewhere. The target uses:

1. immutable total order for chronology;
2. a direct `ToolResultMessage -> ToolCallMessage` foreign key for call/result identity; and
3. one atomic final insertion for a complete emission with calls and all of its Results.

An adapter may consume the validated contiguous LLM emission when it needs to construct one provider container. It may never use adjacency to guess which Result belongs to which Call. The single-frontier grammar—not a persisted response-group object—makes the emission boundary deterministic. If Xenix later permits concurrent generations, server-push LLM entries, or resumable partial emissions, it must introduce and justify a new protocol fact; this model must not smuggle one in now.

Provider adapters own wire translation:

- a Chat Completions-style adapter may fold a canonical LLM emission into one assistant wire message with text plus `tool_calls`, then emit tool-result wire messages using the stored provider call IDs;
- a Responses- or Gemini-style adapter may project the same canonical entries as separate output/function items or steps; and
- adapters retain only allowlisted, lossless continuity facts that their provider requires. Missing required continuity fails or degrades explicitly; it is never reconstructed from a summary or observability.

The adapter must preserve canonical sequence and direct call/result pairing. It may synthesize the provider's container shape; that synthesized container never becomes SQLite's canonical Message shape.

### Current supported adapter: OpenAI-compatible Chat Completions

v15 supports one runtime dialect: an OpenAI-compatible Chat Completions response with exactly one selected assistant choice. Its completed output is one assistant container with optional `content`, `reasoning_content`, and `refusal`, plus an ordered `tool_calls[]` array. The target canonical Assistant fields are therefore typed nullable `text`, `reasoning`, and `refusal`; there is no opaque Assistant-continuity JSON or raw provider-response blob. The supported adapter needs no further remote cursor/continuity fact. A future dialect that does must add a lossless typed capability and migration before it is enabled.

Its canonical ordering contract is fixed:

1. Normalize the complete assistant content/reasoning/refusal into zero or one `AssistantMessage`.
2. Normalize `tool_calls[]` into `ToolCallMessage`s in the array's source order.
3. The resulting sequence is `AssistantMessage?`, followed by `ToolCallMessage*`. A tool-only response has no empty Assistant Message.

Normal and streaming output must produce that same sequence. Stream chunk arrival is transport fragmentation, not canonical chronology: text/reasoning/refusal fragments are accumulated into the one optional Assistant draft, and Tool Calls are ordered by their strict non-negative stream `index`. Final stream indexes must be contiguous from `0`; arrival in a different order does not reorder the final Calls.

The adapter fails before dispatch and discards the pending exchange when it cannot establish that projection: the completed response has zero or multiple selected choices; a selected choice/message has an invalid shape; an output is empty without a Tool Call; a Tool Call ID is blank or duplicated; a Tool name is not exposed; arguments are not a JSON object or exceed the bound below; or a stream index is absent, non-integral, negative, duplicated inconsistently, or non-contiguous. A usage-only terminal stream chunk may omit `choices`; it cannot stand in for a completed assistant choice. The adapter must never silently select the first of several choices, default a malformed index to zero, skip an unknown Tool, or derive ordering from raw chunk arrival.

## No Orphan Tool Call in Final History

The final-history invariant is deliberately strong:

1. A sampled output with no Tool Calls may replace its pending placeholder with its final LLM Messages immediately.
2. A sampled output with `N` Tool Calls replaces its pending placeholder only in the same transaction that inserts all `N` final Tool Call Messages and exactly `N` immutable Tool Result Messages.
3. A known handler failure or cooperative cancellation is a terminal Tool Result with bounded error/cancellation facts. The next LLM sample can therefore see the failure and choose a fresh Tool Call.
4. A process exit before the joint commit creates **no** final Tool Call and fabricates **no** Tool Result. The provisional sampling Message is discarded during the main writer's startup barrier.

Thus a historical snapshot can never contain “Tool Call but no Tool Result”. It contains either a complete protocol unit or neither side of an interrupted unit. This is an atomic conversation commit, not a cross-domain transaction: a domain effect may already exist when the provisional exchange is discarded.

Tool Results are not exposed through a generic client-append API. The LLM Conversation Service creates them from the registered AgentTool implementation's bounded terminal result.

## Provisional Exchange Lifecycle

1. `append_user_message` is valid only from an `IDLE` final-LLM frontier and commits one Client Message. A Thread whose final tail is already Client-side (`NEEDS_LLM`) rejects a second User append; the caller must explicitly sample/retry that existing frontier rather than create an implicit batch. `client_submission_id` still prevents a lost acknowledgement from duplicating the User Message itself.
2. Immediately before provider I/O, LLM Conversation Service inserts one empty `PendingLLMSamplingMessage`. A partial unique constraint permits at most one pending sampling Message per Thread.
3. Harness observes a provider-sampling transition and may create a Chatbot activity. The pending Message is excluded from provider context, ordinary history, title generation, and data/tool discovery.
4. The adapter normalizes the completed provider output into an ordered list of independent Message drafts. For output without Tool Calls, the service atomically removes the pending Message and inserts the final LLM Messages.
5. For output with Tool Calls, the complete draft sequence remains provisional. Harness requests live tool progress through the LLM public interface; LLM Service validates each staged Call and dispatches the registered AgentTool implementation itself.
6. Tool completions are held as bounded live candidates, keyed by staged Tool Call Message ID. Success, known failure, and cooperative cancellation all count as terminal candidates. Harness may show tool activity, but that activity is not canonical history.
7. When every staged Tool Call has a terminal candidate, one transaction removes the pending Message and inserts the final LLM Messages, final Tool Call Messages, and all linked Tool Result Messages. Completion order never changes canonical Message order.
8. Every provider error before finalization, malformed/unsupported output, cancellation before a terminal tool candidate, database failure, or process exit discards the pending Message. It never invents a failure Tool Result and never re-dispatches the old backend call. A completed Tool whose normal result exceeds the bounded-result contract is different: it becomes one bounded terminal `tool_result_too_large` error candidate, preserving the no-unmatched-Call invariant without silently truncating the result.
9. On restart, only the main LLM-writer startup barrier discards stale pending sampling Messages. It sends no provider request and executes no tool. A later **explicit** retry samples the existing finalized Client frontier; the provider may produce a new Tool Call and the semantic effect may occur again.

Thinking ends when provider sampling ends, even if live tools are still running. Tool activity is a distinct Harness/UI projection. This prevents a pending sampling Message from becoming a loading-indicator synonym.

## Deterministic Frontier Eligibility

The canonical database has no durable `NEEDS_TOOLS` or `TOOL_EXECUTING` state. Those are live Harness facts only.

| State | Canonical eligibility | Next valid operation |
| --- | --- | --- |
| `IDLE` | Empty Thread, or final LLM tail with no unresolved protocol unit | append a User Message |
| `NEEDS_LLM` | Final Client tail, including a complete Tool Result set, or a stale provisional exchange discarded at startup | explicitly sample the existing frontier; reject another User append |
| `PENDING` | One provisional sampling Message exists | live Harness/provider/tool callbacks only; no new User or model command |

User submission is also rejected while a `NEEDS_LLM` Client tail awaits its first/retry sample. Model/scope changes, Thread deletion, and ordinary Client controls are rejected while a pending Message exists. Xenix does not create a hidden durable queue or implicit User batching.

The fact that an in-process Harness is currently sampling versus executing a tool is not represented by a stored status. It may hold that fact in memory for cancellation and Chatbot reduction, then loses it at exit.

## A Natural Python Writer Boundary

Python cannot give Rust-style compile-time affine ownership: privacy is architectural rather than unforgeable. The clean equivalent is a capability topology, not a public setter on mutable ORM rows:

```text
UI / Harness / provider callbacks
             │ typed commands and immutable snapshots only
             ▼
LLMConversationService
 ├─ private ConversationWriter capability
 ├─ private serialized per-Thread mutation gate
 ├─ provider/context compiler
 └─ LLM-owned AgentTool protocol and registry
```

Only the service holds `ConversationWriter`; it opens the database transaction and mutates the Message aggregate. Callers receive immutable DTOs/snapshots and submit commands, never sessions, repositories, ORM rows, or a setter. The mutation gate orders append, pending insert/finalize/discard, joint final-exchange commit, deletion, and model/scope changes. Provider and tool I/O occur outside that gate; terminal state re-enters through a compare-and-swap transaction.

There is deliberately no separate call-ID single-flight subsystem, durable claim, or replay promise. Normal live control flow consumes one normalized provider response and dispatches its Tool Calls without automatic retry. Final-history uniqueness rejects a second canonical Result for the same Tool Call Message, but it does not claim to undo a duplicate domain effect should an implementation bug invoke a handler twice.

This private capability plus import-boundary tests is the Python substitute for Rust ownership. SQLite uniqueness/foreign-key constraints remain the backstop, not the primary topology. At deployment scope, the GUI root must hold one `SingleInstanceGuard` before constructing the service. Domain worker processes may write their own domain tables but never construct `ConversationWriter`, mutate Messages, or run pending cleanup. The current packaged entry has that guard while the development entry bypasses it; the common GUI root must own it before the invariant is considered enforced.

## Tool Ownership and Side Effects

`invoke_tool` remains an LLM-owned operation: Harness never invokes a concrete handler and returns an outcome for persistence; LLM Service never calls Harness. Concrete implementations satisfy the LLM-owned `AgentTool` protocol, are injected through a registration interface/composition root, and depend on their domain services.

Harness chooses whether and when live policy allows tool progress. LLM Service reads a staged Tool Call's identity, arguments, scope, and contract from its own provisional exchange, invokes the registered implementation, and writes the sole canonical Tool Result only as part of the joint final commit. A live invocation command cannot be resumed after process exit.

The pending exchange has fixed, non-persistent resource limits:

- at most **16** staged Tool Calls per provider response, matching the current initial live step limit;
- at most **64 KiB** of canonical UTF-8 JSON for each Tool Call argument object and each terminal Tool Result payload (including its value/error envelope); and
- at most **1 MiB** of terminal Tool Result candidate payloads for the whole exchange (`16 × 64 KiB`).

More than 16 Calls or an oversized argument is a provider-normalization failure before dispatch. An oversized completed Tool result is replaced by the bounded terminal error described above; its raw value is not truncated into history. These limits keep staged memory bounded without creating a persisted Run, result ledger, or idempotency regime. The 64 KiB unit follows the existing bounded Agent Skill resource contract.

Artifact registration is a domain operation. `ArtifactService` accepts neither Turn/Message/Tool Call provenance nor a conversation foreign key, and `ToolResultMessage` has no normalized artifact-reference field. Tool-specific output may still contain its ordinary bounded result value, but it cannot create a second cross-domain lineage contract.

No current or future AgentTool is granted a blanket “duplicate effects are harmless” proof. This design instead makes a narrower product trade:

- it does not automatically retry a dispatched Tool Call;
- it accepts that an explicit later provider sample can issue a new Tool Call for similar work;
- it accepts orphaned domain data/effects when an incomplete provisional exchange is discarded; and
- it treats file-collision, external-worker, destructive, expensive, or otherwise unsuitable tool behavior as an independent tool/domain concern rather than hiding it in conversation state.

Current facts to preserve in the migration risk register: default local success paths mostly create app-owned data, `data.integrate` can collide on timestamped output names, error cleanup may delete app-owned material, and optional SSH ML workers perform remote operations. This protocol neither solves nor masks those facts.

## Provider History and Observability

- Provider history is compiled only from finalized Messages. A complete tool exchange preserves Message sequence plus direct Tool Call/Result correlation.
- Chat Completions receives provider-valid history; Responses may use a locally committed cursor where valid. The adapter decides transport shape, but SQLite finalized Messages remain the SSoT.
- A stale provisional sampling Message never enters provider replay, title generation, dataset/tool availability, or ordinary UI history. Its discarded domain effects do not automatically appear in conversation context merely because they exist in domain tables.
- Provider attempts, retry timing, raw wire, failures, and successful token usage belong to Observability. They cannot recover a discarded exchange, create a Tool Result, or determine the next frontier action. Harness may project a transient usage Chatbot event, but usage never becomes a Message field or recovery input.

### Streaming and retry presentation

The first cutover preserves the current retry-safe buffering rule. While a streaming request is retryable, text/reasoning/refusal deltas remain inside the provider buffer; Harness projects only live sampling/retry activity, not irreversible partial assistant text. After one completed output normalizes successfully, Harness may start Tool activity for staged Calls and the service eventually projects final Message history. This deliberately avoids rollback/replacement UI for partial text; a later task may choose that UX explicitly.

## Invariants and Proof Obligations

1. `LLMConversationService` is the only production holder of `ConversationWriter`; UI, Harness, provider adapters, and domain workers cannot mutate canonical Message storage directly.
2. At most one pending sampling Message exists per Thread, and its lifecycle is only provisional replacement with final Messages or discard.
3. `ToolCallMessage` and `ToolResultMessage` are independent canonical Message kinds; no canonical Message contains a Tool Call part or has a hidden parent/response-group relationship.
4. A final Tool Result directly references one final Tool Call in the same Thread; a final tool-containing emission and its complete Result set are committed atomically; final history has no unmatched Call.
5. A known tool failure/cancellation becomes a bounded Tool Result; process loss does not manufacture one.
6. Process restart sends no provider request and executes no tool. It only discards stale provisional Messages from the main writer startup barrier.
7. An explicit retry after discard starts from the prior finalized Client frontier and may cause new provider Tool Call IDs and repeated semantic effects.
8. Provider adapters preserve canonical sequence and call/result correlation or fail explicitly; no adapter container becomes canonical storage.
9. Thinking and all Chatbot activity are Harness/UI projections of live sampling/tool policy, never LLM Service concepts.
10. Observability loss cannot change Message replay, Tool Result truth, authorization, or the next canonical action.
11. User submission, Thread deletion, model/scope change, and callbacks are transactionally gated against the pending frontier and total sequence; no command silently queues behind live work.

## Product Trade Accepted by This Model

Removing persistent Run is correct only if Xenix explicitly accepts all of the following:

- no automatic cross-process continuation of sampling, tool execution, step-budget pause, guard attempt, or cancellation;
- one enforced conversation-writer process/service lifetime per local database and no persisted concurrent branches; domain workers remain outside conversation ownership;
- known tool failure is shown to the next model sample through a canonical Tool Result, while process-loss interruption is not;
- a process-loss interruption removes the incomplete LLM/tool exchange from history and an explicit retry may repeat semantic work with new provider call IDs;
- no tool-result recovery from execution logs, domain artifacts, or provider attempts; and
- provider-attempt history is diagnostic telemetry, not conversation state.

If any of these capabilities becomes a product requirement, durable execution state or domain-specific idempotence may again be needed. It should then be introduced honestly rather than hidden in Message metadata.

## Accepted Pre-Implementation Contracts

1. v15 has typed Assistant `text`, `reasoning`, and `refusal` fields, no generic opaque continuity blob, and the Chat Completions ordering/validation contract above.
2. Successful token usage is observability-only; a live Chatbot display is not canonical history.
3. A second User Message cannot extend a `NEEDS_LLM` Client block; it must first be sampled explicitly.
4. Streaming retains retry-safe text buffering for this cutover; `Thinking`/retry/Tool activity remain Harness Chatbot events.
5. One pending exchange permits at most 16 Calls, 64 KiB canonical JSON per argument/result payload, and 1 MiB total result candidates. These are enforced fail-closed or converted to a bounded terminal Tool Result error as specified above.
