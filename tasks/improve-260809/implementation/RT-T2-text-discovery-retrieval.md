# RT-T2 Implementation Plan — Text Discovery and Retrieval Evidence

**Status:** Implemented; service, ordinary Agent, offline Harness, app smoke, package, and frozen binary smoke verified. A completed explicit-privacy paid sample reproduced final-answer grounding and Windows-path privacy defects.

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

## Implemented Evidence

- Active raw-text clustering, topic, and exact local retrieval keys retain preparation identity, support raw-text apply, and expose task-specific typed evaluation/apply facts. Legacy tokenized keys remain unchanged.
- Topic evaluation uses connected-group holdout, train-side vocabulary, permutation-matched stability, and one identity digest across Evaluate and Apply. Retrieval is either `relevance_evaluated` or `index_diagnostic`; ranking facts cannot exist in the latter state.
- Independent service acceptance covers all three active FIT → authoritative EVALUATE → APPLY → finalizer lifecycles, truth/no-truth retrieval, fixed result schemas, lineage/privacy, legacy catalog compatibility, and a 2,001-row pre-dispatch rejection.
- Ordinary Agent projection covers the complete topic chain, cluster/retrieval states, stable identities, public Dataset/Artifact lineage, shallow schemas, and Provider privacy. The independent topic Harness case is the thirteenth live case and collects exactly once in either mode.
- Paid diagnosis reproduced a progressive-disclosure mismatch: modeling instructions required `analysis.profile`, but the activated modeling Tool scope omitted it. Inactive Tool disclosure is now Skill-gated, `analysis.profile` is in the modeling scope, and unknown Skill state fails closed.
- The first frozen binary smoke exposed Joblib physical-core discovery failing under a Windows GUI executable. The packaged entry now supplies `LOKY_MAX_CPU_COUNT` only when no operator value exists; the rebuilt binary smoke exits 0.
- The explicit topic final-answer privacy requirement and exact-value oracle are implemented. Run `d7ecbdf02fce4f899970818c341f1a10` completed with integrity pass and budget within limits, proving provider recovery, but failed final-answer grounding for quality metrics, group/template isolation, exploratory/offline limits, and Windows-path privacy. No raw transcript or private value was promoted to this packet; [O1](O1-topic-final-answer-diagnosis.md) owns the next bounded diagnosis.
