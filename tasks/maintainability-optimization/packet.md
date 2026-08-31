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
- Slice 5 (approved "later" deep splitting) landed:
  - `text_analysis.py` (104 KB → ~88 KB): extracted 38 module-level helper
    functions into `ml/models/_text_helpers.py`.
  - `tools.py` (106 KB → ~93 KB): extracted model-key normalization into an
    `agent/_model_keys.py` mixin. A full split of the remaining registry was not
    attempted — the class is a tightly-coupled god object where further
    extraction has low value and high regression risk.

## Next Step

Task complete. All in-scope slices landed and verified (`pdm run test` 197 passed
after each code change).

## Open follow-up (not this packet)

- `pyproject.toml` ruff `extend-exclude = ["ml"]` unintentionally excludes the
  whole `src/xenix/services/ml/` subtree from `pdm run lint`/`pdm run check`
  (the glob `"ml"` matches that directory name, not just the legacy root `ml/`).
  The native ML subtree is therefore not lint-covered; the two files split here
  were verified with a direct `ruff check` instead. Root-anchoring the exclude
  (e.g. `/ml` or `ml/`) would re-enable coverage but may surface pre-existing
  lint debt in the ML subtree.
