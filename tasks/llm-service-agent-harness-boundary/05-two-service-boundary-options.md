# Two-Service Boundary Decision

The two-owner and dependency-direction decision remains active. Its earlier persistent-Run lifecycle was superseded by the Message protocol in [11-client-llm-message-protocol.md](11-client-llm-message-protocol.md).

## Fixed Constraints

- There are exactly two top-level owners: LLM Service and Agent Harness. No Conversation Ledger/Service is introduced.
- LLM Service owns Thread, typed Client/LLM Messages, pending/final LLM Message lifecycle, provider interaction, context compilation, AgentTool abstraction/registry/invocation, and canonical conversation persistence.
- Agent Harness owns policy and sequence: import coordination, when to sample, which registered tools are eligible, when to trigger a tool invocation, in-process step/guard/cancellation policy, and typed Chatbot-event projection.
- Observability owns diagnostic execution logs, traces, metrics, raw wire where permitted, timing, retry detail, and usage telemetry. It is never a recovery store.
- Dataset, artifact, and ML services retain domain authority. Messages carry only stable references and bounded facts.

## Selected — Corrected Refined Option A

```text
UI -> Harness -> LLM Service -> Thread / typed Message (SQLite)
                   |         -> provider adapters -> remote provider
                   +--------> LLM-owned AgentToolRegistry
                                  +-> injected AgentTool implementations -> domain services

LLM / Harness -> Observability (one-way projection; never recovery)
```

The important distinction is between source dependency and runtime dispatch:

- LLM defines and owns the `AgentTool` protocol, registry, invocation DTO/result, exposed-scope validation, and call/result commit operation.
- Concrete tools implement that LLM-owned protocol and depend on the relevant domain services. They are constructed externally and registered into LLM; LLM never imports their modules.
- Harness depends on the LLM public interface and explicitly triggers sampling or live tool progress. LLM never calls `harness_port.invoke_tool(...)`, and Harness never invokes a concrete handler then returns an outcome for persistence.
- Once a tool is registered, the LLM registry owns dispatch to that object. This is dependency inversion: the runtime call reaches an injected implementation, while the compile-time dependency still points toward the LLM abstraction.

`AgentTool` ownership and orchestration ownership are therefore different. Harness decides **when** live policy allows tool progress; LLM owns **how** a staged call is validated, dispatched, and turned into a canonical Result as part of the final exchange commit.

## Message Is the Conversation SSoT

Message is not a UI history row, provider-context snapshot, or transcript projection. It is a typed canonical atom of conversation state. Provider context and Chatbot events are projections from it.

- Provider output normalizes to an ordered sequence of independent `AssistantMessage` and `ToolCallMessage` entries. `ToolCallMessage` stores canonical tool identity, arguments, and adapter pairing data; it is not an LLM Message part.
- A tool-calling LLM emission reaches final history only in one transaction with exactly one directly linked `ToolResultMessage` per Tool Call. The Result stores the sole bounded terminal result/status/error; incomplete exchanges remain provisional and are discarded at exit.
- A finalized result is immutable. No `AgentToolCallRow.result_payload`, UI event payload, or provider-formatted payload may duplicate the result truth.
- Artifact/domain records remain authoritative for their entities and carry no Message/Tool Call provenance. A Result stores only its bounded tool outcome; it has no normalized artifact-reference field.
- Raw provider responses, SSE chunks, timing, retries, and execution attempts remain observability data.

The call/result invariant is encoded by independent typed Messages and a direct Result-to-Call relationship rather than a separate ToolExchange table. The pending sampling Message identifies only a provisional exchange; live tool execution remains Harness memory. No Turn/Run/request identity spans stages or persists beside them.

## Not Selected — Split LLM / Harness Persistence

The rejected alternative lets LLM persist conversation while Harness persists tool/run outcomes and sends projections back. It creates two writers and a crash-reconciliation protocol for one causal interaction. It also encourages the forbidden `LLM -> HarnessPort` dependency or a procedural Harness-invoke-then-persist sequence.

Corrected Refined A keeps a single state writer: every canonical Message transition goes through LLM Service. Harness receives typed outcomes/snapshots only for policy and event projection.

## Non-Negotiable Invariants

1. `services.llm` imports no Harness, concrete tool, Dataset, Artifact, or ML implementation module.
2. Unknown or unexposed provider tool calls fail closed inside the LLM boundary before invocation.
3. Harness never supplies tool name/arguments/result back for persistence; LLM reads staged call data from its own provisional Message and dispatches the registered implementation.
4. External side effects are not claimed to be atomic with SQLite. There is no call-ID idempotency/replay contract: process loss discards the incomplete Message unit, and a later explicit provider sample may create new semantic work.
5. Provider and UI projections read the same typed Result Message.
6. Observability loss cannot change a snapshot, replay, final Result truth, or next valid frontier action.
7. Harness live policy is not persisted or reconstructed; a pending LLM Message is finalized or discarded and cannot become a shadow Run.
8. Final history never contains an unresolved Tool Call. A live handler is not automatically retried; known terminal failure gets a Result, while process loss discards the provisional exchange rather than creating a ledger, an unknown outcome, or a resumable claim.

The active object and sequence contract is in [11-client-llm-message-protocol.md](11-client-llm-message-protocol.md). [07-refined-a-state-and-tool-contract.md](07-refined-a-state-and-tool-contract.md) retains the earlier persistent-Run reasoning as historical evidence.
