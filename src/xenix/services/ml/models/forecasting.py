from __future__ import annotations

import math
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from ....exceptions import ValidationError
from ...storage.models import ProblemKind
from ..digests import sha256_json
from ..contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    CandidateMetrics,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    ForecastEvaluationFacts,
    ForecastGroupMetrics,
    ForecastIntervalFacts,
    ForecastOptions,
    ForecastSarimaBudgetFacts,
    ForecastSarimaSelectionFact,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    TrainingScopeFacts,
)
from ..dataset_loader import load_dataset
from ..evaluation import build_evaluation_comparison
from ..forecast_preparation import (
    PreparedForecastPanel,
    PreparedForecastSeries,
    RollingForecastFold,
    build_forecast_split_facts,
    build_rolling_folds,
    prepare_forecast_panel,
    rolling_positions,
)
from ..types import (
    ApplyMode,
    ColumnRoleKind,
    EvaluationKind,
    ModelFamily,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)

INTERVAL_METHOD = "residual_quantile.v1"
SARIMA_POLICY_KEY = "bounded_auto.v1"
FORECAST_DIGEST_QUANTIZATION = 6
INNER_TEMPORAL_FOLDS = 2


class ForecastModelKey(StrEnum):
    SEASONAL_NAIVE = "forecasting.seasonal_naive"
    HOLT_WINTERS = "forecasting.holt_winters"
    SARIMA = "forecasting.sarima"


class ForecastParamsBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon: int = Field(default=4, ge=1, le=365)
    seasonal_period: int = Field(default=4, ge=2, le=365)
    frequency: Literal["auto", "daily", "weekly", "monthly"] = "auto"
    interval_level: float = Field(default=0.8, ge=0.5, le=0.99)
    rolling_windows: int = Field(default=3, ge=2, le=5)


class SeasonalNaiveForecastParams(ForecastParamsBase):
    pass


class HoltWintersForecastParams(ForecastParamsBase):
    damped_trend: bool = False


class SarimaForecastParams(ForecastParamsBase):
    """Shallow policy controls; raw SARIMA orders and optimizer options stay internal."""

    model_config = ConfigDict(extra="forbid")

    policy: Literal["bounded_auto.v1"] = SARIMA_POLICY_KEY
    max_fits_per_group: int = Field(default=48, ge=9, le=96)
    max_total_fits: int = Field(default=1152, ge=9, le=2304)
    max_wall_seconds: float = Field(default=120.0, ge=1.0, le=900.0)


@dataclass(frozen=True)
class SarimaOrderSpec:
    order: tuple[int, int, int]
    seasonal_order: tuple[int, int, int, int]


@dataclass(frozen=True)
class SarimaFitOutcome:
    fitted_model: Any
    converged: bool
    warning_codes: tuple[str, ...] = ()


SarimaFitter = Callable[[np.ndarray, SarimaOrderSpec], SarimaFitOutcome]
Clock = Callable[[], float]


@dataclass(frozen=True)
class SarimaFitBudget:
    max_fits_per_group: int = 48
    max_total_fits: int = 1152
    max_wall_seconds: float = 120.0


@dataclass(frozen=True)
class ForecastBudgetFacts:
    attempted_fit_count: int
    converged_fit_count: int
    attempted_by_group: tuple[tuple[int, int], ...]
    warning_count: int
    elapsed_seconds: float


@dataclass(frozen=True)
class _PredictionRecord:
    group_index: int
    fold_index: int
    forecast_time: pd.Timestamp
    actual: float
    forecast: float
    lower_bound: float
    upper_bound: float
    mase_scale: float
    calibration_count: int


@dataclass(frozen=True)
class _SarimaSelection:
    group_index: int
    selected: SarimaOrderSpec
    inner_residuals: np.ndarray
    attempted_fit_count: int
    converged_fit_count: int


@dataclass(frozen=True)
class _ForecastRun:
    predictions: np.ndarray
    calibration_residuals: np.ndarray
    state: Any
    sarima_selection: _SarimaSelection | None = None


@dataclass(frozen=True)
class RetainedForecastGroup:
    group_index: int
    group_value: Any | None
    state: Any
    interval_radius: float
    calibration_count: int
    sarima_order: SarimaOrderSpec | None = None


@dataclass(frozen=True)
class SeasonalNaiveState:
    history: np.ndarray
    seasonal_period: int


@dataclass(frozen=True)
class RetainedForecastAnalyzer:
    model_key: ForecastModelKey
    time_column: str
    target_column: str
    group_column: str | None
    frequency: Literal["daily", "weekly", "monthly"]
    calendar_anchor: str
    last_time: pd.Timestamp
    seasonal_period: int
    interval_level: float
    interval_method: str
    groups: tuple[RetainedForecastGroup, ...]


@dataclass(frozen=True)
class ForecastEvaluationArtifact:
    panel: PreparedForecastPanel
    options: ForecastOptions
    model_key: ForecastModelKey
    model_params: dict[str, Any]


@dataclass(frozen=True)
class ForecastEngineEvaluation:
    candidate: CandidateMetrics
    baseline: CandidateMetrics
    facts: ForecastEvaluationFacts
    records: tuple[_PredictionRecord, ...]
    budget_facts: ForecastBudgetFacts


@dataclass
class _FitBudgetTracker:
    budget: SarimaFitBudget
    clock: Clock
    started_at: float
    attempted_fit_count: int = 0
    converged_fit_count: int = 0
    warning_count: int = 0
    attempted_by_group: dict[int, int] | None = None

    def __post_init__(self) -> None:
        if self.attempted_by_group is None:
            self.attempted_by_group = {}

    def fit(
        self,
        *,
        group_index: int,
        values: np.ndarray,
        order: SarimaOrderSpec,
        fitter: SarimaFitter,
    ) -> SarimaFitOutcome:
        self._check_wall_budget(group_index)
        group_attempts = self.attempted_by_group.get(group_index, 0) if self.attempted_by_group else 0
        if group_attempts >= self.budget.max_fits_per_group:
            self._raise_budget_error("per_group_fit_count", group_index)
        if self.attempted_fit_count >= self.budget.max_total_fits:
            self._raise_budget_error("total_fit_count", group_index)
        self.attempted_fit_count += 1
        if self.attempted_by_group is not None:
            self.attempted_by_group[group_index] = group_attempts + 1
        try:
            outcome = fitter(values, order)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(
                "SARIMA initialization or fit failed; the task was rejected without fallback.",
                error_code="forecast_sarima_fit_failed",
                error_details={"group_index": group_index, "exception_type": type(exc).__name__},
            ) from exc
        self.warning_count += len(outcome.warning_codes)
        self._check_wall_budget(group_index)
        if not outcome.converged:
            raise ValidationError(
                "SARIMA did not converge; the task was rejected without fallback.",
                error_code="forecast_sarima_nonconvergence",
                error_details={
                    "group_index": group_index,
                    "attempted_fit_count": self.attempted_fit_count,
                    "warning_codes": list(outcome.warning_codes[:8]),
                },
            )
        self.converged_fit_count += 1
        return outcome

    def facts(self) -> ForecastBudgetFacts:
        elapsed = max(0.0, self.clock() - self.started_at)
        attempts = self.attempted_by_group or {}
        return ForecastBudgetFacts(
            attempted_fit_count=self.attempted_fit_count,
            converged_fit_count=self.converged_fit_count,
            attempted_by_group=tuple(sorted(attempts.items())),
            warning_count=self.warning_count,
            elapsed_seconds=float(elapsed),
        )

    def _check_wall_budget(self, group_index: int) -> None:
        if self.clock() - self.started_at > self.budget.max_wall_seconds:
            self._raise_budget_error("wall_time", group_index)

    def _raise_budget_error(self, budget_kind: str, group_index: int) -> None:
        raise ValidationError(
            "SARIMA fit budget was exhausted; the task was rejected without fallback.",
            error_code="forecast_sarima_budget_exhausted",
            error_details={
                "budget_kind": budget_kind,
                "group_index": group_index,
                "attempted_fit_count": self.attempted_fit_count,
                "max_fits_per_group": self.budget.max_fits_per_group,
                "max_total_fits": self.budget.max_total_fits,
                "max_wall_seconds": self.budget.max_wall_seconds,
            },
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


_FORECAST_TRAIN_ROLE_SCHEMA = ModelRoleSchema(
    roles=[
        ModelRoleDefinition(
            name="time",
            kind=ColumnRoleKind.SINGLE_COLUMN,
            required=True,
            description="Regular daily, weekly, or monthly observation timestamp.",
        ),
        ModelRoleDefinition(
            name="target",
            kind=ColumnRoleKind.SINGLE_COLUMN,
            required=True,
            description="Finite numeric business measure to forecast.",
        ),
        ModelRoleDefinition(
            name="group",
            kind=ColumnRoleKind.SINGLE_COLUMN,
            required=False,
            description="Optional independent series with aligned timestamps and cutoff.",
        ),
    ],
    additional_roles=False,
)
_FORECAST_APPLY_ROLE_SCHEMA = ModelRoleSchema(roles=[], additional_roles=False)


class ForecastingModelService(ModelServiceBase):
    """ML lifecycle bridge around the isolated forecasting engine."""

    problem_kind = ProblemKind.FORECASTING
    evaluation_kind = EvaluationKind.FORECASTING
    model_family = ModelFamily.FORECASTING
    model_task_kind = ModelTaskKind.FORECASTER
    family = "Classical seasonal forecasting"
    requires_target = True
    supports_evaluation = True
    supports_apply = True
    apply_mode = ApplyMode.FUTURE_HORIZON
    supports_hyperparameter_tuning = False
    train_role_schema = _FORECAST_TRAIN_ROLE_SCHEMA
    apply_role_schema = _FORECAST_APPLY_ROLE_SCHEMA
    param_grid_model = None
    params_model: ClassVar[type[BaseModel]] = SeasonalNaiveForecastParams

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        model_key = ForecastModelKey(cls.key)
        params = cls.validate_params(request.manual_training.params)
        options = _options_from_params(params)
        _require_matching_request_options(request.forecast_options, options)
        panel = _prepare_request_panel(request, options)
        budget = _budget_from_params(params)
        _validate_service_budget_admission(model_key, panel, options, budget)
        folds = build_rolling_folds(
            panel,
            options,
            minimum_training_observations=_minimum_outer_training(model_key, options),
        )
        analyzer = fit_full_history(
            panel,
            model_key=model_key,
            options=options,
            sarima_budget=budget,
            damped_trend=_damped_trend_from_params(params),
        )

        model_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        evaluation_path = task_dir / "input" / "forecast-evaluation.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        evaluation_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(analyzer, model_path)
        joblib.dump(
            ForecastEvaluationArtifact(
                panel=panel,
                options=options,
                model_key=model_key,
                model_params=params.model_dump(mode="json"),
            ),
            evaluation_path,
        )
        split_facts = build_forecast_split_facts(panel, options, folds)
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            holdout_artifact_path=str(evaluation_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="chronological_training_prefixes",
                apply_model="all_observed_history",
            ),
            forecast_split_facts=split_facts,
            forecast_preparation_facts=panel.preparation_facts,
            result_summary={
                "frequency": panel.frequency,
                "horizon": options.horizon,
                "seasonal_period": options.seasonal_period,
                "rolling_windows": options.rolling_windows,
                "group_count": panel.group_count,
                "evaluation_scope": "rolling_origin_holdouts",
                "apply_scope": "all_observed_history",
            },
        )

    @classmethod
    def tune(
        cls,
        request: HyperparameterTuningTaskRequest,
        task_dir: Path,
    ) -> HyperparameterTuningTaskResult:
        del request, task_dir
        raise ValidationError(
            f"Model '{cls.key}' uses a fixed bounded policy and does not support hyperparameter tuning."
        )

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        del task_dir
        try:
            artifact = joblib.load(request.evaluate_model.holdout_artifact_path)
            analyzer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        except Exception as exc:
            raise ValidationError(
                "Forecast evaluation artifacts could not be loaded.",
                error_code="forecast_invalid_evaluation_artifact",
            ) from exc
        if not isinstance(artifact, ForecastEvaluationArtifact):
            raise ValidationError(
                "Forecast evaluation artifact has an invalid contract.",
                error_code="forecast_invalid_evaluation_artifact",
            )
        if not isinstance(analyzer, RetainedForecastAnalyzer):
            raise ValidationError(
                "Retained forecast analyzer has an invalid contract.",
                error_code="forecast_invalid_analyzer",
            )
        if artifact.model_key.value != cls.key or analyzer.model_key.value != cls.key:
            raise ValidationError(
                "Forecast evaluation artifacts do not match the selected model.",
                error_code="forecast_model_artifact_mismatch",
            )
        params = cls.validate_params(artifact.model_params)
        evaluation = evaluate_forecast(
            artifact.panel,
            model_key=artifact.model_key,
            options=artifact.options,
            sarima_budget=_budget_from_params(params),
            retained_analyzer=analyzer,
            damped_trend=_damped_trend_from_params(params),
        )
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=evaluation.candidate,
            baseline_evaluation=evaluation.baseline,
            comparison=build_evaluation_comparison(
                request.evaluation_policy,
                evaluation.candidate,
                evaluation.baseline,
            ),
            forecast_evaluation=evaluation.facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        if request.forecast_horizon is None or request.input_files:
            raise ValidationError(
                "Forecast apply requires only a future horizon and no row/file inputs.",
                error_code="forecast_apply_mode_mismatch",
            )
        try:
            analyzer = joblib.load(request.apply_model.trained_model_artifact_path)
        except Exception as exc:
            raise ValidationError(
                "Retained forecast analyzer could not be loaded.",
                error_code="forecast_invalid_analyzer",
            ) from exc
        if not isinstance(analyzer, RetainedForecastAnalyzer) or analyzer.model_key.value != cls.key:
            raise ValidationError(
                "Retained forecast analyzer does not match the selected model.",
                error_code="forecast_model_artifact_mismatch",
            )
        result_frame = apply_future_forecast(analyzer, horizon=request.forecast_horizon)
        output_path = task_dir / "output" / "forecast.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_frame.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(result_frame.index),
                input_file_count=0,
                prediction_column_name="forecast",
                apply_mode="future_horizon",
                horizon=request.forecast_horizon,
                group_count=len(analyzer.groups),
            ),
            source_dataset_ids=[request.dataset_id],
        )


class SeasonalNaiveForecastingService(ForecastingModelService):
    key = ForecastModelKey.SEASONAL_NAIVE.value
    display_name = "Seasonal Naive Forecast"
    guidance = "Repeats the latest observed seasonal cycle as a transparent retained forecast."
    recommendation_tier = 10
    params_model = SeasonalNaiveForecastParams


class HoltWintersForecastingService(ForecastingModelService):
    key = ForecastModelKey.HOLT_WINTERS.value
    display_name = "Holt-Winters Forecast"
    guidance = "Fits additive level, trend, and seasonality for regular business series."
    recommendation_tier = 12
    params_model = HoltWintersForecastParams


class SarimaForecastingService(ForecastingModelService):
    key = ForecastModelKey.SARIMA.value
    display_name = "Bounded Auto SARIMA Forecast"
    guidance = "Selects from a versioned bounded seasonal ARIMA policy using training-side temporal folds."
    recommendation_tier = 15
    params_model = SarimaForecastParams


def _prepare_request_panel(request: FitTaskRequest, options: ForecastOptions) -> PreparedForecastPanel:
    time_column = _single_role_column(request.time_columns, "time", required=True)
    target_column = _single_role_column(request.column_selection.target_columns, "target", required=True)
    group_column = _single_role_column(request.group_columns, "group", required=False)
    dataframe = load_dataset(Path(request.dataset_source_path))
    return prepare_forecast_panel(
        dataframe,
        time_column=time_column,
        target_column=target_column,
        group_column=group_column,
        options=options,
        source_dataset_snapshot_digest=_dataset_snapshot_digest(request.dataset_snapshot.model_dump(mode="json")),
    )


def _single_role_column(columns: list[str], role: str, *, required: bool) -> str | None:
    if not columns:
        if required:
            raise ValidationError(
                f"Forecasting requires exactly one {role} column.",
                error_code=f"forecast_missing_{role}_role",
            )
        return None
    if len(columns) != 1:
        raise ValidationError(
            f"Forecasting accepts at most one {role} column.",
            error_code=f"forecast_invalid_{role}_role",
        )
    return columns[0]


def _options_from_params(params: BaseModel) -> ForecastOptions:
    if not isinstance(params, ForecastParamsBase):
        raise ValidationError("Forecast model parameters have an invalid contract.")
    return ForecastOptions(
        horizon=params.horizon,
        seasonal_period=params.seasonal_period,
        frequency=params.frequency,
        interval_level=params.interval_level,
        rolling_windows=params.rolling_windows,
    )


def _require_matching_request_options(
    request_options: ForecastOptions | None,
    params_options: ForecastOptions,
) -> None:
    if request_options is not None and request_options != params_options:
        raise ValidationError(
            "Forecast request options must match the selected model parameters.",
            error_code="forecast_option_mismatch",
        )


def _budget_from_params(params: BaseModel) -> SarimaFitBudget:
    if not isinstance(params, SarimaForecastParams):
        return SarimaFitBudget()
    return SarimaFitBudget(
        max_fits_per_group=params.max_fits_per_group,
        max_total_fits=params.max_total_fits,
        max_wall_seconds=params.max_wall_seconds,
    )


def _damped_trend_from_params(params: BaseModel) -> bool:
    return bool(params.damped_trend) if isinstance(params, HoltWintersForecastParams) else False


def _validate_service_budget_admission(
    model_key: ForecastModelKey,
    panel: PreparedForecastPanel,
    options: ForecastOptions,
    budget: SarimaFitBudget,
) -> None:
    if model_key is not ForecastModelKey.SARIMA:
        return
    fits_per_selection = (len(_sarima_order_policy(options.seasonal_period)) * INNER_TEMPORAL_FOLDS) + 1
    required_per_group = fits_per_selection * options.rolling_windows
    required_total = required_per_group * panel.group_count
    if budget.max_fits_per_group < required_per_group or budget.max_total_fits < required_total:
        raise ValidationError(
            "SARIMA fit-count budget cannot cover the declared rolling evaluation.",
            error_code="forecast_sarima_budget_insufficient",
            error_details={
                "required_fits_per_group": required_per_group,
                "required_total_fits": required_total,
                "max_fits_per_group": budget.max_fits_per_group,
                "max_total_fits": budget.max_total_fits,
            },
        )


def _dataset_snapshot_digest(snapshot: dict[str, Any]) -> str:
    return _digest_json(snapshot)
