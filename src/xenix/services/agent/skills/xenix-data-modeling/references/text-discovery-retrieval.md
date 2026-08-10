# Multilingual Text Discovery and Retrieval Reference

Use this reference for exploratory clustering, topic discovery, and local similarity retrieval over bilingual raw business text. It does not apply to supervised labels, descriptive token frequency, embeddings, ANN search, sentiment, summarization, or automatic topic naming.

## Shared raw-text preparation

Use an active multilingual key and bind the raw `text` column directly. Do not run `data.tokenize` first unless the requested product is an explicit token Dataset or term-frequency analysis. Inspect the selected model's metadata, then fill only its advertised preparation profile, phrase mode, feature bound, task count/Top-K, displayed-term count or minimum similarity, and registered dictionary/stopword Dataset IDs.

The retained specification owns Unicode NFKC/case normalization, URL/email/number masking, bilingual tokenization, n-gram mode, and resource identities. Vocabulary and raw text remain local. Terms in evaluation facts are a small sanitized interpretation surface, not a vocabulary dump or stable business label.

## Clustering

Use `text.clustering.multilingual_kmeans_tfidf`. Bind an optional business `group` when repeated rows belong to one entity. Require cosine silhouette, realized sizes, degeneracy facts, connected-group resampling stability, sanitized top terms, and a stable-label mapping digest. Apply the retained analyzer to raw text and require the same mapping digest. Cluster labels are display identities inside that analyzer, not observed segments or causal explanations.

## Topic discovery

Use `text.topic_modeling.multilingual_lda`. Bind an optional business `group`; Xenix joins it with template constraints before the held-out document split. Require zero connected-group overlap, held-out perplexity, coherence, term diversity, prevalence, permutation-matched stability, and the topic-label identity digest.

The evaluation model fits its vocabulary on the train side. The all-admitted apply model reuses that vocabulary and aligns its components to the evaluation labels. Require the same identity digest in Evaluate and Apply. Topic numbers are permutation-invariant display labels; do not invent semantic topic names unless the user explicitly supplies and validates them.

## Local retrieval

Use `text.similarity.multilingual_tfidf_cosine`. Bind optional unique `document_id` for stable local results. Bind `relevance_group` only when it is genuine relevance truth: membership means documents are relevant to one another for the current business question.

`relevance_evaluated` may report Recall@K, MRR@K, and NDCG@K. `index_diagnostic` intentionally has no relevance metrics. In both modes require unique consecutive ranks, self-exclusion, no duplicate matches, index identity, and result digest. v1 exact retrieval admits at most 2,000 source rows; do not work around that bound or claim ANN-scale behavior.

## Delivery and limits

Use public Dataset and Artifact IDs for assignments, topic distributions, or ranked matches. Do not ask lifecycle Tools to return raw rows, matched text, document IDs, group values, relevance truth, or vocabulary into Provider context. Explain that internal clustering/topic evidence is exploratory and that offline retrieval metrics do not prove causal business lift or permission for automatic decisions.
