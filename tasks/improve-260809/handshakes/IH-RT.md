# Impact Handshake RT — Recommendation Ranking and Trustworthy Text

**Status:** Consumed on 2026-08-10; RT-R, RT-T1, and RT-T2 are implemented and objectively verified. Further product mutation requires a new exact handshake.
**Implementation plans:** [RT-R — recommendation ranking](../implementation/RT-R-recommendation-ranking.md), [RT-T1 — multilingual preparation and grouped classification](../implementation/RT-T1-text-preparation-classification.md), and [RT-T2 — text discovery and retrieval](../implementation/RT-T2-text-discovery-retrieval.md).

## Evidence Consumed

- Vertical 01 now supplies immutable Dataset snapshots, task-specific split/preparation facts, candidate/baseline comparison, evaluation/apply training scopes, real Dataset/Artifact finalization, and bounded Agent projection.
- The current `recommendation.item_similarity` produces a global item-to-item lookup table. It has no user-level Top-K, ranking Evaluate task, seen-item exclusion, cold-user fallback, or recommendation service integration tests.
- Text classification already uses group-safe split and train-only TF-IDF, but the tokenizer configuration is not retained with the analyzer. Text clustering, topic modeling, and similarity retrieval advertise fit/apply while exposing only count-like training summaries and no authoritative evaluation.
- The current text Agent case proves deterministic token frequency, not classification, topic quality, clustering quality, or retrieval relevance.
- Supplied recommendation evaluation files colocate precomputed outputs/truth, while supplied text classification rows are strongly template-contaminated. They are private evaluator evidence only and cannot become committed fixtures or subject-visible answers.

## Address and Object

This consumed handshake changed only the following product objects:

- recommendation ranking contracts, split/preparation/evaluation, retained analyzer, lifecycle, public Dataset/Artifact output, Agent projection, Skill guidance, and independently owned service/Agent cases;
- multilingual raw-text preparation, template/business-group leakage control, classification, text clustering, topic modeling, similarity retrieval, lifecycle, bounded term projection, packaging smoke, and independently owned service/Agent cases;
- shared ML taxonomy/result-contract/finalization seams only where the three implementation plans require them;
- task-local material adoption, evidence, and execution records.

It does not authorize matrix factorization, hybrid ranking, embeddings/ANN, sentiment, summarization, extraction, open-ended tuning, a new Agent Tool name, corpus publication, or formal repeated/headed acceptance.

## Proposed Product Decisions

Sir is asked to confirm this decision set as a unit:

1. **Recommendation v1:** explicit ratings only; a new personalized collaborative user Top-K analyzer with a same-holdout popularity baseline and deterministic popularity fallback for cold users. Matrix factorization/hybrid and implicit-feedback semantics remain later work.
2. **Recommendation truth:** the Agent supplies a bounded, business-interpretable positive-rating threshold after profiling the rating scale. An optional time role selects latest-positive-per-user holdout; without time, an explicitly recorded deterministic per-user positive holdout is used. There is no silent fallback between policies.
3. **Recommendation compatibility:** add a new active model key rather than changing the persisted semantics of `recommendation.item_similarity`. Cold users are supported; cold items are explicitly unsupported in v1.
4. **Raw text analyzers:** active text analyzers accept raw text and retain their exact preparation specification for apply. `data.tokenize` remains the atomic derived-data path for token rows, frequencies, and explicit inspection.
5. **Text explanation/privacy:** finite sanitized top terms may enter Provider context only as purpose-required, bounded evaluation facts. Full text, matched text, vocabulary, template values, and index rows remain local Dataset/Artifact content.
6. **Retrieval truth:** similarity retrieval is `relevance_evaluated` only with an admitted relevance-group role/truth. Without it, the result is `index_diagnostic`; it may be applied but cannot claim semantic relevance quality.
7. **Advertised text scope:** classification, clustering, topic modeling, and similarity retrieval all receive honest service contracts in this handshake. Existing persisted-key semantics are never silently changed; active raw-text replacements and legacy compatibility are explicit in registry metadata.

## Product State Diff

### Recommendation

- **From:** global `base_item → similar item` rows, count summary, item-input apply, no evaluation.
- **To:** `user → bounded unseen Top-K` rows with `rank`, `score`, and `strategy`; domain-specific per-user holdout; same-truth popularity baseline; NDCG/Recall/HitRate/MRR plus bounded coverage/novelty/diversity; hard zero seen-item violations; known-user personalization; cold-user popularity fallback; public evaluation/apply Artifacts and real lineage.

Recommendation evaluation cannot reuse F2 `SplitFacts`: the same eligible user must contribute training history and held-out truth. It receives independent `RecommendationSplitFacts`, `RecommendationPreparationFacts`, `RecommendationRankingMetrics`, `RecommendationColdStartFacts`, and `RecommendationEvaluationFacts` in a deep recommendation evidence module.

### Text preparation and classification

- **From:** fixed `zh_business_v1` derived tokenization and manually repeated pre-tokenized model input.
- **To:** a versioned multilingual preparation specification with bounded custom dictionary/stopword Dataset references, quality/leakage facts, stable digest, and retained train/apply identity. Classification combines business-group and service-owned template/duplicate constraints, fits vocabulary/IDF only on the outer training side, compares the same-holdout dummy baseline, and applies directly to raw text.

Word/token frequency remains descriptive data analysis. It is never relabeled as learned keyword importance.

### Text discovery and retrieval

- **From:** count-only text clustering/topic/similarity training summaries and no Evaluate task.
- **To:** task-specific typed evaluation and public reports:
  - clustering: cosine quality, sizes, resampling stability, degeneracy, stable labels, sanitized top terms;
  - topic modeling: held-out perplexity, bounded coherence/diversity, resampling stability, topic prevalence, sanitized top terms;
  - retrieval: Top-K rank/uniqueness/self-exclusion and relevance metrics when truth exists, otherwise explicit index diagnostics.

Topic modeling receives a text-analyzer task kind and similarity receives a retriever task kind. Fit/apply Dataset materialization follows the declared result contract, not an incidental task-kind check.

## Parameter Authority

Parameter breadth follows `D-015`: expose useful shallow choices, but project them progressively through the existing family/model metadata path rather than one global union schema. Each field is typed, bounded, independently validatable, documented with a versioned default, and visible only for the relevant analyzer. This gives the Agent room to act without spending context on unrelated models or inviting it to invent solver internals.

Agent-authored, typed, bounded parameters may include:

- recommendation `top_k`, minimum interaction support, positive-rating threshold, and the presence of an optional time role;
- text raw column, target/business group/document/relevance-group roles;
- multilingual preparation profile, unigram versus short-phrase mode, registered custom dictionary/stopword Dataset IDs;
- cluster/topic candidate count, bounded displayed term count, retrieval `top_k` and minimum similarity.

Versioned service policy owns:

- recommendation holdout membership, candidate generation, similarity/shrinkage, popularity formula, tie-breaks, seeds, and metric formulas;
- Unicode/case/number/URL/email normalization, tokenizer implementation, template fingerprint/threshold, union of business/template groups, vocabulary/IDF fit scope;
- estimator initialization, solver/iterations, stability resampling, topic matching, evaluation folds, fail-closed admission, and runtime budgets.

No Agent parameter may expose raw estimator internals, create open search, weaken split isolation, alter shared comparison truth, or make evidence unbounded.

## Compatibility and Privacy Invariants

- Existing trained analyzer artifacts remain applicable under the service/key semantics that created them.
- Source Dataset bytes remain unchanged; all outputs are derived registered Datasets/Artifacts.
- Recommendation evaluator truth, held-out interactions, user/item values, and ranking rows never enter bounded Agent reports.
- Known-user outputs exclude every admitted seen item. One violation fails integrity regardless of average metrics.
- Text vocabulary and learned preparation fit only on the appropriate training side. Business/template groups have zero cross-split overlap.
- Bounded top terms reject/truncate identifiers, URLs, email-like strings, long numeric tokens, and excessive cardinality; full text is never Provider evidence by default.
- Offline metrics never claim online causal uplift, topic truth, or semantic relevance without admitted truth.

## Acceptance Boundary

- Each implementation plan passes its own ordinary service selectors before its independent paid Agent case is dispatched by development/CI order.
- Full `pdm run test`, `pdm run check`, isolated smoke, package, and targeted frozen recommendation/text smoke pass; the unrelated OCR prerequisite remains separately recorded if still present.
- Service/Agent fixtures and helpers remain physically independent. Private material and answers never cross either executable boundary.
- New headless characterization cases are independently owned:
  - `ml.recommendation_ranking_v1`;
  - `ml.text_grouped_classification_v1`;
  - `ml.text_topic_discovery_v1`.
- Similarity retrieval receives service acceptance in RT-T2; a paid live case waits for an independently accepted business scenario rather than using a truth-free demo.
- Every paid cell uses one pinned real model and existing B0 hard limits. Formal `3 × headless + 1 × headed` remains later program evidence with an independent calibrated Judge.

## Return to Discussion

Return before implementation if Sir rejects any proposed product decision above, or if implementation would require implicit feedback, cold-item recommendation, matrix factorization/hybrid, embeddings/ANN, automatic semantic labels, user-authored template thresholds, raw text/identifier projection, a new Tool name, or migration that can no longer apply an existing trained artifact.
