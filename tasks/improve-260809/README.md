# Improve ML Capability — Program Dashboard

**Status:** Active. Vertical 01 is committed and verified. Vertical 02 implementation and objective verification are complete; its first completed explicit-privacy topic characterization reproduced final-answer grounding and path-privacy failures.
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

- `pdm run test -q`: 136 passed on 2026-08-10.
- Provider-free B0 infrastructure/policy/calibration checks: 30 passed.
- Headless Agent Harness collect-only: 13 live cases.
- Headed Agent Harness collect-only: the same 13 live cases.
- An explicit live case selector collects exactly one cell in either mode.
- `pdm run check` and isolated-runtime `pdm run smoke` pass.
- `pdm run package` passes. A waited frozen `xenix.exe --smoke-test` exits 0 after recommendation, classification, text-discovery/retrieval, forecast, and non-OCR Knowledge smoke complete. The first RT-T2 frozen run exposed and fixed Joblib CPU discovery under a Windows GUI executable. Official `pdm run smoke-package` remains blocked before app launch because the locked OCR golden image is absent.
- One live `ml.cleaning_service_tickets` characterization passed on `kimi/kimi-k2.6`: semantic pass, integrity pass, 8 rounds, 69,863 reported tokens, 102.266 seconds.
- The final clustering sample produced the exact k=3 assignment/report, a grounded final answer, and passed every deterministic semantic/integrity check in 10 rounds and 165,231 tokens; its same-model Judge failed at the provider and exposed a now-fixed semantic/Judge channel coupling.
- One live `ml.forecast_validation_v1` improvement sample passed semantic and integrity checks on `kimi/kimi-k2.6`: 11 rounds, 191,102 reported tokens, 127.877 seconds; Judge is explicitly `not_configured`, so the result is characterization rather than formal evidence.
- One live `ml.recommendation_ranking_v1` sample passed semantic and integrity checks on `kimi/kimi-k2.6`: 7 rounds, 104,201 reported tokens, 94.896 seconds; Judge is `not_configured`.
- One live `ml.text_grouped_classification_v1` sample passed semantic and integrity checks on `kimi/kimi-k2.6`: 8 rounds, 154,981 reported tokens, 122.900 seconds; Judge is `not_configured`.
- `ml.text_topic_discovery_v1` is service-qualified and collects exactly one cell. Its paid diagnosis proved the complete FIT/EVALUATE/APPLY outcome and exposed Skill-scope/profile plus final-answer privacy gaps. Post-fix run `d7ecbdf02fce4f899970818c341f1a10` completed without a provider/network failure, but failed bounded final-answer grounding and Windows-path privacy checks.

## Current Truth

- The agreed program has two product verticals and one first cross-cut:
  - Cross-cut 00: baseline, acceptance, diagnosis, and exact optimization of the failing layer;
  - Vertical 01: foundation + trustworthy clustering + first-class forecasting;
  - Vertical 02: recommendation ranking + text-pipeline quality.
- Cross-cut 00 starts before product implementation, brackets both verticals, and continues after them. It is not a third product vertical or a final cleanup phase.
- Clustering has recomputable trustworthiness evidence and honest apply capability; native seasonal-naive, Holt-Winters, and bounded-auto SARIMA share chronological comparison, interval, lineage, and future-apply contracts. Recommendation has personalized explicit-rating Top-K with same-truth popularity comparison. Active text classification, clustering, topic discovery, and exact local retrieval retain multilingual raw-text preparation and task-specific evidence; retrieval metrics are truth-gated and exact retrieval fails before dispatch above 2,000 source rows.
- The ordinary test portfolio now covers bounded profile/cleaning, group-safe supervised lifecycles, clustering trustworthiness/apply, native forecast evaluation/future apply, personalized recommendation, multilingual raw-text classification, and text discovery/retrieval through public service boundaries without asserting implementation internals.
- The live benchmark catalog now has thirteen outcome-oriented cases: the eight-case B0 base plus independently owned clustering-selection, forecast-validation, recommendation-ranking, grouped-classification, and topic-discovery cases. It retains one pinned subject model, hard cell/invocation safety boundaries, and a separate versioned acceptance policy. Semantic failure remains a valid measurement rather than a pytest infrastructure failure.
- RT-T2 diagnosis made Skill activation an executable progressive-disclosure gate. Inactive tasks see only Skill activation and Knowledge lookup; an activated modeling Skill receives `analysis.profile` plus its atomic modeling Tools. Unknown Skill state fails closed.
- The supplied corpus is rich enough to qualify cleaning, leakage-safe preparation, clustering, recommendation, forecasting, and bilingual text risks, but it contains severe answer contamination and unresolved redistribution rights. The RT material plan binds ten logical ch14/ch16 sets and explicitly rejects their precomputed recommendations, colocated truth, and template-contaminated random split as product acceptance oracles.
- Detailed decisions, uncertainties, topology, working sets, and slice status live in the linked packet files rather than this dashboard.

## Next Step

Review the three independent closure plans: first classify the topic final-answer failure through the proposed bounded `IH-O1` diagnostic, then execute private-material service characterization, and only after the resulting state is clean run the formal six-case Agent acceptance cohort. Product mutation remains gated by a later exact optimization handshake.

## Packet Map

- [Packet-local protocol](protocol.md)
- [Program topology and sequence](program-plan.md)
- [Decisions](decisions.md)
- [Open questions](open-questions.md)
- [Verification architecture](verification.md)
- [Working-set and ownership map](working-set.md)
- [Case catalog](cases/catalog.md)
- [Materials adoption index](materials/README.md)
- [Vertical 01 — Foundation, clustering, forecasting](workstreams/01-foundation-clustering-forecasting/packet.md)
- [Vertical 02 — Recommendation and text](workstreams/02-recommendation-text/packet.md)
- [Cross-cut 00 — Baseline, acceptance, diagnosis](crosscuts/00-baseline-acceptance-diagnosis/packet.md)
- [B0 solution proposal](crosscuts/00-baseline-acceptance-diagnosis/b0-design.md)
- [Impact Handshake index](handshakes/README.md)
- [Independent implementation-plan index](implementation/README.md)
- [Evidence index](evidence/README.md)
- [Execution-log policy](execution/README.md)
