# RT-T1 Implementation Plan — Multilingual Preparation and Grouped Classification

**Status:** Implemented and objectively verified; one paid headless characterization passed on 2026-08-10 under [IH-RT](../handshakes/IH-RT.md).

## Outcome

Xenix can inspect and derive bilingual tokens for descriptive analysis, while active classification analyzers accept raw text, retain the exact preparation specification, prevent business/template leakage, fit vocabulary/IDF only on the outer training side, compare a same-holdout baseline, and apply consistently to new raw text.

## Working Set

- data tokenization contracts/service, Dataset/Artifact finalization, Agent `data.tokenize` input/result presentation;
- new deep text preparation/leakage contracts and raw-text classification adapter;
- shared ML taxonomy/contracts/registry/lifecycle/metadata and bounded Agent projection;
- Data Preprocessing and Modeling Skills/references;
- independent bilingual service fixtures/tests and independent grouped-classification Agent assets;
- [RT material adoption](../materials/rt-on-demand-adoption.md), evidence, and execution record.

## Coherent Passes

1. Add a versioned multilingual business preparation profile while preserving `zh_business_v1`. Define deterministic Unicode/case/number/URL/email rules, bounded custom dictionary/stopword Dataset references, preparation digest, and privacy-safe quality facts.
2. Keep `data.tokenize` atomic: it creates a derived token Dataset plus a reusable preparation-spec Artifact and reports source/output/non-empty/token/retention/custom-term/duplicate-template facts without default token values. A later call may reuse the spec Artifact.
3. Introduce an active raw-text classification key without changing existing persisted-key semantics. Retain the preparation spec in evaluation and all-row apply analyzers.
4. Build service-owned exact-duplicate/template constraints and union them with an optional business group. Fit TF-IDF inside outer train only; assert zero business/template overlap and stable apply schema/OOV/empty-text facts.
5. Reuse F2 classification metrics, dummy baseline, comparison, and evaluation/apply training scopes; add typed text preparation/leakage facts and bounded public report/Agent projection.
6. Project only relevant preparation/classification parameter schemas through existing model metadata, then add independent service, Agent projection, package smoke, and `ml.text_grouped_classification_v1` paid case. Preserve the legacy `ml.text_keyword_frequency` case as descriptive workflow evidence.

## Independent Service Proof

Use a committed clean-room bilingual Dataset containing Simplified Chinese, English, NFKC variants, empty text, exact duplicates, repeated templates, business groups, registered custom terms/stopwords, and independently designed labels. Use a separate raw-text apply Dataset with unseen vocabulary and empty text.

Assert source immutability, exact profile/spec/output digests, custom list bounds, quality counts, template/business zero overlap, train-only vocabulary, no label/template columns as features, same-holdout baseline recomputation, evaluation/apply training scopes, raw-text apply consistency, empty/OOV facts, Dataset/Artifact IDs, lineage, legacy artifact compatibility, and bounded Agent projection with no raw text/template values/vocabulary.

## Independent Agent Proof

`ml.text_grouped_classification_v1` uses separately authored training/apply attachments. The evaluator privately checks the exact public predictions, authoritative Evaluate facts, group/template isolation, raw-text apply, Dataset/Artifact linkage, source immutability, and a final answer that distinguishes classification evidence from causal/automatic-decision authority.

The benchmark does not import service fixtures or reports and does not prescribe the Tool trace.

## Verification Order

1. tokenizer/spec and text preparation/leakage selectors;
2. raw classification model/service/lifecycle/Agent projection and legacy compatibility selectors;
3. `pdm run test -q`, proof-portfolio review, and `pdm run check`;
4. isolated smoke, package, and targeted frozen bilingual classification smoke;
5. exact-selector offline collection, then one paid headless characterization.

## Stop Conditions

Stop for discussion if the implementation needs learned/provider-generated stopwords, automatic semantic labels, user-authored template thresholds, raw text/vocabulary projection, embedding models, a new Tool name, or a migration that prevents applying an existing text analyzer.
