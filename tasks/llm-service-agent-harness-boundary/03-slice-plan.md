# Review and Implementation Workstreams

## Current Gate

Solidify, ready to prepare one whole-task Impact Handshake. The former combined Slice 1 draft is retained as superseded evidence in [04-slice-1-impact-handshake.md](04-slice-1-impact-handshake.md); it is not an approval request. No cross-owner implementation state diff is approved yet.

Sir selected one complete delivery for this task. The numbered sections below are therefore dependency-ordered development workstreams, not independently deployable migrations, releases, or approvals. The Artifact work in `15`/`16` is folded into the same final source and schema cutover; [17-whole-task-implementation-rehearsal.md](17-whole-task-implementation-rehearsal.md) is the controlling rehearsal.

## Slice 0 — Facts and Decision Inputs

- Reproduce or disprove historical-context loss using a persisted multi-turn thread and inspect the generated provider messages.
- Map the current conversation records and their readers/writers; identify the semantic value of `Turn` separately from table shape.
- Compare LLM-owned versus split execution-boundary alternatives, including dependency direction and authority consequences.
- Settle the product contract for visible streaming text versus retry safety.

**Result:** historical-context loss is disproved for ordinary messages. Sir selected corrected Refined A ownership: LLM owns canonical Thread/typed Message plus AgentTool protocol/registry/invocation; concrete tools implement that LLM-owned protocol and are injected; Harness owns orchestration policy and never acts as a tool-execution port. Observability owns logs and never conversation reconstruction. Sir then rejected persistent Run because Xenix does not require cross-process execution continuation; `11` replaces the earlier Thread+Run shape with a Client/LLM Message protocol where incomplete tool exchanges stay provisional and are discarded at exit. `10` recommends `LLMConversationService` over `LLMChatService`. `12` maps the concrete repository and migration impact. The selected contracts are retry-safe streamed-text buffering, observability-only token usage, no implicit Client-message batching, bounded staged Tool results, and one cohesive whole-task cutover.

## Slice 1 — Adapter Protocol Correctness

- Fail closed for unknown/unexposed provider tool calls without leaking raw provider detail.
- Normalize malformed provider response and stream shapes into explicit domain errors and retry classification.
- Add real LLM-Service-to-Harness tests for retry success/exhaustion without treating retry telemetry as recovery state.

**Potential blast radius:** LLM adapter, retry projection, focused tests. This slice does not move canonical state and requires a new, narrower Impact Handshake.

## Slice 2 — LLM Conversation Port and Tool Contract

- Establish the LLM-owned Thread/typed Client/LLM Message port and typed snapshot without exposing a SQL session or storage rows to Harness.
- Define the LLM-owned `AgentTool` protocol, registry, per-sampling exposed scope, and live invocation DTO/result. Concrete adapters are injected and never imported by LLM. Do not add call-ID replay, a durable claim, or a generic effect disposition.
- Prove the source dependency direction with an import/architecture test and fail closed on any provider call outside the exposed scope.
- Replace Turn/Run public commands with explicit `append_user_message`, `sample_existing_frontier`, and `cancel_sampling(message_id)`, plus narrow live-tool progress commands that cannot resume after process exit. User append is idempotent by client submission ID.
- Keep Harness execution context in-process; lock model/step/guard/cancel policy there and remove any dependency on persisted Run/provider-request lifecycle. Sampling and tool execution use different Message/Call identities rather than a spanning Run ID. Give LLM Conversation Service the private ConversationWriter/mutation gate; Harness receives only typed commands and snapshots.

**Potential blast radius:** LLM service, current conversation store/repository seam, Harness, Chatbot projections, observability, application composition, compatibility exports, and focused tests.

## Slice 3 — Typed Message Protocol and Frontier Convergence

- Move the canonical Thread/Message journal behind LLM Service and remove Harness direct persistence access. Explicitly reshape or replace `AgentMessageRow`; do not leave its old kind/status/provider-payload contract as a parallel authority.
- Normalize one sampled provider response into an ordered sequence of independent `AssistantMessage` / `ToolCallMessage` drafts. A Tool Call is never an LLM Message part; final tool-containing emissions and their one-for-one directly linked `ToolResultMessage`s commit atomically. Remove duplicate ToolCall result payload and current adjacency-as-identity grouping.
- Change provider DTOs/normalizers to preserve ordered text, refusal, reasoning, Tool Call, provider-wire correlation, and required opaque continuity before the old row shape is removed. Each adapter reconstructs its own response container from the canonical sequence.
- Implement `sample` as `validate frontier -> commit PendingLLMSamplingMessage -> external request -> atomically replace with final Message sequence or discard`. For Tool Calls, stage independent Message drafts provisionally, collect terminal live Tool Results, then atomically finalize the emission plus all Results. Exclude pending/partial Messages from every provider/UI/title/tool-scope projection.
- Enforce one pending sampling Message per Thread, one immutable Result per Tool Call Message, original ToolScope/contract revalidation, and exact completion of parallel Results before the joint commit. Project Results by source Tool Call order rather than completion order. Do not create a durable call claim or replay subsystem.
- Define cancellation separately for sampling and live tools. A known terminal failure/cancellation becomes a Result; process loss discards the provisional exchange and never fabricates a Result.
- Prove normal/stream final-state parity across text, tools, parallel tools, known failure, empty/invalid response, guard, live step confirmation, cancellation races, explicit frontier retry, process loss after a domain effect/before joint commit, duplicate submission, stale-placeholder cleanup, late provider callback, and observability sink failure.

**Potential blast radius:** storage schema/repositories, Harness, LLM Service, observability, Chatbot events, application composition, tests, and runtime recovery.

## Slice 4 — Obsolete Execution Persistence and FK Removal

- Apply only after the protocol decisions and acceptance trade in `11` are confirmed.
- Backfill finalized typed Messages, ordered independent LLM Message sequences, exact allowlisted adapter continuity, and unique direct Result associations. Audit old raw payloads rather than silently treating them as reconstructible state.
- Remove `AgentTurnRow`, `AgentRunRow`, `AgentProviderRequestRow`, and `AgentTurnCompletionGuardRow`. Replace the mutable authority of `AgentToolCallRow`; any retained Tool Call index is immutable Message-owned storage, not a second result/lifecycle owner.
- Rewrite every Turn/Run/tool-call consumer before dropping foreign keys: remove Artifact provenance and its repository/worker DTO fields rather than replacing it, then move ToolExecutionContext, Chatbot detail/actions, cancellation/step-budget UI, auto-title/history prompts, observability attributes, app composition, exports, fixtures, and owned documentation. The concrete map is [12-no-run-repository-impact.md](12-no-run-repository-impact.md).
- Provide both a current fresh bootstrap and an explicit v14-to-next forward migration. Rebuild SQLite tables/FKs in dependency order, map only complete old Tool Call/Result groups into final history, and omit legacy interrupted exchanges rather than replaying or reconstructing them. Clean stale provisional rows without retry only from the main LLM-writer startup barrier, preserve stable domain/call references, and prove upgrade/fresh-schema equivalence.
- Define migration policy for old `IN_PROGRESS`/`FAILED`/`CANCELLED` Assistant rows, RUNNING provider requests, malformed/non-adjacent Tool Call groups, SYSTEM rows, usage/retry telemetry, and sequence compaction. Never promote uncertain legacy execution into finalized conversation truth.

**Potential blast radius:** storage schema/migrations/repositories, provider DTOs, Harness, LLM Service, UI, snapshots/events, tools/domain workers, artifacts, observability, fixtures/exports, tests, task contracts, and durable conversation/recovery documentation.

## Slice 5 — Causal-Loop Simplification

- Establish a shared internal step boundary for normal and streaming execution while keeping live rendering as a projection.
- Prove normal/stream final-state parity after the selected ownership is in place.

**Potential blast radius:** Harness orchestration, LLM interaction commands, observability, Chatbot events, focused tests.

## Whole-Task Mutation Gate

Before the cohesive implementation, record and obtain approval for:

1. **Address and Object:** exact files, symbols, schema edges, and tests.
2. **State Diff:** precise `From -> To` behavior and ownership.
3. **Blast Radius:** all consumers, persisted records, migration and UI effects.
4. **Invariants:** behavior and authority that must remain unchanged.
5. **Verification:** focused PDM commands, migration proof, and regression scenarios.
