---
name: xenix-data-modeling
description: >-
  Use this skill when the user asks Xenix to predict, classify, regress, score,
  rank, train a model, tune hyperparameters, apply a trained model, estimate
  risk/probability, identify drivers through model output, compare supervised
  models, forecast a regular time series, compare seasonal-naive,
  Holt-Winters, and bounded-auto SARIMA, handle partially labeled data, run text classification, text
  clustering, topic modeling, similarity retrieval, or use neural networks as a
  candidate model. Use for Chinese requests such as “预测一下”, “训练模型”,
  “哪些因素影响结果”, “客户流失预测”, “风险评分”, “转化概率”, “调参”, “应用模型”,
  “销量预测”, “需求预测”, “未来几周”, “文本分类”, “主题分析”, “相似检索”, or “半监督”.
  Do not use for pure descriptive profiling, charts, reporting, or association
  analysis unless modeling is explicitly part of the task; use xenix-data-analysis
  for that. Activate xenix-data-preprocessing first when cleaning,
  transformation, or role binding is not ready.
license: MIT
metadata:
  version: "0.6.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Modeling Skill

This skill guides Xenix Agent for modeling workflows over tabular business data: target validation, feature exclusion, role binding, baseline training, constrained tuning, regular-series forecasting, model application, probability scoring, and model-result interpretation.

Xenix Agent has no script execution environment. Use only available Xenix tools:

- `analysis.profile` first for bounded whole-Dataset shape, type, missingness, duplicate, and numeric facts.
- `data.query` once with a focused projection or aggregation only when business-role semantics remain materially ambiguous.
- `data.tokenize` only after activating `xenix-data-preprocessing`, when raw Chinese text must become a tokenized derived dataset before text-analysis models.
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

## Default workflow

1. Clarify or infer the modeling objective: classification, regression, scoring, ranking, regular-series forecasting, semi-supervised labeling, text analysis, or model application.
2. Use `analysis.profile` for the default bounded Dataset inspection. If target meaning, group meaning, or leakage timing is still ambiguous, use one purpose-limited `data.query` that retrieves only the relevant values or aggregation.
3. When saved knowledge may define the target, constraints, threshold, human-review policy, or interpretation, call `knowledge.lookup` with a compact business-language query and prefer `mode: "auto"`. Keep its claim separate from current-data and model evidence.
4. If the task is text classification, text clustering, topic modeling, or similarity retrieval, require a tokenized text dataset first; activate `xenix-data-preprocessing` if the source still contains raw Chinese sentences.
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

## Optional References

When the resource tool is available, load only the relevant file:

- `references/model-presets.md` before calling `model.train`, `model.hyper_train`, or `model.apply`.
- `references/supervised-learning.md` for classification or regression tasks.
- `references/forecasting.md` for regular daily, weekly, or monthly forecasting and future-horizon apply.
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
