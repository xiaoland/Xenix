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

Slice 0 (audit) is the entry point; findings live in `preflight.md`. The plan in
`plan.md` sequences the cleanup into small verified slices.

## Next Step

Review `preflight.md`, then approve Slice 1.
