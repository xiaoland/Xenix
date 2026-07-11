# Agent Service Guidance

## Scope

Applies to `src/xenix/services/agent/`, where provider orchestration, tool execution, persistence, and Chatbot projection meet.

## Tripwires

- Persist one canonical tool result and derive provider replay from it. Do not create a second human-facing or provider-facing result truth.
- Keep provider schemas within a conservative portable subset. Enforce complex mutual exclusion, priority, and cross-field rules in execution validation rather than relying on schema combinators.
- Keep credentials, raw local paths, debug or observability dumps, and unbounded evidence out of provider schemas and results. Return stable ids and bounded facts needed for the next operation.
- Project typed `ChatbotEvent` values. UI code must not infer tool pairing or lifecycle state from storage rows or raw tool payloads.
- Preserve causal ordering and persisted convergence across provider calls, tools, streaming, guards, step budgets, cancellation, and failure. Use [Unit TDD](../../../../docs/30-unit-tdd/README.md) when changing that loop.

Verify focused behavior in `tests/test_agent_harness_foundation.py`, `tests/test_agent_harness_first_slice.py`, and `tests/test_agent_harness_streaming.py`. Use source and tests—not this file—for exact schemas, events, records, and method contracts.
