# Impact Handshake F2 — Group-Safe Preparation, Evaluation, and Lifecycle Facts

**Status:** Consumed. Implementation and objective service acceptance completed on 2026-08-09; the unrelated OCR packaged-smoke prerequisite exception is recorded separately.
**Implementation plan:** [Foundation 2 — Group-safe preparation, evaluation, and lifecycle facts](../implementation/F2-group-safe-preparation-evaluation.md).
**Execution record:** [Foundation execution — 2026-08-09](../execution/foundations-2026-08-09.md).

## Evidence and Decisions Consumed

- Standard tabular supervised models already split before fitting sklearn Pipelines and refit a canonical apply analyzer on all eligible rows.
- The declared split strategy is not enforced; infeasible stratification silently downgrades while retaining a false claim.
- Role binding has feature/target only and is tied to Dataset/path/schema, not immutable content bytes.
- Evaluation facts are copied by a best-effort callback; apply finalization can claim the training Dataset as the scoring source; Agent projection exposes absolute paths and raw metadata/result payloads.
- Material-derived preparation/evaluation/apply risks support an independently designed grouped lifecycle case.
- `D-002`, `D-003`, `D-005`, `D-006`, `D-008`, `D-011`, `D-012`, and `D-013`.

## Address and Object

Authorized objects are Dataset-binding content identity, optional group-role contracts, actual split/preparation/evaluation facts, group-aware outer/inner splitting for supervised tabular and supervised text classification, same-holdout simple baselines, evaluation authority/reference/report finalization, actual apply-source lineage, bounded Agent ML projections, clean-room fixtures, migrations, and direct tests.

The later time role and forecasting semantics, clustering/recommendation algorithms, a universal preprocessing DSL, UI redesign, and broad Harness changes are outside this handshake.

## State Diff

- **From:** a binding can silently point at changed bytes; only feature/target roles exist; declared split policy can differ from execution; group leakage is unprevented; metrics are copied without a single authority; apply lineage can be false; Agent sees paths/raw payloads.
- **To:** new bindings freeze Dataset content identity; optional groups stay disjoint and out of features; split/preparation/candidate/baseline facts state actual scope; infeasible truthful evaluation fails without fallback; Evaluate task result is authoritative and directly referenced; apply lineage names actual sources; Agent receives only bounded IDs and decision-relevant facts.

## Blast Radius

- Dataset column-binding storage and forward migration;
- supervised catalog roles and worker request/result schemas;
- fit/tune/evaluate/apply finalization;
- trained-model metadata compatibility consumers;
- Agent model Tool schemas, projection, and modeling guidance;
- storage/bootstrap/registry/execution/Tool integration tests;
- shipped worker payload compatibility.

## Invariants

- Existing sklearn Pipeline placement remains; no parallel generic preparation framework is introduced.
- Learned preprocessing for evaluation fits only on outer training rows.
- The canonical apply analyzer may refit on all eligible rows but cannot inherit unsupported holdout claims.
- Group and target values never become features.
- A declared split is never silently replaced by a weaker one.
- Evaluate task results own evaluation facts; metadata copies are compatibility projections only.
- Apply output remains a derived Dataset plus user-openable Artifact and names its real source.
- Worker artifacts and Joblib paths remain local internals and are not provider-visible.
- Service tests and Agent benchmarks remain independent.

## Acceptance

- The focused and repository commands in the implementation plan pass.
- Migration tests prove legacy bindings require rebind and new bindings reject changed bytes.
- The grouped lifecycle case proves group disjointness, train-only preparation, same-holdout baseline comparison, deterministic digests, authoritative evaluation reference/report, unseen-category apply, and true source lineage.
- Agent projection tests prove paths, raw rows, preview rows, full metadata, and raw worker payloads are absent.

## Return to Discussion

Return to design when any stop condition in the implementation plan occurs, especially if temporal semantics, silent legacy backfill, a user-facing split-algorithm menu, a new persistent evaluation entity, or a general lineage graph becomes necessary.
