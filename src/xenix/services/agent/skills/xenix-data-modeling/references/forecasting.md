# Forecasting

Xenix forecasts regular daily, weekly, or monthly series. Roles are one `time`, one numeric `target`, and optionally an independent `group`. The service validates cadence, missing periods, duplicate keys, finite values, history length, and aligned cutoffs; a reported data issue may need an explicit business transformation.

## Candidates and parameters

`forecasting.seasonal_naive` repeats the observed seasonal cycle; `forecasting.holt_winters` models additive trend and seasonality; `forecasting.sarima` uses service-managed bounded order selection. Select suitable candidates rather than always running all three. `model.metadata` with `model_family: "forecasting", include_details: true` returns their contracts together when needed.

Parameters include horizon, seasonal period, frequency, interval level, and rolling-window count. Shared settings make comparisons meaningful. SARIMA's optimizer and order-search internals belong to the service, not tool arguments. Forecasting uses `model.train`, not `model.hyper_train`.

## Evidence and delivery

Training returns rolling evaluation facts and public reports. MAE expresses average error in demand units; RMSE emphasizes large misses; sMAPE and MASE support scale-aware comparison. Use the reported comparable evaluation to select a retained model. No separate query is needed for already returned facts, and no digest checklist needs to be reproduced in the answer.

`model.apply` takes `trained_model_id` and `horizon`, without `input_sources` or `input_rows`. It returns a future Dataset and Artifact with forecast values and interval bounds. New observations require a new fit. The public output is sufficient for delivery; read rows or create a chart only when the requested analysis needs them.

Explain the selection and uncertainty relevant to the decision. Residual-based intervals have empirical calibration, not guaranteed future coverage. Link the requested forecast and evaluation report; the answer need not enumerate every internal fact or include a chart.
