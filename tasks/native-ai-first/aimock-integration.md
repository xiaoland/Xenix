# AIMock Integration

## Status

- Mode: Execute.
- Scope: CopilotKit AIMock local setup for Xenix's OpenAI-compatible provider boundary.

## Boundary

AIMock attaches at the LLM provider boundary.

Xenix provider clients point their base URL at an AIMock server during local development:

```text
OpenAIChatCompletionsV1Provider
  base_url = http://127.0.0.1:4010

DeepSeekChatCompletionsProvider
  base_url = http://127.0.0.1:4010
```

## Integration Modes

### 1. Fixture Replay Server

Run AIMock with fixtures and no real provider calls.

```text
npx -p @copilotkit/aimock llmock -f ./fixtures
```

Best for deterministic local and CI tests after fixtures exist.

### 2. Record Then Replay

Record real provider responses once, then replay them from fixtures.

```text
npx -p @copilotkit/aimock llmock --record --provider-openai https://api.openai.com -f ./fixtures
npx -p @copilotkit/aimock llmock -f ./fixtures
```

Best for capturing realistic tool-call responses.

### 3. Docker In CI

Run the official Docker image with fixtures mounted.

```text
docker run -d --rm --name aimock \
  -v $(pwd)/fixtures:/fixtures \
  -p 4010:4010 \
  ghcr.io/copilotkit/aimock \
  --strict -f /fixtures -h 0.0.0.0
```

Best for language-agnostic Python/PySide6 CI.

### 4. Config-Driven Multi-Service Mode

Run `npx @copilotkit/aimock --config aimock.json` when tests need LLM plus MCP/A2A/AG-UI/vector fixtures.

First slice probably needs only LLM mocking.

### 5. Vitest/Jest Plugins

AIMock has JS test framework plugins that manage server lifecycle and patch env vars.

This is less relevant for Xenix Python tests unless a future frontend/plugin test layer uses JS.

## First-Slice Recommendation

Use `npx @copilotkit/aimock --config aimock.json` as a real HTTP mock server and configure the Xenix LLM provider base URL to AIMock.

This keeps local mock traffic on the same provider boundary used in production.

## Current Native Mock Foundation

Product code has a single LLM provider contract: OpenAI-compatible `/v1/chat/completions`.

LLM provider configuration is stored in `config/agent_settings.json` and edited through Settings. `XENIX_LLM_*` environment variables are not provider configuration inputs.

Development-only AIMock settings are visible when:

```powershell
$env:XENIX_ENV = "development"
```

Implemented OpenAI-compatible streaming parser:

- request body sets `stream: true`
- SSE `delta.content` becomes provider-independent assistant deltas
- SSE `delta.tool_calls` are accumulated into canonical tool calls at stream completion

HTTP AIMock remains attached through the same provider boundary:

```text
Settings -> AIMock -> Use AIMock
AIMock base URL = http://127.0.0.1:4010
AIMock API key = test
```

## Local Setup

Repository setup:

- `aimock.json`: npx AIMock configuration.
- `fixtures/aimock/10-xenix-streaming.json`: preset Xenix Chatbot streaming, tool-round, and rich Markdown preview fixtures.
- `fixtures/data/aimock-sales-demand.csv`: drag-and-drop sample training dataset.
- `fixtures/data/aimock-sales-future.csv`: drag-and-drop sample future rows.
- `.vscode/tasks.json`: `AIMock: serve fixtures` task.

Start AIMock from VSCode:

```text
Terminal -> Run Task... -> AIMock: serve fixtures
```

Equivalent shell command:

```powershell
npx --yes @copilotkit/aimock --config aimock.json --port 4010 --host 127.0.0.1
```

Run Xenix in development mode, open Settings, then configure:

```text
LLM provider:
  Model = gpt-4o-mini
  Streaming = enabled

AIMock:
  Use AIMock = enabled
  AIMock base URL = http://127.0.0.1:4010
  AIMock API key = test
```

Preset prompts:

- `inspect uploaded dataset`: drag `fixtures/data/aimock-sales-demand.csv` into the composer, then sends a real `data.peek` tool call; the follow-up fixture is keyed by `toolCallId=call_xenix_data_peek`.
- `show analysis result`: streams a rich Markdown analysis result with tables, artifact links, and an image link.
- `stream test`: streams assistant text plus a small Markdown table.
- `hello xenix`: validates that the OpenAI-compatible provider boundary is routed to AIMock.
- Any other chat request hits the final catch-all fixture, which returns the available preset prompts.

See `tasks/native-ai-first/streaming-message-mock.md` for the implemented streaming path and verification.

## Sources

- AIMock home: https://aimock.copilotkit.dev/
- Record & Replay: https://aimock.copilotkit.dev/record-replay/
- CLI/Docker: https://aimock.copilotkit.dev/aimock-cli/
- Fixtures: https://aimock.copilotkit.dev/fixtures/
- Test plugins: https://aimock.copilotkit.dev/test-plugins/
