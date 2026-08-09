# Improve ML Capability — Program Dashboard

**Status:** Active. `IH-B0` (B0 Agent Harness baseline, acceptance, and diagnosis infrastructure) is implemented and offline-verified; the paid live baseline remains intentionally deferred until the matching service black-box cases land green.
**Opened:** 2026-08-09

## Objective

Make Xenix reliably complete business-facing recommendation, clustering, forecasting, and text-analysis workflows, including the data preparation needed to keep their results honest. Use the supplied case corpus as evaluator-private evidence for service integration tests, Agent Harness benchmarks, before/after comparison, and targeted ablation.

The product outcome is not a larger algorithm menu. A non-technical user should be able to provide business data, ask a business question, receive a correctly prepared and evaluated result, inspect the resulting Dataset/Artifact, and understand the action, uncertainty, and limitations.

## Guardrails

- Preserve source files and source Datasets; transformations and model outputs are separately registered derived results.
- Keep local services, SQLite state, Datasets, and Artifacts authoritative. Workers remain execution helpers.
- Keep hidden labels, recommendation truth, future observations, reference code, sample outputs, and rubrics physically outside the Agent-visible projection.
- Do not index the supplied corpus into the subject Agent's Knowledge Library for derived cases.
- Do not commit or redistribute supplied source material while provenance and redistribution rights remain unresolved. Do not load supplied Joblib files.
- Fit preprocessing only on the training side of a split. Identifiers, hidden labels, future values, and post-outcome fields are not model features.
- Service correctness and Agent behavior have different owners: a failed service qualification is not an Agent semantic failure.
- Service black-box cases and all executable support stay under `tests/`; Agent Harness cases and all executable support stay under `benchmarks/agent_harness/`. Neither tree imports, invokes, or reads results from the other.
- Benchmark-driven changes to preprocessing, Skills, Tool schemas, orchestration, logs, or traces require a reproduced failure and a new bounded Impact Handshake; this packet does not pre-authorize broad Harness changes.
- Branches, worktrees, commits, pushes, durable docs, tests, and product source remain separately permissioned.

## Verification

The accepted proof topology has three layers:

1. **Oracle qualification** proves that a private case, split, expected result, tolerance, and runtime identity are valid.
2. **Ordinary service integration tests** prove deterministic data/ML behavior through public service boundaries, worker finalization, registered Dataset/Artifact output, and reusable apply where promised.
3. **Agent Harness benchmarks** prove that the Agent can understand a business request, choose and orchestrate valid Tools, ground its answer in public outputs, and complete the user-visible workflow.

The benchmark runner remains a paid live measurement surface over one pinned subject model. A versioned Agent-report policy decides acceptance; service qualification is enforced only by development guidance and CI dispatch order. Details are in [Verification architecture](verification.md) and [Case catalog](cases/catalog.md).

Current verified repository state:

- `pdm run test -q`: 45 passed on 2026-08-09.
- Provider-free B0 infrastructure/policy/calibration checks: 26 passed.
- Headless Agent Harness collect-only: 8 live cases.
- Headed Agent Harness collect-only: the same 8 live cases.
- An explicit live case selector collects exactly one cell in either mode.
- `pdm run check` and isolated-runtime `pdm run smoke` pass.
- No live provider baseline has been run for this program.

## Current Truth

- The agreed program has two product verticals and one first cross-cut:
  - Cross-cut 00: baseline, acceptance, diagnosis, and exact optimization of the failing layer;
  - Vertical 01: foundation + trustworthy clustering + first-class forecasting;
  - Vertical 02: recommendation ranking + text-pipeline quality.
- Cross-cut 00 starts before product implementation, brackets both verticals, and continues after them. It is not a third product vertical or a final cleanup phase.
- Existing clustering, recommendation, and text implementations have useful model seams but weak product-level evaluation. Native forecasting is absent. Shared preparation is broad but not yet split-aware or reusable enough for every future-apply workflow.
- The current ordinary test portfolio no longer directly covers real ML lifecycle outcomes. Material-derived cases should restore public-boundary integration coverage without asserting sklearn internals.
- The B0 live benchmark now has eight outcome-oriented cases, one pinned subject model, hard cell/invocation safety boundaries, and a separate versioned acceptance policy. Semantic failure remains a valid measurement rather than a pytest infrastructure failure.
- The supplied corpus is rich enough to qualify cleaning, leakage-safe preparation, clustering, recommendation, forecasting, and bilingual text cases, but it contains severe answer contamination and unresolved redistribution rights.
- Detailed decisions, uncertainties, topology, working sets, and slice status live in the linked packet files rather than this dashboard.

## Next Step

Discuss and draft `IH-F` (foundation: bounded profile/evaluation/result facts and split-aware preparation), then resolve the forecast-scope decision needed by `IH-CF` (clustering trustworthiness and the first native forecast workflow). Once an approved handshake is explicitly started, objective automated acceptance advances the program without a separate phase-review pause; Sir's manual real-world acceptance remains the final program gate. No paid baseline runs before the product slices provide matching green service selectors.

## Packet Map

- [Packet-local protocol](protocol.md)
- [Program topology and sequence](program-plan.md)
- [Decisions](decisions.md)
- [Open questions](open-questions.md)
- [Verification architecture](verification.md)
- [Working-set and ownership map](working-set.md)
- [Case catalog](cases/catalog.md)
- [Vertical 01 — Foundation, clustering, forecasting](workstreams/01-foundation-clustering-forecasting/packet.md)
- [Vertical 02 — Recommendation and text](workstreams/02-recommendation-text/packet.md)
- [Cross-cut 00 — Baseline, acceptance, diagnosis](crosscuts/00-baseline-acceptance-diagnosis/packet.md)
- [B0 solution proposal](crosscuts/00-baseline-acceptance-diagnosis/b0-design.md)
- [Impact Handshake index](handshakes/README.md)
- [Evidence index](evidence/README.md)
- [Execution-log policy](execution/README.md)
