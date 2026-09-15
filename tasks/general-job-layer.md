# General Job Layer

> Superseded by `tasks/pr1-job-layer-rework/` (the generic scheduler rework that
> made `JobRow`/`JobScheduler` the actual scheduling authority). Kept for history;
> its "read-only projection" wording no longer describes the landed design.

## Objective

Provide one service-owned job projection and one global GUI surface for observing
Knowledge and ML background work.

## Guardrails

- Existing Knowledge and ML rows remain authoritative for lifecycle and results.
- The common layer is a read-only projection; it must not duplicate persisted state.
- Existing Knowledge retry/cancel workflows and ML execution behavior remain unchanged.
- User-visible text remains translatable.

## Verification

- Focused service tests prove mapping, filtering, ordering, and status normalization (2 passed).
- Ruff, strict type checking for the new modules, lock validation, skill-catalog checks,
  translation compilation, and bytecode compilation pass.
- Translation catalogs contain 414/414 completed entries in both locales.
- Full GUI-backed test and smoke entrypoints require system `libEGL.so.1`, which is
  unavailable in the current Linux execution container.

## Current Truth

`JobQueryService` now projects ML and Knowledge authorities into one typed feed,
and `JobCenterDialog` provides global filtering, refresh, summary, and details.
No duplicate lifecycle state or schema migration was introduced. Knowledge task
errors now preserve their domain-owned human-readable summaries.

## Next Step

Run final checks, commit, and push `feat/general-job-layer`.
