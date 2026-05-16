# Streaming Message Mock

## Objective & Hypothesis

Add the first streaming path for ChatBox message rendering without changing the first-slice tool execution contract.

The working hypothesis is that Xenix needs a provider-independent streaming event contract first:

```text
LLM provider SSE / AIMock HTTP chunks
  -> ProviderStreamEvent
  -> AgentHarnessStreamEvent
  -> ThreadDetailView assistant delta rendering
  -> final persisted AgentMessage snapshot
```

## Guardrails Touched

- `AgentProvider.complete()` remains available for synchronous tool-call flows and existing tests.
- Providers may additionally expose `stream()`.
- `AgentHarnessService.submit_user_turn_stream()` starts and persists the user turn, emits assistant deltas, persists the final assistant message, runs tool calls, and emits the final snapshot.
- `ThreadDetailView` renders streaming assistant deltas into one temporary assistant message.
- The final snapshot remains the durable UI truth after the streaming run completes.
- Provider construction reads `config/agent_settings.json` through `AgentSettingsService`.
- `XENIX_ENV=development` exposes AIMock settings in the Settings window.
- Product code uses AIMock through the same OpenAI-compatible HTTP provider boundary as production.

## Mock Switches

LLM provider configuration is stored in Settings, not in `XENIX_LLM_*` environment variables.

```powershell
$env:XENIX_ENV = "development"
```

When development mode is active, Settings shows an AIMock section:

```text
Use AIMock: enabled
AIMock base URL: http://127.0.0.1:4010
AIMock API key: test
```

The local AIMock service can be started through the VSCode task `AIMock: serve fixtures`, backed by `aimock.json` and `fixtures/aimock/10-xenix-streaming.json`.

## Current Scope

- Text deltas stream through UI incrementally.
- OpenAI-compatible `/v1/chat/completions` SSE parsing supports text deltas and accumulated function tool-call deltas.
- AIMock is configured through Settings and attached through provider base URL.
- Preset AIMock fixtures cover fixed streaming text, rich Markdown result rendering, and one real `data.peek` tool-round keyed by `toolCallId`.
- A final chat catch-all fixture keeps arbitrary development prompts inside AIMock and returns the available fixture prompts.
- Turns end when the final provider response has no tool calls. ChatBox renders turn dividers before user Messages.
- Full data-to-prediction AIMock fixtures need dynamic fixture responses or another mechanism that can read runtime `dataset_id` and `trained_model_id` values from tool results.

## References

- OpenAI Chat Completions streaming: https://platform.openai.com/docs/api-reference/chat/create-chat-completion
- AIMock fixtures and streaming knobs: https://aimock.copilotkit.dev/fixtures/
- AIMock record and replay: https://aimock.copilotkit.dev/record-replay/

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_agent_settings.py tests/test_agent_harness_streaming.py tests/test_main.py`
