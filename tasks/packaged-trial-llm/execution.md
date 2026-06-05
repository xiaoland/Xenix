# Packaged Trial LLM

## Objective & Hypothesis

- Objective: Let packaged builds optionally include a built-in trial LLM provider so first-run users can chat without configuring an LLM provider.
- Hypothesis: A generated package-local trial settings module can inject the real provider secret at `LLMService.build_provider()` time while keeping `agent_settings.json` free of the packaged API key.

## Guardrails Touched

- LLM Service owns provider/model resolution and packaged trial secret injection.
- UI stays service-driven and only reflects provider configuration state.
- Packaged secrets must not be committed, logged, or persisted into runtime settings.
- If packaging env vars are absent, builds must still succeed and first-run behavior must remain the existing manual-provider setup path.

## Verification

- Add focused tests for trial availability, fallback without trial env, no secret persistence, and generated packaging module helpers.
- Run targeted settings/build/UI tests.
- Command: `pdm run pytest tests/test_agent_settings.py tests/test_build_info.py -q`
- Observed: 13 passed.
- Command: `pdm run pytest tests/test_main.py -q`
- Observed: 37 passed.
- Command: `pdm run i18n-extract`
- Observed: 1 new settings placeholder string extracted.
- Command: `pdm run i18n-compile`
- Observed: zh_CN compiled with 199 finished translations and 0 unfinished.
- Command: `pdm run check`
- Observed: source, tests, and scripts compile.
- Command: `pdm run pytest -q`
- Observed: 193 passed.
