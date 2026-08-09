# Vertical 01 — Foundation, Clustering, Forecasting

## Objective & Hypothesis

Build the shared preparation/evaluation facts needed for trustworthy unsupervised and temporal workflows, then deliver useful clustering and native forecasting through the existing ML task lifecycle.

Hypothesis: improving evaluation, split semantics, and grounded outputs produces more business value than adding more clustering algorithms, while forecasting needs a first-class family rather than reuse of random-holdout regression.

## Status

`solidify`; sequence accepted, exact product scope and handshakes pending.

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

- Cross-cut 00 `IH-B0` must qualify `grouped-preparation-v1`, `cluster-selection-v1`, and `forecast-validation-v1` and record a comparable baseline.
- Shared result/evaluation and role contracts must stabilize before Vertical 02 production integration.

## Durable Owners / Blast Radius

Likely owners include analysis profile/data preparation services, ML types/contracts/evaluation/registry, base model execution, clustering, a new forecasting service, ML lifecycle/finalization, Agent Tool projection, public-boundary tests, and product/unit contracts where behavior changes.

Shared hotspot edits are serialized through the integration lane in [Working set](../../working-set.md).

## Candidate State Diff

- `From`: generic preparation can be fitted before a split; clustering returns assignments/counts with weak quality evidence; DBSCAN appears reusable; forecasting has no native workflow.
- `To`: split-aware preparation and bounded evidence support a defensible clustering workflow and a native temporal workflow with honest validation and registered outputs.

This is not yet an approved Impact Handshake.

## Invariants

- Source Dataset immutability and local authority remain unchanged.
- Holdout/future observations never influence fitted preprocessing or candidate training.
- Cluster IDs are product-consistent but evaluation remains permutation-invariant.
- Models without `predict` are never advertised as reusable apply analyzers.
- Forecast output is a derived Dataset plus user-openable Artifact; evaluation and future forecast scopes remain distinct.

## Decisions Consumed

`D-002` through `D-007`; proposed `P-002` remains open.

## Cases Consumed

`grouped-preparation-v1`, `cluster-selection-v1`, `forecast-validation-v1`, and selected preparation behavior from `clean-orders-v1`.

## Verification Plan

- Direct public-boundary integration tests for prepare/split, clustering fit/evidence/apply contract, and forecasting fit/evaluate/future apply.
- Deterministic Dataset/Artifact, lineage, metric, ordering, and leakage assertions.
- Corresponding independently owned paid live headless/headed Agent benchmark after service tests pass through development/CI order only.
- Full repository gates from [Verification architecture](../../verification.md).

## Current Evidence

- Five tabular clustering implementations exist, but quality/stability/profile evidence is absent or weak.
- Generic regression currently uses random holdout and cannot serve as a forecasting contract.
- A bounded analysis-profile service exists but is not Agent-facing.
- Representative private clustering and forecasting scripts run under the current environment; exact evaluator results remain private.

## Next Action

Resolve `O-004`, then draft separate `IH-F` and `IH-CF` after `IH-B0` establishes qualified cases and baseline evidence.
