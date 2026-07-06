# LLM Service Retry Interface

## Objective & Hypothesis

Move the Agent/LLM collaboration boundary so Agent Harness calls a canonical LLM Service interface instead of obtaining a provider instance, and make LLM Service own bounded retry for retryable provider failures and invalid retryable provider responses.

Hypothesis: LLM Service should become the provider adapter layer and expose request/stream operations plus retry telemetry events. Agent Harness remains the turn/message/tool orchestration owner and projects LLM retry telemetry into Chatbot UI events.

## Guardrails Touched

- `src/xenix/services/llm/`: provider adapter, settings, retry policy authority.
- `src/xenix/services/agent/`: harness provider-call boundary, provider request persistence, streaming event projection.
- `src/xenix/ui/`: Chatbot event rendering if no existing event shape can represent retry.
- `docs/30-unit-tdd/agent-harness.md`: current provider-boundary contract is stale under the target design.
- `docs/20-product-tdd/` or unit TDD may need LLM Service boundary contract if not already documented.

## Verification

- Unit tests for LLM retry policy: transient HTTP/network and invalid tool-call JSON retry up to configured limit.
- Unit tests that non-retryable errors fail without extra attempts.
- Harness tests proving retry telemetry is emitted and provider request/run status remains correct.
- UI projection/rendering tests if a new Chatbot event kind is introduced.

Current verification run:

- `pdm run pytest tests\test_agent_settings.py`
- `pdm run pytest tests\test_llm_service_retry.py`
- `pdm run pytest tests\test_agent_harness_streaming.py`
- `pdm run pytest tests\test_settings_dialog.py tests\test_i18n.py`
- `pdm run pytest tests\test_main.py`
- `pdm run pytest tests\test_agent_harness_foundation.py tests\test_agent_harness_first_slice.py`
- `pdm run pytest tests\test_agent_ai_observability.py`
- `pdm run pytest tests/test_agent_harness_streaming.py::test_agent_harness_projects_llm_retry_connection_event tests/test_agent_harness_streaming.py::test_connection_retry_snapshot_projection_keeps_failed_request_only tests/test_main.py::test_thread_detail_view_removes_connection_retry_after_recovery tests/test_i18n.py -q`
- `pdm run pytest tests/test_agent_harness_streaming.py tests/test_main.py tests/test_i18n.py -q`

## Current Understanding

- Current `LLMService` only loads/saves settings and constructs `OpenAICompatibleChatProvider`.
- Current OpenAI-compatible provider is under `src/xenix/services/agent/providers.py`, so provider adapter ownership is inside Agent Service.
- Current provider HTTP calls are single-shot.
- Current invalid `function.arguments` JSON is raised by provider response parsing before tool execution.
- Current Harness records failed provider requests and rethrows; it does not retry provider-call failures.
- `docs/20-product-tdd/runtime-boundaries.md` already says LLM Service sits between Agent Harness and provider adapters, but `docs/30-unit-tdd/agent-harness.md` and code still expose provider construction to Harness.
- `MainWindow._reload_agent_provider()` currently rebuilds providers through `LLMService.build_provider()` and injects them into Harness; this is a visible old-boundary coupling point.
- User explicitly rejected reusing `ChatbotEventKind.THINKING`. LLM retry should be a new Chatbot event, visually closer to a tool-call item, with summary text shaped as `Connecting (n/max)` and expandable retry details.
- User clarified the visual similarity does not mean reusing `ToolCallItem`. `CONNECTION` needs a dedicated UI implementation, and a recovered connection must remove the live connecting item instead of leaving a completed row in the chat history.
- User clarified retry count is global LLM settings state, not per-provider state. Settings UI should place it in the global AI/LLM configuration area.
- `AgentProviderRequestRow` has no retry-attempt columns. Retry telemetry can initially remain transient UI/observability state, while the final provider request row records the logical request outcome and token usage.
- No retry dependency exists in `pyproject.toml`; a small standard-library retry loop is the conservative default.
- Implementation stores retry telemetry in provider request `usage_payload.retry_events`, so failed/cancelled provider requests can restore `CONNECTION` events without a schema migration. Successful recovered requests keep telemetry for observability but do not project a historical connection item.

## Next Step

Map the current callable interfaces, storage/event projection surfaces, and tests before proposing the exact impact handshake.
