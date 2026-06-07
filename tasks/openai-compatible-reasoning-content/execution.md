# OpenAI Compatible Reasoning Content Execution

- Objective & Hypothesis: Make OpenAI Compatible V1 backend payload assembly preserve `reasoning_content` for any compatible provider, not only DeepSeek. Kimi/Moonshot thinking mode requires the same assistant tool-call history field.
- Guardrails Touched: Provider adapter serialization only. Agent storage schema and UI are unchanged.
- Verification:
  - `pdm run pytest tests/test_agent_harness_streaming.py::test_openai_compatible_provider_serializes_assistant_tool_calls_before_tool_result`
