from __future__ import annotations
from tests.support.paths import FIXTURES_ROOT

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from xenix.exceptions import ValidationError
from xenix.services.ml.contracts import (
    ApplyModelPayload,
    ApplyTaskRequest,
    DatasetSnapshotFact,
    EvaluateModelPayload,
    EvaluateTaskRequest,
    FitTaskRequest,
    ForecastOptions,
    ManualTrainingPayload,
)
from xenix.services.ml.evaluation import get_default_policy
from xenix.services.ml.forecast_preparation import prepare_forecast_panel
from xenix.services.ml.models.forecasting import (
    ForecastModelKey,
    HoltWintersForecastParams,
    HoltWintersForecastingService,
    SarimaFitBudget,
    SarimaFitOutcome,
    SarimaForecastParams,
    SarimaForecastingService,
    SeasonalNaiveForecastParams,
    SeasonalNaiveForecastingService,
    apply_future_forecast,
    evaluate_forecast,
    fit_full_history,
)
from xenix.services.ml.types import ApplyMode, EvaluationKind, ModelFamily, ModelTaskKind

FIXTURE_ROOT = FIXTURES_ROOT / "ml_cf_service"
WEEKLY_PANEL = FIXTURE_ROOT / "weekly_panel_v1.csv"
WEEKLY_TAIL_VARIANT = FIXTURE_ROOT / "weekly_panel_tail_variant_v1.csv"


def _weekly_options() -> ForecastOptions:
    return ForecastOptions(
        horizon=4,
        seasonal_period=4,
        frequency="weekly",
        interval_level=0.8,
        rolling_windows=3,
    )


def _weekly_panel(path: Path = WEEKLY_PANEL, *, snapshot: str = "snapshot-v1"):
    return prepare_forecast_panel(
        pd.read_csv(path),
        time_column="week",
        target_column="orders",
        group_column="region",
        options=_weekly_options(),
        source_dataset_snapshot_digest=snapshot,
    )


def test_three_forecasters_share_rolling_folds_and_apply_future_horizon() -> None:
    panel = _weekly_panel()
    options = _weekly_options()

    seasonal = evaluate_forecast(panel, model_key=ForecastModelKey.SEASONAL_NAIVE, options=options)
    holt_winters = evaluate_forecast(panel, model_key=ForecastModelKey.HOLT_WINTERS, options=options)
    sarima = evaluate_forecast(
        panel,
        model_key=ForecastModelKey.SARIMA,
        options=options,
        sarima_budget=SarimaFitBudget(
            max_fits_per_group=48,
            max_total_fits=100,
            max_wall_seconds=120.0,
        ),
    )

    fold_digests = {
        result.facts.split.fold_identity_digest
        for result in (seasonal, holt_winters, sarima)
    }
    assert len(fold_digests) == 1
    assert [fold.train_observation_count for fold in seasonal.facts.split.folds] == [120, 128, 136]
    assert [fold.holdout_observation_count for fold in seasonal.facts.split.folds] == [8, 8, 8]
    assert seasonal.facts.split.future_overlap_count == 0
    assert seasonal.candidate.metrics == seasonal.baseline.metrics
    assert holt_winters.baseline.metrics == seasonal.candidate.metrics
    assert sarima.baseline.metrics == seasonal.candidate.metrics
    assert set(holt_winters.candidate.metrics) == {"mae", "rmse", "smape", "mase"}
    assert holt_winters.candidate.primary_metric_name == "mae"
    assert holt_winters.facts.intervals.method == "residual_quantile.v1"
    assert holt_winters.facts.intervals.calibration_count == 48
    assert holt_winters.facts.intervals.coverage_guaranteed is False
    assert all(record.lower_bound <= record.forecast <= record.upper_bound for record in holt_winters.records)
    assert sarima.budget_facts.attempted_by_group == ((1, 27), (2, 27))
    assert sarima.budget_facts.converged_fit_count == 54
    assert sarima.facts.sarima_budget is not None
    assert sarima.facts.sarima_budget.attempted_fit_count == 54
    assert sarima.facts.sarima_budget.converged_fit_count == 54
    assert sarima.facts.sarima_budget.max_fits_per_group == 48
    assert sarima.facts.sarima_budget.max_total_fits == 100
    assert sarima.facts.sarima_budget.budget_exhausted is False
    assert holt_winters.facts.sarima_budget is None
    assert len(sarima.facts.sarima_selection) == 2
    assert all(fact.inner_fold_count == 2 for fact in sarima.facts.sarima_selection)

    records = list(holt_winters.records)
    actual = np.asarray([record.actual for record in records])
    predicted = np.asarray([record.forecast for record in records])
    absolute_errors = np.abs(actual - predicted)
    smape_denominator = np.abs(actual) + np.abs(predicted)
    expected_metrics = {
        "mae": float(np.mean(absolute_errors)),
        "rmse": float(np.sqrt(np.mean(np.square(actual - predicted)))),
        "smape": float(
            np.mean(
                np.divide(
                    2.0 * absolute_errors,
                    smape_denominator,
                    out=np.zeros_like(absolute_errors),
                    where=smape_denominator > np.finfo(float).eps,
                )
            )
        ),
        "mase": float(
            np.mean(
                [abs(record.actual - record.forecast) / record.mase_scale for record in records]
            )
        ),
    }
    assert holt_winters.candidate.metrics == pytest.approx(expected_metrics, abs=1e-6)
    expected_coverage = np.mean(
        [record.lower_bound <= record.actual <= record.upper_bound for record in records]
    )
    expected_width = np.mean([record.upper_bound - record.lower_bound for record in records])
    assert holt_winters.facts.intervals.empirical_coverage == pytest.approx(expected_coverage, abs=1e-6)
    assert holt_winters.facts.intervals.mean_width == pytest.approx(expected_width, abs=1e-6)

    first_fold_records = [
        record
        for record in seasonal.records
        if record.group_index == 1 and record.fold_index == 0
    ]
    first_group = panel.groups[0]
    expected_seasonal = first_group.values[56:60]
    assert [record.forecast for record in first_fold_records] == pytest.approx(expected_seasonal, abs=1e-6)

    for model_key in ForecastModelKey:
        analyzer = fit_full_history(
            panel,
            model_key=model_key,
            options=options,
            sarima_budget=SarimaFitBudget(
                max_fits_per_group=48,
                max_total_fits=100,
                max_wall_seconds=120.0,
            ),
        )
        output = apply_future_forecast(analyzer, horizon=5)
        assert len(output.index) == 10
        assert output[["region", "forecast_time"]].duplicated().sum() == 0
        assert output["region"].tolist() == ["north"] * 5 + ["south"] * 5
        assert (output["lower_bound"] <= output["forecast"]).all()
        assert (output["forecast"] <= output["upper_bound"]).all()
        assert output.columns.tolist() == [
            "region",
            "forecast_time",
            "forecast",
            "lower_bound",
            "upper_bound",
            "model_key",
            "interval_method",
            "interval_level",
            "horizon",
        ]
        assert output["model_key"].unique().tolist() == [model_key.value]
        assert output["horizon"].unique().tolist() == [5]


def test_prefix_identical_tail_variant_changes_only_validation_dependent_facts() -> None:
    options = _weekly_options()
    original = _weekly_panel(WEEKLY_PANEL, snapshot="original")
    changed = _weekly_panel(WEEKLY_TAIL_VARIANT, snapshot="changed")

    original_result = evaluate_forecast(
        original,
        model_key=ForecastModelKey.HOLT_WINTERS,
        options=options,
    )
    changed_result = evaluate_forecast(
        changed,
        model_key=ForecastModelKey.HOLT_WINTERS,
        options=options,
    )

    assert original.preparation_facts.preparation_digest == changed.preparation_facts.preparation_digest
    assert original_result.facts.split.fold_identity_digest == changed_result.facts.split.fold_identity_digest
    assert original_result.facts.forecast_digest == changed_result.facts.forecast_digest
    assert original_result.facts.interval_digest == changed_result.facts.interval_digest
    assert original_result.candidate.metrics != changed_result.candidate.metrics
    assert original_result.facts.intervals.empirical_coverage != changed_result.facts.intervals.empirical_coverage


def test_regular_daily_weekly_and_monthly_cadence_are_admitted() -> None:
    cases = [
        (pd.date_range("2025-01-01", periods=40, freq="D"), "daily", "daily"),
        (pd.date_range("2025-01-05", periods=40, freq="7D"), "weekly", "weekly"),
        (pd.date_range("2020-01-01", periods=60, freq="MS"), "monthly", "monthly"),
        (pd.date_range("2020-01-31", periods=60, freq="ME"), "monthly", "monthly"),
    ]
    for times, requested, expected in cases:
        options = ForecastOptions(
            horizon=2,
            seasonal_period=4 if expected != "monthly" else 12,
            frequency=requested,
            interval_level=0.8,
            rolling_windows=2,
        )
        panel = prepare_forecast_panel(
            pd.DataFrame({"time": times, "value": np.arange(len(times), dtype=float)}),
            time_column="time",
            target_column="value",
            group_column=None,
            options=options,
            source_dataset_snapshot_digest="cadence",
        )
        assert panel.frequency == expected
        assert len(panel.future_times(3)) == 3

        inferred = prepare_forecast_panel(
            pd.DataFrame({"time": times, "value": np.arange(len(times), dtype=float)}),
            time_column="time",
            target_column="value",
            group_column=None,
            options=options.model_copy(update={"frequency": "auto"}),
            source_dataset_snapshot_digest="cadence-auto",
        )
        assert inferred.frequency == expected


def test_forecast_preparation_fails_closed_for_invalid_panel_shapes() -> None:
    options = _weekly_options()
    frame = pd.read_csv(WEEKLY_PANEL)

    invalid_cases: list[tuple[pd.DataFrame, str]] = []
    invalid_cases.append((pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "forecast_duplicate_key"))
    missing_period = frame.drop(index=frame.index[3]).reset_index(drop=True)
    invalid_cases.append((missing_period, "forecast_unaligned_groups"))
    non_finite = frame.copy()
    non_finite.loc[0, "orders"] = np.inf
    invalid_cases.append((non_finite, "forecast_non_finite_target"))
    irregular = frame[frame["region"] == "north"].copy()
    shifted_times = pd.to_datetime(irregular.loc[4:, "week"]) + pd.Timedelta(days=1)
    irregular.loc[4:, "week"] = shifted_times.dt.strftime("%Y-%m-%d")
    invalid_cases.append((irregular, "forecast_frequency_mismatch"))
    missing_single_series = frame[frame["region"] == "north"].drop(index=3).reset_index(drop=True)
    invalid_cases.append((missing_single_series, "forecast_frequency_mismatch"))

    for invalid_frame, error_code in invalid_cases:
        with pytest.raises(ValidationError) as exc_info:
            prepare_forecast_panel(
                invalid_frame,
                time_column="week",
                target_column="orders",
                group_column="region" if invalid_frame["region"].nunique() > 1 else None,
                options=options,
                source_dataset_snapshot_digest="invalid",
            )
        assert exc_info.value.error_code == error_code

    too_many_groups = pd.DataFrame(
        {
            "week": list(pd.date_range("2025-01-05", periods=2, freq="7D")) * 25,
            "region": [f"group-{index:02d}" for index in range(25) for _ in range(2)],
            "orders": np.arange(50, dtype=float),
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        prepare_forecast_panel(
            too_many_groups,
            time_column="week",
            target_column="orders",
            group_column="region",
            options=options,
            source_dataset_snapshot_digest="too-many-groups",
        )
    assert exc_info.value.error_code == "forecast_group_limit"


def test_each_forecaster_rejects_insufficient_seasonal_history() -> None:
    options = _weekly_options()
    short_frame = pd.read_csv(WEEKLY_PANEL)
    short_frame = short_frame[short_frame["region"] == "north"].iloc[:20].copy()
    panel = prepare_forecast_panel(
        short_frame,
        time_column="week",
        target_column="orders",
        group_column=None,
        options=options,
        source_dataset_snapshot_digest="short",
    )

    for model_key in ForecastModelKey:
        with pytest.raises(ValidationError) as exc_info:
            evaluate_forecast(panel, model_key=model_key, options=options)
        assert exc_info.value.error_code == "forecast_insufficient_history"


class _FakeSarimaModel:
    def __init__(self, values: np.ndarray, order: tuple[int, int, int], seasonal_period: int) -> None:
        bias_by_order = {
            (0, 1, 0): 0.0,
            (1, 1, 0): 2.4,
            (0, 1, 1): -2.0,
        }
        self._pattern = np.asarray(values[-seasonal_period:], dtype=float) + bias_by_order[order]

    def forecast(self, steps: int) -> np.ndarray:
        return np.resize(self._pattern, steps)


def _deterministic_sarima_fitter(values: np.ndarray, order: Any) -> SarimaFitOutcome:
    return SarimaFitOutcome(
        fitted_model=_FakeSarimaModel(values, order.order, order.seasonal_order[3]),
        converged=True,
    )


def test_bounded_sarima_selection_uses_four_orders_two_inner_folds_and_budgets() -> None:
    panel = _weekly_panel()
    options = _weekly_options()
    evaluation = evaluate_forecast(
        panel,
        model_key=ForecastModelKey.SARIMA,
        options=options,
        sarima_fitter=_deterministic_sarima_fitter,
        sarima_budget=SarimaFitBudget(
            max_fits_per_group=48,
            max_total_fits=100,
            max_wall_seconds=120.0,
        ),
    )

    assert evaluation.budget_facts.attempted_fit_count == 54
    assert evaluation.budget_facts.converged_fit_count == 54
    assert all(fact.attempted_fit_count == 27 for fact in evaluation.facts.sarima_selection)
    assert all(fact.selected_order == (1, 1, 0) for fact in evaluation.facts.sarima_selection)
    assert all(fact.selected_seasonal_order == (0, 1, 0, 4) for fact in evaluation.facts.sarima_selection)

    with pytest.raises(ValidationError) as budget_error:
        evaluate_forecast(
            panel,
            model_key=ForecastModelKey.SARIMA,
            options=options,
            sarima_fitter=_deterministic_sarima_fitter,
            sarima_budget=SarimaFitBudget(
                max_fits_per_group=1,
                max_total_fits=1,
                max_wall_seconds=120.0,
            ),
        )
    assert budget_error.value.error_code == "forecast_sarima_budget_exhausted"


def test_sarima_nonconvergence_nonfinite_and_wall_budget_fail_without_fallback() -> None:
    panel = _weekly_panel()
    options = _weekly_options()

    def nonconverged(values: np.ndarray, order: Any) -> SarimaFitOutcome:
        return SarimaFitOutcome(
            fitted_model=_FakeSarimaModel(values, order.order, order.seasonal_order[3]),
            converged=False,
            warning_codes=("ConvergenceWarning",),
        )

    with pytest.raises(ValidationError) as nonconvergence_error:
        evaluate_forecast(
            panel,
            model_key=ForecastModelKey.SARIMA,
            options=options,
            sarima_fitter=nonconverged,
        )
    assert nonconvergence_error.value.error_code == "forecast_sarima_nonconvergence"

    class _NonFiniteModel:
        def forecast(self, steps: int) -> np.ndarray:
            return np.full(steps, np.inf)

    def nonfinite(_values: np.ndarray, _order: Any) -> SarimaFitOutcome:
        return SarimaFitOutcome(fitted_model=_NonFiniteModel(), converged=True)

    with pytest.raises(ValidationError) as nonfinite_error:
        evaluate_forecast(
            panel,
            model_key=ForecastModelKey.SARIMA,
            options=options,
            sarima_fitter=nonfinite,
        )
    assert nonfinite_error.value.error_code == "forecast_non_finite_output"

    clock_values = iter([0.0, 0.0, 2.0])

    def exhausted_clock() -> float:
        return next(clock_values, 2.0)

    with pytest.raises(ValidationError) as wall_error:
        evaluate_forecast(
            panel,
            model_key=ForecastModelKey.SARIMA,
            options=options,
            sarima_fitter=_deterministic_sarima_fitter,
            sarima_budget=SarimaFitBudget(
                max_fits_per_group=48,
                max_total_fits=100,
                max_wall_seconds=1.0,
            ),
            clock=exhausted_clock,
        )
    assert wall_error.value.error_code == "forecast_sarima_budget_exhausted"
    assert wall_error.value.error_details["budget_kind"] == "wall_time"


def test_forecast_service_bridge_fit_evaluate_apply_and_catalog(tmp_path: Path) -> None:
    source_path = tmp_path / "weekly.csv"
    source_path.write_bytes(WEEKLY_PANEL.read_bytes())
    options = _weekly_options()
    policy = get_default_policy(EvaluationKind.FORECASTING)
    snapshot = DatasetSnapshotFact(
        dataset_id="weekly-dataset",
        source_sha256="a" * 64,
        source_byte_size=source_path.stat().st_size,
        schema_digest="b" * 64,
    )
    fit_request = FitTaskRequest(
        task_id="forecast-fit",
        project_id="project-1",
        dataset_id=snapshot.dataset_id,
        dataset_source_path=str(source_path),
        evaluation_kind=EvaluationKind.FORECASTING,
        train_role_bindings=[
            {"role": "time", "columns": ["week"]},
            {"role": "target", "columns": ["orders"]},
            {"role": "group", "columns": ["region"]},
        ],
        evaluation_policy=policy,
        dataset_snapshot=snapshot,
        forecast_options=options,
        manual_training=ManualTrainingPayload(
            model_key=HoltWintersForecastingService.key,
            params={
                "horizon": 4,
                "seasonal_period": 4,
                "frequency": "weekly",
                "interval_level": 0.8,
                "rolling_windows": 3,
                "damped_trend": False,
            },
        ),
    )
    fit_result = HoltWintersForecastingService.fit(fit_request, tmp_path / "fit")
    assert fit_result.training_scopes is not None
    assert fit_result.training_scopes.evaluation_model == "chronological_training_prefixes"
    assert fit_result.training_scopes.apply_model == "all_observed_history"
    assert fit_result.forecast_split_facts is not None
    assert fit_result.forecast_preparation_facts is not None

    evaluate_request = EvaluateTaskRequest(
        task_id="forecast-evaluate",
        project_id="project-1",
        dataset_id=snapshot.dataset_id,
        dataset_source_path=str(source_path),
        evaluation_kind=EvaluationKind.FORECASTING,
        train_role_bindings=fit_request.train_role_bindings,
        evaluation_policy=policy,
        dataset_snapshot=snapshot,
        forecast_options=options,
        evaluate_model=EvaluateModelPayload(
            trained_model_id="trained-forecast",
            model_key=HoltWintersForecastingService.key,
            trained_model_artifact_path=fit_result.model_artifact_path,
            holdout_artifact_path=fit_result.holdout_artifact_path or "",
        ),
    )
    evaluate_result = HoltWintersForecastingService.evaluate(
        evaluate_request,
        tmp_path / "evaluate",
    )
    assert evaluate_result.forecast_evaluation is not None
    assert evaluate_result.comparison.primary_metric_name == "mae"
    assert evaluate_result.evaluation.details["interval_method"] == "residual_quantile.v1"

    apply_request = ApplyTaskRequest(
        task_id="forecast-apply",
        project_id="project-1",
        dataset_id=snapshot.dataset_id,
        dataset_source_path=str(source_path),
        apply_model=ApplyModelPayload(
            trained_model_id="trained-forecast",
            model_key=HoltWintersForecastingService.key,
            trained_model_artifact_path=fit_result.model_artifact_path,
        ),
        forecast_horizon=6,
    )
    apply_result = HoltWintersForecastingService.apply(apply_request, tmp_path / "apply")
    output = pd.read_csv(apply_result.output_file_path)
    assert apply_result.summary.apply_mode == "future_horizon"
    assert apply_result.summary.horizon == 6
    assert apply_result.source_dataset_ids == [snapshot.dataset_id]
    assert len(output.index) == 12

    for service in (
        SeasonalNaiveForecastingService,
        HoltWintersForecastingService,
        SarimaForecastingService,
    ):
        entry = service.catalog_entry()
        assert entry.model_family is ModelFamily.FORECASTING
        assert entry.model_task_kind is ModelTaskKind.FORECASTER
        assert entry.supports_evaluation is True
        assert entry.supports_apply is True
        assert entry.apply_mode is ApplyMode.FUTURE_HORIZON
        assert entry.apply_role_schema.roles == []

    common_fields = {"horizon", "seasonal_period", "frequency", "interval_level", "rolling_windows"}
    assert set(SeasonalNaiveForecastParams.model_fields) == common_fields
    assert set(HoltWintersForecastParams.model_fields) == common_fields | {"damped_trend"}
    assert set(SarimaForecastParams.model_fields) == common_fields | {
        "policy",
        "max_fits_per_group",
        "max_total_fits",
        "max_wall_seconds",
    }
    sarima_schema = SarimaForecastParams.model_json_schema()
    assert "optimizer" not in sarima_schema["properties"]
    assert "order" not in sarima_schema["properties"]
    assert "seasonal_order" not in sarima_schema["properties"]
