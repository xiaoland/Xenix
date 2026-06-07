# Provider Tool Call Projection Execution

- Objective & Hypothesis: Fix failed follow-up provider requests where persisted tool results are sent without the preceding assistant tool-call message. The persisted tool-call/result pair is intact; the provider-facing projection is incomplete.
- Guardrails Touched: Agent Harness owns provider-facing Message projection, tool-call/result persistence, and provider interaction. Storage schema is unchanged.
- Verification:
  - `pdm run pytest tests/test_agent_harness_foundation.py::test_conversation_store_persists_thread_turn_messages_and_tool_calls tests/test_agent_harness_streaming.py::test_openai_compatible_provider_serializes_assistant_tool_calls_before_tool_result tests/test_agent_harness_streaming.py::test_agent_harness_pauses_for_step_budget_confirmation_and_resumes`
  - `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_agent_harness_first_slice.py`
