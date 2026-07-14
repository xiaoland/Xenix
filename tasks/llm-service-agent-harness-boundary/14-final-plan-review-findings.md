# Final Plan Review Findings

## Status

The final independent review is complete. The core topology is not rejected. The decisions that closed its architecture gates are now recorded in `11` and `17`; O-4 remains implementation-proof gated, not product-choice gated. This packet is ready to prepare one whole-task Impact Handshake, which still authorizes no mutation by itself.

This record is task-local evidence. It authorizes no product-code, schema, durable-document, external-state, or commit mutation.

## Review Inputs

- **Deductive topology audit:** one-authority ontology, hidden Turn/Run/envelope detection, dependency direction, and provider-neutral Message algebra.
- **Adversarial temporal audit:** frontier races, cancellation, late callbacks, stream/non-stream convergence, process loss, artifact writes, and migration residue.
- **Inductive source audit:** current schema, provider normalizer, Harness dispatch, Artifact/worker paths, bootstrap topology, and existing tests.

## Verdict by Root Objective

| Objective | Verdict | Why |
| --- | --- | --- |
| O-1 — one durable conversation language | **Satisfied conceptually; implementation-gated** | Independent final `AssistantMessage`, `ToolCallMessage`, and directly linked `ToolResultMessage` remain the smallest SSoT. Current code is the known opposite: replay joins adjacent rows and `AgentToolCallRow.result_payload` owns outcome truth. |
| O-2 — no false execution promise | **Satisfied under the accepted loss trade; gate required** | One pending sampling placeholder, in-memory staged calls, atomic final commit, and process-loss discard do not require Run/Turn/replay. They need exact CAS, callback invalidation, and cancellation linearization to stay that way. |
| O-3 — one-way authority topology | **Target satisfied; source not yet aligned** | LLM-owned Tool protocol/registry/dispatch with injected implementations is clean. Current Harness still directly dispatches tools and mixes tool spec, handler, and presentation. |
| O-4 — faithful, enforceable realization | **Blocked until the gates below close** | Artifact provenance, provider normalization/continuity, writer concurrency, schema enforcement, and migration cut-set behavior are currently incompatible or underspecified. |

## Confirmed Non-Blockers

These remain explicit product trades, not defects to solve in this slice:

- process loss may orphan domain rows/files and a later explicit sample may repeat semantic tool work;
- no automatic cross-process continuation, call replay, idempotency guarantee, generic unknown-effect state, or execution ledger;
- no persisted `Turn`, `Run`, response group, parent Assistant, or third conversation service; and
- `Thinking` remains a Harness Chatbot Event, not a Message lifecycle.

## Blocking Gates

### G-01 — Remove Artifact Conversation Provenance

The current design cannot retain `ArtifactRow.turn_id`, `message_id`, or `tool_call_id` conversation provenance or their foreign keys:

- `ArtifactService._validate_links` imports and queries conversation storage before artifact registration.
- concrete tools and the preprocessing worker register artifacts during handler execution, in independent sessions/processes;
- the selected protocol intentionally keeps staged Tool Calls in memory and writes final Calls/Results only in the joint final transaction.

Pre-inserting a durable provisional Call or retaining a discarded Call tombstone would reintroduce an unmatched, execution-shaped persistence surface. That conflicts with the fixed no-orphan/no-ledger contract.

**Accepted decision from Sir:** remove the relationship rather than replacing it. Artifact owns only Artifact facts; it does not import/query Conversation/Harness storage, validate Conversation IDs, or store Thread/Turn/Message/Tool Call provenance. `ToolResultMessage` does not gain `artifact_refs` or any other normalized lineage field. `Artifact.thread_id` is removed as well; no opaque UI filter label or metadata substitute remains. A discarded exchange may leave a domain Artifact, but it creates no conversation history and is never fed back to provider context.

**Evidence:** `src/xenix/services/storage/models.py:455-463`; `src/xenix/services/artifact_service.py:181-208`; `src/xenix/services/agent/tools.py:879-884`, `954-965`, `1386-1396`, `1528-1547`; `src/xenix/services/preprocessing_worker.py:128-169`.

### G-02 — Claim the Client Frontier Atomically

`append_user_message` and `sample_existing_frontier` cannot be independent, unguarded steps. Otherwise one caller can append `U1`, another append `U2`, and the first caller samples a frontier it did not claim; a stale retry can also invoke the provider after a later exchange has completed.

**Required rule:** `sample_existing_frontier(thread_id, expected_frontier_id)` validates the exact finalized Client tail and inserts `PendingLLMSamplingMessage` under the same private per-Thread gate. A stale expected frontier fails closed. For the initial UX, a Thread with a `NEEDS_LLM` Client tail must reject another User append rather than silently batching it; explicit batching can be designed later as a separate product rule. Attachment materialization must occur only after that claim or carry the same submission key, so a rejected/duplicate UI request cannot still create duplicate domain imports.

The pending Message ID is the one allowed live generation token. It is not a Run: it has no retry, ownership, step, tool-progress, or recovery state.

**Evidence:** `src/xenix/services/agent/conversation_store.py:317-498`; `src/xenix/services/agent/harness_service.py:307-313`, `725-824`, `1024-1162`.

### G-03 — Make Finalization and Cancellation Linearizable

The no-orphan claim cannot rest on a simple foreign key and service convention.

**Required rule set:**

1. Staged calls live only in an LLM-service in-memory registry keyed by `(pending_message_id, staged_call_id)` with frozen scope/contract and deep-copied arguments.
2. All staged calls validate before any dispatch. A scope/registry mismatch before side effects discards the whole provisional exchange; it never leaves a partial Call.
3. The finalizer performs compare-and-swap on the current pending Message and writes final LLM Messages, Tool Call Messages, and all Results in one transaction. Result insertion is available only through that finalizer.
4. A User Stop/delete/cancel invalidates the pending Message under the writer gate. Late provider/tool callbacks then no-op. If finalization wins first, it is final; if cancellation wins first, the whole provisional exchange is discarded. A handler-returned cancellation is a terminal Result only while the pending generation remains current.
5. SQLite/schema plus writer validation must enforce unique Result-to-Call, same Thread, target kind, immutable final Messages, total sequence uniqueness, and no generic independent Call/Result mutation. Cross-row order/completeness remains a writer/transaction invariant with tests.

Dispatch of multiple calls is **serial by default**. The protocol must preserve source-call order and must not depend on completion order; actual parallel dispatch is a future Harness policy, not a required migration scope.

### G-04 — Provider Normalization Must Be Ordered, Bounded, and Fail Closed

The target algebra requires an ordered provider-output representation, not current parallel `assistant_content_blocks` plus `tool_calls` lists. The selected v15 scope supports only OpenAI-compatible Chat Completions: one completed assistant choice becomes typed `text`/`reasoning`/`refusal`, followed by Calls in the normal `tool_calls[]` order or strict completed stream-index order. There is no opaque `ContinuityFacts` blob, remote cursor, or response envelope in canonical storage.

Normal and stream paths must use identical final normalization. Raw response payload, observability record, or summary may never reconstruct continuity. Zero/multiple choices, an empty output without Calls, unknown/unexposed calls, blank/duplicate IDs, non-object or oversized arguments, malformed/non-contiguous stream indexes, and unsupported ordering fail before dispatch and discard the pending exchange. Text deltas stay retry-safe buffered for this cutover.

**Evidence:** `src/xenix/services/llm/providers.py:26-45`, `324-354`, `401-444`, `447-461`; `src/xenix/services/agent/harness_service.py:686-693`.

### G-05 — Move Real Tool Authority and Context Compilation

The target dependency graph is right but has to include built-in skills and provider-context construction:

- LLM defines ToolDefinition/Invoker/Result/Registry and dispatches injected concrete implementations.
- Harness decides scope and live policy, triggers an LLM command, and projects Chatbot events; it never dispatches a concrete handler or supplies a canonical outcome.
- Tool presentation stays Harness/UI-owned. LLM core imports neither `services.agent`, concrete tools, nor domain services.
- Provider-context compilation and tool-definition normalization move behind the LLM public boundary; Harness may supply a provider-neutral scope command, not provider wire data or prompt fragments.

**Evidence:** `src/xenix/services/agent/harness_service.py:1634-1680`, `1690-1753`; `src/xenix/services/agent/tools.py:77-172`; `src/xenix/services/agent/skill_catalog.py:62-177`; `src/xenix/app.py:511-531`.

### G-06 — Enforce One Writer and a Safe Migration Cut-Set

- Move `SingleInstanceGuard` to the common GUI root before `ConversationWriter` construction; the packaged entry alone is insufficient. Workers may initialize domain storage but may never clean pending conversation state or construct the writer.
- A database failure cannot promise immediate deletion; startup cleanup is best effort and must be fail-closed if final/provisional invariants cannot be classified.
- v14 migration must cut at an unmatched legacy Tool Call. It may retain the verified prefix and a later independently rooted User segment, but cannot project dependent assistant/tool suffixes as valid history. Remove Artifact conversation links; migration must never fabricate Calls, Results, lineage replacements, or tombstones.
- Before adding the one-pending partial unique index, classify/remove multiple stale legacy pending rows. Sequence allocation moves from `max + 1` to writer-gated allocation plus unique constraint.

**Evidence:** `scripts/run_packaged.py:47-60`; `scripts/run_dev.py`; `src/xenix/services/preprocessing_worker.py:133-142`; `src/xenix/services/storage/repositories/agent_conversations.py:185-205`.

## Required Go/No-Go Tests

1. Concurrent submit/sample, including source attachments: exactly one claimed frontier and no duplicated User/import side effect.
2. SQLite failpoints at pending insert, final exchange commit, and cleanup: no partial final Call/Result history.
3. Provider/tool cancellation, Thread deletion, shutdown, and late/duplicate callback races: no resurrection and no hidden tombstone.
4. Multiple Tool Calls with reversed completion order and duplicate callbacks: one Result per Call and source-order replay. Initial dispatch remains serial.
5. Artifact-producing local and worker tool: registration succeeds without Thread/Turn/Message/Tool Call provenance; discard leaves no dangling conversation FK and no context-visible phantom.
6. Unknown raw provider tool call, zero/multiple choices, malformed/duplicate IDs, invalid/oversized arguments, reasoning/refusal, content-plus-Calls ordering, non-contiguous stream indexes, and stream/non-stream parity all fail or project deterministically.
7. v14 upgrade with unmatched Calls, downstream rows, artifacts, and stale pending records: explicit cut/failure, no fabricated history.
8. GUI/dev/worker startup topology, observability sink loss, and provider/title/dataset/UI filtering preserve canonical replay/frontier behavior.

## Accepted Decision from Sir Before the Impact Handshake

Artifact provenance is removed directly. It is not replaced by `ToolResultMessage.artifact_refs`, a lineage table, a Tool Call tombstone, or a deferred conversation-owned binding step. This retains Artifact domain ownership and makes the selected loss boundary honest.
