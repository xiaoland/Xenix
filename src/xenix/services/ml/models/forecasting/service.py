from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import joblib
from pydantic import BaseModel

from .....exceptions import ValidationError
from ....storage.models import ProblemKind
from ...contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    ForecastOptions,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    TrainingScopeFacts,
)
from ...dataset_loader import load_dataset
from ...evaluation import build_evaluation_comparison
from ...forecast_preparation import (
    PreparedForecastPanel,
    build_forecast_split_facts,
    build_rolling_folds,
    prepare_forecast_panel,
)
from ...types import (
    ApplyMode,
    ColumnRoleKind,
    EvaluationKind,
    ModelFamily,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)
from .contracts import (
    INNER_TEMPORAL_FOLDS,
    ForecastEvaluationArtifact,
    ForecastModelKey,
    ForecastParamsBase,
    HoltWintersForecastParams,
    RetainedForecastAnalyzer,
    SarimaFitBudget,
    SarimaForecastParams,
    SeasonalNaiveForecastParams,
)
from .engine import (
    _digest_json,
    _minimum_outer_training,
    _sarima_order_policy,
    apply_future_forecast,
    evaluate_forecast,
    fit_full_history,
)


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
    return snapshot.get("sampling_fingerprint") or _digest_json(snapshot)
