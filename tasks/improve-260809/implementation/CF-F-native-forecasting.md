# CF-F Implementation Plan — Native Forecasting V1

**Status:** Implemented and objectively verified under consumed [IH-CF](../handshakes/IH-CF.md). Paid characterization and diagnosis are recorded in the [CF execution record](../execution/CF-2026-08-09.md).

## Outcome

Xenix gains first-class, reusable seasonal-naive, Holt-Winters, and bounded-auto SARIMA workflows over regular daily/weekly/monthly series with optional independent groups, honest rolling temporal evaluation, comparable intervals, and future Dataset/Artifact delivery.

## Working Set

- shared capability/Artifact seam delivered by `CF-C`;
- `src/xenix/services/storage/models.py` for forecasting problem kind only if not already landed;
- `src/xenix/services/ml/types.py`, `contracts.py`, `evaluation.py`, `preparation.py`, `registry.py`;
- new `src/xenix/services/ml/models/forecasting.py` and the narrow forecasting base seam in `models/base.py`;
- `src/xenix/services/ml_service.py`, `ml_task_service.py`, `trained_model_metadata.py`;
- `src/xenix/services/agent/tool_inputs.py`, `tools.py`, modeling Skill plus new forecast reference;
- `src/xenix/app.py` or the exact packaged-runtime smoke owner for short Statsmodels fits;
- focused forecast contracts/lifecycle/Agent projection/package tests;
- new clean-room fixtures under `tests/fixtures/ml_cf_service/`;
- implemented independently owned `ml.forecast_validation_v1` benchmark case/fixture under `benchmarks/agent_harness/`; paid execution still waits for completed service/offline/package qualification.

Do not reuse supervised random/group split, sklearn preparation facts, DummyRegressor, row-scoring apply, or the legacy non-native forecasting benchmark as forecast authority.

## Passes

1. Add forecasting family/task/evaluation/problem semantics, explicit `time`/`target`/optional `group` roles, common `ForecastOptions`, capability/apply mode, temporal split/preparation/interval/training-scope facts, and task-specific typed results.
2. Implement regular-series admission and deterministic rolling origins. Reject duplicate keys, missing periods, mixed cadence/cutoffs, non-finite targets, insufficient history, and more than 24 groups without mutation or fallback.
3. Implement three retained adapters: seasonal-naive, additive Holt-Winters, and SARIMA with a four-order versioned policy, two training-side inner folds, convergence/warning checks, and explicit fit-count/wall-time budgets.
4. Evaluate all methods on identical outer folds with MAE/RMSE/sMAPE/MASE and per-group facts. Calibrate `residual_quantile.v1` intervals only from training-side rolling residuals; store quantized point/interval digests.
5. Preserve evaluation-prefix and all-observed-history analyzers. Route horizon-only `model.apply`, materialize ordered future rows, derive from the training/history Dataset, and publish stable Dataset/Artifact IDs.
6. Extend bounded Agent metadata/task/apply projection and modeling guidance. The Agent resolves time/target/group/horizon/grain under `D-011`, fills typed shallow parameters under `D-015`, uses focused query only for material ambiguity, compares all three public results, and explains interval limitations. Fold construction, SARIMA order search/convergence, optimizer controls, and fit/time ceilings remain versioned service policy.
7. Add clean-room/metamorphic service cases, Statsmodels package smoke, full gates, then one separately owned paid native-forecast characterization.

## Independent Service Proof

Use an independently generated regular weekly fixture with two aligned groups, at least 72 periods, trend + period-4 seasonality + autoregressive residual structure, and enough hidden suffix for three outer origins plus two SARIMA inner folds. Keep hidden future values out of the input and create a metamorphic twin identical before cutoff but changed after cutoff.

Assert:

- typed role/cadence/season/horizon/cutoff/window/group facts and immutable snapshot;
- identical outer fold identities for all three methods and future-overlap zero;
- seasonal-naive recomputation; Holt-Winters and SARIMA candidate metrics; bounded per-group SARIMA selected-order/convergence/fit-budget facts;
- prefix-identical twins produce identical fitted/preparation and forecast digests while only validation metrics change;
- MAE/RMSE/sMAPE/MASE recomputation, candidate/baseline direction, interval order/calibration count/coverage/width, and no coverage guarantee;
- evaluation-prefix versus all-history future scope;
- exact horizon × group output rows, ordered unique future keys, stable schema/digests, public Artifact, derived Dataset, and training-history lineage;
- explicit failure for irregular/missing cadence, duplicates, insufficient cycles, unaligned groups, SARIMA non-convergence/non-finite output, group/fit/wall budget, and row/file inputs combined with forecast horizon.

Use `1e-6` metric/point tolerance with versioned quantization before digests. Do not assert wall-clock timing in pytest; assert budget admission/counters through injected deterministic seams.

## Verification Order

1. focused forecast contract/registry/lifecycle/metamorphic/Agent projection/package selectors;
2. `pdm run test -q` and proof-portfolio architecture review;
3. `pdm run check` and isolated `pdm run smoke`;
4. `pdm run package` and targeted packaged seasonal-naive/Holt-Winters/SARIMA smoke; attempt official `smoke-package` and record the unrelated OCR prerequisite separately if still present;
5. exactly one paid `ml.forecast_validation_v1` headless characterization with existing B0 limits.

## Stop Conditions

Stop and return to design for irregular-calendar repair, exogenous features, user-authored SARIMA orders, partial-group success, more than 24 groups, horizon-dependent refitting policy changes, a new ML task type/Agent Tool, a different interval guarantee, or any parameter that can create leakage, incomparable folds, unbounded search, or raw optimizer control.
