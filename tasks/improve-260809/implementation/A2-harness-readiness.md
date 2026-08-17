# A2 Implementation Plan — Formal Agent Harness Readiness

**Status:** implemented and provider-free verified under
[IH-A2](../handshakes/IH-A2-harness-readiness.md).

## Objective

Remove only evidence-backed local Harness admission blockers before paid A1:
correct invocation topology and supply exact-rubric calibration inputs without
changing cases, Judge independence, or budgets.

## Guardrails

- Do not call Subject, Judge, or Embedding providers.
- Do not create Judge observations, edit persisted reports, or label any offline
  check as live evidence.
- Do not change case prompts, semantic rubrics/checks, product code, service
  tests, the one-model subject boundary, or installed budget maxima.
- Do not add a shared invocation-ID switch without one durable aggregate-budget
  owner.
- Preserve concurrent topic/O2, Skill, and M1 work.

## Coherent Passes

1. Trace formal identity comparison and invocation budget ownership through the
   report policy, pytest plugin, runner, scripts, and workflow.
2. Add an explicit regression proof for four distinct invocation IDs; make no
   runtime/controller change when the claimed blocker is disproved.
3. Add a strict case-agnostic manifest loader and one versioned manifest with
   exact authoritative rubric references and four bounded labelled packets per
   Judge-required A1 case.
4. Extend the calibration CLI additively and prove source selection without
   dispatching a provider.
5. Run provider-free Harness checks, exact six-case collect-only checks,
   repository checks, and diff hygiene; update A1/A2 records with any remaining
   external blocker.

## Verification

```powershell
pdm run benchmark-agent-harness-check -q
pdm run benchmark-agent-harness -- @selectors --collect-only -q
pdm run benchmark-agent-harness-headed -- @selectors --collect-only -q
pdm run check
git diff --check
```

The calibration CLI loader is exercised separately by parsing one manifest
suite and confirming its stable path-free suite identity and four packets; it
does not load external settings or call a provider.

## Stop Conditions

- A case rubric cannot be referenced as the sole authority.
- Exact calibration would require retaining raw/private evidence.
- Invocation safety would require shared mutable state with ambiguous ownership.
- Topic or another concurrently owned file blocks collection; report it to its
  owner rather than editing across the boundary.
