# Agent Harness Unit Design

## Admission

Agent Harness qualifies for durable unit memory because one causal orchestration unit spans persistence, provider calls, tool execution, streaming, interruption, and UI projection. Its ordering and convergence rules are expensive to reconstruct from implementation details alone.

Exact records, event shapes, tool schemas, fields, registries, and method signatures remain source and test truth. UI rendering contracts remain in typed Chatbot events, UI code, and integration tests.

## Stable Invariants

- Establish durable conversation and run facts before treating dependent provider or tool side effects as complete.
- Persist one canonical tool result and derive provider replay from it. Do not maintain a second provider-facing result truth.
- Evaluate the completion guard only when the primary provider proposes a zero-tool completion. The guard is bounded; an unavailable or invalid guard falls back to normal completion rather than trapping the run.
- Streaming, step-budget pause and resume, cancellation, failure, and final snapshots must converge persisted run, turn, and message state. A UI-only terminal state is insufficient.
- Domain services own data, artifacts, and ML behavior. LLM Service owns provider-adapter mechanics. Harness owns their causal orchestration and typed Chatbot projection.

## Change Guidance

Preserve ordering explicitly when refactoring the provider/tool loop. A new path must reach the same persisted terminal state as its synchronous counterpart and must not make the UI infer state from storage rows or raw tool payloads.

Use the nearest `src/xenix/services/agent/AGENTS.md` for implementation tripwires. Verify causal and persistence behavior in `tests/test_agent_harness_foundation.py`, `tests/test_agent_harness_first_slice.py`, and `tests/test_agent_harness_streaming.py`; verify UI convergence at the Harness/UI integration boundary.
