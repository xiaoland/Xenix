# Text Discovery and Retrieval

These analyzers accept raw bilingual `text` and retain preparation. Optional dictionary and stopword sources are registered one-column Datasets. Use metadata for unfamiliar parameters; standalone tokenization is not a prerequisite.

- `text.clustering.multilingual_kmeans_tfidf` groups related documents. Evaluation describes silhouette, sizes, stability, and representative terms. An optional business `group` identifies repeated entities.
- `text.topic_modeling.multilingual_lda` produces topic distributions. Evaluation describes held-out fit, coherence, diversity, prevalence, and stability. Topic numbers identify components within the retained analyzer; descriptive names are interpretations of their terms, not observed labels.
- `text.similarity.multilingual_tfidf_cosine` returns ranked matches. Optional `document_id` identifies documents. `relevance_group` supplies genuine relevance truth when available; only relevance-evaluated results support Recall, MRR, or NDCG. Exact retrieval supports at most 2,000 source rows.

Use completed evaluation facts and public assignment, distribution, or match outputs directly. Services maintain identity and split consistency; additional digest checks are not an Agent workflow. Read result values when the user's interpretation requires them. Explain that clustering and topics are exploratory and retrieval metrics depend on the supplied relevance definition.
