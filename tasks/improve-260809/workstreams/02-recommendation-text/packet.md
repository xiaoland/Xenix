# Vertical 02 — Recommendation and Text

## Objective & Hypothesis

Turn the existing recommendation and text implementations into evaluated, reusable business workflows after the shared preparation/result contracts from Vertical 01 are stable.

Hypothesis: user-level ranking, cold-start behavior, leakage-aware multilingual preparation, and task-specific evaluation matter more than adding advanced recommenders or text infrastructure in v1.

## Status

`verification`; Sir approved `IH-RT` on 2026-08-10. RT-R, RT-T1, and RT-T2 implementation and objective proof are complete. A completed post-fix paid topic characterization reproduced final-answer grounding and path-privacy defects.

## Scope and Non-Goals

In scope:

- explicit-rating popularity/cold-start baseline and personalized collaborative user Top-K;
- seen-item exclusion, ranking metrics, coverage, and bounded diversity/novelty evidence;
- explicit latest-positive or deterministic-hash holdout policy, reusable per-user apply, and honest cold-item limitations;
- language-aware normalization, bounded stopword/custom-dictionary references, tokenization quality report, duplicate/template leakage checks, and reusable preparation/vectorizer/model bundles;
- appropriate evidence for classification, clustering, topics, and similarity rather than count-only summaries.

Non-goals for the first pass:

- offline metrics presented as online causal uplift;
- implicit-feedback ranking, matrix factorization, and hybrid recommendation before explicit-rating evaluation/apply are proven;
- vector database/ANN before scale evidence shows the current approach is inadequate;
- heuristic sentiment, summarization, or information extraction without a defensible contract;
- naïve random-split classification acceptance on the contaminated ch16 templates.

## Dependencies

- Cross-cut 00 B0 qualification for recommendation and safe text cases.
- Vertical 01 shared result/evaluation and split-aware preprocessing contracts.

## Durable Owners / Blast Radius

Owners are enumerated by [IH-RT](../../handshakes/IH-RT.md) and split across [RT-R](../../implementation/RT-R-recommendation-ranking.md), [RT-T1](../../implementation/RT-T1-text-preparation-classification.md), and [RT-T2](../../implementation/RT-T2-text-discovery-retrieval.md). Shared registry/contracts/lifecycle/Agent projection are serialized integration hotspots; recommendation and text domain modules remain separate working sets.

## Candidate State Diff

- `From`: one item-similarity recommender and several text analyzers with count-only or weak evaluation.
- `To`: evaluated user-level ranking with cold-start and seen-item rules, plus leakage-aware multilingual text workflows that produce bounded quality evidence and reusable outputs.

This state diff is authorized by [IH-RT](../../handshakes/IH-RT.md). New evidence that requires implicit feedback, cold-item recommendation, embeddings/ANN, raw Provider projection, or incompatible artifact semantics returns to discussion.

## Invariants

- Recommendation results are per user, bounded Top-K, and exclude admitted seen interactions.
- Evaluator truth is never visible to the subject.
- A/B evidence is reported as observed experiment data only when design supports it; offline quality does not claim online uplift.
- Text normalization/tokenization is fitted/configured once and reused on apply.
- Duplicate/template groups cannot cross evaluation splits.

## Decisions Consumed

`D-002` through `D-019`; Sir resolved the recommendation/text scope and evidence boundary on 2026-08-10.

## Cases Consumed

`recommendation-ranking-v1`, `bilingual-text-preparation-v1`, `text-grouped-classification-v1`, and `text-topic-discovery-v1`. Similarity retrieval is service-qualified only until relevance-bearing live truth exists.

## Verification Plan

- Direct public-boundary integration tests for ranking/evaluation/apply and text prepare/train/evaluate/apply contracts.
- Exact schema/integrity checks plus tolerance-bound numeric metrics.
- Independently owned paid live Agent cases only after matching service tests pass through development/CI order; the runner does not read those results.
- Baseline/after/ablation comparison for quality, latency, Tool calls, tokens, and cost.

## Current Evidence

- Existing recommendation is a global item-to-item Euclidean lookup over explicit ratings. It lacks user ranking, ranking evaluation, seen exclusion, cold-user behavior, reusable user-list apply, and ordinary service acceptance; changing that persisted key in place would break artifact semantics.
- Recommendation ranking needs a dedicated per-user holdout contract rather than F2 group-disjoint split: one eligible user's train history and held-out truth intentionally coexist. The popularity baseline and candidate must share the exact truth/candidate catalog.
- Existing text classification has group-safe supervised evaluation, but analyzers expect pretokenized text and do not retain an upstream preparation spec. Clustering/topic/similarity advertise fit/apply while exposing count-only or no task-quality evidence.
- The supplied ch14 material has no single independent train → truth → apply closure. Its precomputed Top-10/truth bundle is evaluator-only. The supplied ch16 model data has only 38 analysis texts across 1,500 rows and template-determined labels, so random-split results are leakage evidence, not acceptance truth.
- Ten bounded logical material sets, clean-room correspondence, hashes/shapes, and fail-closed private triggers are recorded in the [RT adoption plan](../../materials/rt-on-demand-adoption.md); no reference script was executed and no private byte is authorized for Provider upload.
- RT-R and RT-T1 each have one passing paid characterization. RT-T2 has complete independent service and ordinary Agent evidence, package/binary smoke, and one exact-selector topic case. Its bounded live diagnosis fixed Skill-gated progressive disclosure and packaged CPU discovery; the later completed sample failed only final-answer grounding and Windows-path privacy checks rather than service, integrity, budget, or provider transport.

## Next Action

Review and, if accepted, execute [O1 topic final-answer diagnosis](../../implementation/O1-topic-final-answer-diagnosis.md). Do not start the formal repetition/Judge series until its exact product optimization, if any, is verified on a clean state.
