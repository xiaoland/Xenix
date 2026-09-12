# LLM Service Guidance

Applies to `src/xenix/services/llm/`: canonical conversations, provider interaction, and Tool invocation.

- Keep concrete/domain Tools behind the LLM-owned protocol and registry; do not import Harness or domain implementations into this boundary.
- Derive provider schemas from the strict typed input model. Keep cross-field validation in execution; do not maintain another schema authority.
- Before changing pending/final messages, deletion, Stop, or result paging, read the [conversation boundary](../../../../docs/20-prd-tdd/llm-conversation-boundary.md). It owns ordering, result semantics, and provider-data constraints.
- Verification routes: `tests/agent/test_agent_harness_first_slice.py`, `tests/llm/test_tool_result_pagination.py`, and the contract's storage checks for persistence changes.
