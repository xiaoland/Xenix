# Maintainability Optimization — Control Surface

## Objective

Reduce the codebase's structural debt — delete dead code, simplify oversized
units, correct stale/incorrect docs and comments — and add the missing durable
guides (local `AGENTS.md`, `docs/30-unit-tdd/*`, code comments) so a future
contributor can navigate the seams without archaeology. Do not change product
behavior except where a small, verifiable correction is clearly warranted.

## Guardrails

- Default is behavior-equivalent. A small behavior fix is allowed only when it
  corrects an obvious defect or stale contract, and it must be recorded in the
  slice and covered by an existing or new test.
- Never rewrite or renumber an existing migration edge; migrations are
  historically frozen. See `docs/40-deployment/local-state-evolution.md`.
- `ml/` legacy model scripts are untouched.
- `tasks/` stays volatile; durable truth lands in `docs/`.
- UI text changes stay translatable (`i18n-extract` / `i18n-compile`).
- Each slice lands verified: `pdm run check` plus `pdm run test` (or the smallest
  focused selection that proves the affected contract). Commit only on explicit
  user command.

## Verification

- `pdm run check` green after every slice (Ruff F catches unused imports/vars).
- `pdm run test` (197 passed baseline) stays green; add/trim tests only per the
  Testing Intent in `CONTRIBUTING.md`.
- For deletions: the removed symbol has zero static references in `src/` and
  `tests/` (grep-verified), or is provably unreachable through the dynamic
  `load_module` seam.

## Current Truth

- Slice 0 (audit) recorded in `preflight.md`.
- Slice 1 (dead-code deletion + `services/AGENTS.md` and `services/llm/AGENTS.md`)
  landed and committed.
- Slice 2 (`conversation.py` message-row / provider-message builder extraction)
  landed and committed; `pdm run test` 197 passed.
- Slice 3 (UI/init hot spots) is delegated to another session and out of scope here.
- Slice 4 (correct stale docs) landed: marked the Job-layer feed-source wording as
  superseded in `pr1-job-layer-rework/plan.md` and `general-job-layer.md`.
  Durable docs were audited and found consistent — no `docs/` correction needed.

## Next Step

Task complete. The optional "later" deep splitting of `tools.py` /
`text_analysis.py` remains unapproved and was not attempted.
