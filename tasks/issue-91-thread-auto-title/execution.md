# Issue 91 Thread Auto Title

## Objective & Hypothesis

Implement automatic thread naming from the first user message. If a dedicated thread title model is configured, Agent Harness asks that model for a concise title. If the model is not configured, fails, or returns an unusable title, Agent Harness falls back to a deterministic local title.

## Guardrails Touched

- Agent Harness owns Thread semantics and title mutation.
- Settings owns provider/model configuration.
- Qt UI only exposes the setting and renders thread titles from the service.
- Storage schema remains unchanged; `agent_thread.title` already stores the result.
- Thread title generation must not persist naming prompts into normal conversation history.

## Verification

- Added settings persistence tests for `thread_title_model`.
- Added Agent Harness tests for configured LLM title, unconfigured fallback, provider failure fallback, and non-overwrite of existing titles.
- Added SettingsDialog/i18n coverage for the new visible label.
- Ran `pdm run pytest tests/test_agent_settings.py tests/test_agent_harness_streaming.py tests/test_i18n.py tests/test_main.py`: 53 passed.
- Ran `pdm run check`: passed.
- Ran `pdm run pytest`: 139 passed.
- Added manual LLM title proposal flow from History context menu. Manual generation sends all persisted Thread messages to the configured title model, shows a modal progress dialog, lets the user edit the proposal, and only applies the title after confirmation.
- Added tests for manual full-thread title proposal, missing-model UI prompt, loading dialog lifecycle, editable apply, and cancel preserving the existing title.
- Ran `pdm run pytest tests/test_agent_harness_streaming.py tests/test_main.py tests/test_i18n.py tests/test_agent_settings.py`: 58 passed.
- Ran `pdm run check`: passed.
- Ran `git diff --check`: passed.
- Ran `pdm run pytest`: 144 passed.
