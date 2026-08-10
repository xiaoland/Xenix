# Forecast O-004 Safe Spike — 2026-08-09

## Question

Should native forecast v1 ship SARIMA together with a seasonal-naive baseline and Holt-Winters, or retain SARIMA as a later qualified candidate?

This record is evidence for product-scope discussion. It neither authorizes `IH-CF` source mutation nor turns textbook outputs into product requirements.

## Isolation and Runtime

- Only three explicit ch15 CSV inputs were read; their Python examples were statically inspected, not executed.
- Co-located forecasts, plots, reference metrics, prose answers, and serialized artifacts were not read.
- The bounded runner had no network, GUI, deserialization, bytecode, or file-output path and fixed execution to one thread.
- Input SHA-256 values were unchanged before/after; no Joblib, Pickle, or bytecode appeared under ch15.
- Runtime: Python 3.14.2, NumPy 2.5.0, Pandas 3.0.3, SciPy 1.18.0, Statsmodels 0.14.6.

## Material Identity

| Logical material | Private source locator | Original shape / derived series | SHA-256 |
| --- | --- | ---: | --- |
| `ch15.forecast_evaluation.regional_home_orders` | `ch15/code/forecast_evaluation/regional_home_ecommerce_daily_orders.csv` | 2,007 × 8; 66 monthly periods, season 12 | `080a2cbe9b576d1a32b343b146a41979916b02aa1a126071fcb5ccdc19232d45` |
| `ch15.arima.outdoor_direct_store_sales` | `ch15/code/arima/outdoor_direct_store_sales.csv` | 2,557 × 5; 84 monthly periods, season 12 | `bbf7faf51ffdf4a6de74ab0ffdb667f5e8ec56a1ad172dfe67fc2cbf891d5fd9` |
| `ch15.smoothing.urban_flower_orders` | `ch15/code/smoothing/urban_instant_retail_flower_orders.csv` | 1,277 × 4; 1,277 daily periods, season 7 | `6706c70c45355ea4492b518fdd9419d29ac7dcb04524f54d93f05303e3e75d0a` |

Reference-code hashes were recorded without execution:

- `ch15/code/forecast_evaluation/forecast_validation_uncertainty.py`: `0c5dd12c1f0449f016b858be84effbe6e262bf29b27ff5681f559f4b2058cb96`;
- `ch15/code/arima/arima_seasonal_models.py`: `14927308f8935446ee3306fc8feb8450d27fbb7723e62989b38ea8a4b06ae5f1`;
- `ch15/code/smoothing/moving_average_exponential_smoothing.py`: `cdb0d3d845e32947b56abcb5a1658bc37c21dab1b57bf4b6a8fa30be99c1f51e`.

## Method

Each series used four expanding-origin outer folds. Monthly horizon was 6; daily horizon was 14. The same folds compared:

- seasonal-naive;
- additive-trend/additive-seasonality Holt-Winters;
- light SARIMA `(0,1,0) × (0,1,0,m)`;
- full SARIMA `(1,1,1) × (1,1,1,m)`.

The two monthly series also used nested temporal selection: inside each outer fold, two earlier time folds selected one of four bounded SARIMA orders without seeing the outer holdout.

## Safe Aggregate Results

| Case | Holt-Winters MAE improvement over seasonal-naive | Full SARIMA improvement | SARIMA versus Holt-Winters | Fixed-fit time ratio |
| --- | ---: | ---: | ---: | ---: |
| Monthly orders | about 41% | about 55% | about 24% better | about 2.4× |
| Monthly sales | about 31% | about 22% | about 13% worse | about 2.5× |
| Daily weekly-seasonal orders | about 21% | about 20% | about 1% worse | about 7.8× |

Nested selection preserved the roughly 24% SARIMA advantage on the first monthly case but made the second roughly 44% worse than Holt-Winters. Selected order changed frequently across folds. About 12.5% of 64 inner SARIMA fits did not converge; fixed full SARIMA failed to converge on 2 of 8 monthly outer folds while still returning numeric forecasts.

Nominal SARIMA 95% intervals showed about 83%–95% rolling coverage across the three cases, which is insufficient evidence for a general calibrated-interval promise. The SARIMA path also emitted a NumPy 2.5 compatibility deprecation warning; Holt-Winters did not.

## Limitations

- Materials had regular cadence, positive targets, and no missing periods; irregular frequency, zero/negative values, structural breaks, and partial-group behavior remain unqualified.
- Repeated fits were deterministic in this runtime; cross-platform/version determinism is not established.
- Fixed SARIMA cost grows linearly with group × validation-window × candidate count. A bounded nested selection already took about 4.3 seconds for one monthly series.
- Seasonal-naive needs one full cycle. Holt-Winters can fail clearly below two full cycles. SARIMA may return numbers with initialization/convergence warnings, which is a more dangerous product failure mode.

## Original Recommendation and Sir's Decision

The evidence initially recommended that forecast v1 contain:

1. seasonal-naive as the same-fold baseline;
2. Holt-Winters as the first candidate;
3. chronological holdout/rolling-origin evidence on identical cutoffs;
4. an interval contract calibrated from training-side rolling residuals, independent of model-native interval availability;
5. no user-facing `(p,d,q)(P,D,Q,m)` controls.

It initially recommended retaining SARIMA as a later adapter behind a separate Impact Handshake.

The evidence shows SARIMA can be valuable, not that it is a safe general v1 default: benefit was concentrated in one of three series, while selection instability, convergence risk, and runtime cost apply to every series.

Sir rejected the scope-reduction recommendation on 2026-08-09 and confirmed that all three methods belong in forecast v1. `D-014` is the product authority. Accordingly, the spike's risk findings become first-version safeguards:

- at least 3–4 seasonal cycles for SARIMA admission;
- a bounded versioned order set with nested temporal selection;
- fail-closed convergence, initialization, and non-finite-output checks;
- comparable training-side interval calibration;
- per-series and total grouped runtime budgets;
- no ordinary-user exposure of raw order tuples.
