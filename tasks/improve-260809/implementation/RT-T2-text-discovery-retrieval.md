# RT-T2 Implementation Plan — Text Discovery and Retrieval Evidence

**Status:** Proposed; awaits approval of [IH-RT](../handshakes/IH-RT.md) and completion of RT-T1 preparation contracts.

## Outcome

Xenix makes its advertised text clustering, topic modeling, and similarity retrieval honest: each retains the raw-text preparation spec, exposes task-appropriate evaluation or an explicit no-truth diagnostic state, applies to new raw text, and delivers bounded interpretable facts plus local public Datasets/Artifacts.

## Working Set

- raw-text clustering/topic/retrieval adapters and a deep typed text evidence module;
- ML task/evaluation taxonomy, result-contract-driven Dataset materialization, lifecycle/metadata/registry compatibility;
- bounded Agent query projection and Modeling Skill/reference;
- independent service fixtures/tests, a separate topic Agent fixture/case, and frozen package smoke;
- [RT material adoption](../materials/rt-on-demand-adoption.md), evidence, and execution record.

## Coherent Passes

1. Add typed `TextClusteringEvaluationFacts`, `TextTopicEvaluationFacts`, `TextRetrievalEvaluationFacts`, common preparation/leakage facts, and task kinds for text analyzer/retriever. Do not force all three into count-only `SUMMARY`.
2. Clustering: fit train-side TF-IDF, compute cosine silhouette, sizes, degeneracy and resampling stability, retain a stable display-label map, sanitize bounded top terms, and support raw-text apply.
3. Topic modeling: use a train/held-out document contract, compute held-out perplexity plus bounded coherence/diversity/prevalence/stability, match topics permutation-invariantly, sanitize top terms, retain the all-admitted apply analyzer, and output document topic distributions.
4. Retrieval: retain a local TF-IDF index with stable document IDs, exclude self, produce unique ranked Top-K, and report Recall/MRR/NDCG only when relevance truth is bound. Otherwise emit `index_diagnostic` with no fabricated relevance metric.
5. Make fit/apply Dataset materialization follow model result contracts. Project only metrics/counts/digests/statuses/sanitized terms/public IDs to the Agent; full query/matched text and index rows remain local.
6. Project clustering/topic/retrieval parameter schemas separately through existing model metadata, then add independent service/lifecycle/Agent projection/package tests and `ml.text_topic_discovery_v1`. A retrieval paid case waits for a separately accepted relevance-bearing business scenario.

## Independent Service Proof

Use separately authored bilingual discovery fixtures with hidden theme membership owned only by the test, duplicate/template groups, stable document IDs, empty/unseen terms, and a relevance-bearing retrieval twin.

Assert preparation/leakage digests, train/held-out isolation, clustering label permutation/stability/cosine facts, topic permutation/coherence/diversity/perplexity/stability/prevalence facts, sanitized bounded terms, retrieval rank/uniqueness/self-exclusion, relevance-evaluated versus index-diagnostic states, raw-text apply, deterministic digests, Dataset/Artifact output and lineage, legacy apply compatibility, and Provider projection without full text or document IDs.

## Independent Agent Proof

`ml.text_topic_discovery_v1` supplies a separate clean-room bilingual feedback Dataset with evaluator-private themes. The case verifies permutation-invariant topic assignment, public topic/evaluation Artifacts, bounded interpretable terms, raw-text preparation facts, source immutability, isolated state, and a final answer that treats topics as exploratory structure rather than truth.

The existing keyword-frequency case remains independent descriptive evidence. Similarity retrieval remains service-qualified until a truth-bearing live scenario is approved.

## Verification Order

1. text evidence and clustering/topic/retrieval model selectors;
2. lifecycle/result-contract/Agent projection/legacy compatibility selectors;
3. `pdm run test -q`, proof-portfolio review, and `pdm run check`;
4. isolated smoke, package, and targeted frozen text discovery/retrieval smoke;
5. exact-selector offline collection, then one paid topic headless characterization.

## Stop Conditions

Stop for discussion if the implementation needs embeddings/ANN, automatic topic names, relevance claims without truth, provider-generated interpretations as service truth, raw full text in Agent facts, open topic/model search, or semantic changes to existing trained artifacts.
