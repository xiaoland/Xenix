# Supervised Learning Reference

Use this file for classification and regression tasks. Execute with `analysis.profile`, a focused `data.query` only when needed, `model.train`, `model.task.query`, `model.hyper_train`, `model.apply`, and `analysis.graph`; do not rely on scripts.

## Before modeling

Confirm:

- the target is a business outcome, not a descriptor;
- features are available before the target outcome happens;
- identifiers and leakage fields are excluded;
- repeated rows belonging to one business entity are bound as `group`, not as a feature;
- missingness and outliers have been profiled;
- target distribution is understood;
- the selected metric matches the business objective.

Use `analysis.profile` for the default bounded inspection. Use one focused `data.query` only when target or group semantics, outcome timing, or an essential distribution cannot be resolved from the profile and business context.

Whole-Dataset cleaning and model preparation have different authorities. `data.clean` may create a business-cleaned derived Dataset, but imputation, encoding, scaling, and vectorization used by supervised models must be fitted inside the Pipeline on the outer training partition. Verify this through `preparation_facts.fit_scope`, not through the existence of a cleaned Dataset.

## Classification workflow

1. Identify the target class field.
2. Inspect class balance from `analysis.profile` or one focused aggregation when necessary.
3. Exclude leakage and ID fields. Bind a customer/account/case/device entity as `group` when it occurs in multiple rows.
4. Use `model.train` with an interpretable baseline, usually logistic regression or a shallow tree.
5. Query the referenced Evaluate task. Require the realized split and preparation facts, candidate metrics, same-holdout Dummy baseline metrics, metric direction, comparison verdict, and prediction digests.
6. For grouped data, require `group_overlap_count = 0`; never accept a silently downgraded row split as group-safe evidence.
7. Interpret confusion matrix, accuracy, precision, recall, F1, and AUC when probability ranking matters, but do not request raw labels or preview rows from lifecycle tools.
8. If the candidate is useful but insufficient, use `model.hyper_train` for one or two candidate models.
9. Use `model.apply` to output probability scores and ranked lists. Distinguish the training Dataset from the current apply source Dataset or Artifact.
10. Use `analysis.graph` for threshold tradeoff, confusion matrix, top drivers, or segment distribution where available.

## Classification interpretation

Do not rely on accuracy alone. Explain:

- precision: among predicted positives, how many were actually positive;
- recall: among actual positives, how many were found;
- F1: balance between precision and recall;
- AUC: ranking separation ability;
- threshold: business tradeoff between coverage and false positives.

Common business mapping:

- marketing response: compare precision, recall, and contact volume;
- churn warning: prioritize recall when missing risky customers is costly;
- credit/default risk: prioritize false-negative risk and human review;
- conversion prediction: use probability ranking for prioritization.

## Threshold policy

The default 0.5 threshold is not automatically optimal. Ask or infer the business preference:

- conservative strategy: higher threshold, higher precision, fewer targets;
- balanced strategy: threshold near F1 or business-cost optimum;
- coverage strategy: lower threshold, higher recall, more targets.

If the tool can evaluate multiple thresholds, request a threshold table with threshold, precision, recall, F1, positives selected, and false positives.

## Regression workflow

1. Identify the continuous target.
2. Profile the target from `analysis.profile`; use one focused aggregation only if business-relevant quantiles or outliers remain unresolved.
3. Exclude leakage and ID fields. Bind repeated business entities as `group` when applicable.
4. Use `model.train` with linear/ridge regression as baseline.
5. Query the referenced Evaluate task and require actual split/preparation facts plus candidate-versus-same-holdout-baseline evidence. Interpret MAE, RMSE, and R²; use MAPE only when target values are positive and not close to zero.
6. If nonlinear relationships are plausible, compare tree-based regression or gradient boosting through `model.train` or `model.hyper_train`.
7. Use `model.apply` for predicted values and ranked residuals or abnormal predictions.
8. Use `analysis.graph` for actual vs predicted, residual distribution, error by segment, or trend comparison.

## Regression interpretation

Translate error into business units:

- “MAE = 12.5” means the average absolute prediction error is about 12.5 target units.
- RMSE penalizes large errors more heavily; a much larger RMSE than MAE indicates some large misses.
- R² describes explained variance, not business acceptability.

Do not say a regression model is good just because R² is positive. Explain whether the error is acceptable for the decision being made.

## Feature explanation

Use explanation outputs only as model-behavior evidence:

- coefficients explain linear association under model assumptions;
- feature importance ranks predictive usefulness, not causal effect;
- permutation/SHAP-like outputs still do not prove causation.

When explaining to users, say “与预测结果相关” or “模型主要依赖这些变量”, not “导致”.
