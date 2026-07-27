# No-Turn Counterfactual

## Status — Superseded Lifecycle Model

This document preserves the earlier proposal that removed Turn by promoting persistent Run. Sir correctly identified that Run then becomes another Turn-shaped causal aggregate. The active no-Turn/no-persistent-Run protocol is [11-client-llm-message-protocol.md](11-client-llm-message-protocol.md). Its `response_group_id`/response-part mechanics are historical too; the migration-consumer inventory below remains useful evidence, but its Run authority and conclusion are no longer current.

## Question

Can `AgentTurn` be removed while making the corrected Message-centric model simpler and more reliable, rather than merely renaming it?

## Candidate Model

```text
Thread
├─ Messages (ordered canonical conversation atoms)
│  ├─ SystemMessage
│  ├─ UserMessage
│  ├─ AssistantMessage
│  ├─ ToolCallMessage
│  └─ ToolResultMessage
└─ Runs
   ├─ root_user_message_id
   ├─ generic lifecycle / selected model / continuation state
   ├─ RUNNING <-> AWAITING_CONFIRMATION
   └─ SUCCEEDED | FAILED | CANCELLED
```

- Each user submission atomically creates a root `UserMessage` and one Run through LLM Service.
- A Run is the only recoverable execution lifecycle. Harness owns the step/guard/cancellation policy, while LLM persists the resulting generic state transitions.
- A Message contains semantic conversation state, not execution logs, UI events, artifact ownership, or the Run state machine.
- Generated Messages are explicitly associated with a Run or causal root. Thread-level system Messages may have no Run.
- `ToolCallMessage` and its unique `ToolResultMessage` replace the canonical result fields of `AgentToolCallRow`; every committed sampled-response atom uses an internal `response_group_id` plus total `response_part_ordinal`, never adjacency.
- Multiple future Runs may reference the same root UserMessage for an explicit rerun without reintroducing Turn.

## Old-to-New Mapping

| Current fact | No-Turn replacement |
| --- | --- |
| `AgentTurn.id` | `AgentRun.id` as the execution/exchange identity |
| `Turn.user_message_id` | `Run.root_user_message_id` |
| `Turn.sequence_index` | root UserMessage sequence (or explicit Run sequence if needed) |
| `Turn.OPEN/ENDED/CANCELLED` | Run lifecycle only |
| `Message.turn_id` | optional `run_id`/causal-root association; thread system Message is null |
| `AgentToolCallRow` request/result truth | typed `ToolCallMessage` + unique `ToolResultMessage` |
| `ContinueStepBudgetInput.turn_id` | `run_id` |
| per-turn token/connection telemetry | live/observability projection keyed by Run; no recovery role. Step-budget/continuation state remains canonical generic Run state. |
| Artifact `tool_call_id` | stable source call-Message ID or domain-neutral provenance reference |

## Net-Benefit Test

Removal is a real simplification only if all are true:

1. Run is the sole execution lifecycle and root UserMessage correlation is explicit.
2. Every generated Message has an unambiguous Run/causal root without adjacency inference.
3. At most one active Run exists per Thread unless explicit concurrent-run semantics are designed.
4. Tool invocation/result identity is preserved by typed Message constraints and idempotent invocation; removing a table does not remove those concepts.
5. Provider replay and Chatbot projection use the same Message SSoT.
6. Observability can be deleted or unavailable without affecting reload, resume, tool recovery, or terminal state.
7. Every existing `turn_id` consumer—Artifact, export, worker, UI confirmation, events, tests—is migrated rather than hidden behind an indefinite compatibility shim.

## Migration Shape

This is not a global identifier rename. Use forward coexistence and removal edges:

1. Add Run/root-message correlation; enrich sampled-response/call/result Messages with explicit subtype fields, call-result link, internal response-group ID, total response-part ordinal, status, and use internal `ToolCallMessage.id` as the invocation/idempotency identity. Provider-call and provider-response IDs remain adapter correlation only. Backfill from Turn and `AgentToolCallRow`, detecting orphan, multiple-result, and ambiguous multi-call histories.
2. Switch provider replay, Chatbot projection, artifact provenance, cancellation, pause/resume, and all tests to Run + typed Message facts. Keep old Turn/tool-result columns read-only for equivalence checks.
3. Rebuild SQLite tables only after equivalence is proven; remove Turn foreign keys/table and the duplicate tool-result payload/table as approved.

Fresh bootstrap, v14 upgrade, ORM readability, multi-tool replay, pending/failed/cancelled tool state, paused-run resume, artifact linkage, crash/idempotency recovery, normal/stream parity, and observability-loss independence are mandatory proofs.

## Ecosystem Cross-Check

The official comparison in [09-ecosystem-comparison.md](09-ecosystem-comparison.md) repeatedly separates:

- durable Thread/Conversation state;
- one execution Run;
- inner graph step, super-step, or model invocation.

LangGraph uses Thread + Run + checkpoints; PydanticAI uses Conversation + Run + graph steps; OpenAI Agents uses Session + Run while overloading *turn* for both an outer logical interaction and an inner model-invocation budget. None demonstrates a required persistent aggregate between root UserMessage and Run.

This does not prove removal by popularity or by absence in another public API. It shows that tool loops, replay, and multi-run conversations can be modeled without a persistent intermediate Turn. Xenix may retain *turn* as product prose, but code and storage should call the inner budget a model step/invocation and use Run for the recoverable user-submission execution if the migration proof succeeds.

## Provisional Verdict

The Xenix counterfactual favors Turn removal; ecosystem evidence shows that the result is viable but is not the deciding proof. Thread owns conversation order, Run owns execution lifecycle, and Message owns semantic state. Turn should be removed only if migration proves those three authorities cover current intent, status, sequence, UI/export, artifact provenance, cancellation, rerun, pause/resume, and terminal semantics. Keeping Turn is justified if any distinct lifecycle remains that neither root UserMessage nor Run can express.
