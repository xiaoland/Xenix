# Maintainability Optimization — Implementation Plan

Each slice lands as one verified, separately-reviewable change. No commit without
explicit instruction. Behavior-equivalent by default; any small behavior fix is
called out in the slice and covered by a test.

## Slice 0 — Audit (complete)

- `preflight.md` records the dead-code, size, and function-length findings.

## Slice 1 — Delete confirmed dead code + add missing guides (complete)

- Delete the four unused "compatibility forwarding" functions in `app.py`
  (`_register_agent_skill_tools`, `_agent_skill_activated_skill_names`,
  `_agent_skill_context_messages`, `_agent_skill_tool_scope_names`); verify zero
  references in `src/` and `tests/` first.
- Add `services/llm/AGENTS.md` and `services/AGENTS.md` (owner + seam guidance,
  not product truth).
- Verify: `pdm run check` + `pdm run test`.

## Slice 2 — Structural simplification (conversation.py first) (complete)

- Extracted `_final_message_rows` into three pure row-builders and
  `_provider_messages` into four pure provider-message builders in
  `services/llm/conversation.py`, behavior-equivalent.
- Verify: `pdm run check` + `pdm run test` (197 passed).

## Slice 3 — Largest UI/init hot spots (delegated elsewhere)

- Simplify `app.py::build_main_window` (294 lines) and the oversized widget
  `__init__`/`_build_ui` methods (`settings_dialog`, `main_window`, `chatbot`) by
  extracting construction helpers. Keep translations and signal wiring intact.
- Verify: `pdm run check` + `pdm run test` + `pdm run smoke`.

## Slice 4 — Correct stale docs and comments (complete)

- Marked the Job-layer feed-source wording as superseded in
  `pr1-job-layer-rework/plan.md` and `general-job-layer.md`.
- Audited durable `docs/` for divergence: none found; `job-feed-contract.md`
  already codifies the landed feed design, and the index/unit-design docs are
  consistent. No `docs/30-unit-tdd/` admission was warranted — the extracted
  builders are source/test truth, not a new local seam.

## Later (only if approved)

- Re-measure size/complexity after Slices 1–4 and decide whether deeper file
  splitting (e.g. `tools.py`, `text_analysis.py`) is warranted.
