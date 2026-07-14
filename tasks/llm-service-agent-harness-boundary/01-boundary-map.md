# Boundary Map and Architecture Hypotheses

## Current Realized Topology

```text
UI -> AgentHarnessService -> LLMService -> provider adapter -> remote provider
                 |
                 +-> ConversationStore -> SQLite
                 +-> data/artifact services and tool registry
                 +-> typed AgentHarnessStreamEvent / ChatbotEvent -> UI
LLM/Harness instrumentation -> observability (logs / traces / metrics; non-authoritative)
```

`AgentHarnessService` currently materializes a user turn, creates a run, rebuilds provider messages from a persisted thread snapshot, invokes LLM Service, persists assistant/tool facts, and projects typed events. `LLMService` currently loads model settings, selects/builds provider adapters, normalizes provider calls, and applies retry policy. It does not yet own conversation persistence or a tool-registration contract.

## Confirmed Architecture Constraint

The target has two top-level services only. LLM Service owns persisted Thread/typed Message state, the AgentTool abstraction and registry, provider interaction, context compilation, and the tool-invocation operation. Agent Harness owns import coordination, sampling/tool-call progression policy, in-process step/guard/cancellation policy, and Chatbot-event projection. A separate Conversation Ledger/Service is excluded. Observability is a cross-cutting sink/projection, never a conversation owner.

## Questions Raised by Sir

| ID | Hypothesis | Evidence required before a decision | Initial architectural concern | Status |
| --- | --- | --- | --- | --- |
| H-01 | LLM Service should hold threads and expose a thread/message-oriented interface. | Specify an API that owns thread/message creation, retrieval, persistence, context projection, and lifecycle without exposing storage mechanics to Harness. | Selected. The design must be a deep interaction API, not a renamed `ConversationStore`. | Contract specified; implementation pending |
| H-02 | Canonical conversation state belongs inside LLM Service, while execution logs belong to observability. | Classify every fact by whether it changes replay or the next valid Message-frontier action; define one writer and prove observability loss cannot alter either. | Selected refined Option A. Typed Messages are canonical; provider/tool attempts, timing, retry, and raw wire are logs. Xenix does not automatically continue abandoned execution after process exit. | Contract specified; migration pending |
| H-03 | Harness should only orchestrate import, tools, LLM sampling, and Chatbot events. | Define cancellation, step budgets, completion guard, and side-effect ordering through LLM commands and typed snapshots. | Selected. Harness must not receive an LLM SQL session or rows; LLM must not import or call a Harness port. | Contract specified; implementation pending |
| H-04 | Reopened historical threads may omit prior messages from new provider requests. | A temporary SQLite restart probe captured the second provider request after an existing thread was reopened. | Disproved for ordinary messages: the request contained `system -> prior user -> prior assistant -> current user`. Low token use is not reliable evidence. Source attachments are intentionally projected differently. | Evaluated |
| H-05 | Remove `Turn` and persistent `Run`. | Specify a complete typed-Message state machine, live-only Harness policy, tool-side-effect interruption behavior, and migration; compare net complexity and behavior against the current shape. | Favored because promoting Run merely renamed Turn. The replacement genuinely removes a durable authority by accepting no cross-process continuation: an incomplete tool exchange is provisional/discarded, and a later sample may do new work. | Favored; remaining `11` decisions and `12` migration proof pending |
| H-06 | AgentTool is owned by LLM Service; interface and implementation remain separate. | Demonstrate LLM-owned protocol/registry/invocation, externally registered concrete adapters, per-sampling exposed scope, and a one-way source dependency graph. | Selected correction. Runtime dispatch to an injected implementation is dependency inversion, not an LLM-to-Harness dependency. | Contract specified; implementation pending |
| H-07 | Message is the atomic canonical unit of conversation state and may hold the sole tool result. | Specify a provider-neutral typed Message grammar, direct call/result reference, atomic completeness, provisional discard, projections, and migration away from duplicate result rows. | Selected correction. `AssistantMessage` and `ToolCallMessage` are independent LLM-side Messages; unique Client Tool Result Messages directly reference Calls only when the full exchange commits. | Contract specified; migration pending |

## Mandated Target Topology (Detail Under Review)

```text
UI -> Agent Harness -> LLM Service -> canonical Thread / typed Message (SQLite)
       |               +-> provider adapter -> remote provider
       |               +-> LLM-owned AgentToolRegistry
       |                         +-> injected AgentTool implementations -> domain services
       +-> typed Chatbot events -> UI

LLM Service / Harness -- state-change projection --> Observability
                                               (logs / traces / metrics only)
```

- **LLM Service** is the target owner of settings, provider construction/transport/retry/wire normalization, Thread/typed Message persistence, context compilation, pending/final sampling lifecycle, AgentTool protocol/registry/exposed-scope enforcement, and live tool invocation. A Tool Call is an independent LLM-side Message and Tool Result is a canonical Client Message with a direct Call reference; there is no second canonical `ToolExchange.result_payload` or restart-replay operation.
- **Agent Harness** owns policy and sequence: import coordination, when to sample, which registered tools are eligible for a step, when to trigger an LLM tool invocation, step/guard/cancellation policy, and typed Chatbot projection. It never invokes a concrete handler itself, returns a tool outcome to LLM, or writes LLM-owned rows.
- **Concrete AgentTool implementations** are adapters created at composition time. They implement an LLM-owned protocol and depend on domain services; after registration, the LLM registry owns lookup and dispatch. LLM source code imports neither these adapters nor their domains.
- **Observability** owns traces, metrics, diagnostics, raw wire/SSE data where permitted, retry timing, and execution-log retention. It consumes state-change projections only. Its data is allowed to be delayed, duplicated, lost, rotated, or unavailable without changing conversation replay, call/result pairing, or the next valid Message-frontier action.
- **Dataset, artifact, and ML services** retain domain authority. LLM interaction state can hold stable IDs and bounded provider-safe projections, never artifact files, absolute paths, or a second domain record.
- The design must preserve one source of truth for each durable fact and keep the dependency direction acyclic without introducing another top-level service.

```text
Compile-time dependencies:
Harness --------------------------> LLM public port
Concrete AgentTool implementation -> LLM AgentTool protocol
Concrete AgentTool implementation -> Dataset / Artifact / ML ports
LLM core ------------------------X-> Harness / concrete tools / domain services
```

## Review Method

1. **Topology:** list public calls, dependency directions, state writers, and projections. A fact must have one authoritative owner.
2. **Sequence parity:** run the same workflow through normal and streaming paths; compare finalized Messages, tool results, derived frontier state, and final Chatbot projection.
3. **Failure injection:** exercise malformed provider payloads, unknown tools, retry exhaustion, cancellation after a delta, late provider callbacks, stale pending LLM Messages, known tool failure, process loss after a domain effect, live step confirmation, and explicit re-sampling of the prior Client frontier.
4. **Observability independence:** delete, rotate, block, or fail the observability sink and prove that Thread reload, provider-context replay, call/result pairing, and next valid action are unchanged.
5. **Message SSoT:** provider replay and Chatbot projection must read the same typed Message result; remove the alternative result payload and prohibit adjacency-based multi-call pairing.
6. **Changeability:** for each policy—model selection, retry, tool authorization, history selection, persistence, and event projection—measure how many units must change. Multiple independent edits for one policy indicate a boundary leak.

## Decision Criteria

- A **defect** is reproducible and violates an invariant, contract, or fail-closed rule.
- **Design debt** has no immediate failed behavior but makes equivalent paths or authority hard to keep aligned.
- A **readability issue** leaves an owner or state transition unclear from public interfaces and names.
- An **intentional trade-off** is current expected behavior whose user, reliability, or performance contract needs a conscious decision.
