# CF-C Implementation Plan — Clustering Trustworthiness

**Status:** Implemented and objectively verified under consumed [IH-CF](../handshakes/IH-CF.md). Paid characterization and diagnosis are recorded in the [CF execution record](../execution/CF-2026-08-09.md).

## Outcome

Existing clustering adapters produce a trustworthy, inspectable segmentation workflow: typed quality/stability/null/size/profile evidence, one assignment Dataset, one public report/profile Artifact, stable within-analyzer labels, and truthful apply capability.

## Working Set

- `src/xenix/services/storage/models.py`, `migrations.py`, artifact/task repositories;
- `src/xenix/services/ml/types.py`, `contracts.py`, `evaluation.py`, `preparation.py`, `registry.py`;
- `src/xenix/services/ml/models/base.py`, `clustering.py`;
- `src/xenix/services/ml_service.py`, `ml_task_service.py`, `trained_model_metadata.py`;
- `src/xenix/services/agent/tool_inputs.py`, `tools.py`, modeling Skill clustering reference;
- focused migration, registry, clustering lifecycle, Artifact, and Agent projection tests;
- new clean-room fixtures under `tests/fixtures/ml_cf_service/`;
- implemented independently owned `ml.cluster_selection_v1` benchmark case/fixture under `benchmarks/agent_harness/`; paid execution still waits for completed service/offline qualification.

Do not edit forecasting, recommendation, text, anomaly, or supplied material files in this plan.

## Passes

1. Add explicit evaluation/apply/apply-mode catalog facts and one public Artifact reference from ML task finalization. Remove Agent-side duplicate output registration.
2. Define typed `ClusteringEvaluationFacts`, stability, null-baseline, size/noise, label-map, profile, limitation, and digest contracts. Use typed unavailable reasons for single-cluster/all-noise/insufficient cases.
3. Extend clustering fit/evaluate with deterministic preprocessing, fixed versioned resampling, original-scale aggregate profiles, and a persisted raw-to-display label mapping.
4. Materialize the fit assignment CSV as a derived Dataset and publish assignment/profile outputs through stable Dataset/Artifact IDs. Enforce true apply capability before dispatch; DBSCAN is non-applicable.
5. Add bounded clustering facts to Agent metadata/task projection and modeling guidance. Under `D-015`, the Agent fills typed shallow candidate parameters while seeds, resampling/null policy, search limits, and solver details stay versioned service policy. Purpose-specific category aggregates are bounded; identifiers and rows remain excluded.
6. Add the independently designed service fixture/cases, run repository/package gates, then execute one separately owned paid clustering characterization.

## Independent Service Proof

Use `segment_quality_v1.csv` with approximately 78 entities: three independently generated segments plus noise, numeric/categorical/missing fields, an excluded entity ID, and no membership truth column. Use a distinct apply fixture with unseen category values.

Assert:

- source immutability and explicit feature exclusion;
- KMeans `k=2/3/4` candidate facts, the qualified `k=3` selection, and a DBSCAN noise case;
- independently recomputable silhouette/Calinski-Harabasz/Davies-Bouldin, five-seed 80% subsample stability, permuted-label null baseline, sizes/proportions/noise, and bounded profile facts;
- permutation-invariant hidden membership comparison, exact/quantized digests, stable within-analyzer labels, noise `-1`;
- assignment Dataset/profile Artifact readiness and IDs without provider-visible paths;
- training re-apply label consistency, unseen-category apply, actual apply-Dataset lineage, and DBSCAN pre-dispatch refusal.

Use `1e-6` numeric tolerance, exact counts/schema/order/capability/digests where defined, and no wall-clock pytest assertion.

## Verification Order

1. focused registry/migration/Artifact/clustering lifecycle/Agent projection selectors;
2. `pdm run test -q` and proof-portfolio architecture review;
3. `pdm run check` and isolated `pdm run smoke`;
4. `pdm run package` plus targeted packaged clustering/apply smoke if worker packaging changed;
5. exactly one paid `ml.cluster_selection_v1` headless characterization with existing B0 limits.

## Stop Conditions

Stop and return to design for semantic cross-run label naming, DBSCAN out-of-sample approximation, entity-level sensitive-value disclosure, partial fit/apply outputs, a generic unsupervised tuning framework broader than the bounded clustering need, or any Agent parameter that is unbounded, opaque, leakage-sensitive, or able to change comparison identity.
