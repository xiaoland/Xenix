# System Prompt Business Guidance

## Objective & Hypothesis

Update Xenix's default Agent system prompt so the assistant behaves as a business-facing data analysis guide for non-technical users.

Hypothesis: the durable owner is `src/xenix/services/storage/models.py` because `default_agent_thread_system_prompt()` seeds new Agent threads and the first hidden provider-facing system message.

## Guardrails Touched

- Product intent: Chatbot-first native experience for non-technical users.
- Service boundary: Agent Harness owns provider-facing Thread and Message semantics; Storage owns persistence model defaults.
- Persistence: no schema or migration change expected because this changes default text for new threads, not stored rows.

## Verification

- Focused tests:
  - `tests/test_agent_harness_foundation.py`
  - `tests/test_agent_harness_streaming.py`
- Expected proof:
  - default prompt still formats `interface_locale`
  - system prompt remains the first provider message
  - prompt includes business-facing analysis-selection, evidence-boundary, and output-shape instructions

Passed run:

- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_streaming.py`
- Result: 32 passed.

## Current Understanding

The existing prompt already tells Xenix to communicate in the UI locale and prefer business-oriented language. It does not explicitly require the assistant to identify business scenario, analysis object, data grain, field roles, and user intent before choosing a path. It also does not explicitly hide algorithm menus, prioritize data-structure fit over model choice, compare complex models against baselines, or require result explanations to include business meaning, actions, risks, and process trace.

Implementation updated:

- `src/xenix/services/storage/models.py` now adds explicit business-analysis behavior rules to the default thread system prompt.
- `tests/test_agent_harness_foundation.py` and `tests/test_agent_harness_streaming.py` now assert the key prompt obligations remain present in new thread prompts and provider-facing messages.
- `docs/30-unit-tdd/agent-harness.md` now records the system prompt behavior contract.

## Next Step

Ready for review.
