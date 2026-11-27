from __future__ import annotations

import math
import time
import warnings
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .....exceptions import ValidationError
from ...contracts import (
    CandidateMetrics,
    ForecastEvaluationFacts,
    ForecastGroupMetrics,
    ForecastIntervalFacts,
    ForecastOptions,
    ForecastSarimaBudgetFacts,
    ForecastSarimaSelectionFact,
)
from ...digests import sha256_json
from ...forecast_preparation import (
    PreparedForecastPanel,
    PreparedForecastSeries,
    RollingForecastFold,
    build_forecast_split_facts,
    build_rolling_folds,
    rolling_positions,
)
from .contracts import (
    FORECAST_DIGEST_QUANTIZATION,
    INNER_TEMPORAL_FOLDS,
    INTERVAL_METHOD,
    SARIMA_POLICY_KEY,
    Clock,
    ForecastEngineEvaluation,
    ForecastModelKey,
    RetainedForecastAnalyzer,
    RetainedForecastGroup,
    SarimaFitBudget,
    SarimaFitOutcome,
    SarimaFitter,
    SarimaOrderSpec,
    SeasonalNaiveState,
    _FitBudgetTracker,
    _ForecastRun,
    _PredictionRecord,
    _SarimaSelection,
)


def evaluate_forecast(
    panel: PreparedForecastPanel,
    *,
    model_key: ForecastModelKey | str,
    options: ForecastOptions,
    sarima_budget: SarimaFitBudget | None = None,
    sarima_fitter: SarimaFitter | None = None,
    clock: Clock = time.monotonic,
    retained_analyzer: RetainedForecastAnalyzer | None = None,
    damped_trend: bool = False,
) -> ForecastEngineEvaluation:
    resolved_key = ForecastModelKey(model_key)
    _validate_options_for_panel(panel, options)
    folds = build_rolling_folds(
        panel,
        options,
        minimum_training_observations=_minimum_outer_training(resolved_key, options),
    )
    split_facts = build_forecast_split_facts(panel, options, folds)
    tracker = _new_tracker(sarima_budget, clock)
    fitter = sarima_fitter or _fit_statsmodels_sarima
    candidate_records: list[_PredictionRecord] = []
    baseline_records: list[_PredictionRecord] = []
    selections_by_group: dict[int, list[_SarimaSelection]] = {}

    for group in panel.groups:
        for fold in folds:
            history = group.values[: fold.train_end_position]
            actual = group.values[fold.holdout_start_position : fold.holdout_end_position]
            candidate_run = _forecast_from_history(
                history,
                model_key=resolved_key,
                options=options,
                group_index=group.group_index,
                tracker=tracker,
                sarima_fitter=fitter,
                damped_trend=damped_trend,
            )
            baseline_run = (
                candidate_run
                if resolved_key is ForecastModelKey.SEASONAL_NAIVE
                else _forecast_from_history(
                    history,
                    model_key=ForecastModelKey.SEASONAL_NAIVE,
                    options=options,
                    group_index=group.group_index,
                    tracker=tracker,
                    sarima_fitter=fitter,
                    damped_trend=False,
                )
            )
            if candidate_run.sarima_selection is not None:
                selections_by_group.setdefault(group.group_index, []).append(candidate_run.sarima_selection)
            holdout_times = group.times[fold.holdout_start_position : fold.holdout_end_position]
            candidate_records.extend(
                _prediction_records(group, fold, holdout_times, actual, history, candidate_run, options)
            )
            baseline_records.extend(
                _prediction_records(group, fold, holdout_times, actual, history, baseline_run, options)
            )

    candidate = _candidate_metrics(candidate_records)
    baseline = _candidate_metrics(baseline_records)
    forecast_digest = _prediction_digest(candidate_records, include_intervals=False)
    interval_digest = _prediction_digest(candidate_records, include_intervals=True)
    candidate = candidate.model_copy(
        update={
            "details": {
                "forecast_digest": forecast_digest,
                "interval_digest": interval_digest,
                "interval_method": INTERVAL_METHOD,
            }
        }
    )
    baseline = baseline.model_copy(
        update={"details": {"forecast_digest": _prediction_digest(baseline_records, include_intervals=False)}}
    )
    per_group = [
        ForecastGroupMetrics(
            group_index=group.group_index,
            metrics=_metrics_for_records(
                [record for record in candidate_records if record.group_index == group.group_index]
            ),
            baseline_metrics=_metrics_for_records(
                [record for record in baseline_records if record.group_index == group.group_index]
            ),
        )
        for group in panel.groups
    ]
    interval_facts = _interval_facts(candidate_records, options)
    selection_facts = _selection_facts(
        panel,
        selections_by_group,
        tracker,
        retained_analyzer=retained_analyzer,
    )
    facts = ForecastEvaluationFacts(
        split=split_facts,
        preparation=panel.preparation_facts,
        per_group=per_group,
        intervals=interval_facts,
        forecast_digest=forecast_digest,
        interval_digest=interval_digest,
        sarima_selection=selection_facts,
        sarima_budget=(
            _sarima_budget_facts(tracker)
            if resolved_key is ForecastModelKey.SARIMA
            else None
        ),
    )
    return ForecastEngineEvaluation(
        candidate=candidate,
        baseline=baseline,
        facts=facts,
        records=tuple(candidate_records),
        budget_facts=tracker.facts(),
    )


def fit_full_history(
    panel: PreparedForecastPanel,
    *,
    model_key: ForecastModelKey | str,
    options: ForecastOptions,
    sarima_budget: SarimaFitBudget | None = None,
    sarima_fitter: SarimaFitter | None = None,
    clock: Clock = time.monotonic,
    damped_trend: bool = False,
) -> RetainedForecastAnalyzer:
    resolved_key = ForecastModelKey(model_key)
    _validate_options_for_panel(panel, options)
    build_rolling_folds(
        panel,
        options,
        minimum_training_observations=_minimum_outer_training(resolved_key, options),
    )
    tracker = _new_tracker(sarima_budget, clock)
    fitter = sarima_fitter or _fit_statsmodels_sarima
    retained_groups: list[RetainedForecastGroup] = []
    for group in panel.groups:
        run = _forecast_from_history(
            group.values,
            model_key=resolved_key,
            options=options,
            group_index=group.group_index,
            tracker=tracker,
            sarima_fitter=fitter,
            damped_trend=damped_trend,
        )
        radius = _residual_quantile(run.calibration_residuals, options.interval_level)
        retained_groups.append(
            RetainedForecastGroup(
                group_index=group.group_index,
                group_value=group.group_value,
                state=run.state,
                interval_radius=radius,
                calibration_count=len(run.calibration_residuals),
                sarima_order=(
                    run.sarima_selection.selected if run.sarima_selection is not None else None
                ),
            )
        )
    return RetainedForecastAnalyzer(
        model_key=resolved_key,
        time_column=panel.time_column,
        target_column=panel.target_column,
        group_column=panel.group_column,
        frequency=panel.frequency,
        calendar_anchor=panel.calendar_anchor,
        last_time=panel.last_time,
        seasonal_period=options.seasonal_period,
        interval_level=options.interval_level,
        interval_method=INTERVAL_METHOD,
        groups=tuple(retained_groups),
    )


def apply_future_forecast(
    analyzer: RetainedForecastAnalyzer,
    *,
    horizon: int,
) -> pd.DataFrame:
    if horizon < 1 or horizon > 365:
        raise ValidationError(
            "Forecast apply horizon must be between 1 and 365 periods.",
            error_code="forecast_invalid_horizon",
        )
    future_times = _future_times(analyzer, horizon)
    rows: list[dict[str, Any]] = []
    for group in analyzer.groups:
        predictions = _forecast_retained_state(analyzer.model_key, group.state, horizon)
        _require_finite(predictions, "future forecast", group.group_index)
        lower = predictions - group.interval_radius
        upper = predictions + group.interval_radius
        _require_finite(lower, "future lower interval", group.group_index)
        _require_finite(upper, "future upper interval", group.group_index)
        for forecast_time, point, lower_bound, upper_bound in zip(
            future_times, predictions, lower, upper, strict=True
        ):
            row: dict[str, Any] = {
                "forecast_time": forecast_time.isoformat(),
                "forecast": float(point),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "model_key": analyzer.model_key.value,
                "interval_method": analyzer.interval_method,
                "interval_level": analyzer.interval_level,
                "horizon": horizon,
            }
            if analyzer.group_column is not None:
                row[analyzer.group_column] = group.group_value
            rows.append(row)
    columns = [analyzer.group_column] if analyzer.group_column is not None else []
    columns.extend(
        [
            "forecast_time",
            "forecast",
            "lower_bound",
            "upper_bound",
            "model_key",
            "interval_method",
            "interval_level",
            "horizon",
        ]
    )
    result = pd.DataFrame(rows).loc[:, columns]
    key_columns = ["forecast_time"] if analyzer.group_column is None else [analyzer.group_column, "forecast_time"]
    if result.duplicated(subset=key_columns).any():
        raise ValidationError(
            "Forecast apply produced duplicate future keys.",
            error_code="forecast_duplicate_output_key",
        )
    return result.reset_index(drop=True)


def _forecast_from_history(
    history: np.ndarray,
    *,
    model_key: ForecastModelKey,
    options: ForecastOptions,
    group_index: int,
    tracker: _FitBudgetTracker,
    sarima_fitter: SarimaFitter,
    damped_trend: bool,
) -> _ForecastRun:
    if model_key is ForecastModelKey.SARIMA:
        return _fit_selected_sarima(
            history,
            options=options,
            group_index=group_index,
            tracker=tracker,
            sarima_fitter=sarima_fitter,
        )

    minimum = _base_history_requirement(model_key, options)
    inner_folds = rolling_positions(
        observation_count=len(history),
        horizon=options.horizon,
        window_count=INNER_TEMPORAL_FOLDS,
        minimum_training_observations=minimum,
    )
    residuals: list[float] = []
    for train_end, holdout_start, holdout_end in inner_folds:
        _inner_state, predictions = _fit_direct_model(
            history[:train_end],
            model_key=model_key,
            options=options,
            damped_trend=damped_trend,
        )
        actual = history[holdout_start:holdout_end]
        residuals.extend(np.abs(actual - predictions).astype(float).tolist())
    state, predictions = _fit_direct_model(
        history,
        model_key=model_key,
        options=options,
        damped_trend=damped_trend,
    )
    return _ForecastRun(
        predictions=predictions,
        calibration_residuals=np.asarray(residuals, dtype=float),
        state=state,
    )


def _fit_direct_model(
    history: np.ndarray,
    *,
    model_key: ForecastModelKey,
    options: ForecastOptions,
    damped_trend: bool,
) -> tuple[Any, np.ndarray]:
    if model_key is ForecastModelKey.SEASONAL_NAIVE:
        state = SeasonalNaiveState(
            history=np.asarray(history, dtype=float).copy(),
            seasonal_period=options.seasonal_period,
        )
        predictions = _seasonal_naive_forecast(
            state.history,
            state.seasonal_period,
            options.horizon,
        )
        return state, predictions
    if model_key is ForecastModelKey.HOLT_WINTERS:
        try:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                fitted = ExponentialSmoothing(
                    np.asarray(history, dtype=float),
                    trend="add",
                    damped_trend=damped_trend,
                    seasonal="add",
                    seasonal_periods=options.seasonal_period,
                    initialization_method="estimated",
                ).fit(optimized=True)
        except Exception as exc:
            raise ValidationError(
                "Holt-Winters initialization or fit failed.",
                error_code="forecast_holt_winters_fit_failed",
                error_details={"exception_type": type(exc).__name__},
            ) from exc
        optimizer_result = getattr(fitted, "mle_retvals", None)
        optimizer_success = getattr(optimizer_result, "success", True)
        if optimizer_success is False:
            raise ValidationError(
                "Holt-Winters optimization did not converge.",
                error_code="forecast_holt_winters_nonconvergence",
            )
        predictions = np.asarray(fitted.forecast(options.horizon), dtype=float)
        _require_finite(predictions, "Holt-Winters forecast", None)
        return fitted, predictions
    raise ValidationError(
        f"Forecast model '{model_key.value}' is not a direct model.",
        error_code="forecast_unknown_model",
    )


def _fit_selected_sarima(
    history: np.ndarray,
    *,
    options: ForecastOptions,
    group_index: int,
    tracker: _FitBudgetTracker,
    sarima_fitter: SarimaFitter,
) -> _ForecastRun:
    inner_folds = rolling_positions(
        observation_count=len(history),
        horizon=options.horizon,
        window_count=INNER_TEMPORAL_FOLDS,
        minimum_training_observations=_base_history_requirement(ForecastModelKey.SARIMA, options),
    )
    attempted_before = tracker.attempted_fit_count
    converged_before = tracker.converged_fit_count
    candidate_scores: list[tuple[float, int, SarimaOrderSpec, np.ndarray]] = []
    for policy_index, order in enumerate(_sarima_order_policy(options.seasonal_period)):
        residuals: list[float] = []
        for train_end, holdout_start, holdout_end in inner_folds:
            outcome = tracker.fit(
                group_index=group_index,
                values=history[:train_end],
                order=order,
                fitter=sarima_fitter,
            )
            predictions = _forecast_sarima_outcome(outcome, options.horizon, group_index)
            actual = history[holdout_start:holdout_end]
            residuals.extend(np.abs(actual - predictions).astype(float).tolist())
        residual_array = np.asarray(residuals, dtype=float)
        candidate_scores.append((float(np.mean(residual_array)), policy_index, order, residual_array))
    _score, _policy_index, selected_order, selected_residuals = min(
        candidate_scores,
        key=lambda item: (item[0], item[1]),
    )
    final_outcome = tracker.fit(
        group_index=group_index,
        values=history,
        order=selected_order,
        fitter=sarima_fitter,
    )
    predictions = _forecast_sarima_outcome(final_outcome, options.horizon, group_index)
    selection = _SarimaSelection(
        group_index=group_index,
        selected=selected_order,
        inner_residuals=selected_residuals,
        attempted_fit_count=tracker.attempted_fit_count - attempted_before,
        converged_fit_count=tracker.converged_fit_count - converged_before,
    )
    return _ForecastRun(
        predictions=predictions,
        calibration_residuals=selected_residuals,
        state=final_outcome.fitted_model,
        sarima_selection=selection,
    )


def _fit_statsmodels_sarima(values: np.ndarray, order: SarimaOrderSpec) -> SarimaFitOutcome:
    # Non-default SARIMAX construction: trend="n" (the differencing orders carry
    # the level), and stationarity/invertibility enforcement is left off so the
    # bounded order search is not pre-rejected at initialization. Convergence is
    # judged from mle_retvals["converged"] below, not the parameter transform.
    caught: list[warnings.WarningMessage]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted = SARIMAX(
            np.asarray(values, dtype=float),
            order=order.order,
            seasonal_order=order.seasonal_order,
            trend="n",
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False, maxiter=100)
    mle_retvals = getattr(fitted, "mle_retvals", {})
    converged = bool(mle_retvals.get("converged", False)) if isinstance(mle_retvals, dict) else False
    warning_codes = tuple(sorted({type(item.message).__name__ for item in caught}))
    return SarimaFitOutcome(
        fitted_model=fitted,
        converged=converged,
        warning_codes=warning_codes,
    )


def _forecast_sarima_outcome(
    outcome: SarimaFitOutcome,
    horizon: int,
    group_index: int,
) -> np.ndarray:
    try:
        predictions = np.asarray(outcome.fitted_model.forecast(steps=horizon), dtype=float)
    except Exception as exc:
        raise ValidationError(
            "SARIMA forecast generation failed; the task was rejected without fallback.",
            error_code="forecast_sarima_output_failed",
            error_details={"group_index": group_index, "exception_type": type(exc).__name__},
        ) from exc
    _require_finite(predictions, "SARIMA forecast", group_index)
    return predictions


def _seasonal_naive_forecast(history: np.ndarray, seasonal_period: int, horizon: int) -> np.ndarray:
    if len(history) < seasonal_period:
        raise ValidationError(
            "Seasonal-naive forecasting requires one complete seasonal cycle.",
            error_code="forecast_insufficient_seasonal_history",
        )
    seasonal_pattern = np.asarray(history[-seasonal_period:], dtype=float)
    return np.resize(seasonal_pattern, horizon).astype(float, copy=False)


def _prediction_records(
    group: PreparedForecastSeries,
    fold: RollingForecastFold,
    holdout_times: pd.DatetimeIndex,
    actual: np.ndarray,
    history: np.ndarray,
    run: _ForecastRun,
    options: ForecastOptions,
) -> list[_PredictionRecord]:
    predictions = np.asarray(run.predictions, dtype=float)
    if len(predictions) != len(actual):
        raise ValidationError(
            "Forecast model returned the wrong horizon length.",
            error_code="forecast_output_length_mismatch",
            error_details={"expected": len(actual), "actual": len(predictions)},
        )
    _require_finite(predictions, "evaluation forecast", group.group_index)
    interval_radius = _residual_quantile(run.calibration_residuals, options.interval_level)
    lower = predictions - interval_radius
    upper = predictions + interval_radius
    _require_finite(lower, "evaluation lower interval", group.group_index)
    _require_finite(upper, "evaluation upper interval", group.group_index)
    mase_scale = _mase_scale(history, options.seasonal_period)
    return [
        _PredictionRecord(
            group_index=group.group_index,
            fold_index=fold.fold_index,
            forecast_time=pd.Timestamp(forecast_time),
            actual=float(actual_value),
            forecast=float(point),
            lower_bound=float(lower_bound),
            upper_bound=float(upper_bound),
            mase_scale=mase_scale,
            calibration_count=len(run.calibration_residuals),
        )
        for forecast_time, actual_value, point, lower_bound, upper_bound in zip(
            holdout_times,
            actual,
            predictions,
            lower,
            upper,
            strict=True,
        )
    ]


def _candidate_metrics(records: list[_PredictionRecord]) -> CandidateMetrics:
    metrics = _metrics_for_records(records)
    return CandidateMetrics(
        primary_metric_name="mae",
        primary_metric_value=metrics["mae"],
        metrics=metrics,
    )


def _metrics_for_records(records: list[_PredictionRecord]) -> dict[str, float]:
    if not records:
        raise ValidationError("Forecast evaluation requires prediction records.")
    actual = np.asarray([record.actual for record in records], dtype=float)
    predicted = np.asarray([record.forecast for record in records], dtype=float)
    absolute_errors = np.abs(actual - predicted)
    denominators = np.abs(actual) + np.abs(predicted)
    smape_terms = np.divide(
        2.0 * absolute_errors,
        denominators,
        out=np.zeros_like(absolute_errors),
        where=denominators > np.finfo(float).eps,
    )
    mase = np.mean(
        [abs(record.actual - record.forecast) / record.mase_scale for record in records]
    )
    metrics = {
        "mae": float(np.mean(absolute_errors)),
        "rmse": float(math.sqrt(float(np.mean(np.square(actual - predicted))))),
        "smape": float(np.mean(smape_terms)),
        "mase": float(mase),
    }
    _require_finite(np.asarray(list(metrics.values())), "forecast metrics", None)
    return metrics


def _interval_facts(
    records: list[_PredictionRecord],
    options: ForecastOptions,
) -> ForecastIntervalFacts:
    coverage = np.mean(
        [record.lower_bound <= record.actual <= record.upper_bound for record in records]
    )
    width = np.mean([record.upper_bound - record.lower_bound for record in records])
    calibration_count = sum(
        next(record.calibration_count for record in records if (record.group_index, record.fold_index) == key)
        for key in sorted({(record.group_index, record.fold_index) for record in records})
    )
    return ForecastIntervalFacts(
        method=INTERVAL_METHOD,
        interval_level=options.interval_level,
        calibration_count=calibration_count,
        empirical_coverage=float(coverage),
        mean_width=float(width),
        coverage_guaranteed=False,
    )


def _selection_facts(
    panel: PreparedForecastPanel,
    selections_by_group: dict[int, list[_SarimaSelection]],
    tracker: _FitBudgetTracker,
    *,
    retained_analyzer: RetainedForecastAnalyzer | None,
) -> list[ForecastSarimaSelectionFact]:
    if not selections_by_group:
        return []
    retained_orders = {
        group.group_index: group.sarima_order
        for group in retained_analyzer.groups
        if group.sarima_order is not None
    } if retained_analyzer is not None else {}
    attempted_by_group = tracker.attempted_by_group or {}
    facts: list[ForecastSarimaSelectionFact] = []
    for group in panel.groups:
        selections = selections_by_group.get(group.group_index, [])
        if not selections:
            continue
        selected = retained_orders.get(group.group_index) or selections[-1].selected
        attempted = attempted_by_group.get(group.group_index, 0)
        facts.append(
            ForecastSarimaSelectionFact(
                group_index=group.group_index,
                policy_key=SARIMA_POLICY_KEY,
                selected_order=selected.order,
                selected_seasonal_order=selected.seasonal_order,
                inner_fold_count=INNER_TEMPORAL_FOLDS,
                attempted_fit_count=attempted,
                converged_fit_count=attempted,
            )
        )
    return facts


def _sarima_budget_facts(tracker: _FitBudgetTracker) -> ForecastSarimaBudgetFacts:
    facts = tracker.facts()
    return ForecastSarimaBudgetFacts(
        policy_key=SARIMA_POLICY_KEY,
        attempted_fit_count=facts.attempted_fit_count,
        converged_fit_count=facts.converged_fit_count,
        warning_count=facts.warning_count,
        max_fits_per_group=tracker.budget.max_fits_per_group,
        max_total_fits=tracker.budget.max_total_fits,
        max_wall_seconds=tracker.budget.max_wall_seconds,
        budget_exhausted=False,
    )


def _prediction_digest(records: list[_PredictionRecord], *, include_intervals: bool) -> str:
    payload: list[list[Any]] = []
    for record in sorted(
        records,
        key=lambda item: (item.group_index, item.fold_index, item.forecast_time),
    ):
        row: list[Any] = [
            record.group_index,
            record.fold_index,
            record.forecast_time.isoformat(),
            round(record.forecast, FORECAST_DIGEST_QUANTIZATION),
        ]
        if include_intervals:
            row.extend(
                [
                    round(record.lower_bound, FORECAST_DIGEST_QUANTIZATION),
                    round(record.upper_bound, FORECAST_DIGEST_QUANTIZATION),
                ]
            )
        payload.append(row)
    return _digest_json(payload)


def _mase_scale(history: np.ndarray, seasonal_period: int) -> float:
    seasonal_errors = np.abs(history[seasonal_period:] - history[:-seasonal_period])
    scale = float(np.mean(seasonal_errors)) if len(seasonal_errors) else 0.0
    return max(scale, np.finfo(float).eps)


def _residual_quantile(residuals: np.ndarray, interval_level: float) -> float:
    values = np.asarray(residuals, dtype=float)
    if values.size == 0:
        raise ValidationError(
            "Residual interval calibration requires training-side residuals.",
            error_code="forecast_empty_interval_calibration",
        )
    _require_finite(values, "interval calibration residuals", None)
    radius = float(np.quantile(values, interval_level, method="higher"))
    if not math.isfinite(radius) or radius < 0:
        raise ValidationError(
            "Residual interval calibration produced an invalid radius.",
            error_code="forecast_non_finite_interval",
        )
    return radius


def _forecast_retained_state(
    model_key: ForecastModelKey,
    state: Any,
    horizon: int,
) -> np.ndarray:
    if model_key is ForecastModelKey.SEASONAL_NAIVE:
        if not isinstance(state, SeasonalNaiveState):
            raise ValidationError(
                "The retained seasonal-naive analyzer state is invalid.",
                error_code="forecast_invalid_analyzer",
            )
        return _seasonal_naive_forecast(state.history, state.seasonal_period, horizon)
    try:
        predictions = np.asarray(state.forecast(horizon), dtype=float)
    except TypeError:
        predictions = np.asarray(state.forecast(steps=horizon), dtype=float)
    return predictions


def _future_times(analyzer: RetainedForecastAnalyzer, horizon: int) -> pd.DatetimeIndex:
    if analyzer.frequency == "daily":
        return pd.date_range(analyzer.last_time + pd.Timedelta(days=1), periods=horizon, freq="D")
    if analyzer.frequency == "weekly":
        return pd.date_range(analyzer.last_time + pd.Timedelta(days=7), periods=horizon, freq="7D")
    if analyzer.calendar_anchor == "month_start":
        return pd.date_range(analyzer.last_time + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    if analyzer.calendar_anchor == "month_end":
        return pd.date_range(analyzer.last_time + pd.offsets.MonthEnd(1), periods=horizon, freq="ME")
    day = int(analyzer.calendar_anchor.removeprefix("day:"))
    return pd.DatetimeIndex(
        [analyzer.last_time + pd.DateOffset(months=offset, day=day) for offset in range(1, horizon + 1)]
    )


def _minimum_outer_training(model_key: ForecastModelKey, options: ForecastOptions) -> int:
    return _base_history_requirement(model_key, options) + (INNER_TEMPORAL_FOLDS * options.horizon)


def _base_history_requirement(model_key: ForecastModelKey, options: ForecastOptions) -> int:
    cycles = {
        ForecastModelKey.SEASONAL_NAIVE: 1,
        ForecastModelKey.HOLT_WINTERS: 2,
        ForecastModelKey.SARIMA: 4,
    }[model_key]
    return cycles * options.seasonal_period


def _sarima_order_policy(seasonal_period: int) -> tuple[SarimaOrderSpec, ...]:
    return (
        SarimaOrderSpec((0, 1, 0), (0, 1, 0, seasonal_period)),
        SarimaOrderSpec((1, 1, 0), (0, 1, 0, seasonal_period)),
        SarimaOrderSpec((0, 1, 1), (0, 1, 0, seasonal_period)),
        SarimaOrderSpec((1, 1, 0), (1, 1, 0, seasonal_period)),
    )


def _validate_options_for_panel(panel: PreparedForecastPanel, options: ForecastOptions) -> None:
    if options.frequency != "auto" and options.frequency != panel.frequency:
        raise ValidationError(
            "Prepared forecast cadence differs from the requested frequency.",
            error_code="forecast_frequency_mismatch",
        )


def _new_tracker(budget: SarimaFitBudget | None, clock: Clock) -> _FitBudgetTracker:
    resolved_budget = budget or SarimaFitBudget()
    return _FitBudgetTracker(
        budget=resolved_budget,
        clock=clock,
        started_at=clock(),
    )


def _require_finite(values: np.ndarray, label: str, group_index: int | None) -> None:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not bool(np.all(np.isfinite(array))):
        details: dict[str, Any] = {"value_count": int(array.size)}
        if group_index is not None:
            details["group_index"] = group_index
        raise ValidationError(
            f"Forecast {label} must contain only finite values.",
            error_code="forecast_non_finite_output",
            error_details=details,
        )


def _digest_json(value: Any) -> str:
    return sha256_json(value)
