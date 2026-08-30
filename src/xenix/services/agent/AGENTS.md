# Agent Service Guidance

## Scope

Applies to Harness-side live coordination and Chatbot projection under
`src/xenix/services/agent/`. `LLMConversationService` owns canonical
conversation, provider interaction, and Tool invocation; this subtree must not
recreate those authorities.

## Tripwires

- Do not directly write or mutate canonical Messages, reconstruct provider
  history, or dispatch a Tool from Harness. Use the LLMConversationService
  command/snapshot boundary.
- Persisted ToolCall/ToolResult truth belongs to the LLM boundary; Chatbot
  grouping is projection only and must not become a second result truth.
- Keep provider schemas within a conservative portable subset. Enforce complex mutual exclusion, priority, and cross-field rules in execution validation rather than relying on schema combinators.
- Keep credentials, raw local paths, debug or observability dumps, and unbounded evidence out of provider schemas and results. Return stable ids and bounded facts needed for the next operation.
- Project typed `ChatbotEvent` values. UI code must not infer tool pairing or lifecycle state from storage rows or raw tool payloads.
- Treat Thinking/activity/connection as live Chatbot Events. Source attachment
  presentation is optional post-snapshot enrichment and never canonical content.
- Preserve causal ordering and canonical convergence across provider calls,
  tools, streaming, cancellation, and failure. Use the
  [LLM conversation boundary](../../../../docs/20-prd-tdd/llm-conversation-boundary.md)
  and [Unit TDD](../../../../docs/30-unit-tdd/README.md) when changing that loop.

Verify focused Harness behavior in `tests/agent/test_agent_harness_first_slice.py`
and `tests/agent/test_agent_skill_tool_scope.py`; pair it with the LLM
conversation, storage, and UI routes named by Unit TDD. Use source and tests—not
this file—for exact schemas, events, records, and method contracts.
