---
name: xenix-data-modeling
description: >-
  Use this skill when the user asks Xenix to predict, classify, regress, score,
  rank, train a model, tune hyperparameters, apply a trained model, estimate
  risk/probability, identify drivers through model output, compare supervised
  models, produce personalized Top-K recommendations from explicit ratings,
  forecast a regular time series, compare seasonal-naive,
  Holt-Winters, and bounded-auto SARIMA, handle partially labeled data, run text classification, text
  clustering, topic modeling, similarity retrieval, or use neural networks as a
  candidate model. Use for Chinese requests such as “预测一下”, “训练模型”,
  “哪些因素影响结果”, “客户流失预测”, “风险评分”, “转化概率”, “调参”, “应用模型”,
  “销量预测”, “需求预测”, “未来几周”, “个性化推荐”, “推荐商品”, “Top-K 推荐”,
  “文本分类”, “主题分析”, “相似检索”, or “半监督”.
  Do not use for pure descriptive profiling, charts, reporting, or association
  analysis unless modeling is explicitly part of the task; use xenix-data-analysis
  for that. Activate xenix-data-preprocessing first when cleaning,
  transformation, or role binding is not ready.
license: MIT
metadata:
  version: "0.10.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Modeling Skill

This skill guides Xenix Agent for modeling workflows over tabular business data: target validation, feature exclusion, role binding, baseline training, constrained tuning, regular-series forecasting, model application, probability scoring, and model-result interpretation.

Xenix Agent has no script execution environment. Use only available Xenix tools:

- `analysis.profile` first for bounded whole-Dataset shape, type, missingness, duplicate, and numeric facts.
- `data.query` once with a focused projection or aggregation only when business-role semantics remain materially ambiguous.
- `data.tokenize` after activating `xenix-data-preprocessing` for explicit token inspection or frequency workflows. Active multilingual analyzers accept raw text and retain preparation themselves.
- `data.feature.select` to create a role-binding snapshot before training.
- `model.metadata` before constructing model parameters; browse `model_family: "forecasting"` for native forecast candidates, then inspect each selected `model_key` and its `param_schema`.
- `model.train` for baseline and candidate model training.
- `model.hyper_train` for constrained hyperparameter search after a valid baseline exists.
- `model.apply` for scoring, prediction, probability output, batch application, or horizon-only future forecasting with a retained forecast model.
- `model.task.query` for background model task status.
- `analysis.graph` only for model-result explanation charts when chart-ready data exists.
- `knowledge.lookup` for saved target definitions, business constraints, threshold policies, review rules, and interpretation guidance.

## Non-negotiable rules

1. Do not train before identifying the business target, unit of analysis, candidate feature fields, leakage fields, time fields, and sensitive fields.
2. Do not use identifiers, post-outcome fields, target duplicates, or sensitive/prohibited fields as predictive features.
3. Train a simple baseline first. Tune only when the baseline is valid and the business question needs better predictive performance.
4. Do not claim causality from coefficients, feature importance, associations, or model explanations.
5. Do not claim the model is suitable for automatic decisions unless threshold, risk, compliance, and human-review boundaries are explicit.
6. If the dataset needs cleaning, derived features, joins, transformations, or role binding preparation, activate `xenix-data-preprocessing`.
7. If the user only needs descriptive analysis, charts, association discovery, or a management report, activate `xenix-data-analysis`.
8. A Knowledge excerpt is a source claim, not label truth, model performance, causal evidence, or authorization for an automatic decision.
9. Treat `data.clean` as a whole-Dataset business transformation, not proof of holdout-safe model preparation. Learned imputation, encoding, scaling, and vectorization must be fitted inside the model Pipeline on the outer training partition.
10. When multiple rows belong to one customer, account, device, household, case, or other business entity, bind that entity as `group`. Never use the group as a feature, and never describe row-random evidence as group-safe.
11. Use the referenced Evaluate ML task as the authority for candidate metrics, same-holdout baseline metrics, actual split facts, and preparation facts. Do not infer those facts from model metadata or algorithm names.
12. Forecast only after binding exactly one `time`, exactly one `target`, and at most one independent `group`. Profile first; reject or explicitly repair duplicate time keys, missing periods, mixed/irregular cadence, non-finite targets, or unaligned group cutoffs before training.
13. Compare `forecasting.seasonal_naive`, `forecasting.holt_winters`, and `forecasting.sarima` on the same cadence, horizon, seasonal period, rolling folds, metric contract, and interval level. Never compare metrics produced from different fold identities as though they were one experiment.
14. Treat forecast intervals as empirical training-side residual evidence, not guaranteed coverage. State the reported calibration count, empirical coverage/width where available, and `coverage_guaranteed: false` plainly.
15. Forecast apply is horizon-only: call `model.apply` with `trained_model_id` and `horizon`, without `input_sources` or `input_rows`. New observations require a new fit; do not pretend apply mutates retained history.
16. The Agent fills typed shallow parameters only after reading each model's `param_schema`. Never invent raw SARIMA orders, order grids, optimizer arguments, convergence flags, seeds, or a wider search/budget than the schema exposes.
17. When distinct model keys share one role binding and comparison contract, submit them together in one `model.train` call with `models` and `params_by_model`. Because `params_by_model` has one object per model key, use separate calls for several parameterizations of the same key. In both cases, reuse returned task ids and trained model ids; never retrain an identical candidate merely to inspect, compare, or apply it.
18. Personalized recommendation requires explicit `user`, `item`, and numeric `rating` roles plus an optional valid `time` role. Use `recommendation.collaborative_top_k`; keep `recommendation.item_similarity` only for the distinct legacy question “which items resemble this base item?”.
19. Before setting `positive_rating_threshold`, profile the rating scale and use one focused `data.query` only if the business meaning of a positive rating remains ambiguous. Never guess a five-star threshold for an unknown scale.
20. Recommendation Evaluate evidence must use the same private per-user truth for candidate and popularity baseline, report the realized latest-positive or deterministic-hash holdout policy, and have zero seen-item violations. Offline ranking metrics do not prove online uplift.
21. Use `text.classification.multilingual_logistic_regression_tfidf` for active bilingual raw-text classification. Keep `text.classification.logistic_regression_tfidf` only for existing analyzers whose persisted input contract is already pre-tokenized.
22. Bind one raw `text`, one `target`, and an optional business `group`. The service joins business groups with exact/template/near-duplicate constraints; all reported train/holdout overlap counts must be zero, and TF-IDF vocabulary/IDF must be fitted only on the training partition.
23. Custom dictionary and stopword inputs are registered one-column Dataset IDs, never inline word dumps or local paths. Use only the advertised maximum of four per purpose and require the retained specification to report the same Dataset identities and hashes.
24. Use the active multilingual raw-text discovery keys for new clustering, topic, and retrieval work. Existing `text.clustering.kmeans_tfidf`, `text.topic_modeling.lda`, and `text.similarity.tfidf_cosine` analyzers keep their pre-tokenized legacy contracts; never silently reinterpret them as raw-text models.
25. Treat cluster and topic labels as stable display identities only within their retained analyzer. Require the mapping/identity digest before comparing Evaluate, assignment, and Apply outputs; topic numbering is permutation-invariant and is not a semantic name or observed truth.
26. Retrieval may report Recall, MRR, or NDCG only when `relevance_group` truth is bound and the authoritative mode is `relevance_evaluated`. In `index_diagnostic` mode, report only index/rank/self-exclusion diagnostics and do not infer semantic relevance quality.

## Default workflow

1. Clarify or infer the modeling objective: classification, regression, scoring, ranking, regular-series forecasting, semi-supervised labeling, text analysis, or model application.
2. Use `analysis.profile` for the default bounded Dataset inspection. If target meaning, group meaning, or leakage timing is still ambiguous, use one purpose-limited `data.query` that retrieves only the relevant values or aggregation.
3. When saved knowledge may define the target, constraints, threshold, human-review policy, or interpretation, call `knowledge.lookup` with a compact business-language query and prefer `mode: "auto"`. Keep its claim separate from current-data and model evidence.
4. For active multilingual text classification, keep the source as raw text and let the retained analyzer own normalization/tokenization. Use `data.tokenize` only when the requested output is an explicit token Dataset or term-frequency analysis. Legacy persisted text analyzers keep their documented pre-tokenized contract.
5. Ask for confirmation when multiple targets or business groups are plausible, the target semantics are unclear, missing labels may mean either “negative” or “unlabeled”, or the business threshold is sensitive.
6. Use `data.feature.select` to bind roles: target, optional group, time for forecasting, partial_target when applicable, text/text_id when applicable, features, and excluded fields with reasons. Exclude identifiers, group/time fields, and post-outcome leakage fields from predictive features.
7. Call `model.metadata` with `model_family` to browse candidates, then call it again with each selected `model_key` to inspect its role schema and `param_schema` before filling `params_by_model`.
8. Train an interpretable candidate with `model.train`; the service evaluates it against a simple same-holdout baseline and returns an authoritative evaluation task id.
9. Resolve the Evaluate task with `model.task.query`. Explain the realized split (including group counts and zero-overlap evidence when present), train-only preparation scope, candidate-versus-baseline comparison, and metric direction. Stop when data quality, label quality, sample size, tokenization quality, split feasibility, or leakage blocks a credible model.
10. Use `model.hyper_train` only for one or two plausible candidates with a small search space.
11. Use `model.apply` for scored records, probabilities, ranking, prediction output, cluster/topic assignment, or similarity retrieval against new rows. For forecasting, use only a future `horizon` with the retained model and no row/file input.
12. Explain model output as decision support, not truth. Include assumptions, fields used/excluded, metrics, threshold policy, Knowledge claims used, risk notes, and next data needed.

### Clustering comparison workflow

For a fixed clustering candidate set, create one role binding and inspect the candidate schema. When comparing several parameterizations of one model key—such as KMeans k=2/3/4—use one `model.train` call per parameterization because the input has one parameter object per key; keep the binding and evaluation contract unchanged. Native preparation handles numeric scaling inside the model boundary, so do not create a transformed Dataset merely to pre-scale complete numeric clustering features. Compare the returned evaluation reports, then apply the selected returned `trained_model_id` directly. Do not retrain the winner. Finish by linking the public assignment Dataset and evaluation Artifact and by explaining original-scale profiles and internal-evidence limits.

### Personalized recommendation workflow

For explicit-rating interactions, profile the data grain and rating scale, then bind exactly one `user`, `item`, and `rating`, plus `time` only when it is a valid interaction timestamp. Inspect `recommendation.collaborative_top_k` metadata before choosing bounded `top_k`, minimum user/item support, and positive-rating threshold. Train once and query the authoritative Evaluate task. Compare NDCG@K, Recall@K, HitRate@K, MRR@K, coverage, novelty, diversity, and short-list facts against the same-truth popularity baseline; require `seen_item_violation_count = 0`. Apply the retained analyzer to a Dataset or inline rows containing the trained `user` column. Known users receive unseen personalized recommendations where evidence exists; cold users receive popularity fallback, while unseen cold items are outside v1. Link the local recommendation Dataset and Artifact instead of requesting ranking rows through lifecycle Tools, and state that offline evidence does not establish causal online lift.

### Multilingual raw-text classification workflow

Profile text/target completeness and label counts without retrieving raw text rows by default. Bind `text`, `target`, and an optional stable business `group`; do not transform text into a feature table first. Inspect `text.classification.multilingual_logistic_regression_tfidf`, then choose its preparation profile, unigram/short-phrase mode, train-side feature bounds, class weighting, and any registered dictionary/stopword Dataset IDs. Train once, query the authoritative Evaluate task and require the retained preparation specification, zero business/template/connected overlap, train-only vectorization facts, candidate-versus-dummy metrics, and prediction digest. Apply the returned full-history analyzer directly to raw text with the same column name. Link the public prediction Dataset and authoritative evaluation Artifact, and distinguish offline group-safe classification evidence from causal or automatic-decision authority.

### Multilingual text discovery and retrieval workflow

Keep the source as raw text and inspect exactly one active key before filling its shallow schema: `text.clustering.multilingual_kmeans_tfidf`, `text.topic_modeling.multilingual_lda`, or `text.similarity.multilingual_tfidf_cosine`. For clustering/topic discovery bind `text` plus an optional stable business `group`; for retrieval bind `text`, optional unique `document_id`, and `relevance_group` only when it is genuine evaluator truth. Query the authoritative Evaluate task before interpretation.

For clustering, require cosine silhouette, non-degenerate sizes, connected-group resampling stability, sanitized bounded profiles, and the stable-label mapping digest. For topics, require group-safe held-out perplexity, coherence, diversity, prevalence, permutation-matched stability, zero group overlap, and the topic-label identity digest shared by Evaluate and Apply. For retrieval, require zero self/duplicate/rank violations and distinguish `relevance_evaluated` from `index_diagnostic` before mentioning ranking metrics. Link the local assignment/retrieval Dataset and evaluation Artifact; never request or reproduce raw text, document IDs, relevance groups, vocabulary, or result rows in the final answer. Cluster/topic structure is exploratory, retrieval metrics are offline evidence, and none of them authorizes causal or automatic decisions.

## Optional References

When the resource tool is available, load only the relevant file:

- `references/model-presets.md` before calling `model.train`, `model.hyper_train`, or `model.apply`.
- `references/supervised-learning.md` for classification or regression tasks.
- `references/forecasting.md` for regular daily, weekly, or monthly forecasting and future-horizon apply.
- `references/recommendation.md` for explicit-rating personalized Top-K, cold-user apply, and ranking evidence.
- `references/text-classification.md` for bilingual raw-text preparation, leakage-safe classification, and raw-text apply.
- `references/text-discovery-retrieval.md` for raw-text clustering, topic discovery, truth-aware local retrieval, identity, and privacy boundaries.
- `references/semi-supervised-learning.md` when labels are partially missing or only some samples are labeled.
- `references/neural-network.md` only when using a neural network as a nonlinear comparison model.

Use `assets/model-presets.json` only when a structured preset is useful for model selection or parameter planning.

## Final-Answer Standard

A good modeling answer contains:

1. Business target and unit of analysis.
2. Role binding: target, features, excluded fields, and leakage/sensitive-field decisions.
3. Actual evaluation scope and split facts, including group handling when applicable.
4. Train-only preparation facts and the distinction between evaluation-model and apply-model training scope.
5. Tool-returned candidate and same-holdout baseline metrics, their direction, comparison, and plain-language interpretation.
6. Threshold or scoring policy when relevant.
7. Model limitations, data-quality risks, and manual-review boundaries.
8. Recommended next step: more data, more labels, threshold review, deployment caution, or application to new records.

For forecasting, do not finish after `model.apply` until the final answer explicitly names seasonal-naive, Holt-Winters, and SARIMA with their reported results; identifies the selected model and comparison basis; gives the bound roles, cadence, cutoff, shared rolling-fold identity, horizon, and interval evidence; links both the public future Dataset/Artifact and evaluation Artifact; states that empirical intervals are not a coverage guarantee; and gives at least one operational limit or retraining/monitoring trigger.

For clustering, also report every compared candidate (including its cluster count), the selected cluster count, quality and resampling-stability evidence, cluster sizes, original-scale profiles for the business features, the public assignment Dataset and linked evaluation Artifact, and the limits of internal clustering evidence. Keep identifiers out of features and profiles, and recommend an external business validation step.

For personalized recommendation, report the rating and holdout policies, Top-K and support parameters, candidate-versus-same-truth-popularity metrics, zero seen-item violations, cold-user strategy and cold-item limitation, the public recommendation Dataset and evaluation Artifact, and an online experiment/monitoring next step. Do not claim offline ranking improvement is causal business uplift.

For multilingual text classification, report the retained profile/specification digest and registered resource identities, eligible/empty/custom-match facts, business/template/connected group counts with zero overlaps, train-only vocabulary size/digest and OOV facts, candidate-versus-dummy classification metrics, prediction Dataset and evaluation Artifact, and the limits of historical-label evidence. Never print raw text, vocabulary terms, group values, dictionary contents, or stopwords in the final answer.

### Multilingual topic pre-finalization audit

Before finalizing a multilingual topic-discovery answer, reconcile the user's requested deliveries with the authoritative Evaluate result and the completed FIT/APPLY results. Do not finalize until the answer:

- states the realized topic count and that topic numbers are permutation-invariant display labels, not semantic names or observed truth;
- reports the Tool-returned held-out perplexity, coherence, and stability values, plus connected/template group isolation and zero train/holdout overlap;
- uses only bounded sanitized terms and includes the topic-label identity needed to reconcile Evaluate and Apply;
- includes every public Dataset ID and Artifact link the user requested and that the completed results returned, using `artifact://` URIs for Artifact links;
- states that topics are exploratory, names an external validation or review step, and explains that offline evidence neither proves causality nor authorizes automatic business decisions;
- removes raw text, document IDs, group values, full vocabulary, matched rows, dictionary/stopword contents, and local filesystem paths.

If a requested fact, Dataset ID, or Artifact ID is absent from the public Tool results, state that it is unavailable instead of inventing it or a local path.

For clustering, report the retained preparation/specification, eligible/empty counts, quality and stability, bounded sanitized terms, label-identity digest, local assignment Dataset, evaluation Artifact, and an external validation step. For retrieval, report the mode, Top-K, self/duplicate/rank diagnostics, and ranking metrics only when relevance truth was admitted. Apply the same raw-content and local-path exclusions.
