# Vertical 02 — Recommendation and Text

## Objective & Hypothesis

Turn the existing recommendation and text implementations into evaluated, reusable business workflows after the shared preparation/result contracts from Vertical 01 are stable.

Hypothesis: user-level ranking, cold-start behavior, leakage-aware multilingual preparation, and task-specific evaluation matter more than adding advanced recommenders or text infrastructure in v1.

## Status

`explore / solidify`; ordering accepted, exact scope pending.

## Scope and Non-Goals

In scope:

- popularity/cold-start baseline and personalized collaborative user Top-K;
- seen-item exclusion, ranking metrics, coverage, and bounded diversity/novelty evidence;
- language-aware normalization, configurable stopwords/custom dictionary, tokenization quality report, duplicate/template leakage checks, and reusable vectorizer/model bundles;
- appropriate evidence for classification, clustering, topics, and similarity rather than count-only summaries.

Non-goals for the first pass:

- offline metrics presented as online causal uplift;
- matrix factorization/hybrid before ranking evaluation and apply are proven;
- vector database/ANN before scale evidence shows the current approach is inadequate;
- heuristic sentiment, summarization, or information extraction without a defensible contract;
- naïve random-split classification acceptance on the contaminated ch16 templates.

## Dependencies

- Cross-cut 00 B0 qualification for recommendation and safe text cases.
- Vertical 01 shared result/evaluation and split-aware preprocessing contracts.

## Durable Owners / Blast Radius

Likely owners include recommendation/text model services, tokenization/preparation, ML registry/contracts/evaluation, lifecycle/finalization, Agent Tool projection, public-boundary tests, and relevant product/unit contracts.

## Candidate State Diff

- `From`: one item-similarity recommender and several text analyzers with count-only or weak evaluation.
- `To`: evaluated user-level ranking with cold-start and seen-item rules, plus leakage-aware multilingual text workflows that produce bounded quality evidence and reusable outputs.

This is not yet an approved Impact Handshake.

## Invariants

- Recommendation results are per user, bounded Top-K, and exclude admitted seen interactions.
- Evaluator truth is never visible to the subject.
- A/B evidence is reported as observed experiment data only when design supports it; offline quality does not claim online uplift.
- Text normalization/tokenization is fitted/configured once and reused on apply.
- Duplicate/template groups cannot cross evaluation splits.

## Decisions Consumed

`D-002` through `D-007`; proposed `P-003` and `P-004` remain open.

## Cases Consumed

`recommendation-ranking-v1`, `bilingual-text-preparation-v1`, and a future safe text topic/grouped-template derivative.

## Verification Plan

- Direct public-boundary integration tests for ranking/evaluation/apply and text prepare/train/evaluate/apply contracts.
- Exact schema/integrity checks plus tolerance-bound numeric metrics.
- Independently owned paid live Agent cases only after matching service tests pass through development/CI order; the runner does not read those results.
- Baseline/after/ablation comparison for quality, latency, Tool calls, tokens, and cost.

## Current Evidence

- Existing recommendation is item-to-item Euclidean similarity over explicit ratings; it lacks personalized ranking evaluation and cold start.
- Text classification, clustering, topics, and similarity exist, but raw Chinese needs a separate tokenize step and non-classification quality is weak.
- The supplied classification split is template-contaminated; bilingual preprocessing is the safer deterministic first service case.

## Next Action

Confirm `O-005` and the safe text live-case shape, then draft `IH-RT` after Vertical 01 shared contracts are stable.
