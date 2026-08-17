# Native Forecasting Reference

Use this file for regular daily, weekly, or monthly forecasting through Xenix Tools. Native forecasting is a temporal modeling workflow, not random-holdout regression and not an SQL lag transformation.

## Public capability

The admitted native model keys are:

- `forecasting.seasonal_naive`: transparent seasonal baseline that repeats the latest observed cycle;
- `forecasting.holt_winters`: additive trend/season forecasting with the shallow options exposed by its schema;
- `forecasting.sarima`: bounded-auto SARIMA whose order candidates, temporal inner selection, convergence checks, and hard fit/time budgets are versioned service policy.

Use `model.metadata` with `model_family: "forecasting"` to browse them. Before training, inspect each selected `model_key` separately and read its `train_role_schema`, `apply_mode`, and `param_schema`. Do not guess a field merely because Statsmodels or another library supports it.

## Profile and role admission

1. Run `analysis.profile` on the source Dataset first. Confirm row/column counts, missingness, duplicate evidence, numeric target suitability, and likely date fields without requesting raw rows.
2. Resolve exactly one `time`, exactly one finite numeric `target`, and at most one independent `group`. Use one focused `data.query` only if business semantics, not structure, leave multiple credible bindings.
3. Use `data.feature.select` to bind `time`, `target`, and optional `group`. Forecasting has no generic feature role in v1. Identifiers are not features; a group column partitions independent series and must not be presented as an exogenous predictor.
4. Require a regular daily, weekly, or monthly cadence. Duplicate `(group?, time)` keys, missing periods, non-finite targets, mixed cadence, different group cutoffs, insufficient seasonal history, or too many groups must fail closed. Never silently aggregate, fill dates, interpolate, or drop a failing group inside modeling.

If the business wants explicit aggregation or calendar repair, activate `xenix-data-preprocessing`, create a new derived Dataset, profile it again, and bind roles on that immutable result.

## Comparable three-model workflow

1. Choose a business horizon, seasonal period, optional explicit cadence, interval level, and rolling-window count. Fill these shallow fields from the model's returned `param_schema`; use documented defaults when the business request does not justify an override.
2. Put common options into every selected model's object in `params_by_model`. The three models must use the same Dataset binding, time/target/group roles, horizon, seasonal period, cadence, interval level, rolling-window count, outer fold identities, and metric direction.
3. Model-specific shallow fields are allowed only when present in that model's `param_schema`. For Holt-Winters, do not invent trend/seasonal modes beyond the schema. For SARIMA, do not send raw `(p,d,q)`, seasonal orders, order grids, solver/optimizer kwargs, seeds, convergence flags, or expanded fit/time ceilings.
4. Call `model.train` with the three canonical keys and the validated `params_by_model`. Forecasting does not use `model.hyper_train`; bounded SARIMA selection happens inside the service on the training side of every outer fold.
5. Training may settle asynchronously. Resolve every returned Fit/Evaluate task id with `model.task.query` until terminal. The referenced Evaluate tasks are authoritative for `evaluation`, `comparison`, `forecast_evaluation`, and `artifacts[*].artifact_id`.
6. Compare MAE as the primary lower-is-better metric. Also explain RMSE, sMAPE, and MASE overall and by anonymous group index when available. Require identical `forecast_evaluation.split.fold_identity_digest` values before making a cross-model ranking.
7. Select a retained model from the comparable public evidence. A failed SARIMA task remains a failed candidate; never describe a seasonal-naive or Holt-Winters result as a SARIMA fallback.

## Temporal and interval evidence

From `forecast_evaluation`, verify and explain:

- frequency, seasonal period, horizon, rolling-window count, aligned cutoff, fold identities, and `future_overlap_count = 0`;
- chronological training-prefix preparation, duplicate/missing/non-finite counts, and the absence of silent partial-group success;
- candidate and seasonal-naive baseline metrics on the same holdouts;
- `residual_quantile.v1` interval level, calibration count, empirical holdout coverage, and mean width;
- `coverage_guaranteed: false`: an 80% empirical interval is not a promise that 80% of future values will fall inside it;
- for SARIMA, the bounded policy key, per-group selected orders as report facts, convergence/warning counts, and whether the budget was exhausted. These facts may be explained after execution but must not be turned back into user-authored optimizer parameters.

Do not claim future accuracy from training fit, report random-split metrics as temporal evidence, or let future/holdout rows influence preparation, order selection, candidate fitting, or interval calibration for the fold that evaluates them.

## Future-horizon apply

Call `model.apply` with only:

- the selected `trained_model_id`;
- `horizon`, matching the requested number of future periods.

Do not include `input_sources` or `input_rows`; horizon mode is mutually exclusive with both. The retained analyzer uses all observed training history after evaluation facts are fixed. New observations require a new fit rather than mutation of the old analyzer.

A successful apply returns `result_dataset_id` and `artifact_id`. Ground the final answer in that public future Dataset/Artifact. Check that the output has exactly `group_count × horizon` unique ordered `(group?, forecast_time)` rows, finite `forecast`, `lower_bound <= forecast <= upper_bound`, the selected `model_key`, interval method/level, and horizon facts.

## Final answer

State:

1. bound time, target, optional group, cadence, observed cutoff, and requested horizon;
2. the shared rolling validation contract and all three candidate outcomes, including failed candidates;
3. selected retained model and evidence-based reason, with metric direction;
4. interval method, level, empirical evidence, and non-guarantee;
5. the public future Dataset/Artifact link and output grain;
6. assumptions, data/cadence limitations, monitoring/re-fit trigger, and the business decision the forecast can support.
