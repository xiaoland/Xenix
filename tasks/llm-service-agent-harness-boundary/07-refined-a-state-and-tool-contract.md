# Corrected Refined A — Object, State, and Tool Contract

## Status — Partially Superseded

The two-owner topology, LLM-owned AgentTool protocol/registry/dispatch, single canonical Tool Result, and observability firewall remain active. Its persistent Run lifecycle, response-group fields, automatic recovery assumptions, and its earlier ToolCall-atom mechanics are superseded by [11-client-llm-message-protocol.md](11-client-llm-message-protocol.md). This is historical evidence only; it neither defines nor rejects the active independent `ToolCallMessage` model.

## Decision

Sir's corrections define a two-deep-module design:

- **LLM Service/Kernel:** Thread, typed Message, generic Run lifecycle, conversation persistence, context compiler, provider adapters, AgentTool protocol/registry/invocation, and canonical state transitions.
- **Agent Harness:** import coordination, sampling/tool progression policy, step/guard/cancellation policy, and typed Chatbot-event projection.

There is no Conversation Ledger service and no LLM dependency on Harness. Observability remains a one-way cross-cutting projection.

## Object Graph

```text
LLMService
├─ ThreadRepository port -> SQLite adapter
├─ ProviderGateway / ProviderAdapterRegistry
├─ ContextCompiler (typed Message -> provider wire)
├─ AgentToolRegistry
│  └─ AgentTool protocol instances registered from composition
└─ Run operations
   ├─ sample
   ├─ invoke_tool
   ├─ pause / resume / cancel
   └─ finish

Thread
├─ ordered typed Messages
└─ Runs rooted at UserMessages
```

The LLM package can be internally separated into conversation, tooling, provider, and persistence modules while remaining one public service boundary.

## Dependency Inversion for AgentTool

LLM owns the following concepts:

- `AgentTool` protocol/ABC;
- provider-neutral `AgentToolDefinition` with stable canonical tool ID and portable input schema;
- `AgentToolInvocation` built by LLM from canonical Run/call Message state;
- bounded `AgentToolResult`;
- mutable startup registry and immutable per-sampling exposed ToolScope;
- invocation validation and lifecycle.

Concrete implementations such as a data-query tool are adapters. They implement the LLM protocol and capture Dataset/Artifact/ML dependencies in their constructors. The composition root wires them; Harness bootstrap may call the LLM registration interface as a client, but registry storage, lookup, scope validation, dispatch, and lifecycle remain LLM-owned.

```text
Source dependencies:
Harness ---------------------> LLM public API
ConcreteDataTool ------------> LLM AgentTool protocol
ConcreteDataTool ------------> Dataset/Artifact domain ports
LLM core -------------------X> Harness / ConcreteDataTool / domains

Runtime dispatch:
Harness -> LLM.invoke_tool -> LLM registry -> injected AgentTool instance -> domain
```

The runtime call into an injected implementation is not a source dependency on Harness. The forbidden shape is `LLM -> HarnessPort.invoke_tool`; it does not exist.

## Public Operation Shape

The exact names remain subject to an Impact Handshake, but the public behavior is narrow:

```text
register_tool(AgentTool)
begin_user_submission(thread_id, UserMessage) -> RunHandle
sample(run_id, ToolScope) -> typed Message changes
invoke_tool(run_id, call_message_id, tool_scope_version) -> ToolInvocationOutcome
pause / resume / cancel / finish(run_id)
snapshot(thread_id) -> typed immutable read model
```

`begin_user_submission` atomically appends the root UserMessage and creates its Run. `sample` performs provider interaction and commits the resulting canonical Assistant/ToolCall Messages inside LLM before returning typed changes; Harness never persists those changes.

`invoke_tool` does not accept a tool name, arguments, handler, Harness context, or result payload. LLM reads name/arguments/scope from canonical state, constructs an LLM-owned invocation DTO, and resolves the registered implementation itself.

Harness explicitly triggers `invoke_tool`; LLM does not hide a complete agent loop inside `sample`. This preserves Harness orchestration while keeping tool ownership and state transitions inside LLM.

## Canonical Message Algebra

```text
Message = SystemMessage
        | UserMessage
        | AssistantMessage
        | ToolCallMessage
        | ToolResultMessage
```

Common Message fields are stable ID, Thread, optional Run/causal root, sequence, subtype, lifecycle/finalization, and typed semantic content. `ui_author` and raw `provider_payload` are not canonical concepts.

`ToolCallMessage` owns:

- stable internal `ToolCallMessage.id` used as invocation/idempotency identity;
- canonical tool ID and immutable arguments;
- provider-call ID kept as adapter correlation, not canonical identity;
- internally allocated `response_group_id` plus total `response_part_ordinal` shared with every atom from that committed sampled response;
- exposed ToolScope/version;
- non-terminal invocation state (`REQUESTED`, `IN_PROGRESS`, or `UNKNOWN_AFTER_CRASH`);
- idempotency/reconciliation policy keyed by internal `ToolCallMessage.id`, never by a provider ID.

`ToolResultMessage` owns:

- a unique foreign/reference link to exactly one call Message;
- the sole bounded result facts or error;
- the terminal outcome (`SUCCEEDED`, `FAILED`, `CANCELLED`, or a carefully defined committed-after-cancel outcome);
- stable artifact/domain IDs only.

There is at most one Result Message per call. A finalized Result Message is immutable. Tool name/arguments/result are never duplicated into a second canonical ToolExchange row. A rebuildable relational index is allowed only if it contains no independent truth.

Provider context and Chatbot events are independent projections of these same typed Messages. Provider formatting, Xenix table rendering, presentation labels, and UI actions do not live in the canonical Message payload.

The Context Compiler consumes an immutable canonical snapshot and returns a new provider-facing value. Token trimming, summarization, provider normalization, or history processing must never delete, replace, or mutate canonical Messages as a side effect. Any future canonical compaction requires an explicit state transition and retention contract.

Provider response envelopes and canonical atoms are not required to have the same shape. Every atom committed from one sampled response receives an internally allocated stable `response_group_id` and a total `response_part_ordinal`. Text-before/call/text-after may use multiple contiguous `AssistantMessage` atoms. The Context Compiler reconstructs the provider-required envelope from those explicit facts; it never infers grouping from adjacency and never requires an empty Assistant Message shell. Provider response IDs are correlation only, and `ToolCallMessage.id` remains the independent invocation identity.

## Invocation Sequence and Crash Boundary

```text
Harness            LLM Service             ToolRegistry / AgentTool           Domain
   | sample(scope)      |                              |                         |
   |------------------->| compile context / provider call                       |
   |                    | commit Assistant + ToolCall Messages                  |
   |<-------------------| typed call Message(s)                                 |
   | invoke(call_id)    |                              |                         |
   |------------------->| preflight tx: REQUESTED -> IN_PROGRESS                |
   |                    | dispatch ------------------->| invoke(idempotency=id)  |
   |                    |                              |------------------------>|
   |                    |                              |<-- bounded result ------|
   |                    | final tx: append unique ToolResult + finalize call    |
   |<-------------------| typed outcome/snapshot                                |
   | project Chatbot event                                                      |
```

The external side effect cannot share an SQLite transaction. Therefore invocation is one logical operation with two short canonical commits:

1. persist `IN_PROGRESS` before the side effect;
2. after return, atomically append the sole Result Message and finalize the call.

A crash between domain commit and result commit leaves an explicit `UNKNOWN_AFTER_CRASH` call. Recovery uses the internal `ToolCallMessage.id`: it may re-invoke only under the registered tool's idempotency contract, otherwise it must reconcile before the Run can progress. Provider-call IDs are never recovery keys and logs are never consulted. Cancellation is cooperative: a domain effect already committed cannot be rewritten as if it never happened.

## State / Observability Firewall

Canonical state includes Thread, typed Messages, and generic Run lifecycle needed to determine the next valid action. Harness owns policy values; LLM stores only the resulting generic state/continuation contract and does not import Harness policy types.

Provider attempts, raw requests/responses, SSE chunks, retry/timing detail, token metrics, and diagnostic tool attempts belong to Observability unless a minimal state fact is demonstrably required for recovery. No field named `usage` may carry step-budget/model recovery state.

Canonical transition commits first; logging/telemetry happens afterwards and may fail, duplicate, delay, or disappear without changing state.

## Acceptance Proofs for a Future Impact Handshake

1. Architecture/import test proves `services.llm` imports no Harness, concrete tool, or domain implementation.
2. Registration test proves duplicate canonical/provider names fail and per-sampling ToolScope is immutable and isolated across concurrent Runs.
3. Unknown/unexposed provider tool calls fail closed inside LLM before a call Message becomes invokable.
4. Harness triggers one `invoke_tool` command and may observe the returned typed outcome/snapshot for policy and projection, but never authors, reposts, persists, or duplicates handler result truth; LLM commits the sole Result Message.
5. Duplicate invocation with the same call ID returns/reconciles the existing canonical result; conflicting duplicate outcomes fail closed.
6. Multi-tool provider responses replay by internal `response_group_id` and total `response_part_ordinal`, not adjacency or provider IDs.
7. Provider and Chatbot projections use the same Result Message and remain equivalent across normal/stream paths.
8. Crash after side effect but before finalization leaves `UNKNOWN_AFTER_CRASH`; recovery proves idempotent re-invocation or reconciliation and never blindly duplicates an unprotected effect.
9. Artifact/domain authority remains outside LLM; result Messages contain only stable references and bounded facts.
10. Deleting/failing observability leaves snapshots, replay, pause/resume, invocation recovery, and terminal state unchanged.
11. Recompiling provider context, including a bounded/trimmed view, leaves the canonical Message sequence semantically unchanged.
12. Text-before/call/text-after plus parallel calls round-trip through stable internal response-group IDs and total ordinals without adjacency inference or duplicate result truth.
13. Streaming deltas never masquerade as finalized Messages; completion, cancellation, and transport failure leave an explicit canonical Run/Message state independent of the live event stream.
