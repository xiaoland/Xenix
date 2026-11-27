from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .....exceptions import ValidationError
from ...contracts import (
    CandidateMetrics,
    ForecastEvaluationFacts,
    ForecastOptions,
)
from ...forecast_preparation import PreparedForecastPanel

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
