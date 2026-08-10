# Personalized Recommendation Reference

Use this reference for explicit-rating user-to-item Top-K recommendation. It does not apply to the legacy base-item similarity lookup, implicit clicks/views, matrix factorization, or hybrid/content recommendation.

## Admission

Require one row grain that represents a user-item rating event and bind:

- `user`: stable account/customer/member identity;
- `item`: stable product/content/offer identity;
- `rating`: finite numeric explicit preference where larger means more positive;
- optional `time`: a valid event timestamp used only for latest-positive holdout.

Profile counts, missingness, duplicates, cardinality, and rating range first. If the business meaning of “positive” is unresolved, use one focused aggregation over the rating field or ask the user. Do not infer a five-star scale from a field name.

## Model and parameters

Browse `model_family: "recommendation"`, then inspect `recommendation.collaborative_top_k` directly. Fill only its advertised shallow schema:

- `top_k`: requested list length;
- `min_user_interactions`: minimum history needed for evaluation eligibility;
- `min_item_interactions`: minimum training-side support for a candidate item;
- `positive_rating_threshold`: business-defined positive preference boundary.

Candidate generation, similarity shrinkage, holdout membership, popularity formula, tie-breaks, seeds, and metric formulas remain service policy.

## Evaluation

With a valid `time` role, evaluation holds out each eligible user's latest positive interaction. Without time, it uses a recorded deterministic hash-positive holdout. There is no silent policy switch.

Candidate and popularity baseline must use the same truth and candidate catalog. Interpret:

- NDCG@K: whether relevant held-out items appear near the top;
- Recall@K and HitRate@K: whether the held-out positive is recovered;
- MRR@K: how early the first relevant result appears;
- coverage: how much of the candidate catalog is used;
- novelty/diversity: supporting discovery evidence, not relevance truth;
- short lists: users for whom fewer than K valid unseen candidates exist.

Any seen-item violation invalidates the ranking regardless of average metrics. Require the authoritative Evaluate task and linked report Artifact; never reconstruct evaluation from displayed recommendation rows.

## Apply and cold start

Call `model.apply` with the retained `trained_model_id` and a registered Dataset or inline rows containing exactly the trained user-column name. The local result contains `user_id`, `rank`, `recommended_item`, `score`, and `strategy`.

- known user: personalized collaborative ranking, with deterministic popularity completion when needed;
- cold user: deterministic popularity fallback;
- cold item: unsupported because an unseen item has no retained interaction evidence.

Do not request user/item ranking rows through task-query output. Link the registered result Dataset and Artifact for local review.

## Interpretation boundary

Offline ranking evidence measures recovery under a historical holdout. It does not prove incremental conversion, revenue, satisfaction, fairness, or causal uplift. Recommend a controlled online experiment, guardrail metrics, periodic retraining, coverage/short-list monitoring, and human review where recommendations affect high-risk decisions.
