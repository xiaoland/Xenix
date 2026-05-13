# AIMock Integration

## Status

- Mode: Explore.
- Scope: possible CopilotKit AIMock integration modes for Xenix.

## Boundary

AIMock attaches at the LLM provider boundary.

Xenix provider clients point their base URL at an AIMock server in tests:

```text
OpenAIChatCompletionsV1Provider
  base_url = http://127.0.0.1:4010/v1

DeepSeekChatCompletionsProvider
  base_url = http://127.0.0.1:4010/v1
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

Use Docker or `npx llmock` as a real HTTP mock server and configure the Xenix LLM provider base URL to AIMock.

This keeps tests language-agnostic and validates the same provider boundary used in production.

## Sources

- AIMock home: https://aimock.copilotkit.dev/
- Record & Replay: https://aimock.copilotkit.dev/record-replay/
- CLI/Docker: https://aimock.copilotkit.dev/aimock-cli/
- Fixtures: https://aimock.copilotkit.dev/fixtures/
- Test plugins: https://aimock.copilotkit.dev/test-plugins/
