from __future__ import annotations

import numpy as np
import pandas as pd

from .ml.contracts import ForecastOptions
from .ml.forecast_preparation import prepare_forecast_panel
from .ml.models.forecasting import (
    ForecastModelKey,
    apply_future_forecast,
    evaluate_forecast,
    fit_full_history,
)


def run_forecasting_packaged_smoke() -> None:
    """Exercise every shipped classical forecast path inside the frozen app."""

    period_count = 72
    seasonal_pattern = np.asarray([0.0, 12.0, -4.0, 7.0])
    residual_pattern = np.asarray([0.0, 1.5, 0.5, -0.5, -1.0, 0.25])
    positions = np.arange(period_count)
    frame = pd.DataFrame(
        {
            "week": pd.date_range("2024-01-07", periods=period_count, freq="7D"),
            "orders": (
                100.0
                + (0.6 * positions)
                + np.resize(seasonal_pattern, period_count)
                + np.resize(residual_pattern, period_count)
            ),
        }
    )
    options = ForecastOptions(
        horizon=4,
        seasonal_period=4,
        frequency="weekly",
        interval_level=0.8,
        rolling_windows=3,
    )
    panel = prepare_forecast_panel(
        frame,
        time_column="week",
        target_column="orders",
        group_column=None,
        options=options,
        source_dataset_snapshot_digest="packaged-forecast-smoke",
    )
    for model_key in ForecastModelKey:
        evaluation = evaluate_forecast(
            panel,
            model_key=model_key,
            options=options,
        )
        analyzer = fit_full_history(
            panel,
            model_key=model_key,
            options=options,
        )
        future = apply_future_forecast(analyzer, horizon=2)
        if (
            evaluation.facts.split.future_overlap_count != 0
            or len(future.index) != 2
            or not np.isfinite(future[["forecast", "lower_bound", "upper_bound"]]).all().all()
        ):
            raise RuntimeError(
                f"Packaged forecast smoke failed for {model_key.value}."
            )
