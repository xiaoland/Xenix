# PR1 Job Layer Rework — Control Surface

## Objective

Make the generic Job layer the actual scheduling authority for ML and Knowledge
background work — one persisted job table, one scheduler, one worker-dispatch
contract, one lifecycle status model — replacing the read-only projection PR#122
delivered and the per-domain ad-hoc queues. Fix the ML "pending" status crash.
Keep the global Jobs GUI as the modeless management surface (with actions).

## Guardrails

- JobRow is the single scheduling authority; domain services remain authoritative
  for domain results, recovery semantics, and artifact finalization.
- Job row status and domain row status stay consistent through handler transitions.
- ML restart semantics stay PERMANENT ORPHAN (deliberate product decision): queued
  ML jobs are never auto-requeued at startup.
- Knowledge restart semantics stay requeue-after-verification (existing
  _recover_imports / index recovery behavior preserved).
- ML worker pools/runners stay execution helpers (ml/AGENTS.md); lifecycle
  branching and artifact finalization stay in MLTaskService.
- GUI stays modeless, service-driven, translated, LanguageChange-aware.
- Schema changes go through a forward migration edge (v26→v27); never rewrite
  an existing edge; prove fresh bootstrap and upgrade.
- Commit only on explicit user command; each phase lands as a verified slice.

## Verification

- Regression: ML PENDING projects to QUEUED; feed never crashes on queued ML work.
- Scheduler unit tests (fake handlers): FIFO dispatch, per-domain concurrency
  caps, cancel queued/running, per-domain restart policy (ML orphan / Knowledge
  requeue).
- Migration: v26→v27 edge test + fresh-bootstrap equivalence; backfilled job
  rows match existing domain rows.
- Integration: one real Knowledge import and one real ML task through the
  generic scheduler end to end; existing MLService call sites still work.
- GUI: offscreen dialog tests for feed, filters, summary, and actions
  (cancel/retry/view-log per capability).
- Full suites: pdm run test, pdm run check, i18n extract/complete/compile,
  pdm run smoke.

## Current Truth

See design.md (architecture + decisions) and preflight.md (baseline evidence).
Confirmed bug (user reproduced): JobStatus(task.status.value) raises on
MLTaskStatus.PENDING because the unified vocabulary uses "queued".

## Open Decisions

All six decisions D1–D6 are resolved — see design.md §Decisions.
D1 = B (unified job table, deep rework). D3 = ML permanent orphan (deliberate).
D6 (PRD vocabulary) landed in Phase 5.

## Next Step

Complete. Phases 0–5 landed as verified slices: Phase 0 pending→queued fix,
Phase 1 job table + scheduler core, Phase 2 ML adapter, Phase 3 Knowledge
adapters, Phase 4 Job Center cancel action, Phase 5 PRD vocabulary. Final
verification: pdm run test (197 passed), pdm run check, pdm run smoke all green.
