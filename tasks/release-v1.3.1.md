# v1.3.1 Release Packet

## Status

Ready for the `develop -> main` Promotion PR. The accepted CI/test portfolio and
headed Agent Harness benchmark have unlocked the v1.3.1 version mutation. Tag
creation and release execution still wait for the promoted Native CI result.

## Objective

Publish the corrected Xenix Native release as v1.3.1 only after Promotion CI is
proportionate to the product and the redesigned proof portfolio passes.

## Guardrails

- Never move or delete `v1.3.0`; it remains the immutable identity of the failed,
  unpublished attempt.
- Do not create `v1.3.1`, enter the release Environment, or mutate OSS/public
  feeds before the redesigned Native CI passes on the promotion PR.
- Preserve the promoted product/release history and use a new
  `develop -> main` Promotion PR for the accepted CI/test architecture.
- Preserve unrelated user worktree changes.

## Verification

- Promotion pytest collects at most 100 intentionally selected semantic cases.
- Boundary models and static analysis own input-shape facts; semantic tests own
  user outcomes, state, side effects, and trust-boundary failure behavior.
- The agreed Promotion duration budgets pass the required qualifying sample.
- A final promoted main result declares v1.3.1 and passes release identity
  preflight before the immutable tag is pushed.
- Native Release publishes and publicly verifies v1.3.1 without moving v1.3.0.

## Current Truth

- `v1.3.0` targets `8b7dd79a` and published no artifacts or feed update.
- The corrected proof topology was promoted as `a5b1f905` through PR #114.
- The user selected v1.3.1 rather than an unpublished-tag mutation exception.
- CI/CD Slice 04 now selects 30 semantic Promotion cases, delegates shape facts
  to typed boundary models and static analysis, and removes the obsolete suite
  manifest topology.
- Local acceptance passed `pdm run test`, `pdm run check`, and `pdm run smoke`.
  The visible benchmark also exercised real file import, the configured external
  LLM, chart work, and knowledge retrieval through the actual desktop UI.
- `pyproject.toml` now declares `1.3.1`; the immutable tag remains uncreated.

## Next Step

Promote this result through a `develop -> main` PR, require Native CI to pass,
then create and locally verify `v1.3.1` on the eligible main promotion result
before pushing the immutable tag.
