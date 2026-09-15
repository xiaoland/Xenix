# Recommendation

`recommendation.collaborative_top_k` supports explicit user-item ratings. Bind `user`, `item`, numeric `rating`, and optionally `time`. Larger ratings mean stronger preference; the positive-rating threshold should reflect the actual scale. `recommendation.item_similarity` instead answers which items resemble a base item.

The shallow parameters include `top_k`, minimum user/item support, and `positive_rating_threshold`. Model metadata supplies exact contracts if needed. Candidate generation and holdout construction are implemented by the service.

Returned evaluation compares the candidate with popularity on the same held-out truth. NDCG and MRR describe ranking quality; Recall and HitRate describe recovery; coverage and short lists explain reach. Use these facts to explain relevant tradeoffs without reconstructing evaluation from displayed rows.

Apply accepts a Dataset or inline rows containing the trained user column. Known users receive personalized unseen candidates where supported; cold users receive popularity fallback. Unseen items lack retained interaction evidence. The result contains user_id, rank, recommended_item, score, and strategy, with public Dataset and Artifact handles.

Deliver the requested rankings and evaluation. Offline recovery of historical preferences does not establish incremental revenue or conversion.
