# RT-R Implementation Plan — Personalized Recommendation Ranking

**Status:** Proposed; awaits approval of [IH-RT](../handshakes/IH-RT.md).

## Outcome

Xenix can evaluate and retain a personalized explicit-rating Top-K analyzer, compare it with a same-truth popularity baseline, exclude seen items, serve cold users through a deterministic popularity fallback, and deliver per-user recommendations as a public Dataset/Artifact without exposing ranking rows to the Provider.

## Working Set

- recommendation model plus a new deep recommendation evidence/preparation module;
- ML problem/evaluation taxonomy, task/result contracts, default ranking policy, registry, lifecycle finalization, and trained metadata;
- Agent role/parameter schemas, bounded task projection, Modeling Skill/reference;
- independent service fixtures/tests and an independently authored Agent fixture/case;
- [RT material adoption](../materials/rt-on-demand-adoption.md), task evidence, and execution record.

Do not load text implementation symbols while changing recommendation internals. Shared contract/finalizer/Agent projection changes are serialized before RT-T1 begins.

## Coherent Passes

1. Add active `recommendation.collaborative_top_k`, `ProblemKind.RECOMMENDATION`, `EvaluationKind.RANKING`, user/item/rating/optional-time train roles, and user-only apply role. Preserve legacy item-similarity artifact semantics.
2. Implement explicit-rating admission, deterministic latest-positive or hash-positive per-user holdout, interaction/candidate digests, duplicate aggregation, support filtering, and same-split popularity truth.
3. Implement retained item-neighborhood collaborative scoring, stable tie-breaks, known-user seen exclusion, cold-user fallback, and cold-item unsupported facts. Refit the apply analyzer on all admitted interactions without attaching holdout claims to it.
4. Produce typed NDCG@K/Recall@K/HitRate@K/MRR@K, coverage, novelty, bounded intra-list diversity, short-list, and zero seen-violation facts; write a public evaluation report and bounded Agent projection.
5. Materialize fit recommendations for eligible users and apply recommendations for a user-list Dataset through declared result contracts. Preserve apply Dataset lineage and training-analyzer identity; never project user/item values or rows.
6. Project only recommendation-relevant shallow parameter schemas through existing model metadata, extend Modeling Skill with rating-threshold/time-policy/cold-user/offline-evidence guidance, then add independent service, Agent projection, package smoke, and paid Agent cases.

## Independent Service Proof

Use a committed clean-room explicit-rating history with:

- enough known users/items for deterministic personalized ranking;
- one admitted cold user in the apply user list;
- stable rating ties and duplicate user-item ratings;
- optional event time for the chronological policy, plus a no-time twin for the deterministic hash policy;
- private expected holdout/ranking truth owned only by the service test.

Assert exact source immutability, role/threshold admission, split membership digests, train/holdout interaction counts, same candidate catalog and truth for candidate/baseline, independent metric recomputation at `1e-6`, zero seen violations, rank continuity/uniqueness/K bounds, deterministic tie-breaks, ranking digest replay, known-user results, cold-user popularity fallback, cold-item limitation, evaluation/apply training scopes, public Artifact IDs, and real Dataset lineage.

Test the actual `StorageBootstrap → Dataset → binding → MLService FIT → EVALUATE → APPLY → finalizer` path. A unit test of a scoring helper is not acceptance.

## Independent Agent Proof

Create a separate clean-room ratings attachment and target-user attachment for `ml.recommendation_ranking_v1`. The evaluator privately verifies exact seen exclusion, per-user Top-K ordering, cold-user strategy, public Dataset/Artifact linkage, source immutability, isolated runtime, and a final answer grounded in candidate-versus-popularity evidence and the offline-not-online limitation.

The case judges only public final outcomes, not a Tool trace. One bounded headless characterization follows green service/package qualification; formal repeated/headed evidence remains later.

## Verification Order

1. focused ranking evidence/model/service/lifecycle selectors;
2. focused Agent Tool projection and registry/metadata compatibility selectors;
3. `pdm run test -q`, proof-portfolio review, and `pdm run check`;
4. isolated smoke, package, and targeted frozen ranking smoke;
5. exact-selector offline collection, then one paid headless characterization.

## Stop Conditions

Stop for discussion if the implementation needs implicit feedback, cold-item inference, content metadata, hybrid/matrix-factorization ranking, user-authored similarity/search controls, multiple holdout policies in one run, raw ranking rows in Agent context, or an incompatible reinterpretation of the legacy model key.
