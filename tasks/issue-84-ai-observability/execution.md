# Issue 84 AI Observability Execution

## Objective & Hypothesis

- Objective: add the first user-visible AI token observability slice in Chatbot, using provider request rows as the usage authority and turn-level UI summaries as the display surface.
- Hypothesis: provider request records close the causality gap between message history and token usage better than message-level usage, because each request can include several persisted messages and can produce assistant and tool-call outputs.

## Pre-Execution Restatement

- Target: issue #84 basic AI observability.
- Current state and context: Agent Harness persists threads, turns, messages, tool calls, runs, and guard rows. Provider usage is only kept incidentally in assistant `provider_payload` when a provider returns it, and streaming does not request usage chunks.
- Operation: add durable provider request records, parse normalized usage including cached input tokens, make system prompt a hidden first-turn system message, and render a turn-end usage overview inside Chatbot.
- Scope included: OpenAI-compatible usage parsing, provider request persistence, first-turn hidden system message semantics, turn usage projection, Chatbot overview rendering, schema migration, tests, translations, and durable docs.
- Scope excluded: cost estimation, standalone observability panel, charts, latency metrics, model comparison, organization usage APIs, and local token estimation when provider usage is absent.
- Invariants: Chatbot remains the default operator path; UI does not own storage semantics; Agent Harness owns provider requests and message history; hidden system messages do not render as normal Chatbot messages.
- Likely affected files: `src/xenix/services/agent/*`, `src/xenix/services/storage/*`, `src/xenix/ui/chatbot.py`, translations, tests, and runtime/storage docs.
- Uncertainty: whether all OpenAI-compatible providers accept `stream_options.include_usage`; implementation should request it and degrade cleanly if usage is not returned.

## Guardrails Touched

- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, provider interaction, and run recording.
- Storage changes require a forward migration, schema version bump, fresh bootstrap coverage, and upgrade coverage.
- User-visible UI strings must go through Qt translation files.
- Chatbot UI should show observability inline, not as a standalone panel.

## Plan

1. Add storage model, repository/store APIs, and migration for `agent_provider_request`.
2. Make first turn create a hidden system message and use persisted messages for provider input.
3. Parse provider usage, including cached input tokens, for non-streaming and streaming calls.
4. Persist provider request records around primary and guard provider calls.
5. Project turn-level usage overview events and render them in Chatbot.
6. Update tests, docs, and translations.
7. Run targeted tests, then broader verification.

## Verification

- Command: `pdm run pytest tests/test_storage_bootstrap.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_main.py -q`
- Expected: targeted storage, harness, provider parsing, and Chatbot UI tests pass.
- Observed: `60 passed`; pytest emitted a Windows temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run pytest tests/test_i18n.py tests/test_storage_bootstrap.py tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py tests/test_main.py -q`
- Expected: targeted tests plus language-switch coverage pass.
- Observed: `64 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run pytest -q`
- Expected: full suite passes.
- Observed: `122 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run check`
- Expected: compileall succeeds for `src`, `tests`, and `scripts`.
- Observed: passed.
- Startup regression: the first implementation wrote the hidden system message as lowercase `system`, but `AgentMessageKind` and `AgentMessageAuthor` persist SQLAlchemy enum member names such as `SYSTEM`.
- Fix: schema `v11 -> v12` rewrites lowercase message kind/UI author values to enum member names, while `v10 -> v11` now inserts the hidden system message with `SYSTEM`.
- Command: `pdm run pytest tests/test_storage_bootstrap.py -q`
- Expected: migration tests cover the v11 enum repair and ORM readability.
- Observed: `14 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run pytest -q`
- Expected: full suite passes after the migration repair.
- Observed: `123 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run check`
- Expected: compileall succeeds for `src`, `tests`, and `scripts`.
- Observed: passed.
- Command: `$env:PYTHONPATH='src'; pdm run python -c "... StorageBootstrapService().initialize(...)"`.
- Expected: default runtime database initializes through the startup storage path.
- Observed: initialized `C:\Users\yyh\AppData\Local\Xenix\state\xenix.db` at `schema_version=12`.
- Command: `pdm run smoke`
- Expected: application startup assembly succeeds without entering the normal UI event loop.
- Observed: passed; logs reported `Xenix native shell started` and `Xenix smoke test completed`.
- UI refinement: turn token usage overview now renders as left-aligned muted metadata text, one point smaller than the surrounding Chatbot text, and no longer includes the `AI usage` / `AI 用量` prefix.
- Command: `pdm run pytest tests/test_main.py::test_thread_detail_view_renders_turn_usage_overview tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`
- Expected: usage overview rendering and language-switch text still pass after the visual/text refinement.
- Observed: `2 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run check`
- Expected: compileall succeeds for `src`, `tests`, and `scripts`.
- Observed: passed.
- UI refinement: turn token usage overview now shows only input and output token totals as `↑ input · ↓ output`; cached input tokens remain as an input-side parenthetical annotation.
- Command: `pdm run pytest tests/test_main.py::test_thread_detail_view_renders_turn_usage_overview tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell -q`
- Expected: usage overview rendering and language-switch text pass after removing total tokens and request count.
- Observed: `2 passed`; same pytest temp-directory cleanup `PermissionError` after completion.
- Command: `pdm run check`
- Expected: compileall succeeds for `src`, `tests`, and `scripts`.
- Observed: passed.

## Promotion Notes

- Durable truth candidates: provider request is the token usage authority; system prompt is a hidden first-turn system message; turn overview is the first user-visible observability surface.
- Keep in task only: implementation notes and transient verification observations.
