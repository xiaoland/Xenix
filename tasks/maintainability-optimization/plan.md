# Maintainability Optimization — Implementation Plan

Each slice lands as one verified, separately-reviewable change. No commit without
explicit instruction. Behavior-equivalent by default; any small behavior fix is
called out in the slice and covered by a test.

## Slice 0 — Audit (complete)

- `preflight.md` records the dead-code, size, and function-length findings.

## Slice 1 — Delete confirmed dead code + add missing guides (low risk)

- Delete the four unused "compatibility forwarding" functions in `app.py`
  (`_register_agent_skill_tools`, `_agent_skill_activated_skill_names`,
  `_agent_skill_context_messages`, `_agent_skill_tool_scope_names`); verify zero
  references in `src/` and `tests/` first.
- Add `services/llm/AGENTS.md` and `services/AGENTS.md` (owner + seam guidance,
  not product truth).
- Verify: `pdm run check` + `pdm run test`.

## Slice 2 — Structural simplification (conversation.py first)

- Start with `services/llm/conversation.py` (67 KB) as the reference seam: extract
  cohesive responsibilities (staged tool invocation, message row projection,
  provider message assembly) into smaller functions/helpers without changing
  behavior.
- Verify: `pdm run check` + focused `tests/` covering the LLM conversation seam.

## Slice 3 — Largest UI/init hot spots

- Simplify `app.py::build_main_window` (294 lines) and the oversized widget
  `__init__`/`_build_ui` methods (`settings_dialog`, `main_window`, `chatbot`) by
  extracting construction helpers. Keep translations and signal wiring intact.
- Verify: `pdm run check` + `pdm run test` + `pdm run smoke`.

## Slice 4 — Correct stale docs and comments

- Reconcile doc/comments that diverged from landed behavior (e.g. the Job layer
  feed-source wording already noted in `pr1-job-layer-rework/packet.md`).
- Admit any unit-design docs to `docs/30-unit-tdd/` where a seam was clarified.

## Later (only if approved)

- Re-measure size/complexity after Slices 1–4 and decide whether deeper file
  splitting (e.g. `tools.py`, `text_analysis.py`) is warranted.
