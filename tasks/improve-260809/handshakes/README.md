# Impact Handshake Index

The first handshake has been consumed for implementation. Later product behavior and service-test work still requires its own reviewed handshake.

| ID | Intended scope | Status |
| --- | --- | --- |
| [`IH-B0`](IH-B0.md) — B0 Agent Harness baseline, acceptance, and diagnosis infrastructure | Independent Agent benchmark assets, single-model live safety, Judge calibration, Agent-report policy, and guidance/CI ordering; no `tests/` service cases or `src/xenix` product behavior change | consumed and offline-verified 2026-08-09; one F1 live characterization recorded |
| [`IH-F1`](IH-F1.md) — Dataset profile and cleaning evidence | Bounded Dataset-ID profile facts, progressive disclosure, whole-Dataset cleaning scope, and a clean-room service case | consumed; implementation/service acceptance complete and live characterization passed 2026-08-09 |
| [`IH-F2`](IH-F2.md) — Group-safe preparation, evaluation, and lifecycle facts | Immutable binding identity, group-disjoint preparation/evaluation, baseline comparison, true apply lineage, and bounded Agent results | consumed; implementation/service acceptance complete 2026-08-09; packaged-smoke exception recorded |
| [`IH-CF`](IH-CF.md) — Trustworthy clustering and native forecasting | Clustering quality/stability/profile/apply truth plus seasonal-naive, Holt-Winters, and bounded-auto SARIMA temporal workflows | consumed; both plans objectively verified and paid characterization recorded 2026-08-09 |
| [`IH-RT`](IH-RT.md) — Recommendation ranking and text quality workflows | Personalized explicit-rating Top-K, multilingual raw-text preparation, grouped classification, text discovery/retrieval evidence, public outputs, and independent service/Agent cases | consumed; all three plans implemented and objectively verified 2026-08-10; topic final-answer outcome remains open |
| [`IH-O1`](IH-O1-topic-final-answer-diagnosis.md) — bounded topic final-answer provenance diagnosis | Classify the observed path category and missing-grounding outcome without retaining private values or changing product behavior | consumed and completed: evaluator false positive fixed, final-synthesis divergence confirmed by paid evidence |
| [`IH-O2`](IH-O2-topic-final-answer-delivery-audit.md) — topic final-answer delivery audit | Consolidate the existing multilingual topic delivery requirements at their canonical Skill boundary without changing Tools or services | consumed; implementation verified and paid-characterized, outcome not reliably closed |
| [`IH-O3`](IH-O3-topic-apply-delivery-projection.md) — topic Apply delivery projection | Test whether bounded authoritative topic evidence beside completed Apply closes the final-synthesis gap | consumed experiment rejected and rolled back after no-improvement paid evidence; paid outcome not closed |
| [`IH-A2`](IH-A2-harness-readiness.md) — formal Agent Harness readiness | Correct formal invocation topology and add strict exact-rubric calibration manifests without changing cases, providers, or budgets | consumed and provider-free verified 2026-08-10 |
| `IH-O<n>` | One exact preprocessing/Skill/Tool/orchestration/observability optimization | evidence-triggered only; product mutation follows a reproduced first divergence and a separate exact handshake |

Each detailed handshake must contain:

- Address and Object: exact files, anchors, or symbols;
- State Diff: objective `From -> To`;
- Blast Radius: downstream consumers and surfaces;
- Invariants: behavior and authority that remain unchanged;
- Verification: focused and repository-wide proof;
- prerequisite Evidence IDs;
- status: `proposed`, `approved`, `consumed`, or `superseded`;
- return-to-discussion triggers.

Detailed execution order belongs in a separate file under [`implementation/`](../implementation/README.md). A handshake authorizes a state diff; an implementation plan owns the working set and coherent passes; `execution/` records completed runs.

The dashboard links to the handshake; it must not copy the detailed authorization and create a second owner.
