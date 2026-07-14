# Reassessment Record — Tool Ownership, Canonical Message, and Persistent Run

## Why This Record Exists

Sir challenged assumptions in successive Refined A drafts. Re-review confirmed that AgentTool ownership, Message authority, and persistent execution grouping were each modeled incorrectly at least once. This record preserves the corrections rather than silently rewriting the rationale.

## Corrections

| Earlier statement | Reassessment | Corrected decision |
| --- | --- | --- |
| Harness owns tool implementations and returns an opaque outcome to LLM for persistence. | This makes tool invocation procedural and can be read as `LLM -> HarnessPort.invoke_tool`. It also leaves a crash gap between Harness execution and LLM persistence. | LLM owns AgentTool protocol, registry, invocation operation, and registered-instance lifecycle. Harness triggers `LLM.invoke_tool`; LLM dispatches an injected implementation and persists the Result Message. |
| Message cannot be the canonical tool-result store. | That conclusion was inferred from the current weak schema, where Result Message is empty and a separate row owns the payload. It is not a domain-law constraint. | An independent `ToolCallMessage` plus unique directly linked `ToolResultMessage` forms the canonical call/result relationship. Provider/UI are projections. No duplicate result payload remains. |
| A distinct LLM-owned ToolExchange record is required. | Call/result completeness is required; a separate table/entity is not. Typed Messages can encode it through a provisional sampling Message and joint final commit. | Remove the separate canonical ToolExchange result. Finalize a tool-calling LLM Message sequence only with all Tool Results; discard an incomplete exchange at process loss rather than adding a reconciliation ledger. |
| Tool Call must be a part of one LLM Message so text and calls can share a provider response. | That mirrors one provider transport shape. Other backends expose output/function items separately, and making a canonical Assistant envelope reintroduces provider-shaped containment into local state. | Normalize one provider response into an ordered sequence of independent `AssistantMessage` / `ToolCallMessage` entries. Use direct Result-to-Call identity, sequence grammar, and adapter projections; do not persist a parent Assistant, response group, or part key. |
| Removing Turn while persisting Run removes the interaction aggregate. | The proposed Run took over Turn's root-user correlation, open/terminal status, cancellation, and complete interaction span. It was another Turn under an execution name. | With no cross-process automatic continuation requirement, persist only typed Messages. Use a pending sampling Message and staged Tool Call Message correlation for live activity; keep all spanning Harness policy only in memory. |

## Source Facts Behind the Correction

- `AgentToolSpec` already lives under LLM provider code, but current `AgentTool` combines spec, handler, and presentation under `services/agent/tools.py`; Harness directly calls `AgentToolRegistry.execute`.
- Current LLM Service accepts a mutable spec list and has no registry or invocation operation.
- `ConversationStore.complete_tool_call` creates an empty `TOOL_CALL_RESULT` Message, then stores result/status/error in `AgentToolCallRow` in the same transaction.
- Provider replay renders the result from `AgentToolCallRow`; Chatbot projection also reads that row. The Message is currently a pointer/projection, not the selected target model.
- Current adjacency grouping of consecutive tool calls is insufficient for a Message SSoT. The newer two-sided protocol stores independent canonical Messages, uses direct Result-to-Call identity, and treats provider response grouping as an adapter projection rather than a persisted response-group identity.
- Tool side effects and the result commit are not one transaction. Sir accepts the resulting loss boundary: a process-loss interruption discards the provisional exchange, and a later provider sample may do new semantic work. No call-ID idempotent-replay contract is required.
- Current `AgentRun` and `AgentProviderRequest` rows remain `RUNNING` after process loss because no startup recovery exists. Their persisted lifecycle currently claims a capability the product does not provide.

## What Remains Outside Message

Making Message canonical does not justify putting every concern into it:

- Harness owns live step/guard/cancellation policy and Chatbot projection. This execution context is deliberately not durable.
- Observability owns execution attempts, timing, retries, metrics, raw diagnostics, and log retention.
- Artifact/Dataset/ML services own their records and bytes. Messages do not own Artifact provenance or normalized Artifact references.
- Provider adapters own wire formatting; canonical Messages remain provider-neutral.

## Quality Judgment

The previous topologies were not sufficiently clean: one assigned AgentTool ownership to the wrong side, one maintained a ToolExchange result beside Message, one copied a provider envelope into canonical state, and one replaced Turn with persistent Run. The corrected topology is coherent if the LLM public interface remains deep (`append_user_message`, `sample_existing_frontier`, live tool progress), the Message algebra is typed and constrained, pending sampling Messages cannot become shadow Runs, incomplete tool exchanges never enter final history, and concrete tools remain dependency-inverted adapters.

This reassessment changes task-packet design only. It does not authorize product code or schema changes.
