from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from ...exceptions import ValidationError
from .contracts import (
    ForecastFoldFact,
    ForecastOptions,
    ForecastPreparationFacts,
    ForecastSplitFacts,
)

ForecastFrequency = Literal["daily", "weekly", "monthly"]

MAX_FORECAST_GROUPS = 24
FORECAST_PREPARATION_POLICY = "regular_forecast_panel.v1"
FORECAST_SPLIT_POLICY = "rolling_origin.v1"


@dataclass(frozen=True)
class PreparedForecastSeries:
    group_index: int
    group_value: Any | None
    times: pd.DatetimeIndex
    values: np.ndarray


@dataclass(frozen=True)
class PreparedForecastPanel:
    time_column: str
    target_column: str
    group_column: str | None
    frequency: ForecastFrequency
    calendar_anchor: str
    groups: tuple[PreparedForecastSeries, ...]
    preparation_facts: ForecastPreparationFacts
    source_dataset_snapshot_digest: str

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def periods_per_group(self) -> int:
        return len(self.groups[0].times)

    @property
    def common_times(self) -> pd.DatetimeIndex:
        return self.groups[0].times

    @property
    def last_time(self) -> pd.Timestamp:
        return self.common_times[-1]

    def future_times(self, horizon: int) -> pd.DatetimeIndex:
        if horizon < 1:
            raise ValidationError("Forecast horizon must be at least one period.")
        if self.frequency == "daily":
            return pd.date_range(self.last_time + pd.Timedelta(days=1), periods=horizon, freq="D")
        if self.frequency == "weekly":
            return pd.date_range(self.last_time + pd.Timedelta(days=7), periods=horizon, freq="7D")
        if self.calendar_anchor == "month_start":
            return pd.date_range(self.last_time + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        if self.calendar_anchor == "month_end":
            return pd.date_range(self.last_time + pd.offsets.MonthEnd(1), periods=horizon, freq="ME")
        day = int(self.calendar_anchor.removeprefix("day:"))
        return pd.DatetimeIndex(
            [self.last_time + pd.DateOffset(months=offset, day=day) for offset in range(1, horizon + 1)]
        )


@dataclass(frozen=True)
class RollingForecastFold:
    fold_index: int
    train_end_position: int
    holdout_start_position: int
    holdout_end_position: int
    fact: ForecastFoldFact


def prepare_forecast_panel(
    dataframe: pd.DataFrame,
    *,
    time_column: str,
    target_column: str,
    group_column: str | None,
    options: ForecastOptions,
    source_dataset_snapshot_digest: str,
) -> PreparedForecastPanel:
    """Validate and order a complete regular panel without repairing it."""

    selected_columns = [time_column, target_column]
    if group_column is not None:
        selected_columns.append(group_column)
    missing_columns = [column for column in selected_columns if column not in dataframe.columns]
    if missing_columns:
        raise ValidationError(
            f"Forecast input is missing required columns: {', '.join(missing_columns)}.",
            error_code="forecast_missing_columns",
        )
    if len(set(selected_columns)) != len(selected_columns):
        raise ValidationError(
            "Forecast time, target, and group roles must bind different columns.",
            error_code="forecast_overlapping_roles",
        )

    working = dataframe.loc[:, selected_columns].copy()
    parsed_times = pd.to_datetime(working[time_column], errors="coerce")
    invalid_time_count = int(parsed_times.isna().sum())
    if invalid_time_count:
        raise ValidationError(
            "Forecast time values must all be valid timestamps.",
            error_code="forecast_invalid_time",
            error_details={"invalid_time_count": invalid_time_count},
        )
    working[time_column] = parsed_times

    numeric_target = pd.to_numeric(working[target_column], errors="coerce")
    finite_mask = np.isfinite(numeric_target.to_numpy(dtype=float, na_value=np.nan))
    non_finite_target_count = int((~finite_mask).sum())
    if non_finite_target_count:
        raise ValidationError(
            "Forecast target values must all be finite numbers.",
            error_code="forecast_non_finite_target",
            error_details={"non_finite_target_count": non_finite_target_count},
        )
    working[target_column] = numeric_target.astype(float)

    if group_column is not None:
        missing_group_count = int(working[group_column].isna().sum())
        if missing_group_count:
            raise ValidationError(
                "Forecast group values cannot be missing.",
                error_code="forecast_missing_group",
                error_details={"missing_group_count": missing_group_count},
            )

    key_columns = [time_column] if group_column is None else [group_column, time_column]
    duplicate_key_count = int(working.duplicated(subset=key_columns, keep=False).sum())
    if duplicate_key_count:
        raise ValidationError(
            "Forecast input contains duplicate time keys; aggregate them explicitly before training.",
            error_code="forecast_duplicate_key",
            error_details={"duplicate_key_count": duplicate_key_count},
        )

    grouped_frames = _ordered_group_frames(working, group_column=group_column, time_column=time_column)
    if len(grouped_frames) > MAX_FORECAST_GROUPS:
        raise ValidationError(
            f"Forecasting supports at most {MAX_FORECAST_GROUPS} independent groups.",
            error_code="forecast_group_limit",
            error_details={"group_count": len(grouped_frames), "maximum_group_count": MAX_FORECAST_GROUPS},
        )
    if not grouped_frames:
        raise ValidationError("Forecast input must contain at least one observation.", error_code="forecast_empty")

    reference_times = pd.DatetimeIndex(grouped_frames[0][1][time_column])
    if len(reference_times) < 2:
        raise ValidationError(
            "Forecasting requires at least two ordered observations per group.",
            error_code="forecast_insufficient_history",
        )
    for _group_value, group_frame in grouped_frames[1:]:
        group_times = pd.DatetimeIndex(group_frame[time_column])
        if not group_times.equals(reference_times):
            raise ValidationError(
                "Forecast groups must have the same regular timestamps and aligned cutoff.",
                error_code="forecast_unaligned_groups",
            )

    resolved_frequency, calendar_anchor = _resolve_frequency(reference_times, options.frequency)
    prepared_groups = tuple(
        PreparedForecastSeries(
            group_index=index,
            group_value=group_value,
            times=pd.DatetimeIndex(group_frame[time_column]),
            values=group_frame[target_column].to_numpy(dtype=float, copy=True),
        )
        for index, (group_value, group_frame) in enumerate(grouped_frames, start=1)
    )
    observation_count = int(sum(len(group.values) for group in prepared_groups))
    preparation_digest = _digest_json(
        {
            "policy_key": FORECAST_PREPARATION_POLICY,
            "time_column": time_column,
            "target_column": target_column,
            "group_column": group_column,
            "frequency": resolved_frequency,
            "calendar_anchor": calendar_anchor,
            "seasonal_period": options.seasonal_period,
            "group_count": len(prepared_groups),
            "groups": [_canonical_group_key(group.group_value) for group in prepared_groups],
            "timestamps": [timestamp.isoformat() for timestamp in reference_times],
        }
    )
    preparation_facts = ForecastPreparationFacts(
        time_column=time_column,
        target_column=target_column,
        group_column=group_column,
        frequency=resolved_frequency,
        seasonal_period=options.seasonal_period,
        group_count=len(prepared_groups),
        observation_count=observation_count,
        duplicate_key_count=0,
        missing_period_count=0,
        non_finite_target_count=0,
        preparation_digest=preparation_digest,
    )
    return PreparedForecastPanel(
        time_column=time_column,
        target_column=target_column,
        group_column=group_column,
        frequency=resolved_frequency,
        calendar_anchor=calendar_anchor,
        groups=prepared_groups,
        preparation_facts=preparation_facts,
        source_dataset_snapshot_digest=source_dataset_snapshot_digest,
    )


def build_rolling_folds(
    panel: PreparedForecastPanel,
    options: ForecastOptions,
    *,
    minimum_training_observations: int,
) -> tuple[RollingForecastFold, ...]:
    folds = rolling_positions(
        observation_count=panel.periods_per_group,
        horizon=options.horizon,
        window_count=options.rolling_windows,
        minimum_training_observations=minimum_training_observations,
    )
    group_count = panel.group_count
    result: list[RollingForecastFold] = []
    for fold_index, (train_end, holdout_start, holdout_end) in enumerate(folds):
        result.append(
            RollingForecastFold(
                fold_index=fold_index,
                train_end_position=train_end,
                holdout_start_position=holdout_start,
                holdout_end_position=holdout_end,
                fact=ForecastFoldFact(
                    fold_index=fold_index,
                    train_end=panel.common_times[train_end - 1].isoformat(),
                    holdout_start=panel.common_times[holdout_start].isoformat(),
                    holdout_end=panel.common_times[holdout_end - 1].isoformat(),
                    train_observation_count=train_end * group_count,
                    holdout_observation_count=(holdout_end - holdout_start) * group_count,
                ),
            )
        )
    return tuple(result)


def rolling_positions(
    *,
    observation_count: int,
    horizon: int,
    window_count: int,
    minimum_training_observations: int,
) -> tuple[tuple[int, int, int], ...]:
    first_train_count = observation_count - (horizon * window_count)
    if first_train_count < minimum_training_observations:
        required = minimum_training_observations + (horizon * window_count)
        raise ValidationError(
            f"Forecast history is too short; at least {required} periods per group are required.",
            error_code="forecast_insufficient_history",
            error_details={
                "periods_per_group": observation_count,
                "required_periods_per_group": required,
                "minimum_training_observations": minimum_training_observations,
                "horizon": horizon,
                "window_count": window_count,
            },
        )
    return tuple(
        (
            first_train_count + (fold_index * horizon),
            first_train_count + (fold_index * horizon),
            first_train_count + ((fold_index + 1) * horizon),
        )
        for fold_index in range(window_count)
    )


def build_forecast_split_facts(
    panel: PreparedForecastPanel,
    options: ForecastOptions,
    folds: tuple[RollingForecastFold, ...],
) -> ForecastSplitFacts:
    fold_identity_digest = _digest_json(
        {
            "policy_key": FORECAST_SPLIT_POLICY,
            "frequency": panel.frequency,
            "seasonal_period": options.seasonal_period,
            "horizon": options.horizon,
            "group_count": panel.group_count,
            "folds": [fold.fact.model_dump(mode="json") for fold in folds],
        }
    )
    evaluation_count = sum(fold.fact.holdout_observation_count for fold in folds)
    return ForecastSplitFacts(
        source_dataset_snapshot_digest=panel.source_dataset_snapshot_digest,
        frequency=panel.frequency,
        seasonal_period=options.seasonal_period,
        horizon=options.horizon,
        rolling_windows=options.rolling_windows,
        group_count=panel.group_count,
        observation_count=panel.preparation_facts.observation_count,
        evaluation_observation_count=evaluation_count,
        aligned_group_cutoff=panel.last_time.isoformat(),
        folds=[fold.fact for fold in folds],
        fold_identity_digest=fold_identity_digest,
        future_overlap_count=0,
    )


def _ordered_group_frames(
    frame: pd.DataFrame,
    *,
    group_column: str | None,
    time_column: str,
) -> list[tuple[Any | None, pd.DataFrame]]:
    if group_column is None:
        return [(None, frame.sort_values(time_column, kind="stable").reset_index(drop=True))]
    groups = [
        (group_value, group_frame.sort_values(time_column, kind="stable").reset_index(drop=True))
        for group_value, group_frame in frame.groupby(group_column, sort=False, observed=True)
    ]
    groups.sort(key=lambda item: _canonical_group_key(item[0]))
    return groups


def _canonical_group_key(value: Any) -> str:
    return json.dumps(
        {"type": type(value).__name__, "value": str(value)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _resolve_frequency(
    times: pd.DatetimeIndex,
    requested: Literal["auto", "daily", "weekly", "monthly"],
) -> tuple[ForecastFrequency, str]:
    candidates: dict[ForecastFrequency, str] = {}
    if _is_fixed_delta(times, pd.Timedelta(days=1)):
        candidates["daily"] = "day"
    if _is_fixed_delta(times, pd.Timedelta(days=7)):
        candidates["weekly"] = f"weekday:{times[0].dayofweek}"
    monthly_anchor = _monthly_anchor(times)
    if monthly_anchor is not None:
        candidates["monthly"] = monthly_anchor

    if requested == "auto":
        if len(candidates) != 1:
            raise ValidationError(
                "Forecast cadence must be regular daily, weekly, or monthly.",
                error_code="forecast_irregular_cadence",
            )
        return next(iter(candidates.items()))
    if requested not in candidates:
        raise ValidationError(
            f"Forecast timestamps do not match the requested {requested} cadence.",
            error_code="forecast_frequency_mismatch",
            error_details={"requested_frequency": requested},
        )
    return requested, candidates[requested]


def _is_fixed_delta(times: pd.DatetimeIndex, expected: pd.Timedelta) -> bool:
    if len(times) < 2:
        return False
    deltas = times[1:] - times[:-1]
    return bool(np.all(deltas == expected))


def _monthly_anchor(times: pd.DatetimeIndex) -> str | None:
    if len(times) < 2:
        return None
    ordinals = np.asarray([timestamp.year * 12 + timestamp.month for timestamp in times], dtype=int)
    if not bool(np.all(np.diff(ordinals) == 1)):
        return None
    if bool(np.all(times.is_month_start)):
        return "month_start"
    if bool(np.all(times.is_month_end)):
        return "month_end"
    days = {timestamp.day for timestamp in times}
    if len(days) == 1 and next(iter(days)) <= 28:
        return f"day:{next(iter(days))}"
    return None


def _digest_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
