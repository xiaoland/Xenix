# Agent Service Guidance

Applies to `src/xenix/services/agent/`: live coordination and Chatbot projection.

- Use `LLMConversationService` commands and snapshots. Harness does not write canonical messages, rebuild provider history, or dispatch Tools.
- Emit typed Chatbot events; presentation must not become a second ToolResult authority.
- When changing sampling, Stop, or projection, read the [conversation boundary](../../../../docs/20-prd-tdd/llm-conversation-boundary.md) and [unit seams](../../../../docs/30-unit-tdd/README.md).
- Verify affected routes in `tests/agent/test_agent_harness_first_slice.py`; the unit guide routes UI/storage verification.
