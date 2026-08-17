# Vertical 01 — Foundation, Clustering, Forecasting

## Objective & Hypothesis

Build the shared preparation/evaluation facts needed for trustworthy unsupervised and temporal workflows, then deliver useful clustering and native forecasting through the existing ML task lifecycle.

Hypothesis: improving evaluation, split semantics, and grounded outputs produces more business value than adding more clustering algorithms, while forecasting needs a first-class family rather than reuse of random-holdout regression.

## Status

`complete`; both Foundation slices, CF-C, and CF-F are implemented and objectively verified. `IH-CF` is consumed and bounded paid characterization/diagnosis is recorded in the [CF execution record](../../execution/CF-2026-08-09.md).

## Scope and Non-Goals

In scope:

- bounded typed data profile exposed to the Agent;
- bounded ML quality facts and Dataset/Artifact IDs for final-answer grounding;
- split-aware preprocessing semantics and reusable preparation where future apply requires it;
- cluster quality, stability, sizes, original-scale profiles, label consistency, and honest apply capability;
- native univariate seasonal forecasting with optional independent groups, chronological validation, horizon, point output, intervals, and forecast metrics.

Non-goals for the first pass:

- another clustering-algorithm showcase;
- exogenous, hierarchical, probabilistic/deep forecasting;
- a universal preprocessing DSL before a concrete apply workflow requires it;
- broad Agent orchestration changes without Cross-cut 00 evidence.

## Dependencies

- Cross-cut 00 B0 Agent Harness infrastructure is offline-verified. Matching paid live cases run only after their independently owned service selectors are green; no paid baseline is a prerequisite for foundation service implementation.
- Shared result/evaluation and role contracts must stabilize before Vertical 02 production integration.

## Durable Owners / Blast Radius

Likely owners include analysis profile/data preparation services, ML types/contracts/evaluation/registry, base model execution, clustering, a new forecasting service, ML lifecycle/finalization, Agent Tool projection, public-boundary tests, and product/unit contracts where behavior changes.

Shared hotspot edits are serialized through the integration lane in [Working set](../../working-set.md).

## Candidate State Diff

- `From`: generic preparation can be fitted before a split; clustering returns assignments/counts with weak quality evidence; DBSCAN appears reusable; forecasting has no native workflow.
- `To`: split-aware preparation and bounded evidence support a defensible clustering workflow and a native temporal workflow with honest validation and registered outputs.

This state diff is approved by [IH-CF](../../handshakes/IH-CF.md); implementation must remain inside its parameter, privacy, comparison, and acceptance boundaries.

## Invariants

- Source Dataset immutability and local authority remain unchanged.
- Holdout/future observations never influence fitted preprocessing or candidate training.
- Cluster IDs are product-consistent but evaluation remains permutation-invariant.
- Models without `predict` are never advertised as reusable apply analyzers.
- Forecast output is a derived Dataset plus user-openable Artifact; evaluation and future forecast scopes remain distinct.

## Decisions Consumed

`D-002` through `D-014`; `P-002` is superseded where it proposed deferring SARIMA.

## Cases Consumed

`grouped-preparation-v1`, `cluster-selection-v1`, `forecast-validation-v1`, and selected preparation behavior from `clean-orders-v1`.

## Verification Plan

- Direct public-boundary integration tests for prepare/split, clustering fit/evidence/apply contract, and forecasting fit/evaluate/future apply.
- Deterministic Dataset/Artifact, lineage, metric, ordering, and leakage assertions.
- Corresponding independently owned paid live headless/headed Agent benchmark after service tests pass through development/CI order only.
- Full repository gates from [Verification architecture](../../verification.md).

## Current Evidence

- Grouped supervised training binds immutable Dataset content, keeps groups disjoint, fits learned preparation on the outer train split, compares a same-holdout baseline, and preserves true apply lineage.
- Clustering publishes recomputable quality/stability/null/profile evidence, retained display labels, honest apply capability, and Dataset/Artifact lineage; the final live sample passed every deterministic semantic and integrity check.
- Seasonal-naive, Holt-Winters, and bounded-auto SARIMA now use one chronological evaluation/interval contract and retained full-history future apply; the final live forecast sample passed semantic and integrity checks.
- Full ordinary/check/smoke/package gates pass for the changed capability. Official whole-app packaged smoke remains blocked only by the separately recorded missing OCR golden image; waited frozen forecast smoke exits 0.
- Repeated focused queries, failed Tool calls, and the discovered semantic/Judge channel coupling produced bounded cross-cut evidence; the coupling is fixed, while query efficiency remains a later optimization lead.

## Next Action

Treat this vertical and the [CF execution record](../../execution/CF-2026-08-09.md) as stable predecessors. Return to solution design for [Vertical 02 — recommendation and text](../02-recommendation-text/packet.md); do not widen CF with formal repeated/headed evidence until an independent calibrated Judge is available or program-level manual acceptance begins.
