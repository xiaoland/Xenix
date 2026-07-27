# Final Plan Review — Top-Level Objectives and Independent Audits

## Status

Active final review. This file changes task control only. It does not authorize product-code, schema, durable-document, external-state, or commit mutations.

## Why This Review Exists

The selected direction is now narrow enough that a broad feature checklist would add little value. The remaining risk is architectural self-deception: a hidden second authority, a forbidden execution aggregate under another name, an adapter-shaped canonical model, or a migration plan that cannot prove the stated behavior.

The review therefore tests four root objectives rather than re-voting individual implementation details.

## Four Top-Level Objectives

| ID | Objective | Must be true at completion | Disqualifying result |
| --- | --- | --- | --- |
| O-1 | **One durable language of conversation** | One ordered Thread Message log is canonical. `AssistantMessage`, `ToolCallMessage`, and `ToolResultMessage` are independent typed facts; Result directly identifies Call; provider containers and UI are projections. | A provider envelope, mutable Tool Call row, UI event, observability record, or side table owns/determines a conversation fact. |
| O-2 | **No false promise of execution** | Neither `Turn`, `Run`, request lifecycle, claim, or replay ledger persists an in-progress Harness span. A provisional sampling Message is only replaced or discarded. Known terminal failure is durable; process loss is intentionally absent from final history. | A stored object spans sampling/tool stages with owner/retry/cancel/recovery semantics, or final history can show unmatched Call/Result. |
| O-3 | **One-way authority topology** | `LLMConversationService` is the sole canonical writer and owns Tool protocol/registry/dispatch. Harness owns live policy and Chatbot projection. Concrete tools depend on the LLM protocol, never the reverse; observability is non-authoritative. | LLM calls Harness to execute/persist a tool, Harness writes Messages, a concrete tool/domain module is imported by LLM core, or recovery reads observability. |
| O-4 | **Faithful, enforceable realization** | Each supported adapter can compile canonical sequence/call correlation into provider-valid input without mutation; storage, migration, concurrency gates, UI projection, and tests can enforce O-1–O-3. | The plan relies on adjacency guesses, opaque provider data that cannot be retained, unrepresented current consumers, or assertions that SQLite/runtime topology cannot prove. |

## Fixed Product Constraints

- No third Conversation Ledger/Service.
- No persisted `Turn` or `Run`; no automatic cross-process continuation, call replay, idempotency requirement, effect ledger, or generic unknown-effect state.
- `ToolCallMessage` is independent canonical Message state, never an `LLMMessage` part, child, or hidden response group.
- A final tool-containing LLM emission commits with its complete directly linked Tool Result set. Process-loss discard and a later new semantic provider call are accepted.
- “Thinking” is a Harness Chatbot Event, not an LLM Conversation Message concept.
- Product code remains untouched until a later, explicit Impact Handshake approval.

## Independent Review Lanes

| Lane | Thinking mode | Primary objectives | Required challenge |
| --- | --- | --- | --- |
| A | Deductive ontology and topology audit | O-1, O-3 | Try to prove a hidden authority, hidden envelope, missing causal fact, or dependency inversion violation. |
| B | Adversarial temporal/state-machine audit | O-2, O-4 | Inject crashes, cancellation, parallel completion, late callback, duplicate command, restart, and stream/non-stream divergence. Distinguish accepted loss from an impossible invariant. |
| C | Inductive source/migration feasibility audit | O-4, then O-1–O-3 | Trace actual schema/consumer/provider/UI/worker paths. Find omitted consumers, unenforceable constraints, or missing proof cases. |
| S | Primary synthesis | All | Cross-check findings against fixed constraints, reject duplicates and category errors, and propose only minimum compatible corrections. |

## Review Rules

1. A finding is actionable only when it contradicts a root objective, a fixed product constraint, or concrete repository evidence.
2. “The accepted process-loss trade is lossy” is not a finding by itself. It becomes one only when the plan falsely claims recovery, safety, or final-history facts that the trade cannot supply.
3. A replacement must reduce or preserve authority count. Renaming a response group, execution span, or envelope does not satisfy the objective.
4. Adapter wire differences are evidence against provider-shaped storage, not evidence to erase provider-required continuity. Required opaque fields must have an explicit canonical retention/projection rule.
5. Final approval requires an implementation-slice Impact Handshake; this review can only establish the go/no-go conditions for that handshake.

## Required Synthesis Output

- A verdict for each O-1 through O-4: satisfied, satisfied with a concrete gate, or blocked.
- Each remaining issue classified as contradiction, proof gap, migration work, or accepted product trade.
- A minimal ordered list of plan edits or first-slice gates; no code proposal unless separately authorized.
- Explicit confirmation that nothing reintroduces `Turn`, persistent `Run`, provider-shaped Message containment, or an observability recovery path.

## Evidence Inputs

- Active target protocol: [11-client-llm-message-protocol.md](11-client-llm-message-protocol.md)
- Repository/migration impact: [12-no-run-repository-impact.md](12-no-run-repository-impact.md)
- Boundary and slice plan: [01-boundary-map.md](01-boundary-map.md), [03-slice-plan.md](03-slice-plan.md), and [05-two-service-boundary-options.md](05-two-service-boundary-options.md)
- Provider/ecosystem evidence: [09-ecosystem-comparison.md](09-ecosystem-comparison.md)
