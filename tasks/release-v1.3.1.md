# v1.3.1 Release Packet

## Status

Consumed by a safe publication failure. `v1.3.1` remains immutable at main
promotion commit `6760286f`; it is not publicly visible because the publisher
failed before updating the canonical feed.

## Objective

Publish the corrected Xenix Native release as v1.3.1 only after Promotion CI is
proportionate to the product and the redesigned proof portfolio passes.

## Guardrails

- Never move or delete `v1.3.0`; it remains the immutable identity of the failed,
  unpublished attempt.
- Never move or delete `v1.3.1`, overwrite its uploaded package, or overwrite the
  conflicting shared OCR object.
- Preserve the promoted product/release history and use a new
  `develop -> main` Promotion PR for the accepted CI/test architecture.
- Preserve unrelated user worktree changes.

## Verification

- Promotion pytest collects at most 100 intentionally selected semantic cases.
- Boundary models and static analysis own input-shape facts; semantic tests own
  user outcomes, state, side effects, and trust-boundary failure behavior.
- The agreed Promotion duration budgets pass the required qualifying sample.
- The canonical feed remains v1.2.0.
- The successor release uses a content-addressed OCR object key and does not
  mutate either conflicting object.

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
- PR #115 passed Native CI and produced main promotion commit `6760286f`.
- Local and remote release identity checks bound `v1.3.1` to that commit and PR.
- Native OCR build, package, and packaged smoke passed in run `30258978782`.
- The publisher uploaded and verified the v1.3.1 full package, then failed closed
  because the current OCR archive and an existing immutable OCR object shared a
  runtime-only key but had different size and SHA-256.
- The canonical feed still declares v1.2.0; v1.3.1 never became visible.

## Next Step

Publish the content-addressing correction as a new v1.3.2 promotion and release.
