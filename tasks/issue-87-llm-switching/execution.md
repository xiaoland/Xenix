# Execution Task

## Objective & Hypothesis

- Objective: Implement per-thread LLM model switching with multi-provider configuration and a fixed two-row Chatbot composer model picker.
- Hypothesis: A dedicated LLM Service can own provider configuration, `fq_model_key` parsing, and provider resolution so Agent Harness can lock one provider per turn while the UI updates only the thread's next-turn model selection.

## Pre-Execution Restatement

- Target: GitHub issue #87, supporting multiple OpenAI-compatible LLM providers, per-thread model selection, and Composer model picker.
- Current state and context: Agent settings are a flat single-provider JSON shape; Agent Harness holds one mutable provider; Composer switches compact/expanded layouts and has no model picker.
- Operation: Add LLM Service, migrate settings shape, persist `agent_thread.selected_fq_model_key`, lock provider at turn start, and update Settings/Composer UI.
- Scope included: OpenAI-compatible dialect only, schema extension point for other dialects, settings compatibility for legacy JSON, storage migration, UI translations, and focused tests.
- Scope excluded: Native non-OpenAI dialect adapters, automatic remote model discovery, and changing Composer model selection into a global default update.
- Invariants: Model keys cannot contain `/`; `fq_model_key` is generated and parsed in LLM Service; Composer selection affects the next turn for the current thread; in-flight turns keep their starting provider; the Composer ModelPicker is the same height as the attach/send controls.
- Likely affected files: `src/xenix/services/llm/*`, `src/xenix/services/agent/*`, `src/xenix/services/storage/*`, `src/xenix/ui/*`, translations, docs, and focused tests.
- Uncertainty: Existing dirty work includes thread-title support in the same files and must be preserved.

## Guardrails Touched

- UI remains service-driven and does not parse provider configuration.
- Agent Harness remains owner of Thread/Turn/Message state, while LLM Service owns provider/model resolution.
- SQLite schema changes require forward migration, bootstrap tests, and runtime documentation updates.
- User-visible strings must go through Qt translation pipeline.

## Plan

1. Add LLM Service settings models, compatibility migration, `fq_model_key` helpers, and OpenAI-compatible provider resolver.
2. Add thread selected model storage and Agent Harness APIs for per-thread selection plus turn-start provider locking.
3. Replace Composer compact/expanded controls with fixed two-row layout and ModelPicker.
4. Replace flat Settings LLM fields with multi-provider settings and model selectors.
5. Update tests, docs, and translations, then run targeted verification.

## Verification

- Command: `pdm run pytest tests/test_agent_settings.py tests/test_agent_harness_streaming.py -q`
- Expected: LLM settings and Harness provider-locking tests pass.
- Observed: 25 passed.
- Command: `pdm run pytest tests/test_main.py tests/test_i18n.py -q`
- Expected: Composer/Settings UI and translation tests pass.
- Observed: 37 passed.
- Command: `pdm run pytest tests/test_storage_bootstrap.py -q`
- Expected: fresh bootstrap and v12 migration coverage pass.
- Observed: 15 passed.
- Command: `pdm run i18n-extract` and `pdm run i18n-compile`
- Expected: new Settings/Composer strings are extracted and zh_CN compiles with complete translations.
- Observed: extraction succeeded; zh_CN compiled with 168 finished translations and 0 unfinished.
- Command: `pdm run pytest -q`
- Expected: full suite passes.
- Observed: 149 passed after fixing the ModelPicker to the Composer control height.
- Command: `pdm run check`
- Expected: source/tests/scripts compile.
- Observed: passed.

## Promotion Notes

- Durable truth candidates: LLM Service owns `fq_model_key` and provider resolution; Agent Thread stores next-turn selected model.
- Keep in task only: exact Settings dialog field layout details unless they become stable product language.
