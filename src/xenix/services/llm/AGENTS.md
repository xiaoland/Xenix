# LLM Service Guidance

## Scope

Applies to the canonical conversation and LLM protocol boundary under
`src/xenix/services/llm/`: `LLMConversationService`, provider adapters, the
`AgentTool` protocol/registry, message records, and tooling. This subtree is the
sole canonical Thread/Message writer and the only LLM invocation authority.

## Tripwires

- `LLMConversationService` owns the provider-facing transcript, pending/final
  Message lifecycle, the `AgentTool` protocol, registry, scope validation, and
  invocation. Agent Harness and the Chatbot UI must not write Messages, dispatch
  Tools, or serialize provider history directly.
- A production Tool's strict typed input model is the single call-contract
  authority; the provider-facing JSON Schema is a bounded portable projection,
  never a separately maintained definition.
- Final Messages are durable. A pending sampling Message is the sole provisional
  canonical state; there is no persistent Turn/Run/execution ledger or automatic
  cross-process recovery.
- Keep provider schemas conservative and portable; enforce cross-field and
  mutual-exclusion rules in model validation, not schema combinators.
- A ToolResult stores one bounded direct JSON value (XTT for tabular, typed
  `ToolFailure` for normalized failures). Do not add a raw-result fallback or a
  second semantic result representation.
- Keep credentials, raw local paths, and unbounded evidence out of provider
  schemas and results.
- Thread deletion, Stop/pause admission, and provider interaction must preserve
  the topology in
  [LLM conversation boundary](../../../../docs/20-prd-tdd/llm-conversation-boundary.md).

Verify canonical storage and deletion ordering in
`tests/storage/test_migrations.py` and `tests/storage/test_storage_artifacts.py`;
Harness/Tool sequencing and the command/snapshot boundary in
`tests/agent/test_agent_harness_first_slice.py` and
`tests/agent/test_agent_skill_tool_scope.py`. Use source and the boundary
contract—not this file—for exact records, payloads, methods, and adapter
mechanics.
